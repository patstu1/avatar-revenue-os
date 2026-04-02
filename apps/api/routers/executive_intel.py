"""Executive Intelligence API."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.executive_intel import EIKPIOut, EIForecastOut, EIUptimeOut, EIOversightOut, EIAlertOut, RecomputeSummaryOut
from apps.api.services import executive_intel_service as svc
from packages.db.models.core import Organization

router = APIRouter()

async def _ro(oid, cu, db):
    o = (await db.execute(select(Organization).where(Organization.id == oid))).scalar_one_or_none()
    if not o or o.id != cu.organization_id: raise HTTPException(status_code=404, detail="Org not found")

@router.get("/orgs/{org_id}/executive/kpis", response_model=list[EIKPIOut])
async def kpis(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.list_kpis(db, org_id)

@router.get("/orgs/{org_id}/executive/forecasts", response_model=list[EIForecastOut])
async def forecasts(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.list_forecasts(db, org_id)

@router.get("/orgs/{org_id}/executive/uptime", response_model=list[EIUptimeOut])
async def uptime(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.list_uptime(db, org_id)

@router.get("/orgs/{org_id}/executive/oversight", response_model=list[EIOversightOut])
async def oversight(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.list_oversight(db, org_id)

@router.get("/orgs/{org_id}/executive/alerts", response_model=list[EIAlertOut])
async def alerts(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.list_alerts(db, org_id)

@router.post("/orgs/{org_id}/executive/recompute", response_model=RecomputeSummaryOut)
async def recompute(org_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _ro(org_id, current_user, db); r = await svc.recompute_executive_intel(db, org_id); await db.commit(); return RecomputeSummaryOut(**r)
