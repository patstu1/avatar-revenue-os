"""MXP Kill Ledger — kill entries, hindsight reviews, and recompute."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.mxp_kill_ledger import KillHindsightReviewOut, KillLedgerBundleOut, KillLedgerEntryOut
from apps.api.services import kill_ledger_service as svc
from apps.api.services.audit_service import log_action
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")


@router.get(
    "/{brand_id}/kill-ledger",
    response_model=KillLedgerBundleOut,
)
async def get_kill_ledger_bundle(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.get_kill_ledger_bundle(db, brand_id)


@router.post(
    "/{brand_id}/kill-ledger/recompute",
    response_model=dict,
)
async def recompute_kill_ledger_full(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await svc.recompute_kill_ledger_full(db, brand_id)
    await log_action(
        db,
        "mxp.kill_ledger_full_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="kill_ledger_entry",
        details=result,
    )
    return result


@router.get(
    "/{brand_id}/kill-ledger-entries",
    response_model=list[KillLedgerEntryOut],
    include_in_schema=False,
)
async def list_entries_legacy(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.get_kill_ledger(db, brand_id)


@router.get(
    "/{brand_id}/kill-hindsight-reviews",
    response_model=list[KillHindsightReviewOut],
)
async def list_reviews(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.get_kill_hindsight_reviews(db, brand_id)


@router.post(
    "/{brand_id}/kill-ledger-entries/recompute",
    response_model=dict,
    include_in_schema=False,
)
async def recompute_entries_legacy(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    return await recompute_kill_ledger_full(brand_id, current_user, db, _rl)


@router.post(
    "/{brand_id}/kill-hindsight-reviews/recompute",
    response_model=dict,
)
async def recompute_hindsight_only(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await svc.recompute_kill_hindsight(db, brand_id)
    await log_action(
        db,
        "mxp.kill_hindsight_reviews_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="kill_hindsight_review",
        details=result,
    )
    return result
