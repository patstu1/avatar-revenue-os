"""Expansion Pack 2 Phase B — pricing, bundling, retention, reactivation services."""
from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.core import Brand
from packages.db.models.offers import Offer
from packages.db.models.expansion_pack2_phase_b import (
    PricingRecommendation,
    BundleRecommendation,
    RetentionRecommendation,
    ReactivationCampaign,
)
from packages.scoring.expansion_pack2_phase_b_engines import (
    EP2B,
    recommend_pricing,
    recommend_bundle,
    recommend_bundles,
    recommend_retention,
    recommend_reactivation_campaign,
)


async def recompute_pricing_recommendations(
    db: AsyncSession, brand_id: uuid.UUID
) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    # Fetch active offers for the brand
    offers = list(
        (await db.execute(select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))))
        .scalars()
        .all()
    )

    # DATA BOUNDARY: No live sales/market/segment feed exists yet.
    # Engine uses offer EPC + conversion_rate as the strongest available price signals.
    # When live POS or analytics integrations exist, replace these with real queries.
    historical_sales_data: list[dict] = []
    market_data: list[dict] = []
    customer_segment_data: list[dict] = []

    # Delete old recommendations
    await db.execute(delete(PricingRecommendation).where(PricingRecommendation.brand_id == brand_id))

    pricing_recommendations = []
    for offer in offers:
        recommendation = recommend_pricing(
            offer_id=offer.id,
            current_price=offer.payout_amount, # Assuming payout_amount is the current price
            historical_sales_data=historical_sales_data,
            market_data=market_data,
            customer_segment_data=customer_segment_data,
        )
        pricing_recommendations.append(recommendation)
        db.add(
            PricingRecommendation(
                brand_id=brand_id,
                offer_id=offer.id,
                recommendation_type=recommendation["recommendation_type"],
                current_price=recommendation["current_price"],
                recommended_price=recommendation["recommended_price"],
                price_elasticity=recommendation["price_elasticity"],
                estimated_revenue_impact=recommendation["estimated_revenue_impact"],
                confidence=recommendation["confidence"],
                explanation=recommendation["explanation"],
            )
        )

    await db.flush()
    return {"pricing_recommendations_count": len(pricing_recommendations)}


async def get_pricing_recommendations(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = list(
        (await db.execute(
            select(PricingRecommendation)
            .where(PricingRecommendation.brand_id == brand_id, PricingRecommendation.is_active.is_(True))
            .order_by(PricingRecommendation.estimated_revenue_impact.desc())
        ))
        .scalars()
        .all()
    )
    return [
        {
            "id": str(r.id),
            "brand_id": str(r.brand_id),
            "offer_id": str(r.offer_id),
            "recommendation_type": r.recommendation_type,
            "current_price": r.current_price,
            "recommended_price": r.recommended_price,
            "price_elasticity": r.price_elasticity,
            "estimated_revenue_impact": r.estimated_revenue_impact,
            "confidence": r.confidence,
            "explanation": r.explanation,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
        }
        for r in rows
    ]


async def recompute_bundle_recommendations(
    db: AsyncSession, brand_id: uuid.UUID
) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    # Fetch active offers for the brand
    offers = list(
        (await db.execute(select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))))
        .scalars()
        .all()
    )
    available_offers_data = [
        {"id": str(o.id), "name": o.name, "price": o.payout_amount, "features": []} for o in offers
    ]

    # DATA BOUNDARY: No live purchase history or trend feed exists yet.
    # Engine derives bundles from offer set, pricing, and niche alone.
    customer_purchase_history: list[dict] = []
    market_trends: list[dict] = []

    # Delete old recommendations
    await db.execute(delete(BundleRecommendation).where(BundleRecommendation.brand_id == brand_id))

    recommendations = recommend_bundles(
        available_offers=available_offers_data,
        customer_purchase_history=customer_purchase_history,
        market_trends=market_trends,
        brand_name=brand.name,
        niche=getattr(brand, "niche", ""),
    )

    for rec in recommendations:
        rec.pop(EP2B, None)
        db.add(
            BundleRecommendation(
                brand_id=brand_id,
                bundle_name=rec["bundle_name"],
                offer_ids=[uuid.UUID(oid) for oid in rec["offer_ids"] if oid],
                recommended_bundle_price=rec["recommended_bundle_price"],
                estimated_upsell_rate=rec["estimated_upsell_rate"],
                estimated_revenue_impact=rec["estimated_revenue_impact"],
                confidence=rec["confidence"],
                explanation=rec["explanation"],
            )
        )

    await db.flush()
    return {"bundle_recommendations_count": len(recommendations)}


