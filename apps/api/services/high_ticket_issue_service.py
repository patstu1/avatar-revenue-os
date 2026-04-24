"""High-ticket issue handling (Batch 12).

Closes the Iss:P → Iss:Y gap for the ``high_ticket`` avenue. Batch 9's
generic ``/gm/write/issues/drafts/{id}/classify`` doesn't know that a
"refund" on a $50K contract is a negotiated outcome, not a one-click
action. This module adds high-ticket-specific issue subtypes + a
structured credit-issuance action.

Two functions:

  1. ``classify_high_ticket_issue`` — opens a ``GMEscalation`` with
     ``reason_code=high_ticket_<subtype>``. Severity scales with
     ``affected_cents``: >= $10k → critical, >= $1k → warning, else info.
     Always creates a ClientOnboardingEvent on the referenced client
     when resolvable, so the issue shows up on the client's timeline.

  2. ``issue_credit`` — writes a ``ClientRetentionEvent(event_type=
     'high_ticket.credit_issued')`` with the dollar amount in the new
     ``amount_cents`` column (first-class, not JSONB). The credit is
     recorded as a liability; actual Stripe refund execution is a
     separate billing-batch concern.
"""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_event
from packages.db.models.clients import (
    Client,
    ClientOnboardingEvent,
    ClientRetentionEvent,
)
from packages.db.models.email_pipeline import EmailReplyDraft
from packages.db.models.gm_control import GMEscalation

logger = structlog.get_logger()


HIGH_TICKET_ISSUE_SUBTYPES = (
    "contract_dispute",
    "scope_creep",
    "timeline_slip",
    "deliverable_dispute",
    "payment_dispute",
    "exclusivity_breach",
)


# Severity thresholds for affected_cents
CRITICAL_THRESHOLD_CENTS = 10_000_00  # $10k
WARNING_THRESHOLD_CENTS = 1_000_00    # $1k


async def classify_high_ticket_issue(
    db: AsyncSession,
    *,
    draft: EmailReplyDraft,
    subtype: str,
    affected_cents: int = 0,
    notes: str | None = None,
    actor_type: str = "operator",
    actor_id: str | None = None,
) -> dict:
    """Classify an inbound-reply draft as a high-ticket issue, opening
    a scoped GMEscalation. Severity scales with affected_cents.

    Returns:
      {"escalation_id", "severity", "subtype", "client_id" | None,
       "onboarding_event_id" | None}
    """
    if subtype not in HIGH_TICKET_ISSUE_SUBTYPES:
        raise ValueError(
            f"subtype must be one of {HIGH_TICKET_ISSUE_SUBTYPES}, got {subtype!r}"
        )
    if affected_cents < 0:
        raise ValueError("affected_cents cannot be negative")

    # Severity scaling
    if affected_cents >= CRITICAL_THRESHOLD_CENTS:
        severity = "critical"
    elif affected_cents >= WARNING_THRESHOLD_CENTS:
        severity = "warning"
    else:
        severity = "info"

    # Best-effort client resolution via draft.to_email
    client = (
        await db.execute(
            select(Client).where(
                Client.org_id == draft.org_id,
                Client.primary_email == (draft.to_email or "").lower(),
            )
        )
    ).scalar_one_or_none()

    # Open the escalation
    esc = GMEscalation(
        org_id=draft.org_id,
        reason_code=f"high_ticket_{subtype}",
        entity_type="email_reply_draft",
        entity_id=draft.id,
        title=f"[high-ticket {subtype}] {(draft.subject or 'reply')[:240]}",
        description=(
            notes
            or f"Operator-classified high-ticket issue: {subtype}. "
            f"Affected amount: ${affected_cents/100:,.2f}. "
            f"Client email: {draft.to_email}."
        )[:4000],
        severity=severity,
        status="open",
        details_json={
            "draft_id": str(draft.id),
            "client_id": str(client.id) if client else None,
            "subtype": subtype,
            "affected_cents": affected_cents,
            "to_email": draft.to_email,
            "avenue_slug": "high_ticket",
        },
    )
    db.add(esc)
    await db.flush()

    onboarding_event_id: uuid.UUID | None = None
    if client is not None:
        ce = ClientOnboardingEvent(
            client_id=client.id,
            org_id=client.org_id,
            event_type=f"high_ticket.issue.{subtype}",
            details_json={
                "draft_id": str(draft.id),
                "escalation_id": str(esc.id),
                "subtype": subtype,
                "affected_cents": affected_cents,
                "severity": severity,
                "notes": notes,
            },
            actor_type=actor_type,
            actor_id=actor_id,
        )
        db.add(ce)
        await db.flush()
        onboarding_event_id = ce.id

    await emit_event(
        db,
        domain="fulfillment",
        event_type=f"client.issue.high_ticket_{subtype}",
        summary=(
            f"High-ticket {subtype}: "
            f"{draft.to_email} ${affected_cents/100:,.2f} ({severity})"
        ),
        org_id=draft.org_id,
        entity_type="email_reply_draft",
        entity_id=draft.id,
        actor_type=actor_type,
        actor_id=actor_id,
        severity=severity,
        details={
            "draft_id": str(draft.id),
            "client_id": str(client.id) if client else None,
            "escalation_id": str(esc.id),
            "subtype": subtype,
            "affected_cents": affected_cents,
        },
    )

    return {
        "escalation_id": str(esc.id),
        "severity": severity,
        "subtype": subtype,
        "client_id": str(client.id) if client else None,
        "onboarding_event_id": (
            str(onboarding_event_id) if onboarding_event_id else None
        ),
        "affected_cents": affected_cents,
    }


