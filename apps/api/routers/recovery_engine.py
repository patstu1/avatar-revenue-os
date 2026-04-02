"""Recovery / Rollback Engine API."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.recovery_engine import RECIncidentOut, RECRollbackOut, RECRerouteOut, RECThrottleOut, RECOutcomeOut, RecomputeSummaryOut
from apps.api.services import recovery_engine_service as svc
from packages.db.models.core import Organization

router = APIRouter()

async def _ro(oid, cu, db):
    o = (await db.execute(select(Organization).where(Organization.id == oid))).scalar_one_or_none()
    if not o or o.id != cu.organization_id: raise HTTPException(status_code=404, detail="Org not found")

@router.get("/orgs/{org_id}/recovery/incidents", response_model=list[RECIncidentOut])
async def incidents(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.list_incidents(db, org_id)

@router.post("/orgs/{org_id}/recovery/recompute", response_model=RecomputeSummaryOut)
async def recompute(org_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _ro(org_id, current_user, db); r = await svc.recompute_recovery(db, org_id); await db.commit(); return RecomputeSummaryOut(**r)

@router.get("/orgs/{org_id}/recovery/rollbacks", response_model=list[RECRollbackOut])
async def rollbacks(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.list_rollbacks(db, org_id)

@router.get("/orgs/{org_id}/recovery/reroutes", response_model=list[RECRerouteOut])
async def reroutes(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.list_reroutes(db, org_id)

@router.get("/orgs/{org_id}/recovery/throttles", response_model=list[RECThrottleOut])
async def throttles(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.list_throttles(db, org_id)

@router.get("/orgs/{org_id}/recovery/outcomes", response_model=list[RECOutcomeOut])
async def outcomes(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.list_outcomes(db, org_id)
