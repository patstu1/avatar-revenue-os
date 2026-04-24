"""High-ticket onboarding (Batch 12).

Closes the On:P → On:Y gap for the ``high_ticket`` avenue. A $50K
contract doesn't open on a 7-field form — it needs a 12-field
scoping schema AND a state machine the operator can drive:

    discovery_pending
      → (GM: schedule-discovery)     → discovery_pending (call set, not yet run)
      → (GM: sow-sent)               → sow_sent
      → (GM: sow-countersigned)      → sow_signed
      → (GM: kickoff)                → kickoff_scheduled / kickoff_complete

Every transition writes:
  - A ``ClientHighTicketProfile`` column update (first-class, indexable).
  - A ``ClientOnboardingEvent(event_type="high_ticket.<step>")``.
  - A ``SystemEvent(domain='fulfillment',
                    event_type='client.onboarding.high_ticket_<step>')``.
  - A ``stage_controller.mark_stage(entity_type='client', stage=<step>)``.

Called from the 4 ``/gm/write/clients/{id}/high-ticket/*`` endpoints.
Also called once from ``client_activation.activate_client_from_payment``
when the paying proposal's avenue_slug is ``high_ticket`` — we create
the profile row at activation time so the operator dashboard sees the
new client in the discovery queue immediately.
"""
from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_event
from packages.db.models.clients import (
    Client,
    ClientHighTicketProfile,
    ClientOnboardingEvent,
)

logger = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════════════
#  High-ticket intake schema (replaces DEFAULT_INTAKE_SCHEMA for this avenue)
# ═══════════════════════════════════════════════════════════════════════════


HIGH_TICKET_INTAKE_SCHEMA: dict = {
    "schema_version": "high_ticket_v1",
    "title": "High-ticket engagement scoping",
    "instructions": (
        "Thanks for starting a high-ticket engagement. The fields below "
        "set us up for a $25K+ contract — we use this to scope the SOW, "
        "align on deliverables, and schedule your discovery call and "
        "kickoff without back-and-forth."
    ),
    "fields": [
        {"field_id": "legal_entity_name", "label": "Legal entity name (for contract)", "type": "text", "required": True},
        {"field_id": "principal_decision_makers", "label": "Principal decision-makers (name + title)", "type": "textarea", "required": True},
        {"field_id": "current_monthly_ad_spend", "label": "Current monthly ad spend (USD)", "type": "text", "required": True},
        {"field_id": "current_cpa", "label": "Current cost per acquisition", "type": "text", "required": False},
        {"field_id": "contract_term_preference", "label": "Preferred contract term (3mo / 6mo / 12mo)", "type": "text", "required": True},
        {"field_id": "net_terms_preference", "label": "Net-terms preference (Net 15 / Net 30 / upfront)", "type": "text", "required": True},
        {"field_id": "legal_counsel_contact", "label": "Your legal counsel (name + email, for SOW review)", "type": "textarea", "required": False},
        {"field_id": "exclusivity_clauses", "label": "Exclusivity / non-compete clauses we should be aware of", "type": "textarea", "required": False},
        {"field_id": "kpi_definition", "label": "Primary KPI you're paying us to move", "type": "textarea", "required": True},
        {"field_id": "review_cadence", "label": "SOW / milestone review cadence (weekly / bi-weekly / monthly)", "type": "text", "required": True},
        {"field_id": "preferred_kickoff_date", "label": "Preferred kickoff date", "type": "text", "required": True},
        {"field_id": "escalation_contact", "label": "Escalation contact (name + email) if things go sideways", "type": "textarea", "required": True},
    ],
}


# ═══════════════════════════════════════════════════════════════════════════
#  Profile row management
# ═══════════════════════════════════════════════════════════════════════════


