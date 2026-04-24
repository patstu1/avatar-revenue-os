"""Affiliate Intelligence Service — rank, link, detect leaks, persist."""
from __future__ import annotations
import uuid
from typing import Any
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from packages.db.models.affiliate_intel import (
    AffiliateOffer, AffiliateLink, AffiliateClickEvent, AffiliateConversionEvent,
    AffiliateCommissionEvent, AffiliatePayoutEvent, AffiliateBlocker, AffiliateLeak,
)
from packages.scoring.affiliate_intel_engine import rank_offers, detect_leaks, detect_blockers, build_affiliate_link


async def recompute_ranking(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    offers = list((await db.execute(select(AffiliateOffer).where(AffiliateOffer.brand_id == brand_id, AffiliateOffer.is_active.is_(True)))).scalars().all())
    offer_dicts = [{"id": str(o.id), "product_name": o.product_name, "epc": float(o.epc), "conversion_rate": float(o.conversion_rate), "commission_rate": float(o.commission_rate), "refund_rate": float(o.refund_rate), "trust_score": float(o.trust_score), "content_fit_score": float(o.content_fit_score), "platform_fit_score": float(o.platform_fit_score), "audience_fit_score": float(o.audience_fit_score), "affiliate_url": o.affiliate_url, "destination_url": o.destination_url, "blocker_state": o.blocker_state, "is_active": o.is_active} for o in offers]
    ranked = rank_offers(offer_dicts)
    for r in ranked:
        for o in offers:
            if str(o.id) == r["id"]:
                o.rank_score = r["rank_score"]
                break

    await db.execute(delete(AffiliateBlocker).where(AffiliateBlocker.brand_id == brand_id))
    blockers = detect_blockers(offer_dicts)
    for b in blockers:
        oid = None
        if b.get("offer_id"):
            try: oid = uuid.UUID(str(b["offer_id"]))
            except (ValueError, AttributeError): pass
        db.add(AffiliateBlocker(brand_id=brand_id, offer_id=oid, blocker_type=b["blocker_type"], description=b["description"], severity=b["severity"]))

    await db.execute(delete(AffiliateLeak).where(AffiliateLeak.brand_id == brand_id))
    links = list((await db.execute(select(AffiliateLink).where(AffiliateLink.brand_id == brand_id, AffiliateLink.is_active.is_(True)))).scalars().all())
    link_dicts = [{"id": str(l.id), "offer_id": str(l.offer_id), "click_count": l.click_count, "conversion_count": l.conversion_count} for l in links]
    leaks = detect_leaks(offer_dicts, link_dicts)
    for lk in leaks:
        oid = lid = None
        if lk.get("offer_id"):
            try: oid = uuid.UUID(str(lk["offer_id"]))
            except (ValueError, AttributeError): pass
        if lk.get("link_id"):
            try: lid = uuid.UUID(str(lk["link_id"]))
            except (ValueError, AttributeError): pass
        db.add(AffiliateLeak(brand_id=brand_id, offer_id=oid, link_id=lid, leak_type=lk["leak_type"], severity=lk["severity"], revenue_loss_estimate=lk["revenue_loss_estimate"], recommendation=lk["recommendation"]))

    await db.flush()
    return {"rows_processed": len(offers), "blockers": len(blockers), "leaks": len(leaks), "status": "completed"}


async def list_offers(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(AffiliateOffer).where(AffiliateOffer.brand_id == brand_id, AffiliateOffer.is_active.is_(True)).order_by(AffiliateOffer.rank_score.desc()))).scalars().all())

async def list_links(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(AffiliateLink).where(AffiliateLink.brand_id == brand_id, AffiliateLink.is_active.is_(True)))).scalars().all())

async def list_leaks(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(AffiliateLeak).where(AffiliateLeak.brand_id == brand_id, AffiliateLeak.is_active.is_(True)).order_by(AffiliateLeak.severity))).scalars().all())

async def list_blockers(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(AffiliateBlocker).where(AffiliateBlocker.brand_id == brand_id, AffiliateBlocker.is_active.is_(True)))).scalars().all())

async def list_commissions(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(AffiliateCommissionEvent).where(AffiliateCommissionEvent.brand_id == brand_id))).scalars().all())

async def list_payouts(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(AffiliatePayoutEvent).where(AffiliatePayoutEvent.brand_id == brand_id))).scalars().all())

async def get_best_offer_for_content(db: AsyncSession, brand_id: uuid.UUID, platform: str = "") -> dict[str, Any]:
    offer = (await db.execute(select(AffiliateOffer).where(AffiliateOffer.brand_id == brand_id, AffiliateOffer.is_active.is_(True)).order_by(AffiliateOffer.rank_score.desc()).limit(1))).scalar_one_or_none()
    if not offer: return {"offer_id": None}
    return {"offer_id": str(offer.id), "product_name": offer.product_name, "rank_score": offer.rank_score, "epc": offer.epc, "affiliate_url": offer.affiliate_url}
