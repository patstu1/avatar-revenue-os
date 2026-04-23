"""Revenue Avenues API — SaaS metrics, pipeline, launches, and avenue optimization."""
import uuid

from fastapi import APIRouter, HTTPException

from apps.api.deps import CurrentUser, DBSession, require_brand_access
from apps.api.services import saas_revenue_service as srs

router = APIRouter()


@router.get("/{brand_id}/avenues/saas-metrics")
async def get_saas_metrics(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Current SaaS metrics — MRR, ARR, NRR, churn rate, quick ratio, LTV."""
    await require_brand_access(brand_id, current_user, db)
    return await srs.get_saas_metrics(db, brand_id)


@router.get("/{brand_id}/avenues/churn-analysis")
async def get_churn_analysis(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Churn risk scoring for all active subscribers."""
    await require_brand_access(brand_id, current_user, db)
    return await srs.get_churn_analysis(db, brand_id)


@router.get("/{brand_id}/avenues/expansion-opportunities")
async def get_expansion_opportunities(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Upsell and cross-sell opportunities from active subscribers."""
    await require_brand_access(brand_id, current_user, db)
    return await srs.get_expansion_opportunities(db, brand_id)


@router.get("/{brand_id}/avenues/pipeline")
async def get_pipeline(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """High-ticket deal pipeline analysis with velocity and bottleneck detection."""
    await require_brand_access(brand_id, current_user, db)
    return await srs.get_pipeline_analysis(db, brand_id)


@router.get("/{brand_id}/avenues/rankings")
async def get_avenue_rankings(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Rank all revenue avenues by expected ROI, effort, and time-to-revenue."""
    await require_brand_access(brand_id, current_user, db)
    return await srs.get_revenue_avenue_rankings(db, brand_id)


@router.get("/{brand_id}/avenues/cohorts")
async def get_cohorts(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Monthly cohort retention analysis on subscriptions."""
    await require_brand_access(brand_id, current_user, db)
    return await srs.get_cohort_analysis(db, brand_id)


@router.get("/{brand_id}/avenues/revenue-stack")
async def get_revenue_stack(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Full revenue stack with diversification scoring and vulnerability assessment."""
    await require_brand_access(brand_id, current_user, db)
    return await srs.get_revenue_stack(db, brand_id)


@router.get("/{brand_id}/avenues/launches/{launch_id}")
async def get_launch_analysis(
    brand_id: uuid.UUID,
    launch_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Analyze a specific product launch — funnel metrics, ROAS, health."""
    await require_brand_access(brand_id, current_user, db)
    result = await srs.get_launch_analysis(db, brand_id, launch_id)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Launch not found")
    return result


@router.post("/{brand_id}/avenues/pipeline/score")
async def score_pipeline(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Score all open deals in the pipeline using engagement, recency, and value signals."""
    await require_brand_access(brand_id, current_user, db)
    return await srs.score_pipeline_deals(db, brand_id)


@router.post("/{brand_id}/avenues/launches/{launch_id}/plan")
async def plan_launch(
    brand_id: uuid.UUID,
    launch_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Generate a phased launch plan for a product launch."""
    await require_brand_access(brand_id, current_user, db)
    result = await srs.plan_launch(db, brand_id, launch_id)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Launch not found")
    return result
