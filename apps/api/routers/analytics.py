"""Analytics, attribution, revenue dashboards, and intelligence endpoints — Phase 4."""
import uuid
from fastapi import APIRouter, Query
from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.schemas.analytics import (
    ClickTrackRequest, ConversionTrackRequest,
    PerformanceIngestRequest, AttributionEventResponse,
)
from apps.api.services import analytics_service as ans
from apps.api.services.audit_service import log_action

router = APIRouter()


@router.post("/performance/ingest")
async def ingest_performance(brand_id: uuid.UUID, body: PerformanceIngestRequest, current_user: OperatorUser, db: DBSession):
    pm = await ans.ingest_performance(
        db, brand_id, body.content_item_id, body.creator_account_id, body.platform, body.metrics,
    )
    await log_action(db, "performance.ingested", organization_id=current_user.organization_id,
                     brand_id=brand_id, user_id=current_user.id, actor_type="system",
                     entity_type="performance_metric", entity_id=pm.id)
    return {"metric_id": str(pm.id), "impressions": pm.impressions, "revenue": pm.revenue, "rpm": pm.rpm}


@router.post("/events/track-click", response_model=AttributionEventResponse)
async def track_click(body: ClickTrackRequest, db: DBSession):
    return await ans.track_click(db, body.model_dump(mode="json"))


@router.post("/events/track-conversion", response_model=AttributionEventResponse)
async def track_conversion(body: ConversionTrackRequest, db: DBSession):
    return await ans.track_conversion(db, body.model_dump(mode="json"))


@router.get("/dashboard/revenue")
async def revenue_dashboard(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    return await ans.get_revenue_dashboard(db, brand_id)


@router.get("/dashboard/content-performance")
async def content_performance(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    return await ans.get_content_performance(db, brand_id)


@router.get("/dashboard/funnel")
async def funnel_dashboard(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    return await ans.get_funnel_data(db, brand_id)


@router.get("/dashboard/leaks")
async def revenue_leaks(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    return await ans.get_revenue_leaks(db, brand_id)


@router.get("/dashboard/bottlenecks")
async def bottleneck_dashboard(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    return await ans.classify_bottlenecks(db, brand_id)


@router.post("/winners/detect")
async def detect_winners(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    result = await ans.detect_and_clone_winners(db, brand_id)
    await log_action(db, "winners.detected", organization_id=current_user.organization_id,
                     brand_id=brand_id, user_id=current_user.id, actor_type="system",
                     entity_type="winner_analysis",
                     details={"winners": len(result["winners"]), "losers": len(result["losers"])})
    return result


@router.post("/suppressions/evaluate")
async def evaluate_suppressions(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    result = await ans.evaluate_suppressions(db, brand_id)
    if result:
        await log_action(db, "suppressions.evaluated", organization_id=current_user.organization_id,
                         brand_id=brand_id, user_id=current_user.id, actor_type="system",
                         entity_type="suppression_evaluation",
                         details={"suppressions_created": len(result)})
    return {"suppressions": result, "count": len(result)}
