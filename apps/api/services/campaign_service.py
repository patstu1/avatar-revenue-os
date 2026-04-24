"""Campaign Constructor Service — build, persist, detect blockers."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.campaigns import Campaign, CampaignAsset, CampaignBlocker, CampaignDestination, CampaignVariant
from packages.db.models.core import Brand
from packages.db.models.failure_family import SuppressionRule
from packages.db.models.landing_pages import LandingPage
from packages.db.models.offers import Offer
from packages.db.models.provider_registry import ProviderBlocker
from packages.scoring.campaign_engine import construct_campaign, construct_variant, detect_blockers


async def recompute_campaigns(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(delete(CampaignBlocker).where(CampaignBlocker.brand_id == brand_id))
    await db.execute(
        delete(CampaignDestination).where(
            CampaignDestination.campaign_id.in_(select(Campaign.id).where(Campaign.brand_id == brand_id))
        )
    )
    await db.execute(
        delete(CampaignAsset).where(
            CampaignAsset.campaign_id.in_(select(Campaign.id).where(Campaign.brand_id == brand_id))
        )
    )
    await db.execute(
        delete(CampaignVariant).where(
            CampaignVariant.campaign_id.in_(select(Campaign.id).where(Campaign.brand_id == brand_id))
        )
    )
    await db.execute(delete(Campaign).where(Campaign.brand_id == brand_id))

    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    offers = list(
        (await db.execute(select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True)))).scalars().all()
    )
    accounts = list(
        (
            await db.execute(
                select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )

    suppressed = list(
        (
            await db.execute(
                select(SuppressionRule.family_key).where(
                    SuppressionRule.brand_id == brand_id,
                    SuppressionRule.is_active.is_(True),
                    SuppressionRule.family_type == "hook_type",
                )
            )
        )
        .scalars()
        .all()
    )
    prov_blockers = list(
        (
            await db.execute(
                select(ProviderBlocker).where(ProviderBlocker.brand_id == brand_id, ProviderBlocker.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    system_state = {
        "suppressed_families": suppressed,
        "provider_blockers": [{"key": b.provider_key} for b in prov_blockers],
    }

    brand_dict = {"niche": brand.niche if brand else "general"}
    acct_dicts = [
        {"id": str(a.id), "platform": a.platform.value if hasattr(a.platform, "value") else str(a.platform)}
        for a in accounts
    ]

    campaigns_created = 0
    for offer in offers:
        offer_dict = {
            "name": offer.name,
            "monetization_method": offer.monetization_method,
            "epc": float(offer.epc or 0),
            "conversion_rate": float(offer.conversion_rate or 0),
        }
        lp = (
            await db.execute(
                select(LandingPage)
                .where(
                    LandingPage.brand_id == brand_id, LandingPage.offer_id == offer.id, LandingPage.is_active.is_(True)
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        lp_id = str(lp.id) if lp else None

        for ct in ("affiliate", "product_conversion"):
            spec = construct_campaign(offer_dict, brand_dict, acct_dicts, lp_id, ct)
            camp = Campaign(
                brand_id=brand_id,
                offer_id=offer.id,
                landing_page_id=lp.id if lp else None,
                **{k: v for k, v in spec.items() if k not in ("landing_page_id",)},
            )
            db.add(camp)
            await db.flush()

            for i in range(2):
                vs = construct_variant(spec, i)
                db.add(CampaignVariant(campaign_id=camp.id, landing_page_id=lp.id if lp else None, **vs))

            if lp:
                db.add(
                    CampaignDestination(
                        campaign_id=camp.id,
                        landing_page_id=lp.id,
                        destination_url=lp.destination_url,
                        destination_type="landing_page",
                    )
                )

            blockers = detect_blockers(spec, system_state)
            for b in blockers:
                db.add(CampaignBlocker(campaign_id=camp.id, brand_id=brand_id, **b))

            campaigns_created += 1

    await db.flush()
    return {"rows_processed": campaigns_created, "status": "completed"}


async def list_campaigns(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(Campaign)
                .where(Campaign.brand_id == brand_id, Campaign.is_active.is_(True))
                .order_by(Campaign.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def list_campaign_variants(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(CampaignVariant)
                .join(Campaign)
                .where(Campaign.brand_id == brand_id, CampaignVariant.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )


async def list_campaign_blockers(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(CampaignBlocker).where(CampaignBlocker.brand_id == brand_id, CampaignBlocker.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )


async def get_campaign_for_content(db: AsyncSession, brand_id: uuid.UUID, offer_id: uuid.UUID = None) -> dict[str, Any]:
    q = select(Campaign).where(Campaign.brand_id == brand_id, Campaign.is_active.is_(True))
    if offer_id:
        q = q.where(Campaign.offer_id == offer_id)
    camp = (await db.execute(q.order_by(Campaign.confidence.desc()).limit(1))).scalar_one_or_none()
    if not camp:
        return {"campaign_id": None, "truth_label": "no_campaign"}
    return {
        "campaign_id": str(camp.id),
        "campaign_type": camp.campaign_type,
        "name": camp.campaign_name,
        "truth_label": camp.truth_label,
        "launch_status": camp.launch_status,
    }
