"""Autonomous execution Phase D — agent orchestration, revenue pressure, overrides, blockers, escalations."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.autonomous_phase_d import (
    AgentOrchestrationBundleOut,
    BlockerDetectionReportOut,
    EscalationBundleOut,
    OverridePolicyOut,
    RecomputeSummaryOut,
    RevenuePressureReportOut,
)
from apps.api.services import autonomous_phase_d_service as svc
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")


@router.get("/{brand_id}/agent-runs", response_model=AgentOrchestrationBundleOut)
async def list_agent_runs(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_agent_runs(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{brand_id}/agent-runs/recompute", response_model=RecomputeSummaryOut)
async def recompute_agent_runs(
    brand_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_agent_orchestration(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Agent orchestration — {result.get('agent_runs_created', 0)} runs, {result.get('messages_created', 0)} messages",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{brand_id}/revenue-pressure", response_model=list[RevenuePressureReportOut])
async def list_revenue_pressure(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(10, ge=1, le=50),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_revenue_pressure(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{brand_id}/revenue-pressure/recompute", response_model=RecomputeSummaryOut)
async def recompute_revenue_pressure(
    brand_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_revenue_pressure(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Revenue pressure — {result.get('pressure_reports_created', 0)} report(s)",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{brand_id}/override-policies", response_model=list[OverridePolicyOut])
async def list_override_policies(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_override_policies(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{brand_id}/override-policies/recompute", response_model=RecomputeSummaryOut)
async def recompute_override_policies(
    brand_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_override_policies(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Override policies — {result.get('override_policies_created', 0)} policies",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{brand_id}/blocker-detection", response_model=list[BlockerDetectionReportOut])
async def list_blocker_detection(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_blocker_detection(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{brand_id}/blocker-detection/recompute", response_model=RecomputeSummaryOut)
async def recompute_blocker_detection(
    brand_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_blocker_detection(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Blocker detection — {result.get('blockers_created', 0)} blockers",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{brand_id}/operator-escalations", response_model=EscalationBundleOut)
async def list_operator_escalations(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    try:
        escalations = await svc.list_escalations(db, brand_id, limit=limit)
        commands = await svc.list_operator_commands(db, brand_id, limit=limit)
        return {"escalations": escalations, "commands": commands}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
