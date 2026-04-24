"""Enterprise Affiliate API."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.affiliate_enterprise import (
    AFApprovalOut,
    AFBannedOut,
    AFGovRuleOut,
    AFPartnerOut,
    AFRiskFlagOut,
    RecomputeSummaryOut,
)
from apps.api.services import affiliate_enterprise_service as svc
from packages.db.models.core import Organization

router = APIRouter()


async def _ro(oid, cu, db):
    o = (await db.execute(select(Organization).where(Organization.id == oid))).scalar_one_or_none()
    if not o or o.id != cu.organization_id:
        raise HTTPException(status_code=403, detail="Organization not accessible")


@router.get("/orgs/{org_id}/affiliate/governance-rules", response_model=list[AFGovRuleOut])
async def gov_rules(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db)
    return await svc.list_governance_rules(db, org_id)


@router.get("/orgs/{org_id}/affiliate/banned", response_model=list[AFBannedOut])
async def banned(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db)
    return await svc.list_banned(db, org_id)


@router.get("/orgs/{org_id}/affiliate/approvals", response_model=list[AFApprovalOut])
async def approvals(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db)
    return await svc.list_approvals(db, org_id)


@router.get("/orgs/{org_id}/affiliate/risk-flags", response_model=list[AFRiskFlagOut])
async def risk_flags(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db)
    return await svc.list_risk_flags(db, org_id)


@router.get("/orgs/{org_id}/affiliate/partners", response_model=list[AFPartnerOut])
async def partners(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _ro(org_id, current_user, db)
    return await svc.list_partners(db, org_id)


@router.post("/orgs/{org_id}/affiliate/governance/recompute", response_model=RecomputeSummaryOut)
async def recompute_gov(
    org_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _ro(org_id, current_user, db)
    r = await svc.recompute_governance(db, org_id)
    await db.commit()
    return RecomputeSummaryOut(**r)


@router.post("/orgs/{org_id}/affiliate/partners/recompute", response_model=RecomputeSummaryOut)
async def recompute_partners(
    org_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _ro(org_id, current_user, db)
    r = await svc.recompute_partner_scores(db, org_id)
    await db.commit()
    return RecomputeSummaryOut(**r)
