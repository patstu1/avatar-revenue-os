"""Revenue Intelligence API — elite-tier revenue optimization endpoints."""

import uuid

from fastapi import APIRouter, Query

from apps.api.deps import CurrentUser, DBSession, require_brand_access
from apps.api.services import revenue_intelligence_service as ris

router = APIRouter()


@router.get("/{brand_id}/intelligence/forecast")
async def get_forecast(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    horizon_days: int = Query(30, ge=7, le=90),
):
    """Revenue forecast using Holt-Winters triple exponential smoothing."""
    await require_brand_access(brand_id, current_user, db)
    return await ris.get_revenue_forecast(db, brand_id, horizon_days)


@router.get("/{brand_id}/intelligence/anomalies")
async def get_anomalies(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Detect revenue anomalies using adaptive EWMA Z-score analysis."""
    await require_brand_access(brand_id, current_user, db)
    return await ris.get_revenue_anomalies(db, brand_id)


@router.get("/{brand_id}/intelligence/offer-rankings")
async def get_offer_rankings(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    platform: str = Query("youtube", description="Target platform"),
    content_type: str = Query("short_video", description="Content type"),
):
    """Rank offers by expected revenue for a given platform/content context."""
    await require_brand_access(brand_id, current_user, db)
    return await ris.get_offer_rankings(db, brand_id, platform, content_type)


@router.get("/{brand_id}/intelligence/content-ltv")
async def get_content_ltv(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(20, ge=1, le=100),
):
    """Compute lifetime value predictions for active content using decay curve fitting."""
    await require_brand_access(brand_id, current_user, db)
    return await ris.get_content_ltv_analysis(db, brand_id, limit)


@router.get("/{brand_id}/intelligence/revenue-ceiling")
async def get_revenue_ceiling(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Revenue ceiling analysis — theoretical max, 90-day achievable, gap analysis."""
    await require_brand_access(brand_id, current_user, db)
    return await ris.get_revenue_ceiling(db, brand_id)


@router.get("/{brand_id}/intelligence/health-score")
async def get_health_score(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Holistic revenue health score (0–100) with sub-component breakdown."""
    await require_brand_access(brand_id, current_user, db)
    return await ris.get_revenue_health(db, brand_id)


@router.get("/{brand_id}/intelligence/attribution/{conversion_id}")
async def get_attribution(
    brand_id: uuid.UUID,
    conversion_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Multi-model attribution for a specific conversion (linear, time-decay, position, Shapley)."""
    await require_brand_access(brand_id, current_user, db)
    return await ris.get_attribution_for_conversion(db, brand_id, conversion_id)


@router.get("/{brand_id}/intelligence/optimal-schedule")
async def get_optimal_schedule(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    platform: str = Query("youtube", description="Target platform"),
    timezone: str = Query("America/New_York", description="Audience timezone"),
    posts_per_day: int = Query(1, ge=1, le=10),
):
    """Bayesian-optimized posting schedule with Thompson sampling for exploration."""
    await require_brand_access(brand_id, current_user, db)
    return await ris.get_optimal_schedule(db, brand_id, platform, timezone, posts_per_day)
