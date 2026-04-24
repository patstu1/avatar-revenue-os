"""Enterprise Security + Compliance API."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.enterprise_security import (
    ESAuditOut,
    ESComplianceOut,
    ESDataPolicyOut,
    ESModelIsolationOut,
    ESRiskOverrideOut,
    ESRoleOut,
    RecomputeSummaryOut,
)
from apps.api.services import enterprise_security_service as svc
from packages.db.models.core import Organization

router = APIRouter()


async def _ro(org_id, cu, db):
    o = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not o or o.id != cu.organization_id:
        raise HTTPException(status_code=403, detail="Organization not accessible")


@router.get("/orgs/{org_id}/security/roles", response_model=list[ESRoleOut])
async def roles(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db)
    return await svc.list_roles(db, org_id)


@router.post("/orgs/{org_id}/security/seed-roles", response_model=RecomputeSummaryOut)
async def seed(org_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    await _ro(org_id, current_user, db)
    r = await svc.seed_system_roles(db, org_id)
    await db.commit()
    return RecomputeSummaryOut(rows_processed=r["roles_created"], status=r["status"])


@router.get("/orgs/{org_id}/security/audit-trail", response_model=list[ESAuditOut])
async def audit(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db)
    return await svc.list_audit_trail(db, org_id)


@router.get("/orgs/{org_id}/security/data-policies", response_model=list[ESDataPolicyOut])
async def data_policies(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db)
    return await svc.list_data_policies(db, org_id)


@router.get("/orgs/{org_id}/security/compliance", response_model=list[ESComplianceOut])
async def compliance(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db)
    return await svc.list_compliance_controls(db, org_id)


@router.post("/orgs/{org_id}/security/compliance/recompute", response_model=RecomputeSummaryOut)
async def recompute_compliance(
    org_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _ro(org_id, current_user, db)
    r = await svc.recompute_compliance(db, org_id)
    await db.commit()
    return RecomputeSummaryOut(**r)


@router.get("/orgs/{org_id}/security/model-isolation", response_model=list[ESModelIsolationOut])
async def model_isolation(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db)
    return await svc.list_model_isolation(db, org_id)


@router.get("/orgs/{org_id}/security/risk-overrides", response_model=list[ESRiskOverrideOut])
async def risk_overrides(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db)
    return await svc.list_risk_overrides(db, org_id)
