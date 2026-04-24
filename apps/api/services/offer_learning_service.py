"""Offer Parameter Learning service — update offers from measured performance."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.live_execution import ConversionEvent
from packages.db.models.offers import Offer
from packages.db.models.publishing import AttributionEvent, PerformanceMetric
from packages.scoring.offer_learning_engine import compute_learned_offer_params


async def run_offer_learning(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    """Aggregate performance data per offer and update offer economics."""
    offers = list(
        (await db.execute(select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True)))).scalars().all()
    )

    updated_count = 0
    skipped_count = 0

    for offer in offers:
        clicks_from_attr = (
            await db.execute(
                select(func.count())
                .select_from(AttributionEvent)
                .where(
                    AttributionEvent.brand_id == brand_id,
                    AttributionEvent.offer_id == offer.id,
                    AttributionEvent.event_type.in_(["click", "link_click", "cta_click"]),
                )
            )
        ).scalar() or 0

        clicks_from_perf = (
            await db.execute(
                select(func.coalesce(func.sum(PerformanceMetric.clicks), 0)).where(
                    PerformanceMetric.brand_id == brand_id,
                )
            )
        ).scalar() or 0

        total_clicks = max(clicks_from_attr, clicks_from_perf)

        conv_agg = (
            await db.execute(
                select(
                    func.count().label("conv_count"),
                    func.coalesce(func.sum(ConversionEvent.revenue), 0.0).label("total_rev"),
                ).where(
                    ConversionEvent.brand_id == brand_id,
                    ConversionEvent.offer_id == offer.id,
                )
            )
        ).first()

        conversions = int(conv_agg[0] if conv_agg else 0)
        revenue = float(conv_agg[1] if conv_agg else 0.0)

        if conversions == 0:
            attr_conv = (
                await db.execute(
                    select(
                        func.count().label("c"),
                        func.coalesce(func.sum(AttributionEvent.event_value), 0.0).label("v"),
                    ).where(
                        AttributionEvent.brand_id == brand_id,
                        AttributionEvent.offer_id == offer.id,
                        AttributionEvent.event_type.in_(["purchase", "conversion", "sale"]),
                    )
                )
            ).first()
            if attr_conv:
                conversions = int(attr_conv[0])
                revenue = float(attr_conv[1])

        result = compute_learned_offer_params(
            offer_id=str(offer.id),
            current_epc=float(offer.epc or 0),
            current_cvr=float(offer.conversion_rate or 0),
            current_aov=float(offer.average_order_value or 0),
            measured_clicks=total_clicks,
            measured_conversions=conversions,
            measured_revenue=revenue,
        )

        if result["updated"]:
            await db.execute(
                update(Offer)
                .where(Offer.id == offer.id)
                .values(
                    epc=result["learned_epc"],
                    conversion_rate=result["learned_cvr"],
                    average_order_value=result["learned_aov"],
                )
            )
            updated_count += 1
        else:
            skipped_count += 1

    await db.flush()
    return {"offers_updated": updated_count, "offers_skipped": skipped_count, "status": "completed"}
