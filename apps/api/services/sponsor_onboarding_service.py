"""Sponsor onboarding (Batch 13).

Closes On:P → On:Y for sponsor_deals. Parallel to
``high_ticket_onboarding`` but with sponsor-specific schema +
state machine + events.

State machine:
  pre_contract
    → (record_contract_signed)   → contract_signed
    → (record_brief_received)    → brief_received
    → (set_campaign_start)       → campaign_live (or campaign_complete
                                                   if end_at already past)
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_event
from packages.db.models.clients import (
    Client,
    ClientOnboardingEvent,
)
from packages.db.models.sponsor_campaigns import SponsorCampaign

logger = structlog.get_logger()


SPONSOR_INTAKE_SCHEMA: dict = {
    "schema_version": "sponsor_v1",
    "title": "Sponsor / brand partnership scoping",
    "instructions": (
        "Thanks for partnering with us. The fields below set up your "
        "sponsor campaign — contract terms, approved talent, content "
        "review process, reporting cadence, and make-good policy. This "
        "replaces a generic creative-services intake because sponsor "
        "deals run on contract + campaign deliverables, not project-based "
        "production."
    ),
    "fields": [
        {
            "field_id": "contracting_entity",
            "label": "Contracting entity (legal name)",
            "type": "text",
            "required": True,
        },
        {
            "field_id": "sponsor_legal_contact",
            "label": "Your legal/contracting contact (name + email)",
            "type": "textarea",
            "required": True,
        },
        {
            "field_id": "campaign_objectives",
            "label": "Campaign objectives (awareness / conversion / both)",
            "type": "textarea",
            "required": True,
        },
        {
            "field_id": "approved_talent_list",
            "label": "Approved talent / creators (by name or pool)",
            "type": "textarea",
            "required": True,
        },
        {
            "field_id": "content_approval_process",
            "label": "Content approval process (who signs off, how fast)",
            "type": "textarea",
            "required": True,
        },
        {
            "field_id": "exclusivity_window",
            "label": "Exclusivity window (category, duration, geography)",
            "type": "textarea",
            "required": False,
        },
        {
            "field_id": "reporting_cadence",
            "label": "Reporting cadence (weekly / monthly / campaign-end)",
            "type": "text",
            "required": True,
        },
        {
            "field_id": "termination_clauses",
            "label": "Termination / kill-fee clauses",
            "type": "textarea",
            "required": False,
        },
        {
            "field_id": "make_good_policy",
            "label": "Make-good policy for missed/under-performing placements",
            "type": "textarea",
            "required": True,
        },
        {
            "field_id": "ip_likeness_rights",
            "label": "IP / likeness / re-use rights post-campaign",
            "type": "textarea",
            "required": True,
        },
        {
            "field_id": "brand_safety_requirements",
            "label": "Brand safety requirements / disclosure language",
            "type": "textarea",
            "required": True,
        },
        {
            "field_id": "measurement_methodology",
            "label": "Measurement methodology (how we'll count impressions / conversions)",
            "type": "textarea",
            "required": True,
        },
    ],
}


async def ensure_campaign(
    db: AsyncSession,
    *,
    client: Client,
) -> SponsorCampaign:
    """Return the client's SponsorCampaign, creating one in
    status='pre_contract' if it doesn't exist. Idempotent.
    """
    existing = (
        await db.execute(select(SponsorCampaign).where(SponsorCampaign.client_id == client.id))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    c = SponsorCampaign(
        client_id=client.id,
        org_id=client.org_id,
        brand_id=client.brand_id,
        avenue_slug="sponsor_deals",
        status="pre_contract",
        is_active=True,
    )
    db.add(c)
    await db.flush()
    return c


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
        event_type=f"sponsor.{step}",
        details_json=details,
        actor_type=actor_type,
        actor_id=actor_id,
    )
    db.add(evt)
    await db.flush()

    await emit_event(
        db,
        domain="fulfillment",
        event_type=f"client.onboarding.sponsor_{step}",
        summary=f"Sponsor {step.replace('_', ' ')}: {client.display_name or client.primary_email}",
        org_id=client.org_id,
        brand_id=client.brand_id,
        entity_type="client",
        entity_id=client.id,
        actor_type=actor_type,
        actor_id=actor_id,
        details={"client_id": str(client.id), "step": step, **details},
    )
    try:
        from apps.api.services.stage_controller import mark_stage

        await mark_stage(
            db,
            org_id=client.org_id,
            entity_type="client",
            entity_id=client.id,
            stage=f"sponsor_{step}",
        )
    except Exception as stage_exc:
        logger.warning(
            "sponsor.stage_mark_failed",
            client_id=str(client.id),
            step=step,
            error=str(stage_exc)[:150],
        )
    return evt


async def record_contract_signed(
    db: AsyncSession,
    *,
    client: Client,
    contract_url: str,
    signed_at: datetime | None = None,
    counterparty_name: str | None = None,
    notes: str | None = None,
    actor_type: str = "operator",
    actor_id: str | None = None,
) -> dict:
    """Record contract signing. Idempotent — calling again on an
    already-signed campaign returns {'already_signed': true}."""
    campaign = await ensure_campaign(db, client=client)

    if campaign.contract_signed_at is not None:
        return {
            "client_id": str(client.id),
            "campaign_id": str(campaign.id),
            "status": campaign.status,
            "already_signed": True,
            "contract_signed_at": campaign.contract_signed_at.isoformat(),
        }

    prior = campaign.status
    now = signed_at or datetime.now(timezone.utc)
    campaign.contract_url = contract_url[:2048]
    campaign.contract_signed_at = now
    if counterparty_name:
        campaign.counterparty_name = counterparty_name[:255]
    campaign.status = "contract_signed"
    await db.flush()

    evt = await _write_onboarding_event(
        db,
        client=client,
        step="contract_signed",
        details={
            "contract_url": contract_url,
            "signed_at_iso": now.isoformat(),
            "counterparty_name": counterparty_name,
            "notes": notes,
            "prior_status": prior,
            "status": campaign.status,
        },
        actor_type=actor_type,
        actor_id=actor_id,
    )
    return {
        "client_id": str(client.id),
        "campaign_id": str(campaign.id),
        "status": campaign.status,
        "contract_url": contract_url,
        "contract_signed_at": now.isoformat(),
        "event_id": str(evt.id),
        "already_signed": False,
    }


async def record_brief_received(
    db: AsyncSession,
    *,
    client: Client,
    brief_json: dict,
    notes: str | None = None,
    actor_type: str = "operator",
    actor_id: str | None = None,
) -> dict:
    campaign = await ensure_campaign(db, client=client)
    prior = campaign.status
    now = datetime.now(timezone.utc)
    campaign.brief_json = brief_json
    campaign.brief_received_at = now
    campaign.status = "brief_received"
    await db.flush()

    evt = await _write_onboarding_event(
        db,
        client=client,
        step="brief_received",
        details={
            "brief_received_at_iso": now.isoformat(),
            "brief_field_count": len(brief_json or {}),
            "notes": notes,
            "prior_status": prior,
            "status": campaign.status,
        },
        actor_type=actor_type,
        actor_id=actor_id,
    )
    return {
        "client_id": str(client.id),
        "campaign_id": str(campaign.id),
        "status": campaign.status,
        "brief_received_at": now.isoformat(),
        "event_id": str(evt.id),
    }


async def set_campaign_start(
    db: AsyncSession,
    *,
    client: Client,
    campaign_start_at: datetime,
    campaign_end_at: datetime | None = None,
    notes: str | None = None,
    actor_type: str = "operator",
    actor_id: str | None = None,
) -> dict:
    campaign = await ensure_campaign(db, client=client)
    prior = campaign.status
    campaign.campaign_start_at = campaign_start_at
    campaign.campaign_end_at = campaign_end_at

    now = datetime.now(timezone.utc)
    if campaign_end_at and campaign_end_at <= now:
        campaign.status = "campaign_complete"
    else:
        campaign.status = "campaign_live"
    await db.flush()

    evt = await _write_onboarding_event(
        db,
        client=client,
        step=("campaign_complete" if campaign.status == "campaign_complete" else "campaign_live"),
        details={
            "campaign_start_at_iso": campaign_start_at.isoformat(),
            "campaign_end_at_iso": (campaign_end_at.isoformat() if campaign_end_at else None),
            "notes": notes,
            "prior_status": prior,
            "status": campaign.status,
        },
        actor_type=actor_type,
        actor_id=actor_id,
    )
    return {
        "client_id": str(client.id),
        "campaign_id": str(campaign.id),
        "status": campaign.status,
        "campaign_start_at": campaign_start_at.isoformat(),
        "campaign_end_at": (campaign_end_at.isoformat() if campaign_end_at else None),
        "event_id": str(evt.id),
    }