async def get_bundle_recommendations(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = list(
        (await db.execute(
            select(BundleRecommendation)
            .where(BundleRecommendation.brand_id == brand_id, BundleRecommendation.is_active.is_(True))
            .order_by(BundleRecommendation.estimated_revenue_impact.desc())
        ))
        .scalars()
        .all()
    )
    return [
        {
            "id": str(r.id),
            "brand_id": str(r.brand_id),
            "bundle_name": r.bundle_name,
            "offer_ids": [str(oid) for oid in r.offer_ids],
            "recommended_bundle_price": r.recommended_bundle_price,
            "estimated_upsell_rate": r.estimated_upsell_rate,
            "estimated_revenue_impact": r.estimated_revenue_impact,
            "confidence": r.confidence,
            "explanation": r.explanation,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
        }
        for r in rows
    ]


async def recompute_retention_recommendations(
    db: AsyncSession, brand_id: uuid.UUID
) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    offers = list(
        (await db.execute(select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))))
        .scalars().all()
    )
    available_retention_offers = [
        {"offer_id": str(o.id), "type": "discount", "discount": 0.10} for o in offers[:3]
    ]

    # Generate retention recommendations for 3 synthetic customer segments
    segments = [
        {"name": "high_value_at_risk", "churn": 0.80, "behavior": [{"activity_level": "low"}]},
        {"name": "declining_engagement", "churn": 0.55, "behavior": [{"activity_level": "medium"}]},
        {"name": "healthy_customers", "churn": 0.15, "behavior": [{"activity_level": "high"}]},
    ]

    await db.execute(delete(RetentionRecommendation).where(RetentionRecommendation.brand_id == brand_id))

    count = 0
    for seg in segments:
        result = recommend_retention(
            customer_id=uuid.uuid4(),
            customer_behavior_data=seg["behavior"],
            churn_risk_score=seg["churn"],
            available_retention_offers=available_retention_offers,
        )
        db.add(RetentionRecommendation(
            brand_id=brand_id,
            customer_segment=seg["name"],
            recommendation_type=result["recommendation_type"],
            action_details=result["action_details"],
            estimated_retention_lift=result["estimated_retention_lift"],
            confidence=result["confidence"],
            explanation=result["explanation"],
        ))
        count += 1

    await db.flush()
    return {"retention_recommendations_count": count}


async def get_retention_recommendations(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = list(
        (await db.execute(
            select(RetentionRecommendation)
            .where(RetentionRecommendation.brand_id == brand_id, RetentionRecommendation.is_active.is_(True))
            .order_by(RetentionRecommendation.estimated_retention_lift.desc())
        ))
        .scalars().all()
    )
    return [
        {
            "id": str(r.id),
            "brand_id": str(r.brand_id),
            "customer_segment": r.customer_segment,
            "recommendation_type": r.recommendation_type,
            "action_details": r.action_details,
            "estimated_retention_lift": r.estimated_retention_lift,
            "confidence": r.confidence,
            "explanation": r.explanation,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
        }
        for r in rows
    ]


async def recompute_reactivation_campaigns(
    db: AsyncSession, brand_id: uuid.UUID
) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    # DATA BOUNDARY: No live lapsed-customer feed or campaign history exists yet.
    # Engine produces rules-based reactivation recommendations from available offer data.
    lapsed_customer_segment: list[dict] = []
    historical_campaign_performance: list[dict] = []
    available_campaign_types = ["email_series", "discount_offer"]

    # Delete old campaigns
    await db.execute(delete(ReactivationCampaign).where(ReactivationCampaign.brand_id == brand_id))

    campaign = recommend_reactivation_campaign(
        lapsed_customer_segment=lapsed_customer_segment,
        historical_campaign_performance=historical_campaign_performance,
        available_campaign_types=available_campaign_types,
    )

    db.add(
        ReactivationCampaign(
            brand_id=brand_id,
            campaign_name=campaign["campaign_name"],
            target_segment=campaign["target_segment"],
            campaign_type=campaign["campaign_type"],
            start_date=datetime.fromisoformat(campaign["start_date"]) if campaign.get("start_date") else None,
            end_date=datetime.fromisoformat(campaign["end_date"]) if campaign.get("end_date") else None,
            estimated_reactivation_rate=campaign["estimated_reactivation_rate"],
            estimated_revenue_impact=campaign["estimated_revenue_impact"],
            confidence=campaign["confidence"],
            explanation=campaign["explanation"],
        )
    )

    await db.flush()
    return {"reactivation_campaigns_count": 1}


async def get_reactivation_campaigns(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = list(
        (await db.execute(
            select(ReactivationCampaign)
            .where(ReactivationCampaign.brand_id == brand_id, ReactivationCampaign.is_active.is_(True))
            .order_by(ReactivationCampaign.estimated_revenue_impact.desc())
        ))
        .scalars()
        .all()
    )
    return [
        {
            "id": str(r.id),
            "brand_id": str(r.brand_id),
            "campaign_name": r.campaign_name,
            "target_segment": r.target_segment,
            "campaign_type": r.campaign_type,
            "start_date": r.start_date.isoformat() if r.start_date else None,
            "end_date": r.end_date.isoformat() if r.end_date else None,
            "estimated_reactivation_rate": r.estimated_reactivation_rate,
            "estimated_revenue_impact": r.estimated_revenue_impact,
            "confidence": r.confidence,
            "explanation": r.explanation,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
        }
        for r in rows
    ]
