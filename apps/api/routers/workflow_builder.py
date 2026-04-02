"""Workflow Builder API."""
import uuid
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.schemas.workflow_builder import WFDefinitionOut, WFInstanceOut, RecomputeSummaryOut
from apps.api.services import workflow_service as svc
from packages.db.models.core import Organization

router = APIRouter()

async def _ro(oid, cu, db):
    o = (await db.execute(select(Organization).where(Organization.id == oid))).scalar_one_or_none()
    if not o or o.id != cu.organization_id: raise HTTPException(status_code=404, detail="Org not found")

@router.get("/orgs/{org_id}/workflows", response_model=list[WFDefinitionOut])
async def list_defs(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db); return await svc.list_definitions(db, org_id)

@router.get("/orgs/{org_id}/workflow-instances", response_model=list[WFInstanceOut])
async def list_instances(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession, status: str = None):
    await _ro(org_id, current_user, db); return await svc.list_instances(db, org_id, status)

@router.post("/orgs/{org_id}/workflows/from-template")
async def from_template(org_id: uuid.UUID, template_key: str, current_user: OperatorUser, db: DBSession, brand_id: uuid.UUID = None):
    await _ro(org_id, current_user, db)
    wf = await svc.create_from_template(db, org_id, template_key, brand_id); await db.commit()
    return {"workflow_id": str(wf.id), "status": "created"}

@router.post("/workflow-instances/{instance_id}/approve")
async def approve(instance_id: uuid.UUID, current_user: OperatorUser, db: DBSession, notes: str = ""):
    r = await svc.approve_step(db, instance_id, current_user.id, getattr(current_user, "role", "org_admin"), notes); await db.commit(); return r

@router.post("/workflow-instances/{instance_id}/reject")
async def reject(instance_id: uuid.UUID, reason: str, current_user: OperatorUser, db: DBSession):
    r = await svc.reject_step(db, instance_id, current_user.id, reason); await db.commit(); return r

@router.post("/workflow-instances/{instance_id}/override")
async def override(instance_id: uuid.UUID, reason: str, current_user: OperatorUser, db: DBSession):
    r = await svc.override_workflow(db, instance_id, current_user.id, reason); await db.commit(); return r
