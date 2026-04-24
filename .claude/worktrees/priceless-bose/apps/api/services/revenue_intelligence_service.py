"""Revenue Intelligence Service — bridges scoring engines to API endpoints."""
import statistics
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.offers import Offer
from packages.db.models.publishing import AttributionEvent, PerformanceMetric
from packages.scoring.revenue_intelligence import (
    AudienceSegment,
    OfferPerformanceProfile,
    TouchPoint,
    attribute_multi_model,
    compute_optimal_offer_mix,
    compute_revenue_ceiling,
    compute_revenue_health_score,
    detect_revenue_anomalies,
    forecast_revenue,
    predict_content_ltv,
    rank_offers_for_content,
)

logger = structlog.get_logger()


async def get_revenue_forecast(
    db: AsyncSession, brand_id: uuid.UUID, horizon_days: int = 30
) -> dict:
    """Build revenue forecast from historical data."""
    ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)

    rows = (
        await db.execute(
            select(
                func.date(PerformanceMetric.measured_at).label("day"),
                func.coalesce(func.sum(PerformanceMetric.revenue), 0.0).label(
                    "revenue"
                ),
            )
            .where(
                PerformanceMetric.brand_id == brand_id,
                PerformanceMetric.measured_at >= ninety_days_ago,
            )
            .group_by(func.date(PerformanceMetric.measured_at))
            .order_by(func.date(PerformanceMetric.measured_at))
        )
    ).all()

    if len(rows) < 14:
        return {
            "status": "insufficient_data",
            "min_days_needed": 14,
            "current_days": len(rows),
        }

    daily = [(str(r.day), float(r.revenue)) for r in rows]
    forecast = forecast_revenue(daily, horizon_days=horizon_days)

    return {
        "period": forecast.period,
        "trend": forecast.trend,
        "growth_rate": round(forecast.growth_rate, 4),
        "confidence": round(forecast.confidence, 3),
        "forecasts": forecast.forecasts,
    }


