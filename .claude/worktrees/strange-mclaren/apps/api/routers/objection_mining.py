"""Objection Mining API."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.objection_mining import (
    ObjectionSignalOut, ObjectionClusterOut, ObjectionResponseOut, ObjectionPriorityReportOut, RecomputeSummaryOut,
)
from apps.api.services import objection_mining_service as svc
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")


@router.get("/{brand_id}/objection-signals", response_model=list[ObjectionSignalOut])
async def list_signals(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_signals(db, brand_id)


@router.get("/{brand_id}/objection-clusters", response_model=list[ObjectionClusterOut])
async def list_clusters(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_clusters(db, brand_id)


@router.get("/{brand_id}/objection-responses", response_model=list[ObjectionResponseOut])
async def list_responses(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_responses(db, brand_id)


@router.get("/{brand_id}/objection-priority", response_model=ObjectionPriorityReportOut)
async def priority_report(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    r = await svc.get_priority_report(db, brand_id)
    if not r:
        raise HTTPException(status_code=404, detail="No priority report yet")
    return r


@router.post("/{brand_id}/objection-mining/recompute", response_model=RecomputeSummaryOut)
async def recompute(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await svc.recompute_objections(db, brand_id)
    await db.commit()
    return RecomputeSummaryOut(rows_processed=result["rows_processed"], status=result["status"])
