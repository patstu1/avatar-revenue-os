"""Discovery, scoring, and recommendation endpoints — Phase 2 core."""
import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.schemas.discovery import (
    ForecastResponse, NicheClusterResponse, OfferFitResponse,
    OpportunityScoreResponse, ProfitForecastResponse, RecommendationResponse,
    SaturationReportResponse, SignalIngestRequest, TopicCandidateResponse,
    TrendSignalResponse,
)
from apps.api.services.audit_service import log_action
from apps.api.services import discovery_service as ds
from packages.db.models.discovery import NicheCluster, TopicCandidate, TrendSignal
from packages.db.models.scoring import (
    OpportunityScore, ProfitForecast, RecommendationQueue, SaturationReport,
)

router = APIRouter()


@router.post("/{brand_id}/signals/ingest")
async def ingest_signals(brand_id: uuid.UUID, body: SignalIngestRequest, current_user: OperatorUser, db: DBSession):
    result = await ds.ingest_signals(db, brand_id, body.source_type, body.topics)
    await log_action(
        db, "signals.ingested",
        organization_id=current_user.organization_id,
        brand_id=brand_id, user_id=current_user.id,
        actor_type="human", entity_type="signal_ingestion",
        details=result,
    )
    return result


@router.get("/{brand_id}/signals")
async def get_signals(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    data = await ds.get_signals(db, brand_id)
    return {
        "topic_candidates": [TopicCandidateResponse.model_validate(t) for t in data["topic_candidates"]],
        "trend_signals": [TrendSignalResponse.model_validate(t) for t in data["trend_signals"]],
        "ingestion_runs": len(data["ingestion_runs"]),
    }


@router.get("/{brand_id}/niches", response_model=list[NicheClusterResponse])
async def get_niches(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(NicheCluster).where(NicheCluster.brand_id == brand_id).order_by(NicheCluster.monetization_potential.desc())
    )
    return result.scalars().all()


@router.post("/{brand_id}/niches/recompute", response_model=list[NicheClusterResponse])
async def recompute_niches(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    clusters = await ds.compute_niches(db, brand_id)
    await log_action(
        db, "niches.recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id, user_id=current_user.id,
        actor_type="human", entity_type="niche_cluster",
        details={"clusters_created": len(clusters)},
    )
    return clusters


@router.get("/{brand_id}/opportunities", response_model=list[OpportunityScoreResponse])
async def get_opportunities(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(OpportunityScore)
        .where(OpportunityScore.brand_id == brand_id)
        .order_by(OpportunityScore.composite_score.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.post("/{brand_id}/opportunities/recompute")
async def recompute_opportunities(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    results = await ds.compute_opportunities(db, brand_id)
    recs = await ds.build_recommendation_queue(db, brand_id)
    await log_action(
        db, "opportunities.recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id, user_id=current_user.id,
        actor_type="human", entity_type="opportunity_score",
        details={"topics_scored": len(results), "recommendations_built": len(recs)},
    )
    return {"topics_scored": results, "recommendations_queued": len(recs)}


@router.get("/{brand_id}/opportunities/queue", response_model=list[RecommendationResponse])
async def get_opportunity_queue(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(RecommendationQueue)
        .where(RecommendationQueue.brand_id == brand_id)
        .order_by(RecommendationQueue.rank.asc())
        .limit(50)
    )
    return result.scalars().all()


@router.post("/{brand_id}/opportunities/{topic_id}/forecast", response_model=ForecastResponse)
async def forecast_topic(brand_id: uuid.UUID, topic_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    try:
        result = await ds.compute_forecast_for_topic(db, brand_id, topic_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


@router.post("/{brand_id}/opportunities/{topic_id}/offer-fit")
async def compute_offer_fit(brand_id: uuid.UUID, topic_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    try:
        results = await ds.compute_offer_fit_for_topic(db, brand_id, topic_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return results


@router.post("/{brand_id}/opportunities/{topic_id}/trigger-brief")
async def trigger_brief(brand_id: uuid.UUID, topic_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    try:
        result = await ds.trigger_brief_for_topic(db, brand_id, topic_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await log_action(
        db, "brief.triggered",
        organization_id=current_user.organization_id,
        brand_id=brand_id, user_id=current_user.id,
        actor_type="human", entity_type="content_brief",
        entity_id=uuid.UUID(result["brief_id"]),
        details=result,
    )
    return result


@router.get("/{brand_id}/trends", response_model=list[TrendSignalResponse])
async def get_trends(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(TrendSignal).where(TrendSignal.brand_id == brand_id).order_by(TrendSignal.velocity.desc()).limit(50)
    )
    return result.scalars().all()


@router.post("/{brand_id}/trends/recompute")
async def recompute_trends(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    # Trend recompute re-classifies existing signals
    trends = (await db.execute(
        select(TrendSignal).where(TrendSignal.brand_id == brand_id)
    )).scalars().all()
    updated = 0
    for t in trends:
        from packages.scoring.opportunity import _clamp
        new_strength = "strong" if t.velocity > 0.7 else "moderate" if t.velocity > 0.4 else "weak" if t.velocity > 0.1 else "insufficient"
        t.is_actionable = t.velocity > 0.3
        updated += 1
    await db.flush()
    return {"trends_updated": updated}


@router.get("/{brand_id}/saturation", response_model=list[SaturationReportResponse])
async def get_saturation(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession, recompute: bool = False):
    if recompute:
        await ds.compute_saturation_report(db, brand_id)
    result = await db.execute(
        select(SaturationReport).where(SaturationReport.brand_id == brand_id).order_by(SaturationReport.saturation_score.desc())
    )
    return result.scalars().all()


@router.get("/{brand_id}/profit-forecasts", response_model=list[ProfitForecastResponse])
async def get_profit_forecasts(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(ProfitForecast).where(ProfitForecast.brand_id == brand_id).order_by(ProfitForecast.estimated_profit.desc())
    )
    return result.scalars().all()


@router.get("/{brand_id}/recommendations", response_model=list[RecommendationResponse])
async def get_recommendations(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(RecommendationQueue)
        .where(RecommendationQueue.brand_id == brand_id, RecommendationQueue.is_actioned.is_(False))
        .order_by(RecommendationQueue.rank.asc())
        .limit(25)
    )
    return result.scalars().all()
