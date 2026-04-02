"""Portfolio Capital Allocator API."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.capital_allocator import (
    AllocationReportOut, AllocationDecisionOut, AllocationRebalanceOut, RecomputeSummaryOut,
)
from apps.api.services import capital_allocator_service as svc
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")


@router.get("/{brand_id}/capital-allocation/reports", response_model=list[AllocationReportOut])
async def list_reports(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_reports(db, brand_id)


@router.post("/{brand_id}/capital-allocation/recompute", response_model=RecomputeSummaryOut)
async def recompute(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, total_budget: float = 1000.0, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await svc.recompute_allocation(db, brand_id, total_budget)
    await db.commit()
    return RecomputeSummaryOut(rows_processed=result["rows_processed"], status=result["status"])


@router.get("/{brand_id}/capital-allocation/decisions", response_model=list[AllocationDecisionOut])
async def list_decisions(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_decisions(db, brand_id)


@router.get("/{brand_id}/capital-allocation/rebalances", response_model=list[AllocationRebalanceOut])
async def list_rebalances(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_rebalances(db, brand_id)
