"""Hyper-Scale Execution API."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.hyperscale import HSCapacityOut, HSQueueSegmentOut, HSCeilingOut, HSScaleHealthOut, RecomputeSummaryOut
from apps.api.services import hyperscale_service as svc
from packages.db.models.core import Organization

router = APIRouter()

async def _ro(oid, cu, db):
    o = (await db.execute(select(Organization).where(Organization.id == oid))).scalar_one_or_none()
    if not o or o.id != cu.organization_id: raise HTTPException(status_code=404, detail="Org not found")

@router.get("/orgs/{org_id}/scale/capacity", response_model=list[HSCapacityOut])
async def capacity(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.list_capacity(db, org_id)

@router.post("/orgs/{org_id}/scale/recompute", response_model=RecomputeSummaryOut)
async def recompute(org_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _ro(org_id, current_user, db); r = await svc.recompute_capacity(db, org_id); await db.commit(); return RecomputeSummaryOut(**r)

@router.get("/orgs/{org_id}/scale/segments", response_model=list[HSQueueSegmentOut])
async def segments(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.list_segments(db, org_id)

@router.get("/orgs/{org_id}/scale/ceilings", response_model=list[HSCeilingOut])
async def ceilings(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.list_ceilings(db, org_id)

@router.get("/orgs/{org_id}/scale/health", response_model=list[HSScaleHealthOut])
async def health(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.list_scale_health(db, org_id)
