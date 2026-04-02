"""Autonomous execution Phase C — funnel, paid operator, sponsor, retention, recovery."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.autonomous_phase_c import (
    AdvanceStatusIn,
    AdvanceStatusOut,
    BatchExecuteOut,
    FunnelExecutionRunOut,
    OperatorNotifyOut,
    PaidOperatorBundleOut,
    PaidPerformanceIn,
    PaidPerformanceOut,
    RecoveryAutonomyBundleOut,
    RecomputeSummaryOut,
    RetentionAutomationActionOut,
    SponsorAutonomousActionOut,
)
from apps.api.services import autonomous_phase_c_service as svc
from apps.api.services import autonomous_phase_c_lifecycle as lifecycle
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")


@router.get("/{brand_id}/funnel-execution", response_model=list[FunnelExecutionRunOut])
async def list_funnel_execution(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_funnel_execution(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{brand_id}/funnel-execution/recompute", response_model=RecomputeSummaryOut)
async def recompute_funnel_execution(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_funnel_execution(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Funnel execution — {result.get('funnel_runs_created', 0)} runs",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{brand_id}/paid-operator", response_model=PaidOperatorBundleOut)
async def list_paid_operator(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_paid_operator(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{brand_id}/paid-operator/recompute", response_model=RecomputeSummaryOut)
async def recompute_paid_operator(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_paid_operator(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=(
                f"Paid operator — {result.get('paid_runs_created', 0)} runs, "
                f"{result.get('decisions_created', 0)} decisions"
            ),
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{brand_id}/sponsor-autonomy", response_model=list[SponsorAutonomousActionOut])
async def list_sponsor_autonomy(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_sponsor_autonomy(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{brand_id}/sponsor-autonomy/recompute", response_model=RecomputeSummaryOut)
async def recompute_sponsor_autonomy(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_sponsor_autonomy(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Sponsor autonomy — {result.get('sponsor_actions_created', 0)} actions",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{brand_id}/retention-autonomy", response_model=list[RetentionAutomationActionOut])
async def list_retention_autonomy(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_retention_autonomy(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{brand_id}/retention-autonomy/recompute", response_model=RecomputeSummaryOut)
async def recompute_retention_autonomy(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_retention_autonomy(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Retention — {result.get('retention_actions_created', 0)} actions",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{brand_id}/recovery-autonomy", response_model=RecoveryAutonomyBundleOut)
async def list_recovery_autonomy(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_recovery_autonomy(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{brand_id}/recovery-autonomy/recompute", response_model=RecomputeSummaryOut)
async def recompute_recovery_autonomy(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_recovery_autonomy(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=(
                f"Recovery — {result.get('escalations_created', 0)} escalations, "
                f"{result.get('self_healing_created', 0)} self-healing actions"
            ),
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Lifecycle PATCH — advance execution_status for any Phase C module
# ---------------------------------------------------------------------------

@router.patch(
    "/{brand_id}/phase-c/{module}/{record_id}/status",
    response_model=AdvanceStatusOut,
)
async def advance_action_status(
    brand_id: uuid.UUID,
    module: str,
    record_id: uuid.UUID,
    body: AdvanceStatusIn,
    current_user: OperatorUser,
    db: DBSession,
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await lifecycle.advance_execution_status(
            db, module, record_id, body.target_status, body.operator_notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Paid performance ingestion — replace synthetic with real ad metrics
# ---------------------------------------------------------------------------

@router.post(
    "/{brand_id}/paid-operator/{run_id}/performance",
    response_model=PaidPerformanceOut,
)
async def ingest_paid_performance(
    brand_id: uuid.UUID,
    run_id: uuid.UUID,
    body: PaidPerformanceIn,
    current_user: OperatorUser,
    db: DBSession,
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await lifecycle.ingest_paid_performance(
            db, run_id, body.dict(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Batch execute all approved actions for a brand
# ---------------------------------------------------------------------------

@router.post(
    "/{brand_id}/phase-c/execute-approved",
    response_model=BatchExecuteOut,
)
async def batch_execute_approved(
    brand_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await lifecycle.execute_approved_actions(db, brand_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Operator notification — collect and dispatch review items
# ---------------------------------------------------------------------------

@router.post(
    "/{brand_id}/phase-c/notify-operator",
    response_model=OperatorNotifyOut,
)
async def notify_operator(
    brand_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await lifecycle.notify_operator_review_items(db, brand_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
