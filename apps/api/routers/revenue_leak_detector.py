"""Revenue Leak Detector API."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.revenue_leak_detector import (
    RecomputeSummaryOut,
    RLDClusterOut,
    RLDCorrectionOut,
    RLDEventOut,
    RLDReportOut,
)
from apps.api.services import revenue_leak_service as svc
from packages.db.models.core import Brand

router = APIRouter()


async def _rb(bid, cu, db):
    b = (await db.execute(select(Brand).where(Brand.id == bid))).scalar_one_or_none()
    if not b or b.organization_id != cu.organization_id:
        raise HTTPException(status_code=403, detail="Brand not accessible")


@router.get("/{brand_id}/revenue-leaks", response_model=list[RLDReportOut])
async def reports(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db)
    return await svc.list_reports(db, brand_id)


@router.post("/{brand_id}/revenue-leaks/recompute", response_model=RecomputeSummaryOut)
async def recompute(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _rb(brand_id, current_user, db)
    r = await svc.recompute_leaks(db, brand_id)
    await db.commit()
    return RecomputeSummaryOut(**r)


@router.get("/{brand_id}/revenue-leaks/events", response_model=list[RLDEventOut])
async def events(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db)
    return await svc.list_events(db, brand_id)


@router.get("/{brand_id}/revenue-leaks/clusters", response_model=list[RLDClusterOut])
async def clusters(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db)
    return await svc.list_clusters(db, brand_id)


@router.get("/{brand_id}/revenue-leaks/corrections", response_model=list[RLDCorrectionOut])
async def corrections(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db)
    return await svc.list_corrections(db, brand_id)
