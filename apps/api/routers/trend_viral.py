"""Trend / Viral Opportunity API."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.trend_viral import (
    RecomputeSummaryOut,
    TVBlockerOut,
    TVOpportunityOut,
    TVSignalOut,
    TVSourceHealthOut,
    TVVelocityOut,
)
from apps.api.services import trend_viral_service as svc
from packages.db.models.core import Brand

router = APIRouter()

async def _rb(bid, cu, db):
    b = (await db.execute(select(Brand).where(Brand.id == bid))).scalar_one_or_none()
    if not b or b.organization_id != cu.organization_id: raise HTTPException(status_code=403, detail="Brand not accessible")

@router.get("/{brand_id}/trend-signals", response_model=list[TVSignalOut])
async def signals(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_signals(db, brand_id)

@router.get("/{brand_id}/trend-velocity", response_model=list[TVVelocityOut])
async def velocity(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_velocity(db, brand_id)

@router.get("/{brand_id}/viral-opportunities", response_model=list[TVOpportunityOut])
async def opportunities(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_opportunities(db, brand_id)

@router.post("/{brand_id}/viral-opportunities/recompute", response_model=RecomputeSummaryOut)
async def recompute(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _rb(brand_id, current_user, db)
    await svc.light_scan(db, brand_id)
    r2 = await svc.deep_analysis(db, brand_id)
    await db.commit()
    return RecomputeSummaryOut(rows_processed=r2.get("opportunities_created", 0), status="completed")

@router.get("/{brand_id}/trend-blockers", response_model=list[TVBlockerOut])
async def blockers(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_blockers(db, brand_id)

@router.get("/{brand_id}/trend-source-health", response_model=list[TVSourceHealthOut])
async def source_health(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_source_health(db, brand_id)

@router.get("/{brand_id}/top-trend-opportunities")
async def top_opps(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.get_top_opportunities(db, brand_id)