async def issue_credit(
    db: AsyncSession,
    *,
    client: Client,
    amount_cents: int,
    reason: str,
    reference_project_id: uuid.UUID | None = None,
    notes: str | None = None,
    actor_type: str = "operator",
    actor_id: str | None = None,
) -> dict:
    """Record a credit/adjustment against a high-ticket client.

    Writes a ClientRetentionEvent with ``amount_cents`` first-class
    (so rollups work via SUM). The credit is a liability entry —
    actual Stripe refund execution is out of Batch 12 scope.
    """
    if amount_cents <= 0:
        raise ValueError("amount_cents must be positive")
    if not reason or not reason.strip():
        raise ValueError("reason is required")

    evt = ClientRetentionEvent(
        org_id=client.org_id,
        client_id=client.id,
        avenue_slug=client.avenue_slug,
        event_type="high_ticket.credit_issued",
        previous_state=client.retention_state,
        new_state=client.retention_state,
        triggered_by_actor_type=actor_type,
        triggered_by_actor_id=actor_id,
        source_proposal_id=client.first_proposal_id,
        amount_cents=amount_cents,
        details_json={
            "reason": reason,
            "reference_project_id": (
                str(reference_project_id) if reference_project_id else None
            ),
            "notes": notes,
            "liability_recorded": True,
            "stripe_refund_executed": False,
        },
    )
    db.add(evt)
    await db.flush()

    await emit_event(
        db,
        domain="fulfillment",
        event_type="client.retention.credit_issued",
        summary=(
            f"High-ticket credit ${amount_cents/100:,.2f} issued for "
            f"{client.display_name or client.primary_email}: {reason[:60]}"
        ),
        org_id=client.org_id,
        brand_id=client.brand_id,
        entity_type="client",
        entity_id=client.id,
        actor_type=actor_type,
        actor_id=actor_id,
        severity="warning",
        details={
            "client_id": str(client.id),
            "retention_event_id": str(evt.id),
            "amount_cents": amount_cents,
            "reason": reason,
            "avenue_slug": client.avenue_slug,
        },
    )
    logger.info(
        "high_ticket.credit_issued",
        client_id=str(client.id),
        amount_cents=amount_cents,
    )
    return {
        "client_id": str(client.id),
        "retention_event_id": str(evt.id),
        "amount_cents": amount_cents,
        "reason": reason,
    }
