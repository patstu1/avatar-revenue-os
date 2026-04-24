"""Operator Permission Matrix API."""
import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.schemas.operator_permission_matrix import OPMExecutionModeOut, OPMMatrixOut, RecomputeSummaryOut
from apps.api.services import operator_permission_service as svc
from packages.db.models.core import Organization

router = APIRouter()

async def _ro(oid, cu, db):
    o = (await db.execute(select(Organization).where(Organization.id == oid))).scalar_one_or_none()
    if not o or o.id != cu.organization_id: raise HTTPException(status_code=403, detail="Organization not accessible")

@router.get("/orgs/{org_id}/permissions/matrix", response_model=list[OPMMatrixOut])
async def matrix(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.list_matrix(db, org_id)

@router.post("/orgs/{org_id}/permissions/seed", response_model=RecomputeSummaryOut)
async def seed(org_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    await _ro(org_id, current_user, db); r = await svc.seed_matrix(db, org_id); await db.commit(); return RecomputeSummaryOut(rows_processed=r["rows_created"], status=r["status"])

@router.get("/orgs/{org_id}/permissions/check/{action_class}")
async def check_action(org_id: uuid.UUID, action_class: str, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.check_action(db, org_id, action_class)

@router.get("/orgs/{org_id}/permissions/override/{action_class}")
async def check_override(org_id: uuid.UUID, action_class: str, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db)
    role = getattr(current_user, "role", "viewer")
    role_str = role.value if hasattr(role, "value") else str(role)
    return await svc.check_override(db, org_id, action_class, role_str)

@router.get("/orgs/{org_id}/permissions/execution-modes", response_model=list[OPMExecutionModeOut])
async def execution_modes(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.list_execution_modes(db, org_id)
