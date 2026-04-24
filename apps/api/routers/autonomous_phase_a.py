"""Autonomous execution Phase A — signal scanning, auto-queue, warmup & output."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.autonomous_phase_a import (
    AccountMaturityReportOut,
    AccountOutputReportOut,
    AccountWarmupPlanOut,
    AutoQueueItemOut,
    NormalizedSignalEventOut,
    PlatformWarmupPolicyOut,
    RecomputeSummaryOut,
    SignalScanRunOut,
)
from apps.api.services import autonomous_phase_a_service as svc
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")


@router.get(
    "/{brand_id}/signal-scans",
    response_model=list[SignalScanRunOut],
)
async def list_signal_scans(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_signal_scans(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/{brand_id}/signal-scans/recompute",
    response_model=RecomputeSummaryOut,
)
async def recompute_signal_scans(
    brand_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.run_signal_scan(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Signal scan completed — {result.get('signals_actionable', 0)} actionable signals",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/{brand_id}/auto-queue",
    response_model=list[AutoQueueItemOut],
)
async def list_auto_queue(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_auto_queue(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/{brand_id}/auto-queue/rebuild",
    response_model=RecomputeSummaryOut,
)
async def rebuild_auto_queue(
    brand_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.rebuild_auto_queue(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Queue rebuilt — {result.get('queue_items_created', 0)} items created",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/{brand_id}/account-warmup",
    response_model=list[AccountWarmupPlanOut],
)
async def list_account_warmup(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_account_warmup(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/{brand_id}/account-warmup/recompute",
    response_model=RecomputeSummaryOut,
)
async def recompute_warmup(
    brand_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_warmup(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Warmup plans recomputed — {result.get('warmup_plans_created', 0)} plans",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/{brand_id}/account-output",
    response_model=list[AccountOutputReportOut],
)
async def list_account_output(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_account_output(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/{brand_id}/account-output/recompute",
    response_model=RecomputeSummaryOut,
)
async def recompute_account_output(
    brand_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_account_output(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Output recomputed — {result.get('output_reports_created', 0)} reports, {result.get('ramp_events_created', 0)} ramp events",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/{brand_id}/account-maturity",
    response_model=list[AccountMaturityReportOut],
)
async def list_account_maturity(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_account_maturity(db, brand_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/{brand_id}/signal-events",
    response_model=list[NormalizedSignalEventOut],
)
async def list_signal_events(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(100, ge=1, le=500),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_signal_events(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/{brand_id}/platform-warmup-policies",
    response_model=list[PlatformWarmupPolicyOut],
)
async def list_platform_warmup_policies(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_platform_warmup_policies(db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
