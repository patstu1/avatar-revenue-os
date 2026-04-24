"""Offer Lab Service — generate, score, test, learn, persist."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()
from packages.db.models.core import Brand
from packages.db.models.offer_lab import (
    OfferLabBlocker,
    OfferLabBundle,
    OfferLabLearning,
    OfferLabOffer,
    OfferLabPositioningTest,
    OfferLabPricingTest,
    OfferLabUpsell,
    OfferLabVariant,
)
from packages.db.models.offers import Offer
from packages.scoring.offer_lab_engine import (
    detect_offer_issues,
    generate_bundles,
    generate_offer,
    generate_positioning_test,
    generate_pricing_test,
    generate_upsells,
    generate_variants,
    score_offer,
)


async def recompute_offer_lab(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(delete(OfferLabBlocker).where(OfferLabBlocker.brand_id == brand_id))
    await db.execute(delete(OfferLabUpsell).where(OfferLabUpsell.brand_id == brand_id))
    await db.execute(delete(OfferLabBundle).where(OfferLabBundle.brand_id == brand_id))
    await db.execute(
        delete(OfferLabPositioningTest).where(
            OfferLabPositioningTest.offer_id.in_(select(OfferLabOffer.id).where(OfferLabOffer.brand_id == brand_id))
        )
    )
    await db.execute(
        delete(OfferLabPricingTest).where(
            OfferLabPricingTest.offer_id.in_(select(OfferLabOffer.id).where(OfferLabOffer.brand_id == brand_id))
        )
    )
    await db.execute(
        delete(OfferLabVariant).where(
            OfferLabVariant.offer_id.in_(select(OfferLabOffer.id).where(OfferLabOffer.brand_id == brand_id))
        )
    )
    await db.execute(delete(OfferLabOffer).where(OfferLabOffer.brand_id == brand_id))

    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    offers = list(
        (await db.execute(select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True)))).scalars().all()
    )
    brand_dict = {"niche": brand.niche if brand else "general"}

    lab_offers = []
    for o in offers:
        source = {
            "name": o.name,
            "monetization_method": o.monetization_method,
            "payout_amount": float(o.payout_amount or 0),
            "epc": float(o.epc or 0),
            "conversion_rate": float(o.conversion_rate or 0),
        }
        spec = generate_offer(source, brand_dict)
        lo = OfferLabOffer(brand_id=brand_id, source_offer_id=o.id, **spec)
        db.add(lo)
        await db.flush()
        lab_offers.append(lo)

        for vs in generate_variants(spec):
            db.add(OfferLabVariant(offer_id=lo.id, **vs))

        pt = generate_pricing_test(spec)
        db.add(OfferLabPricingTest(offer_id=lo.id, **pt))

        pos = generate_positioning_test(spec)
        db.add(OfferLabPositioningTest(offer_id=lo.id, **pos))

        lo.rank_score = score_offer(spec)
        issues = detect_offer_issues(spec)
        for issue in issues:
            db.add(OfferLabBlocker(brand_id=brand_id, offer_id=lo.id, **issue))

    lo_dicts = [
        {"id": str(lo.id), "offer_name": lo.offer_name, "price_point": float(lo.price_point)} for lo in lab_offers
    ]
    for b in generate_bundles(lo_dicts):
        db.add(
            OfferLabBundle(
                brand_id=brand_id,
                bundle_name=b["bundle_name"],
                offer_ids=b["offer_ids"],
                combined_price=b["combined_price"],
                savings_pct=b["savings_pct"],
                expected_uplift=b["expected_uplift"],
            )
        )

    upsells = generate_upsells(lo_dicts)
    for u in upsells:
        try:
            db.add(
                OfferLabUpsell(
                    brand_id=brand_id,
                    primary_offer_id=uuid.UUID(u["primary_offer_id"]),
                    upsell_offer_id=uuid.UUID(u["upsell_offer_id"]),
                    expected_take_rate=u["expected_take_rate"],
                )
            )
        except (ValueError, TypeError):
            logger.debug("upsell_offer_id_parse_failed", exc_info=True)

    await db.flush()
    return {"rows_processed": len(lab_offers), "status": "completed"}


async def list_offers(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(OfferLabOffer)
                .where(OfferLabOffer.brand_id == brand_id, OfferLabOffer.is_active.is_(True))
                .order_by(OfferLabOffer.rank_score.desc())
            )
        )
        .scalars()
        .all()
    )


async def list_variants(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(OfferLabVariant)
                .join(OfferLabOffer)
                .where(OfferLabOffer.brand_id == brand_id, OfferLabVariant.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )


async def list_bundles(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(OfferLabBundle).where(OfferLabBundle.brand_id == brand_id, OfferLabBundle.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )


async def list_blockers(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(OfferLabBlocker).where(OfferLabBlocker.brand_id == brand_id, OfferLabBlocker.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )


async def list_learning(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(OfferLabLearning).where(
                    OfferLabLearning.brand_id == brand_id, OfferLabLearning.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )


async def get_best_offer(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    o = (
        await db.execute(
            select(OfferLabOffer)
            .where(OfferLabOffer.brand_id == brand_id, OfferLabOffer.is_active.is_(True))
            .order_by(OfferLabOffer.rank_score.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if not o:
        return {"offer_id": None}
    return {
        "offer_id": str(o.id),
        "name": o.offer_name,
        "rank_score": o.rank_score,
        "angle": o.primary_angle,
        "truth_label": o.truth_label,
    }