async def ensure_profile(
    db: AsyncSession, *, client: Client,
) -> ClientHighTicketProfile:
    """Return the client's high-ticket profile row, creating one in
    ``status='discovery_pending'`` if it doesn't exist. Idempotent.

    Called from ``client_activation`` at payment time for any client
    whose ``avenue_slug == 'high_ticket'``, and defensively by each
    state-transition function in this module.
    """
    existing = (
        await db.execute(
            select(ClientHighTicketProfile).where(
                ClientHighTicketProfile.client_id == client.id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    p = ClientHighTicketProfile(
        client_id=client.id, org_id=client.org_id,
        status="discovery_pending", is_active=True,
    )
    db.add(p)
    await db.flush()
    return p


async def _write_onboarding_event(
    db: AsyncSession,
    *,
    client: Client,
    step: str,
    details: dict,
    actor_type: str,
    actor_id: str | None,
) -> ClientOnboardingEvent:
    evt = ClientOnboardingEvent(
        client_id=client.id,
        org_id=client.org_id,
        event_type=f"high_ticket.{step}",
        details_json=details,
        actor_type=actor_type,
        actor_id=actor_id,
    )
    db.add(evt)
    await db.flush()

    await emit_event(
        db,
        domain="fulfillment",
        event_type=f"client.onboarding.high_ticket_{step}",
        summary=(
            f"High-ticket {step.replace('_', ' ')}: "
            f"{client.display_name or client.primary_email}"
        ),
        org_id=client.org_id,
        brand_id=client.brand_id,
        entity_type="client",
        entity_id=client.id,
        actor_type=actor_type,
        actor_id=actor_id,
        details={
            "client_id": str(client.id),
            "step": step,
            **details,
        },
    )
    try:
        from apps.api.services.stage_controller import mark_stage
        await mark_stage(
            db, org_id=client.org_id,
            entity_type="client", entity_id=client.id,
            stage=f"high_ticket_{step}",
        )
    except Exception as stage_exc:
        logger.warning(
            "high_ticket.stage_mark_failed",
            client_id=str(client.id),
            step=step,
            error=str(stage_exc)[:150],
        )
    return evt


# ═══════════════════════════════════════════════════════════════════════════
#  Four state transitions (wrapped by /gm/write/clients/{id}/high-ticket/*)
# ═══════════════════════════════════════════════════════════════════════════


async def schedule_discovery_call(
    db: AsyncSession,
    *,
    client: Client,
    when: datetime,
    attendees: list[dict] | None = None,
    agenda: str | None = None,
    notes: str | None = None,
    actor_type: str = "operator",
    actor_id: str | None = None,
) -> dict:
    """Record the discovery call date + attendees. Doesn't SEND a
    calendar invite — that's an integration concern for a later batch.
    This records the commitment.
    """
    profile = await ensure_profile(db, client=client)
    prior_status = profile.status
    profile.discovery_call_at = when
    profile.discovery_attendees_json = {"attendees": attendees or [], "agenda": agenda}
    if profile.status == "discovery_pending":
        # Status stays discovery_pending until the call actually happens;
        # booking it doesn't advance the gate. Kept here for future
        # "call_completed" transition if we add it.
        pass
    await db.flush()

    evt = await _write_onboarding_event(
        db, client=client, step="discovery_scheduled",
        details={
            "when_iso": when.isoformat(),
            "attendees_count": len(attendees or []),
            "agenda": agenda,
            "notes": notes,
            "prior_status": prior_status,
            "status": profile.status,
        },
        actor_type=actor_type, actor_id=actor_id,
    )
    return {
        "client_id": str(client.id),
        "profile_id": str(profile.id),
        "status": profile.status,
        "discovery_call_at": when.isoformat(),
        "event_id": str(evt.id),
    }


async def record_sow_sent(
    db: AsyncSession,
    *,
    client: Client,
    sow_url: str,
    signer_email: str | None = None,
    sent_at: datetime | None = None,
    counterparty_name: str | None = None,
    notes: str | None = None,
    actor_type: str = "operator",
    actor_id: str | None = None,
) -> dict:
    profile = await ensure_profile(db, client=client)
    prior_status = profile.status
    now = sent_at or datetime.now(timezone.utc)

    profile.sow_url = sow_url[:2048]
    profile.sow_sent_at = now
    profile.sow_signer_email = (signer_email or "")[:255] or None
    if counterparty_name:
        profile.counterparty_name = counterparty_name[:255]
    profile.status = "sow_sent"
    await db.flush()

    evt = await _write_onboarding_event(
        db, client=client, step="sow_sent",
        details={
            "sow_url": sow_url,
            "signer_email": signer_email,
            "sent_at_iso": now.isoformat(),
            "counterparty_name": counterparty_name,
            "notes": notes,
            "prior_status": prior_status,
            "status": profile.status,
        },
        actor_type=actor_type, actor_id=actor_id,
    )
    return {
        "client_id": str(client.id),
        "profile_id": str(profile.id),
        "status": profile.status,
        "sow_url": sow_url,
        "sow_sent_at": now.isoformat(),
        "event_id": str(evt.id),
    }


async def record_sow_countersigned(
    db: AsyncSession,
    *,
    client: Client,
    signed_at: datetime | None = None,
    counterparty_name: str | None = None,
    notes: str | None = None,
    actor_type: str = "operator",
    actor_id: str | None = None,
) -> dict:
    """Terminal on the signing branch. Idempotent — calling again on
    an already-signed profile returns {"already_signed": true} without
    writing a duplicate event."""
    profile = await ensure_profile(db, client=client)

    if profile.sow_countersigned_at is not None:
        return {
            "client_id": str(client.id),
            "profile_id": str(profile.id),
            "status": profile.status,
            "already_signed": True,
            "sow_countersigned_at": profile.sow_countersigned_at.isoformat(),
        }

    prior_status = profile.status
    now = signed_at or datetime.now(timezone.utc)
    profile.sow_countersigned_at = now
    if counterparty_name and not profile.counterparty_name:
        profile.counterparty_name = counterparty_name[:255]
    profile.status = "sow_signed"
    await db.flush()

    evt = await _write_onboarding_event(
        db, client=client, step="sow_countersigned",
        details={
            "signed_at_iso": now.isoformat(),
            "counterparty_name": profile.counterparty_name,
            "notes": notes,
            "prior_status": prior_status,
            "status": profile.status,
        },
        actor_type=actor_type, actor_id=actor_id,
    )
    return {
        "client_id": str(client.id),
        "profile_id": str(profile.id),
        "status": profile.status,
        "sow_countersigned_at": now.isoformat(),
        "event_id": str(evt.id),
        "already_signed": False,
    }


async def set_kickoff_date(
    db: AsyncSession,
    *,
    client: Client,
    kickoff_at: datetime,
    team_members: list[dict] | None = None,
    notes: str | None = None,
    actor_type: str = "operator",
    actor_id: str | None = None,
) -> dict:
    profile = await ensure_profile(db, client=client)
    prior_status = profile.status
    profile.kickoff_at = kickoff_at
    profile.kickoff_team_json = {"team_members": team_members or []}
    # If we set kickoff after SOW signed, advance to kickoff_scheduled.
    # If kickoff date is already past, move to kickoff_complete.
    now = datetime.now(timezone.utc)
    if kickoff_at <= now:
        profile.status = "kickoff_complete"
    else:
        profile.status = "kickoff_scheduled"
    await db.flush()

    evt = await _write_onboarding_event(
        db, client=client,
        step=("kickoff_complete" if kickoff_at <= now else "kickoff_scheduled"),
        details={
            "kickoff_at_iso": kickoff_at.isoformat(),
            "team_members_count": len(team_members or []),
            "notes": notes,
            "prior_status": prior_status,
            "status": profile.status,
        },
        actor_type=actor_type, actor_id=actor_id,
    )
    return {
        "client_id": str(client.id),
        "profile_id": str(profile.id),
        "status": profile.status,
        "kickoff_at": kickoff_at.isoformat(),
        "event_id": str(evt.id),
    }
