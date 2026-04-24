"""Brain Architecture Phase A — memory, account/opportunity/execution/audience state APIs."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.brain_phase_a import (
    AccountStateSnapshotOut,
    AudienceStateSnapshotV2Out,
    BrainMemoryBundleOut,
    ExecutionStateSnapshotOut,
    OpportunityStateSnapshotOut,
    RecomputeSummaryOut,
)
from apps.api.services import brain_phase_a_service as svc
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")


# ── Brain Memory ──────────────────────────────────────────────────────

@router.get("/{brand_id}/brain-memory", response_model=BrainMemoryBundleOut)
async def list_brain_memory(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(100, ge=1, le=500),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_brain_memory(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{brand_id}/brain-memory/recompute", response_model=RecomputeSummaryOut)
async def recompute_brain_memory(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_brain_memory(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Brain memory — {result.get('entries_created', 0)} entries, {result.get('links_created', 0)} links",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ── Account State ─────────────────────────────────────────────────────

@router.get("/{brand_id}/account-states", response_model=list[AccountStateSnapshotOut])
async def list_account_states(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(100, ge=1, le=500),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_account_states(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{brand_id}/account-states/recompute", response_model=RecomputeSummaryOut)
async def recompute_account_states(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_account_states(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Account states — {result.get('account_states_created', 0)} snapshots",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ── Opportunity State ─────────────────────────────────────────────────

@router.get("/{brand_id}/opportunity-states", response_model=list[OpportunityStateSnapshotOut])
async def list_opportunity_states(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(100, ge=1, le=500),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_opportunity_states(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{brand_id}/opportunity-states/recompute", response_model=RecomputeSummaryOut)
async def recompute_opportunity_states(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_opportunity_states(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Opportunity states — {result.get('opportunity_states_created', 0)} snapshots",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ── Execution State ───────────────────────────────────────────────────

@router.get("/{brand_id}/execution-states", response_model=list[ExecutionStateSnapshotOut])
async def list_execution_states(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(100, ge=1, le=500),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_execution_states(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{brand_id}/execution-states/recompute", response_model=RecomputeSummaryOut)
async def recompute_execution_states(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_execution_states(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Execution states — {result.get('execution_states_created', 0)} snapshots",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ── Audience State V2 ────────────────────────────────────────────────

@router.get("/{brand_id}/audience-states-v2", response_model=list[AudienceStateSnapshotV2Out])
async def list_audience_states_v2(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(100, ge=1, le=500),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_audience_states_v2(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{brand_id}/audience-states-v2/recompute", response_model=RecomputeSummaryOut)
async def recompute_audience_states_v2(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_audience_states_v2(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Audience states V2 — {result.get('audience_states_created', 0)} snapshots",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
