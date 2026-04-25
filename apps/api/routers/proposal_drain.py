"""Proposal Drain — hand-triggered consumer of send_proposal operator actions.

Closes the loop between ``reply_ingestion.ingest_reply()`` creating
``OperatorAction(action_type IN ('send_proposal', 'respond_to_question'))``
and the actual outbound pricing/package email.

Additive and reversible:
    - Reads only rows with ``status='pending'`` in the two action types above.
    - Uses existing prod services only: ``stripe_billing_service``,
      ``SmtpEmailClient``, ``emit_event``.
    - Does not modify ``reply_ingestion.py`` or any worker-core file.

Auth: both endpoints require an authenticated operator/admin via JWT
(``OperatorUser`` dep). The previous ``X-Ops-Token`` env-token path is
removed — operator/admin accounts are the system-owned primary path.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Query
from sqlalchemy import func, select

from apps.api.deps import DBSession, OperatorUser
from apps.api.services.package_recommender import recommend_package
from apps.api.services.proposals_service import (
    LineItemInput,
)
from apps.api.services.proposals_service import (
    create_proposal as svc_create_proposal,
)
from apps.api.services.proposals_service import (
    mark_proposal_sent as svc_mark_sent,
)
from apps.api.services.proposals_service import (
    record_payment_link as svc_record_payment_link,
)
from apps.api.services.stripe_billing_service import create_payment_link
from apps.api.services.test_record_guard import is_test_or_synthetic_record
from packages.clients.email_templates import build_proof_email
from packages.clients.external_clients import SmtpEmailClient
from packages.db.models.offers import Offer
from packages.db.models.system_events import OperatorAction

router = APIRouter()
logger = structlog.get_logger()

PROPOSAL_ACTION_TYPES = ("send_proposal", "respond_to_question")


def _extract_first_name(email: str) -> str:
    local = email.split("@", 1)[0]
    first = local.split(".")[0].split("+")[0]
    return first.capitalize() if first else "there"


@router.get("/proposals/pending-count")
async def pending_proposal_count(
    db: DBSession,
    current_user: OperatorUser,
) -> dict:
    """Operator health check — how many pending actions would be drained."""
    count = (
        await db.execute(
            select(func.count())
            .select_from(OperatorAction)
            .where(
                OperatorAction.organization_id == current_user.organization_id,
                OperatorAction.status == "pending",
                OperatorAction.source_module == "reply_ingestion",
                OperatorAction.action_type.in_(PROPOSAL_ACTION_TYPES),
            )
        )
    ).scalar() or 0

    return {"pending": int(count), "action_types": list(PROPOSAL_ACTION_TYPES)}


@router.post("/proposals/drain-pending")
async def drain_pending_proposals(
    db: DBSession,
    current_user: OperatorUser,
    limit: int = Query(10, ge=1, le=50),
) -> dict:
    """Drain pending send_proposal / respond_to_question operator actions.

    For each pending action:
        1. recommend a package via ``package_recommender.recommend_package``
        2. look up the matching Offer row by brand_id + slug
        3. generate a Stripe payment link (source=outreach_proposal metadata)
        4. render a proof/pricing email via ``email_templates.build_proof_email``
        5. send via ``SmtpEmailClient`` resolved from DB per-action.organization_id
        6. mark action completed + emit ``proposal.sent`` system event

    Failures on individual actions are recorded and the loop continues —
    they do not roll back already-completed work.
    """
    actions = (
        (
            await db.execute(
                select(OperatorAction)
                .where(
                    OperatorAction.organization_id == current_user.organization_id,
                    OperatorAction.status == "pending",
                    OperatorAction.source_module == "reply_ingestion",
                    OperatorAction.action_type.in_(PROPOSAL_ACTION_TYPES),
                )
                .order_by(OperatorAction.created_at)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    processed: list[dict] = []

    for action in actions:
        try:
            smtp = await SmtpEmailClient.resolve(db, action.organization_id)
            result = await _drain_one(action, db, smtp)
        except Exception as exc:
            logger.exception("proposal_drain.unhandled_exception", action_id=str(action.id))
            result = {
                "action_id": str(action.id),
                "status": "exception",
                "error": str(exc)[:200],
            }
        processed.append(result)

    await db.flush()

    return {
        "scanned": len(actions),
        "processed": processed,
        "summary": {
            "completed": sum(1 for p in processed if p["status"] == "completed"),
            "skipped": sum(1 for p in processed if p["status"] == "skipped"),
            "failed_payment_link": sum(1 for p in processed if p["status"] == "failed_payment_link"),
            "failed_send": sum(1 for p in processed if p["status"] == "failed_send"),
            "exception": sum(1 for p in processed if p["status"] == "exception"),
        },
    }


async def _drain_one(action: OperatorAction, db, smtp: SmtpEmailClient) -> dict:
    payload = dict(action.action_payload or {})
    sender_email = payload.get("sender", "")
    if not sender_email:
        return {
            "action_id": str(action.id),
            "status": "skipped",
            "reason": "no sender in action_payload",
        }

    # ── Live-payment safety guard ──────────────────────────────────────────
    # Block test / synthetic / fixture records before creating a Stripe
    # payment link or sending any customer email.  Marks the action as
    # skipped with an audit reason so it is visible in the drain summary
    # and never silently re-queued.
    _guard_blocked, _guard_reason = is_test_or_synthetic_record(
        email=sender_email,
        source=payload.get("source") or payload.get("reply_type"),
        metadata={
            k: str(v)
            for k, v in payload.items()
            if isinstance(v, str)
        },
    )
    if _guard_blocked:
        logger.warning(
            "proposal_drain.guard_blocked",
            action_id=str(action.id),
            sender=sender_email,
            reason=_guard_reason,
        )
        action.status = "skipped"
        action.action_payload = {
            **payload,
            "guard_blocked_at": datetime.now(timezone.utc).isoformat(),
            "guard_reason": _guard_reason,
        }
        return {
            "action_id": str(action.id),
            "status": "skipped",
            "reason": _guard_reason,
        }

    body_preview = payload.get("body_preview", "")
    intent = payload.get("reply_type", "question")

    rec = recommend_package(
        intent=intent,
        body_text=body_preview,
        subject=action.title or "",
        from_email=sender_email,
    )

    offer: Offer | None = None
    if action.brand_id:
        offer = (
            await db.execute(
                select(Offer)
                .where(
                    Offer.brand_id == action.brand_id,
                    Offer.offer_url.like(f"%/{rec.slug}"),
                    Offer.is_active.is_(True),
                )
                .limit(1)
            )
        ).scalar_one_or_none()

        if offer is None:
            offer = (
                await db.execute(
                    select(Offer)
                    .where(
                        Offer.brand_id == action.brand_id,
                        Offer.is_active.is_(True),
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()

    if offer is None:
        return {
            "action_id": str(action.id),
            "status": "skipped",
            "reason": "no active Offer found for brand",
            "recommendation": rec.slug,
        }

    amount_dollars = float(offer.payout_amount or 0.0)
    amount_cents = int(round(amount_dollars * 100))

    # 1. Persist the Proposal + one ProposalLineItem (the Offer). Emits
    #    proposal.created. Ties the proposal back to the triggering
    #    OperatorAction via operator_action_id so every auto-path
    #    proposal is traceable to the inbound reply that spawned it.
    proposal = await svc_create_proposal(
        db,
        org_id=action.organization_id,
        brand_id=action.brand_id,
        recipient_email=sender_email,
        title=offer.name,
        line_items=[
            LineItemInput(
                description=offer.name,
                unit_amount_cents=amount_cents,
                quantity=1,
                offer_id=offer.id,
                package_slug=rec.slug,
            )
        ],
        operator_action_id=action.id,
        package_slug=rec.slug,
        summary=rec.rationale,
        currency="usd",
        created_by_actor_type="system",
        created_by_actor_id="proposal_drain",
        extra_json={
            "recommendation": rec.to_dict(),
            "reply_type": intent,
        },
    )

    # 2. Create Stripe payment link + persist PaymentLink row. Metadata
    #    includes proposal_id so the incoming Stripe webhook can
    #    resolve the owning proposal.
    stripe_result = await create_payment_link(
        amount_cents=amount_cents,
        currency="usd",
        product_name=offer.name,
        metadata={
            "org_id": str(action.organization_id),
            "brand_id": str(action.brand_id) if action.brand_id else "",
            "offer_id": str(offer.id),
            "proposal_id": str(proposal.id),
            "source": "proposal",
            "origin": "proposal_drain",
        },
        db=db,
        org_id=action.organization_id,
    )
    if stripe_result.get("error") or not stripe_result.get("url"):
        return {
            "action_id": str(action.id),
            "status": "failed_payment_link",
            "error": stripe_result.get("error") or "stripe returned no url",
            "proposal_id": str(proposal.id),
            "recommendation": rec.slug,
        }

    payment_link = await svc_record_payment_link(
        db,
        org_id=action.organization_id,
        brand_id=action.brand_id,
        proposal_id=proposal.id,
        url=stripe_result["url"],
        amount_cents=amount_cents,
        provider="stripe",
        provider_link_id=stripe_result.get("id"),
        currency="usd",
        source="proposal_drain",
        metadata={"offer_id": str(offer.id), "package_slug": rec.slug},
    )
    payment_url = payment_link.url

    # 3. Render + send the proposal email (Stripe link embedded).
    first_name = _extract_first_name(sender_email)
    rendered = build_proof_email(
        first_name=first_name,
        company="",
        vertical="tool-signal",
        package_slug=rec.slug,
        proof_url=payment_url,
    )

    send_result = await smtp.send_email(
        to_email=sender_email,
        subject=rendered.get("subject", "Following up"),
        body_html=rendered.get("html", ""),
        body_text=rendered.get("text", ""),
    )

    if not send_result.get("success"):
        return {
            "action_id": str(action.id),
            "status": "failed_send",
            "error": send_result.get("error"),
            "blocked": send_result.get("blocked", False),
            "proposal_id": str(proposal.id),
            "payment_link_id": str(payment_link.id),
            "recommendation": rec.slug,
        }

    # 4. Transition proposal → sent (emits canonical proposal.sent event
    #    tied to the Proposal entity, replacing the ad-hoc emit that
    #    pointed at OperatorAction).
    await svc_mark_sent(
        db,
        proposal_id=proposal.id,
        actor_type="system",
        actor_id="proposal_drain",
        delivery_details={
            "smtp_message_id": send_result.get("message_id"),
            "operator_action_id": str(action.id),
            "payment_link_id": str(payment_link.id),
        },
    )

    action.status = "completed"
    action.completed_at = datetime.now(timezone.utc)
    payload.update(
        {
            "drained_at": datetime.now(timezone.utc).isoformat(),
            "recommendation": rec.to_dict(),
            "offer_id": str(offer.id),
            "proposal_id": str(proposal.id),
            "payment_link_id": str(payment_link.id),
            "payment_url": payment_url,
            "smtp_message_id": send_result.get("message_id"),
        }
    )
    action.action_payload = payload

    return {
        "action_id": str(action.id),
        "status": "completed",
        "sender": sender_email,
        "package_slug": rec.slug,
        "offer_id": str(offer.id),
        "proposal_id": str(proposal.id),
        "payment_link_id": str(payment_link.id),
        "amount": amount_dollars,
        "payment_url": payment_url,
        "message_id": send_result.get("message_id"),
    }
