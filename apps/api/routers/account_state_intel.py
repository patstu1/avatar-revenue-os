"""Account-State Intelligence API."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.account_state_intel import (
    AccountStateReportOut, AccountStateTransitionOut, AccountStateActionOut, RecomputeSummaryOut,
)
from apps.api.services import account_state_intel_service as svc
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")


@router.get("/{brand_id}/account-state", response_model=list[AccountStateReportOut])
async def list_reports(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_reports(db, brand_id)


@router.post("/{brand_id}/account-state/recompute", response_model=RecomputeSummaryOut)
async def recompute(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await svc.recompute_account_states(db, brand_id)
    await db.commit()
    return RecomputeSummaryOut(rows_processed=result["rows_processed"], status=result["status"])


@router.get("/{brand_id}/account-state/transitions", response_model=list[AccountStateTransitionOut])
async def list_transitions(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_transitions(db, brand_id)


@router.get("/{brand_id}/account-state/actions", response_model=list[AccountStateActionOut])
async def list_actions(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_actions(db, brand_id)
