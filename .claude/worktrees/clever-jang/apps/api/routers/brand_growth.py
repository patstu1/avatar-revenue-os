"""Phase 6: growth intelligence endpoints under /brands/{id}/…

GET endpoints are read-only. POST /growth-intel/recompute triggers the write path.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.growth import (
    AudienceSegmentResponse,
    ExpansionRecommendationsResponse,
    GeoLanguageRecRow,
    LtvModelResponse,
    PaidAmplificationResponse,
    PaidJobRow,
    TrustReportRow,
    TrustSignalsResponse,
)
from apps.api.services import growth_service as gs
from apps.api.services.audit_service import log_action
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, user, db: DBSession) -> Brand:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")
    return brand


@router.post("/{brand_id}/growth-intel/recompute")
async def recompute_growth_intel(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await gs.recompute_growth_intel(db, brand_id, user_id=current_user.id)
    await log_action(
        db,
        "growth_intel.recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="growth_intel",
        details=result,
    )
    return result


@router.get("/{brand_id}/audience-segments", response_model=list[AudienceSegmentResponse])
async def list_audience_segments(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gs.get_audience_segments(db, brand_id)


@router.get("/{brand_id}/ltv", response_model=list[LtvModelResponse])
async def list_ltv_models(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gs.get_ltv_models(db, brand_id)


@router.get("/{brand_id}/expansion-recommendations", response_model=ExpansionRecommendationsResponse)
async def get_expansion_recommendations(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    bundle = await gs.get_expansion_bundle(db, brand_id)
    return ExpansionRecommendationsResponse(
        geo_language_recommendations=[GeoLanguageRecRow(**g) for g in bundle["geo_language_recommendations"]],
        cross_platform_flow_plans=bundle["cross_platform_flow_plans"],
        latest_expansion_decision_id=bundle.get("latest_expansion_decision_id"),
    )


@router.get("/{brand_id}/paid-amplification", response_model=PaidAmplificationResponse)
async def list_paid_amplification(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    bundle = await gs.get_paid_amplification_bundle(db, brand_id)
    return PaidAmplificationResponse(
        jobs=[PaidJobRow(**j) for j in bundle["jobs"]],
        note=bundle.get("note", ""),
    )


@router.get("/{brand_id}/trust-signals", response_model=TrustSignalsResponse)
async def list_trust_signals(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    bundle = await gs.get_trust_signals_bundle(db, brand_id)
    return TrustSignalsResponse(reports=[TrustReportRow(**r) for r in bundle["reports"]])
