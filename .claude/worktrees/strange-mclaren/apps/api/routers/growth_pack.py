"""Portfolio Launch / Growth Pack APIs — persisted plans and reports."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.growth_pack import (
    AccountLaunchBlueprintOut,
    CapitalDeploymentPlanOut,
    CrossAccountCannibalizationReportOut,
    GrowthPackBlockerReportOut,
    NicheDeploymentReportOut,
    PlatformAllocationReportOut,
    PortfolioLaunchPlanOut,
    PortfolioOutputReportOut,
    RecomputeSummaryOut,
)
from apps.api.services import growth_pack_service as gps
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, user, db: DBSession) -> Brand:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")
    return brand


# --- portfolio launch plan ---
@router.get("/{brand_id}/portfolio-launch-plan", response_model=Optional[PortfolioLaunchPlanOut])
async def get_portfolio_launch_plan(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    rows = await gps.list_portfolio_launch_plans(db, brand_id)
    return rows[0] if rows else None


@router.post("/{brand_id}/portfolio-launch-plan/recompute", response_model=RecomputeSummaryOut)
async def post_portfolio_launch_recompute(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await gps.recompute_portfolio_launch_plan(db, brand_id)
    return RecomputeSummaryOut(status="completed", detail="Portfolio launch plan recomputed", counts=result if isinstance(result, dict) else None)


# --- account launch blueprints ---
@router.get("/{brand_id}/account-launch-blueprints", response_model=list[AccountLaunchBlueprintOut])
async def list_blueprints(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gps.list_account_blueprints(db, brand_id)


@router.post("/{brand_id}/account-launch-blueprints/recompute", response_model=RecomputeSummaryOut)
async def post_blueprints_recompute(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await gps.recompute_account_blueprints(db, brand_id)
    return RecomputeSummaryOut(status="completed", detail="Account blueprints recomputed", counts=result if isinstance(result, dict) else None)


# --- platform allocation ---
@router.get("/{brand_id}/platform-allocation", response_model=list[PlatformAllocationReportOut])
async def get_platform_allocation(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gps.list_platform_allocation(db, brand_id)


@router.post("/{brand_id}/platform-allocation/recompute", response_model=RecomputeSummaryOut)
async def post_platform_allocation(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await gps.recompute_platform_allocation(db, brand_id)
    return RecomputeSummaryOut(status="completed", detail="Platform allocation recomputed", counts=result if isinstance(result, dict) else None)


# --- niche deployment ---
@router.get("/{brand_id}/niche-deployment", response_model=list[NicheDeploymentReportOut])
async def get_niche_deployment(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gps.list_niche_deployment(db, brand_id)


@router.post("/{brand_id}/niche-deployment/recompute", response_model=RecomputeSummaryOut)
async def post_niche_deployment(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await gps.recompute_niche_deployment(db, brand_id)
    return RecomputeSummaryOut(status="completed", detail="Niche deployment recomputed", counts=result if isinstance(result, dict) else None)


# --- growth blockers (pack table) ---
@router.get("/{brand_id}/growth-blockers", response_model=list[GrowthPackBlockerReportOut])
async def get_growth_blockers_pack(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gps.list_growth_blockers_pack(db, brand_id)


@router.post("/{brand_id}/growth-blockers/recompute", response_model=RecomputeSummaryOut)
async def post_growth_blockers_pack(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await gps.recompute_growth_blockers_pack(db, brand_id)
    return RecomputeSummaryOut(status="completed", detail="Growth blockers recomputed", counts=result if isinstance(result, dict) else None)


# --- capital deployment ---
@router.get("/{brand_id}/capital-deployment", response_model=list[CapitalDeploymentPlanOut])
async def get_capital_deployment(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gps.list_capital_deployment(db, brand_id)


@router.post("/{brand_id}/capital-deployment/recompute", response_model=RecomputeSummaryOut)
async def post_capital_deployment(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await gps.recompute_capital_deployment(db, brand_id)
    return RecomputeSummaryOut(status="completed", detail="Capital deployment recomputed", counts=result if isinstance(result, dict) else None)


# --- cross-account cannibalization ---
@router.get("/{brand_id}/cross-account-cannibalization", response_model=list[CrossAccountCannibalizationReportOut])
async def get_cross_cannibal(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gps.list_cross_cannibalization(db, brand_id)


@router.post("/{brand_id}/cross-account-cannibalization/recompute", response_model=RecomputeSummaryOut)
async def post_cross_cannibal(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await gps.recompute_cross_account_cannibalization(db, brand_id)
    return RecomputeSummaryOut(status="completed", detail="Cannibalization analysis recomputed", counts=result if isinstance(result, dict) else None)


# --- portfolio output ---
@router.get("/{brand_id}/portfolio-output", response_model=list[PortfolioOutputReportOut])
async def get_portfolio_output(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gps.list_portfolio_output(db, brand_id)


@router.post("/{brand_id}/portfolio-output/recompute", response_model=RecomputeSummaryOut)
async def post_portfolio_output(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await gps.recompute_portfolio_output(db, brand_id)
    return RecomputeSummaryOut(status="completed", detail="Portfolio output recomputed", counts=result if isinstance(result, dict) else None)


# --- Single blueprint (global path per spec) ---
router_root = APIRouter()


@router_root.get("/account-launch-blueprints/{blueprint_id}", response_model=AccountLaunchBlueprintOut)
async def get_blueprint_by_id(blueprint_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    row = await gps.get_account_blueprint(db, blueprint_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blueprint not found")
    bid = uuid.UUID(row["brand_id"])
    brand = (await db.execute(select(Brand).where(Brand.id == bid))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not accessible")
    return row
