"""Winning-Pattern Memory API."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.pattern_memory import (
    LosingPatternOut,
    PatternClusterOut,
    PatternDecayOut,
    PatternReuseOut,
    RecomputeSummaryOut,
    WinningPatternOut,
)
from apps.api.services import pattern_memory_service as svc
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")


@router.get(
    "/{brand_id}/pattern-memory",
    response_model=list[WinningPatternOut],
)
async def list_patterns(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_patterns(db, brand_id)


@router.post(
    "/{brand_id}/pattern-memory/recompute",
    response_model=RecomputeSummaryOut,
)
async def recompute_patterns(
    brand_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    result = await svc.recompute_patterns(db, brand_id)
    return RecomputeSummaryOut(
        rows_processed=int(result.get("rows_processed", 0)),
        status=str(result.get("status", "completed")),
    )


@router.get(
    "/{brand_id}/pattern-clusters",
    response_model=list[PatternClusterOut],
)
async def list_clusters(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_clusters(db, brand_id)


@router.get(
    "/{brand_id}/losing-patterns",
    response_model=list[LosingPatternOut],
)
async def list_losers(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_losers(db, brand_id)


@router.get(
    "/{brand_id}/pattern-reuse",
    response_model=list[PatternReuseOut],
)
async def list_reuse(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_reuse(db, brand_id)


@router.get(
    "/{brand_id}/pattern-decay",
    response_model=list[PatternDecayOut],
)
async def list_decay(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_decay(db, brand_id)


@router.get("/{brand_id}/pattern-experiment-suggestions")
async def experiment_suggestions(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.get_experiment_suggestions(db, brand_id)


@router.get("/{brand_id}/pattern-allocation-weights")
async def allocation_weights(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession, total_budget: float = 1000.0):
    await _require_brand(brand_id, current_user, db)
    return await svc.get_allocation_weights(db, brand_id, total_budget)
