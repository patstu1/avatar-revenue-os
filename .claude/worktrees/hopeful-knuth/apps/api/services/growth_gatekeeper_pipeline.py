"""Shared gatekeeper: DB-backed signals + deferred expansion commands."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.offers import AudienceSegment, Offer, SponsorOpportunity, SponsorProfile
from packages.scoring.growth_pack.gatekeeper import apply_gatekeeper_to_commands, compute_gatekeeper_inputs
from packages.scoring.growth_pack.orchestrator import build_cannibalization_pairs


async def apply_gatekeeper_pipeline(
    db: AsyncSession,
    brand_id: uuid.UUID,
    *,
    commands: list[dict],
    acc_dicts: list[dict],
    scale_dict: dict,
    readiness_dict: Optional[dict],
    trust_avg: float,
    leak_count: int,
    brand_niche: Optional[str],
) -> list[dict]:
    offer_count = (await db.execute(
        select(func.count()).select_from(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
    )).scalar() or 0
    sponsor_profile_count = (await db.execute(
        select(func.count()).select_from(SponsorProfile).where(SponsorProfile.brand_id == brand_id, SponsorProfile.is_active.is_(True))
    )).scalar() or 0
    sponsor_open_deal_count = (await db.execute(
        select(func.count()).select_from(SponsorOpportunity).where(
            SponsorOpportunity.brand_id == brand_id,
            SponsorOpportunity.status.notin_(["closed_lost", "lost", "declined"]),
        )
    )).scalar() or 0
    seg_sum = (await db.execute(
        select(func.coalesce(func.sum(AudienceSegment.estimated_size), 0)).where(
            AudienceSegment.brand_id == brand_id, AudienceSegment.is_active.is_(True),
        )
    )).scalar() or 0

    gatekeeper = compute_gatekeeper_inputs(
        accounts=acc_dicts,
        offer_count=int(offer_count),
        sponsor_profile_count=int(sponsor_profile_count),
        sponsor_open_deal_count=int(sponsor_open_deal_count),
        audience_segment_total_estimated_size=int(seg_sum),
        readiness=readiness_dict,
        trust_avg=trust_avg,
        leak_count=leak_count,
        scale_rec=scale_dict,
    )
    pairs = build_cannibalization_pairs(acc_dicts)
    has_high = any(p["risk_level"] == "high" for p in pairs)
    return apply_gatekeeper_to_commands(
        commands,
        gatekeeper,
        has_high_cannibalization=has_high,
        brand_niche=brand_niche,
    )


async def load_gatekeeper_dict_only(
    db: AsyncSession,
    brand_id: uuid.UUID,
    *,
    acc_dicts: list[dict],
    scale_dict: dict,
    readiness_dict: Optional[dict],
    trust_avg: float,
    leak_count: int,
) -> dict[str, Any]:
    """For pack recompute paths that need gatekeeper scores without re-running full command engine."""
    offer_count = (await db.execute(
        select(func.count()).select_from(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
    )).scalar() or 0
    sponsor_profile_count = (await db.execute(
        select(func.count()).select_from(SponsorProfile).where(SponsorProfile.brand_id == brand_id, SponsorProfile.is_active.is_(True))
    )).scalar() or 0
    sponsor_open_deal_count = (await db.execute(
        select(func.count()).select_from(SponsorOpportunity).where(
            SponsorOpportunity.brand_id == brand_id,
            SponsorOpportunity.status.notin_(["closed_lost", "lost", "declined"]),
        )
    )).scalar() or 0
    seg_sum = (await db.execute(
        select(func.coalesce(func.sum(AudienceSegment.estimated_size), 0)).where(
            AudienceSegment.brand_id == brand_id, AudienceSegment.is_active.is_(True),
        )
    )).scalar() or 0
    return compute_gatekeeper_inputs(
        accounts=acc_dicts,
        offer_count=int(offer_count),
        sponsor_profile_count=int(sponsor_profile_count),
        sponsor_open_deal_count=int(sponsor_open_deal_count),
        audience_segment_total_estimated_size=int(seg_sum),
        readiness=readiness_dict,
        trust_avg=trust_avg,
        leak_count=leak_count,
        scale_rec=scale_dict,
    )
