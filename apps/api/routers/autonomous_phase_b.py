"""Autonomous execution Phase B — policies, content runner, distribution, monetization, suppression."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.autonomous_phase_b import (
    AutonomousRunOut,
    DistributionPlanOut,
    ExecutionPolicyOut,
    MonetizationRouteOut,
    RecomputeSummaryOut,
    SuppressionExecutionOut,
)
from apps.api.services import autonomous_phase_b_service as svc
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")


# --- Execution Policies ---

@router.get("/{brand_id}/execution-policies", response_model=list[ExecutionPolicyOut])
async def list_execution_policies(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_execution_policies(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{brand_id}/execution-policies/recompute", response_model=RecomputeSummaryOut)
async def recompute_execution_policies(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_execution_policies(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Policies recomputed — {result.get('policies_created', 0)} policies",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# --- Autonomous Runs ---

@router.get("/{brand_id}/autonomous-runs", response_model=list[AutonomousRunOut])
async def list_autonomous_runs(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_autonomous_runs(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{brand_id}/autonomous-runs/start", response_model=RecomputeSummaryOut)
async def start_autonomous_runs(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.start_autonomous_run(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Runs started — {result.get('runs_started', 0)} runs in {result.get('execution_mode', 'guarded')} mode",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# --- Distribution Plans ---

@router.get("/{brand_id}/distribution-plans", response_model=list[DistributionPlanOut])
async def list_distribution_plans(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_distribution_plans(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{brand_id}/distribution-plans/recompute", response_model=RecomputeSummaryOut)
async def recompute_distribution_plans(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_distribution_plans(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Distribution plans — {result.get('plans_created', 0)} plans created",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# --- Monetization Routes ---

@router.get("/{brand_id}/monetization-routes", response_model=list[MonetizationRouteOut])
async def list_monetization_routes(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_monetization_routes(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{brand_id}/monetization-routes/recompute", response_model=RecomputeSummaryOut)
async def recompute_monetization_routes(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_monetization_routes(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Monetization routes — {result.get('routes_created', 0)} routes",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# --- Suppression Executions ---

@router.get("/{brand_id}/suppression-executions", response_model=list[SuppressionExecutionOut])
async def list_suppression_executions(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_suppression_executions(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{brand_id}/suppression-executions/recompute", response_model=RecomputeSummaryOut)
async def recompute_suppression_executions(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.run_suppression_check(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Suppression check — {result.get('suppressions_created', 0)} suppressions",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
