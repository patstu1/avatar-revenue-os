"""Conversion-system service: proposals, payment links, payments.

Introduced in Batch 3A. Provides the programmatic surface used by both
the explicit `/proposals` CRUD router and the implicit auto-path in
`proposal_drain` + the Stripe webhook. Every function:

  - validates inputs,
  - writes the canonical row(s) to Postgres,
  - emits the canonical `revenue_event` (proposal.created /
    proposal.sent / payment.link.created / payment.completed),
  - returns the persisted ORM row(s).

No external side-effects beyond DB writes and `event_bus.emit_event`.
Stripe-side work (payment-link creation on stripe.com) is delegated to
`stripe_billing_service.create_payment_link` — this service only
persists the result.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_event
from packages.db.models.proposals import (
    Payment,
    PaymentLink,
    Proposal,
    ProposalLineItem,
)

logger = structlog.get_logger()

# Stripe metadata.source values that identify a public ProofHook checkout
# (no Proposal exists for the buyer). These links carry a static, reused
# proposal_id per package which must be ignored — see record_payment_from_stripe.
PUBLIC_CHECKOUT_SOURCES = frozenset(
    {
        "proofhook_public_checkout",
        "proofhook_public_checkout_live",
    }
)


@dataclass
class LineItemInput:
    description: str
    unit_amount_cents: int
    quantity: int = 1
    offer_id: uuid.UUID | None = None
    package_slug: str | None = None
    currency: str = "usd"
    position: int = 0


# ═══════════════════════════════════════════════════════════════════════════
#  Proposals
# ═══════════════════════════════════════════════════════════════════════════


async def create_proposal(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    recipient_email: str,
    title: str,
    line_items: list[LineItemInput],
    brand_id: uuid.UUID | None = None,
    thread_id: uuid.UUID | None = None,
    message_id: uuid.UUID | None = None,
    draft_id: uuid.UUID | None = None,
    operator_action_id: uuid.UUID | None = None,
    recipient_name: str = "",
    recipient_company: str = "",
    summary: str = "",
    package_slug: str | None = None,
    avenue_slug: str | None = None,
    currency: str = "usd",
    created_by_actor_type: str = "system",
    created_by_actor_id: str | None = None,
    notes: str | None = None,
    extra_json: dict | None = None,
) -> Proposal:
    """Create a Proposal + its ProposalLineItems in one transaction.

    Computes ``total_amount_cents`` from the line items. Emits
    ``proposal.created`` event with the ledger of amount + line-item
    count for downstream observability.
    """
    if not line_items:
        raise ValueError("A proposal must have at least one line item")

    total = sum(li.quantity * li.unit_amount_cents for li in line_items)

    proposal = Proposal(
        org_id=org_id,
        brand_id=brand_id,
        thread_id=thread_id,
        message_id=message_id,
        draft_id=draft_id,
        operator_action_id=operator_action_id,
        recipient_email=recipient_email,
        recipient_name=recipient_name[:255],
        recipient_company=recipient_company[:255],
        title=title[:500],
        summary=summary,
        package_slug=package_slug,
        avenue_slug=avenue_slug,
        status="draft",
        total_amount_cents=total,
        currency=currency,
        created_by_actor_type=created_by_actor_type,
        created_by_actor_id=created_by_actor_id,
        notes=notes,
        extra_json=extra_json,
    )
    db.add(proposal)
    await db.flush()

    for li in line_items:
        db.add(
            ProposalLineItem(
                proposal_id=proposal.id,
                offer_id=li.offer_id,
                package_slug=li.package_slug,
                description=li.description[:500],
                quantity=li.quantity,
                unit_amount_cents=li.unit_amount_cents,
                total_amount_cents=li.quantity * li.unit_amount_cents,
                currency=li.currency,
                position=li.position,
            )
        )
    await db.flush()

    await emit_event(
        db,
        domain="monetization",
        event_type="proposal.created",
        summary=f"Proposal created: {title[:80]} → {recipient_email}",
        org_id=org_id,
        brand_id=brand_id,
        entity_type="proposal",
        entity_id=proposal.id,
        new_state="draft",
        actor_type=created_by_actor_type,
        actor_id=created_by_actor_id,
        details={
            "proposal_id": str(proposal.id),
            "recipient_email": recipient_email,
            "package_slug": package_slug,
            "avenue_slug": avenue_slug,
            "line_item_count": len(line_items),
            "total_amount_cents": total,
            "currency": currency,
            "thread_id": str(thread_id) if thread_id else None,
            "draft_id": str(draft_id) if draft_id else None,
            "operator_action_id": str(operator_action_id) if operator_action_id else None,
        },
    )
    logger.info(
        "proposal.created",
        proposal_id=str(proposal.id),
        org_id=str(org_id),
        recipient=recipient_email,
        total_cents=total,
    )
    return proposal


async def mark_proposal_sent(
    db: AsyncSession,
    *,
    proposal_id: uuid.UUID,
    actor_type: str = "system",
    actor_id: str | None = None,
    delivery_details: dict | None = None,
) -> Proposal:
    """Transition a proposal from draft → sent. Idempotent: already-sent
    proposals are returned as-is without re-emitting the event."""
    proposal = await _require_proposal(db, proposal_id)

    if proposal.status in ("sent", "accepted", "paid"):
        return proposal
    if proposal.status not in ("draft",):
        raise ValueError(f"Cannot transition proposal in status={proposal.status} to sent")

    prior = proposal.status
    proposal.status = "sent"
    proposal.sent_at = datetime.now(timezone.utc)
    await db.flush()

    await emit_event(
        db,
        domain="monetization",
        event_type="proposal.sent",
        summary=f"Proposal sent → {proposal.recipient_email}",
        org_id=proposal.org_id,
        brand_id=proposal.brand_id,
        entity_type="proposal",
        entity_id=proposal.id,
        previous_state=prior,
        new_state="sent",
        actor_type=actor_type,
        actor_id=actor_id,
        details={
            "proposal_id": str(proposal.id),
            "recipient_email": proposal.recipient_email,
            "total_amount_cents": proposal.total_amount_cents,
            "package_slug": proposal.package_slug,
            **(delivery_details or {}),
        },
    )
    logger.info(
        "proposal.sent",
        proposal_id=str(proposal.id),
        recipient=proposal.recipient_email,
    )
    # ── Stage controller: proposal → sent (Batch 4) ──
    try:
        from apps.api.services.stage_controller import mark_stage

        await mark_stage(
            db,
            org_id=proposal.org_id,
            entity_type="proposal",
            entity_id=proposal.id,
            stage="sent",
        )
    except Exception as stage_exc:
        logger.warning(
            "stage_controller.mark_failed", entity="proposal", entity_id=str(proposal.id), error=str(stage_exc)[:150]
        )
    return proposal


# ═══════════════════════════════════════════════════════════════════════════
#  Payment links
# ═══════════════════════════════════════════════════════════════════════════


async def record_payment_link(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    url: str,
    amount_cents: int,
    proposal_id: uuid.UUID | None = None,
    brand_id: uuid.UUID | None = None,
    provider: str = "stripe",
    provider_link_id: str | None = None,
    provider_price_id: str | None = None,
    provider_product_id: str | None = None,
    currency: str = "usd",
    source: str = "proposal",
    metadata: dict | None = None,
) -> PaymentLink:
    """Persist a PaymentLink row already created on the provider side.

    This is a *record* operation — it does not talk to Stripe. Call
    ``stripe_billing_service.create_payment_link`` first, then pass the
    URL + provider IDs here to store the row and emit the event.
    """
    link = PaymentLink(
        org_id=org_id,
        brand_id=brand_id,
        proposal_id=proposal_id,
        provider=provider,
        provider_link_id=provider_link_id,
        provider_price_id=provider_price_id,
        provider_product_id=provider_product_id,
        url=url,
        status="active",
        amount_cents=amount_cents,
        currency=currency,
        source=source,
        metadata_json=metadata,
    )
    db.add(link)
    await db.flush()

    await emit_event(
        db,
        domain="monetization",
        event_type="payment.link.created",
        summary=f"Payment link created: ${amount_cents / 100:.2f} {currency.upper()}",
        org_id=org_id,
        brand_id=brand_id,
        entity_type="payment_link",
        entity_id=link.id,
        new_state="active",
        actor_type="system",
        details={
            "payment_link_id": str(link.id),
            "provider": provider,
            "provider_link_id": provider_link_id,
            "amount_cents": amount_cents,
            "currency": currency,
            "source": source,
            "proposal_id": str(proposal_id) if proposal_id else None,
            "url": url,
        },
    )
    logger.info(
        "payment.link.created",
        payment_link_id=str(link.id),
        provider_link_id=provider_link_id,
        amount_cents=amount_cents,
        proposal_id=str(proposal_id) if proposal_id else None,
    )
    return link


# ═══════════════════════════════════════════════════════════════════════════
#  Payments (Stripe webhook consumer)
# ═══════════════════════════════════════════════════════════════════════════


async def record_payment_from_stripe(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    event_id: str,
    amount_cents: int,
    stripe_object: dict,
    event_type: str,
    brand_id: uuid.UUID | None = None,
    currency: str = "usd",
    payment_intent_id: str | None = None,
    checkout_session_id: str | None = None,
    charge_id: str | None = None,
    customer_email: str = "",
    customer_name: str = "",
    metadata: dict | None = None,
) -> Payment | None:
    """Idempotent insert of a succeeded Payment from a Stripe webhook.

    Resolves the owning Proposal + PaymentLink via Stripe metadata
    (``metadata.proposal_id`` or ``metadata.payment_link_id``) when
    present. On success, flips the linked Proposal to status='paid'
    and marks the PaymentLink completed.

    Returns the persisted Payment, or the existing row if the event has
    already been ingested (short-circuit on duplicate). Returns ``None``
    only if the caller passes an empty ``event_id`` — the unique
    constraint requires one.
    """
    if not event_id:
        logger.warning("payment.record_skipped", reason="empty event_id")
        return None

    # Idempotency — provider+event_id is unique
    existing = (
        await db.execute(
            select(Payment).where(
                Payment.provider == "stripe",
                Payment.provider_event_id == event_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    meta = (metadata or {}) if isinstance(metadata, dict) else {}
    source = str(meta.get("source") or "").strip()
    is_public_checkout = source in PUBLIC_CHECKOUT_SOURCES

    proposal_id = _safe_uuid(meta.get("proposal_id"))
    payment_link_id = _safe_uuid(meta.get("payment_link_id"))
    offer_id = _safe_uuid(meta.get("offer_id"))

    # Public ProofHook checkout links carry a STATIC, REUSED proposal_id per
    # package. Linking to it would flip a draft scaffolding proposal to paid
    # and, via _recover_email_from_proposal, collapse every public buyer of a
    # given package onto the same Client. Drop the link entirely for this
    # source — the Payment row stands alone, attribution flows through
    # package_slug/customer_email instead.
    proposal_id_skipped_reason = None
    if is_public_checkout and proposal_id is not None:
        proposal_id_skipped_reason = "public_checkout"
        proposal_id = None

    package_slug = meta.get("package_slug") or meta.get("package") or None
    if isinstance(package_slug, str):
        package_slug = package_slug[:60].strip() or None
    else:
        package_slug = None
    package_name = meta.get("package_name") or None
    if isinstance(package_name, str):
        package_name = package_name[:255].strip() or None
    else:
        package_name = None

    # Batch 9: avenue attribution — prefer explicit metadata.avenue on the
    # Stripe object; fall back to the originating proposal's avenue_slug
    # once resolved. Keeps every downstream entity (Client, IntakeRequest,
    # ClientProject, ProductionJob, Delivery) tagged with the avenue that
    # earned the revenue.
    avenue_slug = meta.get("avenue") or meta.get("avenue_slug") or None
    if isinstance(avenue_slug, str):
        avenue_slug = avenue_slug[:60] or None
    else:
        avenue_slug = None

    # Try to resolve payment_link by stripe link id if not in metadata.
    # Skip the proposal-id back-fill for public checkout — same corruption
    # rationale as above.
    if payment_link_id is None and stripe_object.get("payment_link"):
        link_row = (
            await db.execute(
                select(PaymentLink).where(
                    PaymentLink.provider == "stripe",
                    PaymentLink.provider_link_id == stripe_object["payment_link"],
                )
            )
        ).scalar_one_or_none()
        if link_row is not None:
            payment_link_id = link_row.id
            if not is_public_checkout and proposal_id is None and link_row.proposal_id is not None:
                proposal_id = link_row.proposal_id

    # Persist package + skip-reason audit on metadata_json so downstream
    # readers (operator dashboards, cascade) can see them without a model
    # migration. metadata_json is JSONB so additive keys are safe.
    persisted_meta = dict(meta)
    if package_slug:
        persisted_meta["package_slug"] = package_slug
    if package_name:
        persisted_meta["package_name"] = package_name
    if proposal_id_skipped_reason:
        persisted_meta["proposal_id_skipped_reason"] = proposal_id_skipped_reason

    now = datetime.now(timezone.utc)
    payment = Payment(
        org_id=org_id,
        brand_id=brand_id,
        proposal_id=proposal_id,
        payment_link_id=payment_link_id,
        offer_id=offer_id,
        provider="stripe",
        provider_event_id=event_id,
        provider_payment_intent_id=payment_intent_id,
        provider_checkout_session_id=checkout_session_id,
        provider_charge_id=charge_id,
        amount_cents=amount_cents,
        currency=currency,
        status="succeeded",
        completed_at=now,
        customer_email=customer_email[:255],
        customer_name=customer_name[:255],
        raw_event_json={"event_type": event_type, "object": stripe_object},
        metadata_json=persisted_meta,
        avenue_slug=avenue_slug,
    )
    db.add(payment)
    await db.flush()

    # Cascade — proposal transitions to paid, payment_link marked completed
    if proposal_id is not None:
        proposal = await _require_proposal(db, proposal_id)
        proposal.status = "paid"
        proposal.paid_at = now
        # Batch 9: clear dunning state on payment — no more reminders.
        proposal.dunning_status = "paid"
        # If avenue wasn't on Stripe metadata, back-fill from proposal.
        if payment.avenue_slug is None and proposal.avenue_slug:
            payment.avenue_slug = proposal.avenue_slug
        await db.flush()

    if payment_link_id is not None:
        link = (await db.execute(select(PaymentLink).where(PaymentLink.id == payment_link_id))).scalar_one_or_none()
        if link is not None:
            link.status = "completed"
            link.completed_at = now
            await db.flush()

    await emit_event(
        db,
        domain="monetization",
        event_type="payment.completed",
        summary=f"Payment captured: ${amount_cents / 100:.2f} {currency.upper()} ({event_type})",
        org_id=org_id,
        brand_id=brand_id,
        entity_type="payment",
        entity_id=payment.id,
        previous_state="pending",
        new_state="succeeded",
        actor_type="stripe_webhook",
        actor_id=event_id,
        details={
            "payment_id": str(payment.id),
            "proposal_id": str(proposal_id) if proposal_id else None,
            "payment_link_id": str(payment_link_id) if payment_link_id else None,
            "provider_event_id": event_id,
            "provider_payment_intent_id": payment_intent_id,
            "provider_checkout_session_id": checkout_session_id,
            "amount_cents": amount_cents,
            "currency": currency,
            "customer_email": customer_email,
            "stripe_event_type": event_type,
        },
    )
    logger.info(
        "payment.completed",
        payment_id=str(payment.id),
        proposal_id=str(proposal_id) if proposal_id else None,
        amount_cents=amount_cents,
        provider_event_id=event_id,
    )

    # Phase 3: analytics_events emission (verified, real revenue).
    try:
        if brand_id is not None and amount_cents > 0:
            from packages.clients.analytics_emitter import emit_analytics_event

            await emit_analytics_event(
                db,
                brand_id=brand_id,
                source="stripe_webhook",
                event_type="payment.succeeded",
                metric_value=float(amount_cents) / 100.0,
                truth_level="verified",
                platform="stripe",
                external_post_id=event_id,
                raw_json={
                    "proposal_id": str(proposal_id) if proposal_id else None,
                    "currency": currency,
                    "event_type": event_type,
                },
            )
            await db.flush()
    except Exception as _aexc:
        import structlog as _sl

        _sl.get_logger().warning("analytics_emit_failed", source="stripe_webhook", error=str(_aexc)[:200])
    return payment


# ═══════════════════════════════════════════════════════════════════════════
#  Internal helpers
# ═══════════════════════════════════════════════════════════════════════════


async def _require_proposal(db: AsyncSession, proposal_id: uuid.UUID) -> Proposal:
    proposal = (await db.execute(select(Proposal).where(Proposal.id == proposal_id))).scalar_one_or_none()
    if proposal is None:
        raise LookupError(f"proposal {proposal_id} not found")
    return proposal


def _safe_uuid(val) -> uuid.UUID | None:
    if not val:
        return None
    try:
        return uuid.UUID(str(val))
    except (ValueError, AttributeError, TypeError):
        return None
