"""Sponsor fulfillment (Batch 13).

Closes F:P → F:Y for sponsor_deals. Placements are the unit of
sponsor delivery (ad spot, host-read, video integration, social
mention, newsletter). Each placement has a schedule, a delivery
record, and — when missed — a linked make-good placement.

Self-referential FK on SponsorPlacement.make_good_of_placement_id
preserves the audit trail from a missed placement to its remedy.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_event
from packages.db.models.sponsor_campaigns import (
    SponsorCampaign,
    SponsorPlacement,
)

logger = structlog.get_logger()


VALID_PLACEMENT_TYPES = (
    "ad_spot", "host_read", "video_integration",
    "social_mention", "newsletter", "other",
)


async def schedule_placement(
    db: AsyncSession,
    *,
    campaign: SponsorCampaign,
    placement_type: str,
    scheduled_at: datetime,
    position: int = 0,
    notes: str | None = None,
    actor_type: str = "operator",
    actor_id: str | None = None,
) -> SponsorPlacement:
    if placement_type not in VALID_PLACEMENT_TYPES:
        raise ValueError(
            f"placement_type must be one of {VALID_PLACEMENT_TYPES}"
        )

    p = SponsorPlacement(
        campaign_id=campaign.id,
        org_id=campaign.org_id,
        position=position,
        placement_type=placement_type,
        status="scheduled",
        scheduled_at=scheduled_at,
        notes=notes,
        is_active=True,
    )
    db.add(p)
    await db.flush()

    await emit_event(
        db, domain="fulfillment",
        event_type="sponsor.placement.scheduled",
        summary=(
            f"Placement scheduled: {placement_type} @ "
            f"{scheduled_at.isoformat()}"
        ),
        org_id=campaign.org_id, brand_id=campaign.brand_id,
        entity_type="sponsor_placement", entity_id=p.id,
        actor_type=actor_type, actor_id=actor_id,
        details={
            "placement_id": str(p.id),
            "campaign_id": str(campaign.id),
            "placement_type": placement_type,
            "scheduled_at": scheduled_at.isoformat(),
        },
    )
    return p


async def record_placement_delivered(
    db: AsyncSession,
    *,
    placement: SponsorPlacement,
    delivered_at: datetime | None = None,
    metrics: dict | None = None,
    notes: str | None = None,
    actor_type: str = "operator",
    actor_id: str | None = None,
) -> dict:
    if placement.status in ("delivered", "cancelled"):
        return {
            "triggered": False,
            "reason": f"placement_status_{placement.status}",
            "placement_id": str(placement.id),
        }

    now = delivered_at or datetime.now(timezone.utc)
    placement.status = "delivered"
    placement.delivered_at = now
    if metrics is not None:
        placement.metrics_json = metrics
    if notes:
        placement.notes = notes
    await db.flush()

    await emit_event(
        db, domain="fulfillment",
        event_type="sponsor.placement.delivered",
        summary=f"Placement delivered: {placement.placement_type}",
        org_id=placement.org_id,
        entity_type="sponsor_placement", entity_id=placement.id,
        new_state="delivered",
        actor_type=actor_type, actor_id=actor_id,
        details={
            "placement_id": str(placement.id),
            "campaign_id": str(placement.campaign_id),
            "placement_type": placement.placement_type,
            "delivered_at": now.isoformat(),
            "metrics": metrics or {},
        },
    )
    return {
        "triggered": True,
        "placement_id": str(placement.id),
        "status": "delivered",
        "delivered_at": now.isoformat(),
    }


async def record_placement_missed(
    db: AsyncSession,
    *,
    placement: SponsorPlacement,
    reason: str,
    make_good: bool = True,
    make_good_placement_type: str | None = None,
    make_good_scheduled_at: datetime | None = None,
    actor_type: str = "operator",
    actor_id: str | None = None,
) -> dict:
    """Mark a placement missed. If ``make_good=True``, also creates a
    new SponsorPlacement with ``make_good_of_placement_id`` pointing
    at the missed one.
    """
    if placement.status in ("delivered", "cancelled"):
        return {
            "triggered": False,
            "reason": f"placement_status_{placement.status}",
            "placement_id": str(placement.id),
        }

    placement.status = "missed"
    if placement.notes:
        placement.notes = f"{placement.notes}\n[missed: {reason}]"
    else:
        placement.notes = f"[missed: {reason}]"
    await db.flush()

    make_good_id: uuid.UUID | None = None
    if make_good:
        mg_type = make_good_placement_type or placement.placement_type
        if mg_type not in VALID_PLACEMENT_TYPES:
            raise ValueError(
                f"make_good_placement_type must be one of {VALID_PLACEMENT_TYPES}"
            )
        mg_scheduled = (
            make_good_scheduled_at
            or (datetime.now(timezone.utc))
        )
        mg = SponsorPlacement(
            campaign_id=placement.campaign_id,
            org_id=placement.org_id,
            position=placement.position,
            placement_type=mg_type,
            status="scheduled",
            scheduled_at=mg_scheduled,
            make_good_of_placement_id=placement.id,
            notes=f"make-good for placement {placement.id} ({reason})",
            is_active=True,
        )
        db.add(mg)
        await db.flush()
        make_good_id = mg.id

    await emit_event(
        db, domain="fulfillment",
        event_type="sponsor.placement.missed",
        summary=(
            f"Placement missed: {placement.placement_type} "
            f"({reason}); make_good={'yes' if make_good else 'no'}"
        ),
        org_id=placement.org_id,
        entity_type="sponsor_placement", entity_id=placement.id,
        new_state="missed",
        actor_type=actor_type, actor_id=actor_id,
        severity="warning",
        details={
            "placement_id": str(placement.id),
            "campaign_id": str(placement.campaign_id),
            "reason": reason,
            "make_good_placement_id": (
                str(make_good_id) if make_good_id else None
            ),
        },
    )
    return {
        "triggered": True,
        "placement_id": str(placement.id),
        "status": "missed",
        "make_good_placement_id": (
            str(make_good_id) if make_good_id else None
        ),
        "reason": reason,
    }