async def get_revenue_anomalies(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[dict]:
    """Detect revenue anomalies from recent data."""
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    rows = (
        await db.execute(
            select(
                func.date(PerformanceMetric.measured_at).label("day"),
                func.coalesce(func.sum(PerformanceMetric.revenue), 0.0).label(
                    "revenue"
                ),
            )
            .where(
                PerformanceMetric.brand_id == brand_id,
                PerformanceMetric.measured_at >= thirty_days_ago,
            )
            .group_by(func.date(PerformanceMetric.measured_at))
            .order_by(func.date(PerformanceMetric.measured_at))
        )
    ).all()

    if len(rows) < 7:
        return []

    daily = [(str(r.day), float(r.revenue)) for r in rows]
    anomalies = detect_revenue_anomalies(daily)

    return [
        {
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "anomaly_type": a.anomaly_type,
            "severity": round(a.severity, 3),
            "expected_value": round(a.expected_value, 2),
            "actual_value": round(a.actual_value, 2),
            "deviation_sigma": round(a.deviation_sigma, 2),
            "explanation": a.explanation,
            "recommended_action": a.recommended_action,
        }
        for a in anomalies
    ]


async def get_offer_rankings(
    db: AsyncSession,
    brand_id: uuid.UUID,
    platform: str,
    content_type: str,
) -> list[dict]:
    """Rank offers by expected revenue for a given context."""
    offers = (
        await db.execute(
            select(Offer).where(
                Offer.brand_id == brand_id, Offer.is_active.is_(True)
            )
        )
    ).scalars().all()

    if not offers:
        return []

    profiles = []
    for o in offers:
        profiles.append(
            OfferPerformanceProfile(
                offer_id=str(o.id),
                epc=o.epc or 0.0,
                conversion_rate=o.conversion_rate or 0.0,
                avg_order_value=o.average_order_value or 0.0,
                audience_fit_score=0.7,
                freshness_score=1.0,
                competition_density=0.3,
                seasonal_multiplier=1.0,
            )
        )

    accounts = (
        await db.execute(
            select(CreatorAccount).where(
                CreatorAccount.brand_id == brand_id,
                CreatorAccount.is_active.is_(True),
            )
        )
    ).scalars().all()

    total_followers = sum(a.follower_count for a in accounts) if accounts else 0
    avg_engagement = (
        statistics.mean([a.ctr for a in accounts]) if accounts else 0.02
    )
    avg_conv = (
        statistics.mean([a.conversion_rate for a in accounts])
        if accounts
        else 0.01
    )

    segment = AudienceSegment(
        segment_id="primary",
        name="Primary Audience",
        size=total_followers,
        avg_engagement_rate=avg_engagement,
        avg_conversion_rate=avg_conv,
        avg_revenue_per_user=0.0,
        top_content_types=[content_type],
        top_platforms=[platform],
        price_sensitivity=0.5,
    )

    rankings = rank_offers_for_content(profiles, segment, platform, content_type)

    offer_map = {str(o.id): o.name for o in offers}
    return [
        {
            "offer_id": oid,
            "offer_name": offer_map.get(oid, "Unknown"),
            "score": round(score, 4),
            "breakdown": breakdown,
        }
        for oid, score, breakdown in rankings
    ]


async def get_content_ltv_analysis(
    db: AsyncSession, brand_id: uuid.UUID, limit: int = 20
) -> list[dict]:
    """Compute LTV predictions for active content."""
    items = (
        await db.execute(
            select(ContentItem)
            .where(ContentItem.brand_id == brand_id)
            .order_by(ContentItem.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    results = []
    for item in items:
        daily_data = (
            await db.execute(
                select(
                    func.date(PerformanceMetric.measured_at).label("day"),
                    func.coalesce(
                        func.sum(PerformanceMetric.revenue), 0.0
                    ).label("revenue"),
                    func.coalesce(
                        func.sum(PerformanceMetric.impressions), 0
                    ).label("impressions"),
                )
                .where(PerformanceMetric.content_item_id == item.id)
                .group_by(func.date(PerformanceMetric.measured_at))
                .order_by(func.date(PerformanceMetric.measured_at))
            )
        ).all()

        if len(daily_data) < 3:
            continue

        content_age = (datetime.now(timezone.utc) - item.created_at).days
        daily_rev = [float(d.revenue) for d in daily_data]
        daily_imp = [float(d.impressions) for d in daily_data]

        ct_value = item.content_type
        ct_str = ct_value.value if hasattr(ct_value, "value") else str(ct_value)
        plat_str = item.platform or "youtube"

        ltv = predict_content_ltv(
            content_age_days=max(content_age, 1),
            daily_revenue_history=daily_rev,
            daily_impression_history=daily_imp,
            content_type=ct_str,
            platform=plat_str,
        )

        results.append(
            {
                "content_id": str(item.id),
                "title": item.title or "",
                "content_age_days": content_age,
                "projected_30d": round(ltv.projected_30d_revenue, 2),
                "projected_90d": round(ltv.projected_90d_revenue, 2),
                "projected_365d": round(ltv.projected_365d_revenue, 2),
                "half_life_days": round(ltv.revenue_half_life_days, 1),
                "evergreen_score": round(ltv.evergreen_score, 3),
                "viral_coefficient": round(ltv.viral_coefficient, 3),
            }
        )

    return sorted(results, key=lambda x: x["projected_90d"], reverse=True)


async def get_revenue_ceiling(
    db: AsyncSession, brand_id: uuid.UUID
) -> dict:
    """Compute revenue ceiling analysis."""
    accounts = (
        await db.execute(
            select(CreatorAccount).where(
                CreatorAccount.brand_id == brand_id,
                CreatorAccount.is_active.is_(True),
            )
        )
    ).scalars().all()

    offers = (
        await db.execute(
            select(Offer).where(
                Offer.brand_id == brand_id, Offer.is_active.is_(True)
            )
        )
    ).scalars().all()

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    monthly_rev = (
        await db.execute(
            select(func.coalesce(func.sum(PerformanceMetric.revenue), 0.0)).where(
                PerformanceMetric.brand_id == brand_id,
                PerformanceMetric.measured_at >= thirty_days_ago,
            )
        )
    ).scalar() or 0.0

    monthly_impressions = (
        await db.execute(
            select(
                func.coalesce(func.sum(PerformanceMetric.impressions), 0)
            ).where(
                PerformanceMetric.brand_id == brand_id,
                PerformanceMetric.measured_at >= thirty_days_ago,
            )
        )
    ).scalar() or 0

    avg_rpm = (float(monthly_rev) / max(monthly_impressions, 1)) * 1000
    avg_conv = (
        statistics.mean([a.conversion_rate for a in accounts])
        if accounts
        else 0.01
    )

    account_data = [
        {
            "account_id": str(a.id),
            "platform": (
                a.platform.value if hasattr(a.platform, "value") else str(a.platform)
            ),
            "follower_count": a.follower_count,
            "posting_capacity_per_day": a.posting_capacity_per_day,
            "avg_engagement_rate": a.ctr,
        }
        for a in accounts
    ]

    offer_data = [
        {
            "offer_id": str(o.id),
            "epc": o.epc or 0.0,
            "conversion_rate": o.conversion_rate or 0.0,
            "avg_order_value": o.average_order_value or 0.0,
        }
        for o in offers
    ]

    content_velocity = sum(a.posting_capacity_per_day for a in accounts) * 30

    ceiling = compute_revenue_ceiling(
        accounts=account_data,
        offers=offer_data,
        content_velocity=content_velocity,
        avg_rpm=avg_rpm,
        avg_conversion_rate=avg_conv,
    )

    return {
        "current_monthly_revenue": round(float(monthly_rev), 2),
        "theoretical_ceiling": round(ceiling.theoretical_ceiling, 2),
        "achievable_ceiling_90d": round(ceiling.achievable_ceiling_90d, 2),
        "efficiency_score": round(ceiling.efficiency_score, 3),
        "gap_analysis": ceiling.gap_analysis,
        "top_opportunities": ceiling.top_opportunities,
    }


async def get_revenue_health(
    db: AsyncSession, brand_id: uuid.UUID
) -> dict:
    """Compute overall revenue health score from last 30 days of data."""
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    rows = (
        await db.execute(
            select(
                func.date(PerformanceMetric.measured_at).label("day"),
                func.coalesce(func.sum(PerformanceMetric.revenue), 0.0).label(
                    "revenue"
                ),
            )
            .where(
                PerformanceMetric.brand_id == brand_id,
                PerformanceMetric.measured_at >= thirty_days_ago,
            )
            .group_by(func.date(PerformanceMetric.measured_at))
            .order_by(func.date(PerformanceMetric.measured_at))
        )
    ).all()

    if len(rows) < 7:
        return {
            "status": "insufficient_data",
            "min_days_needed": 7,
            "current_days": len(rows),
        }

    daily_revenues = [float(r.revenue) for r in rows]
    return compute_revenue_health_score(daily_revenues)


async def get_attribution_for_conversion(
    db: AsyncSession,
    brand_id: uuid.UUID,
    conversion_id: uuid.UUID,
) -> dict:
    """Get multi-model attribution for a specific conversion."""
    conversion = (
        await db.execute(
            select(AttributionEvent).where(
                AttributionEvent.id == conversion_id,
                AttributionEvent.brand_id == brand_id,
            )
        )
    ).scalar_one_or_none()

    if not conversion:
        return {"error": "conversion_not_found"}

    touchpoint_events = (
        await db.execute(
            select(AttributionEvent)
            .where(
                AttributionEvent.brand_id == brand_id,
                AttributionEvent.tracking_id == conversion.tracking_id,
                AttributionEvent.event_at <= conversion.event_at,
            )
            .order_by(AttributionEvent.event_at)
        )
    ).scalars().all()

    if not touchpoint_events:
        return {
            "conversion_id": str(conversion_id),
            "total_value": float(conversion.event_value),
            "models": {},
            "touchpoint_count": 0,
        }

    touchpoints = [
        TouchPoint(
            timestamp=e.event_at,
            channel=e.platform or "unknown",
            content_id=str(e.content_item_id) if e.content_item_id else "",
            event_type=e.event_type,
            value=float(e.event_value),
        )
        for e in touchpoint_events
    ]

    results = attribute_multi_model(touchpoints, float(conversion.event_value))

    serialised: dict[str, dict] = {}
    for model_name, attr_result in results.items():
        serialised[model_name] = {
            "total_value": attr_result.total_value,
            "touchpoint_credits": attr_result.touchpoint_credits,
            "path_length": attr_result.path_length,
            "time_to_conversion_hours": attr_result.time_to_conversion_hours,
        }

    return {
        "conversion_id": str(conversion_id),
        "total_value": float(conversion.event_value),
        "models": serialised,
        "touchpoint_count": len(touchpoints),
    }


async def get_optimal_schedule(
    db: AsyncSession,
    brand_id: uuid.UUID,
    platform: str,
    timezone_str: str,
    posts_per_day: int,
) -> dict:
    """Get optimal posting schedule for a platform using Bayesian optimization."""
    from packages.scoring.realtime_engine import compute_optimal_schedule

    ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)

    metrics = (
        await db.execute(
            select(PerformanceMetric)
            .where(
                PerformanceMetric.brand_id == brand_id,
                PerformanceMetric.measured_at >= ninety_days_ago,
            )
            .order_by(PerformanceMetric.measured_at.desc())
            .limit(500)
        )
    ).scalars().all()

    historical_performance = [
        {
            "posted_at": m.measured_at.isoformat() if m.measured_at else None,
            "engagement_rate": m.engagement_rate,
            "impressions": m.impressions,
        }
        for m in metrics
        if m.measured_at is not None
    ]

    rec = compute_optimal_schedule(
        platform=platform,
        timezone=timezone_str,
        historical_performance=historical_performance,
        posts_per_day=posts_per_day,
    )

    return {
        "platform": platform,
        "timezone": timezone_str,
        "recommended_times": rec.recommended_times,
        "avoid_times": rec.avoid_times,
        "reasoning": rec.reasoning,
        "expected_engagement_lift_pct": rec.expected_engagement_lift_pct,
    }
