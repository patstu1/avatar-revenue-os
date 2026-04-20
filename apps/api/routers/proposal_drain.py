"""Proposal Drain — hand-triggered consumer of send_proposal operator actions.

Closes the loop between ``reply_ingestion.ingest_reply()`` creating
``OperatorAction(action_type IN ('send_proposal', 'respond_to_question'))``
and the actual outbound pricing/package email.

Additive and reversible:
    - Reads only rows with ``status='pending'`` in the two action types above.
    - Uses existing prod services only: ``stripe_billing_service``,
      ``SmtpEmailClient``, ``emit_event``.
    - Does not modify ``reply_ingestion.py`` or any worker-core file.

Triggered manually via ``POST /api/v1/proposals/drain-pending`` with an
``X-Ops-Token`` header (value must match the ``OPS_TOKEN`` env var).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Header, HTTPException, Query, status
from sqlalchemy import func, select

from apps.api.deps import DBSession
from apps.api.services.event_bus import emit_event
from apps.api.services.package_recommender import recommend_package
from apps.api.services.stripe_billing_service import (
    generate_payment_link_for_proposal,
)
from packages.clients.email_templates import build_proof_email
from packages.clients.external_clients import SmtpEmailClient
from packages.db.models.offers import Offer
from packages.db.models.system_events import OperatorAction

router = APIRouter()
logger = structlog.get_logger()

PROPOSAL_ACTION_TYPES = ("send_proposal", "respond_to_question")


def _require_ops_token(x_ops_token: Optional[str]) -> None:
    expected = os.environ.get("OPS_TOKEN", "")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPS_TOKEN not configured on server",
        )
    if x_ops_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing X-Ops-Token header",
        )


def _extract_first_name(email: str) -> str:
    local = email.split("@", 1)[0]
    first = local.split(".")[0].split("+")[0]
    return first.capitalize() if first else "there"


@router.get("/proposals/pending-count")
async def pending_proposal_count(
    db: DBSession,
    x_ops_token: Optional[str] = Header(None, alias="X-Ops-Token"),
) -> dict:
    """Operator health check — how many pending actions would be drained."""
    _require_ops_token(x_ops_token)

    count = (
        await db.execute(
            select(func.count())
            .select_from(OperatorAction)
            .where(
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
    limit: int = Query(10, ge=1, le=50),
    x_ops_token: Optional[str] = Header(None, alias="X-Ops-Token"),
) -> dict:
    """Drain pending send_proposal / respond_to_question operator actions.

    For each pending action:
        1. recommend a package via ``package_recommender.recommend_package``
        2. look up the matching Offer row by brand_id + slug
        3. generate a Stripe payment link (source=outreach_proposal metadata)
        4. render a proof/pricing email via ``email_templates.build_proof_email``
        5. send via ``SmtpEmailClient``
        6. mark action completed + emit ``proposal.sent`` system event

    Failures on individual actions are recorded and the loop continues —
    they do not roll back already-completed work.
    """
    _require_ops_token(x_ops_token)

    actions = (
        await db.execute(
            select(OperatorAction)
            .where(
                OperatorAction.status == "pending",
                OperatorAction.source_module == "reply_ingestion",
                OperatorAction.action_type.in_(PROPOSAL_ACTION_TYPES),
            )
            .order_by(OperatorAction.created_at)
            .limit(limit)
        )
    ).scalars().all()

    smtp = SmtpEmailClient()
    processed: list[dict] = []

    for action in actions:
        try:
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

    body_preview = payload.get("body_preview", "")
    intent = payload.get("reply_type", "question")

    rec = recommend_package(
        intent=intent,
        body_text=body_preview,
        subject=action.title or "",
        from_email=sender_email,
    )

    offer: Optional[Offer] = None
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

    payment_url = await generate_payment_link_for_proposal(
        db,
        org_id=action.organization_id,
        brand_id=action.brand_id,
        offer_id=offer.id,
        amount=float(offer.payout_amount or 0.0),
        product_name=offer.name,
    )

    if payment_url.startswith("error:"):
        return {
            "action_id": str(action.id),
            "status": "failed_payment_link",
            "error": payment_url,
            "recommendation": rec.slug,
        }

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
            "recommendation": rec.slug,
        }

    action.status = "completed"
    action.completed_at = datetime.now(timezone.utc)
    payload.update(
        {
            "drained_at": datetime.now(timezone.utc).isoformat(),
            "recommendation": rec.to_dict(),
            "offer_id": str(offer.id),
            "payment_url": payment_url,
            "smtp_message_id": send_result.get("message_id"),
        }
    )
    action.action_payload = payload

    await emit_event(
        db,
        domain="monetization",
        event_type="proposal.sent",
        summary=f"Proposal sent: {rec.slug} -> {sender_email} (${float(offer.payout_amount):.0f})",
        org_id=action.organization_id,
        brand_id=action.brand_id,
        entity_type="operator_action",
        entity_id=action.id,
        details={
            "sender": sender_email,
            "package_slug": rec.slug,
            "rationale": rec.rationale,
            "signals": rec.signals,
            "confidence": rec.confidence,
            "offer_id": str(offer.id),
            "amount": float(offer.payout_amount or 0.0),
            "payment_url": payment_url,
            "smtp_message_id": send_result.get("message_id"),
        },
    )

    return {
        "action_id": str(action.id),
        "status": "completed",
        "sender": sender_email,
        "package_slug": rec.slug,
        "offer_id": str(offer.id),
        "amount": float(offer.payout_amount or 0.0),
        "payment_url": payment_url,
        "message_id": send_result.get("message_id"),
    }
