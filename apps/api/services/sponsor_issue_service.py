"""Sponsor-specific issue handling (Batch 13).

Closes Iss:P → Iss:Y for sponsor_deals. Parallel to
``high_ticket_issue_service.classify_high_ticket_issue`` but with
sponsor-specific subtypes. Severity scaling same as high_ticket
(>=$10k critical, >=$1k warning, else info).
"""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_event
from packages.db.models.clients import Client, ClientOnboardingEvent
from packages.db.models.email_pipeline import EmailReplyDraft
from packages.db.models.gm_control import GMEscalation

logger = structlog.get_logger()

SPONSOR_ISSUE_SUBTYPES = (
    "under_delivery",
    "metrics_dispute",
    "make_good_required",
    "exclusivity_breach",
    "campaign_paused",
)

CRITICAL_THRESHOLD_CENTS = 10_000_00
WARNING_THRESHOLD_CENTS = 1_000_00


async def classify_sponsor_issue(
    db: AsyncSession,
    *,
    draft: EmailReplyDraft,
    subtype: str,
    affected_cents: int = 0,
    notes: str | None = None,
    actor_type: str = "operator",
    actor_id: str | None = None,
) -> dict:
    if subtype not in SPONSOR_ISSUE_SUBTYPES:
        raise ValueError(
            f"subtype must be one of {SPONSOR_ISSUE_SUBTYPES}, got {subtype!r}"
        )
    if affected_cents < 0:
        raise ValueError("affected_cents cannot be negative")

    if affected_cents >= CRITICAL_THRESHOLD_CENTS:
        severity = "critical"
    elif affected_cents >= WARNING_THRESHOLD_CENTS:
        severity = "warning"
    else:
        severity = "info"

    client = (
        await db.execute(
            select(Client).where(
                Client.org_id == draft.org_id,
                Client.primary_email == (draft.to_email or "").lower(),
            )
        )
    ).scalar_one_or_none()

    esc = GMEscalation(
        org_id=draft.org_id,
        reason_code=f"sponsor_{subtype}",
        entity_type="email_reply_draft",
        entity_id=draft.id,
        title=f"[sponsor {subtype}] {(draft.subject or 'reply')[:240]}",
        description=(
            notes
            or f"Operator-classified sponsor issue: {subtype}. "
            f"Affected amount: ${affected_cents/100:,.2f}. "
            f"Sponsor email: {draft.to_email}."
        )[:4000],
        severity=severity,
        status="open",
        details_json={
            "draft_id": str(draft.id),
            "client_id": str(client.id) if client else None,
            "subtype": subtype,
            "affected_cents": affected_cents,
            "to_email": draft.to_email,
            "avenue_slug": "sponsor_deals",
        },
    )
    db.add(esc)
    await db.flush()

    onboarding_event_id: uuid.UUID | None = None
    if client is not None:
        ce = ClientOnboardingEvent(
            client_id=client.id, org_id=client.org_id,
            event_type=f"sponsor.issue.{subtype}",
            details_json={
                "draft_id": str(draft.id),
                "escalation_id": str(esc.id),
                "subtype": subtype,
                "affected_cents": affected_cents,
                "severity": severity,
                "notes": notes,
            },
            actor_type=actor_type, actor_id=actor_id,
        )
        db.add(ce)
        await db.flush()
        onboarding_event_id = ce.id

    await emit_event(
        db, domain="fulfillment",
        event_type=f"client.issue.sponsor_{subtype}",
        summary=(
            f"Sponsor {subtype}: {draft.to_email} "
            f"${affected_cents/100:,.2f} ({severity})"
        ),
        org_id=draft.org_id,
        entity_type="email_reply_draft", entity_id=draft.id,
        actor_type=actor_type, actor_id=actor_id,
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
