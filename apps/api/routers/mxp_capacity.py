"""MXP Capacity — production throughput, throttle decisions, queue allocations."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.mxp_capacity import CapacityReportOut, QueueAllocationDecisionOut
from apps.api.services import capacity_service as svc
from apps.api.services.audit_service import log_action
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")


@router.get(
    "/{brand_id}/capacity-reports",
    response_model=list[CapacityReportOut],
)
async def list_reports(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.get_capacity_reports(db, brand_id)


@router.get(
    "/{brand_id}/queue-allocations",
    response_model=list[QueueAllocationDecisionOut],
)
async def list_queue_allocations(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.get_queue_allocations(db, brand_id)


@router.post(
    "/{brand_id}/capacity-reports/recompute",
    response_model=dict,
)
async def recompute_reports(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await svc.recompute_capacity(db, brand_id)
    await log_action(
        db,
        "mxp.capacity_reports_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="capacity_report",
        details=result,
    )
    return result
