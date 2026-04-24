"""Integrations + Listening API."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.integrations_listening import ILConnectorOut, ILListeningOut, ILCompetitorOut, ILClusterOut, ILBlockerOut, RecomputeSummaryOut
from apps.api.services import integrations_listening_service as svc
from packages.db.models.core import Organization

router = APIRouter()

async def _ro(oid, cu, db):
    o = (await db.execute(select(Organization).where(Organization.id == oid))).scalar_one_or_none()
    if not o or o.id != cu.organization_id: raise HTTPException(status_code=403, detail="Organization not accessible")

@router.get("/orgs/{org_id}/integrations/connectors", response_model=list[ILConnectorOut])
async def connectors(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.list_connectors(db, org_id)

@router.get("/orgs/{org_id}/integrations/listening", response_model=list[ILListeningOut])
async def listening(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.list_listening(db, org_id)

@router.get("/orgs/{org_id}/integrations/competitor-signals", response_model=list[ILCompetitorOut])
async def competitors(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.list_competitor_signals(db, org_id)

@router.get("/orgs/{org_id}/integrations/clusters", response_model=list[ILClusterOut])
async def clusters(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.list_clusters(db, org_id)

@router.get("/orgs/{org_id}/integrations/blockers", response_model=list[ILBlockerOut])
async def blockers(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.list_blockers(db, org_id)

@router.post("/orgs/{org_id}/integrations/recompute", response_model=RecomputeSummaryOut)
async def recompute(org_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _ro(org_id, current_user, db); r = await svc.recompute_listening(db, org_id); await db.commit(); return RecomputeSummaryOut(**r)
