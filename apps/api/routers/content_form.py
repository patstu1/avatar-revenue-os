"""Content Form Selection — API routes."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.schemas.content_form import (
    ContentFormBlockerOut,
    ContentFormMixReportOut,
    ContentFormRecommendationOut,
    RecomputeSummaryOut,
)
from apps.api.services import content_form_service as cfs
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, user, db: DBSession) -> Brand:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")
    return brand


@router.get("/{brand_id}/content-forms", response_model=list[ContentFormRecommendationOut])
async def list_recommendations(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await cfs.list_recommendations(db, brand_id)


@router.post("/{brand_id}/content-forms/recompute", response_model=RecomputeSummaryOut)
async def recompute_recommendations(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await cfs.recompute_recommendations(db, brand_id)


@router.get("/{brand_id}/content-form-mix", response_model=list[ContentFormMixReportOut])
async def list_mix_reports(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await cfs.list_mix_reports(db, brand_id)


@router.post("/{brand_id}/content-form-mix/recompute", response_model=RecomputeSummaryOut)
async def recompute_mix(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await cfs.recompute_mix(db, brand_id)


@router.get("/{brand_id}/content-form-blockers", response_model=list[ContentFormBlockerOut])
async def list_blockers(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await cfs.list_blockers(db, brand_id)
