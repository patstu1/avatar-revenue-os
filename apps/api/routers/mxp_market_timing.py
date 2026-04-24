"""MXP Market Timing — timing reports and macro signal analysis."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.mxp_market_timing import MacroSignalEventOut, MarketTimingReportOut
from apps.api.services import market_timing_service as svc
from apps.api.services.audit_service import log_action
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")


@router.get(
    "/{brand_id}/market-timing",
    response_model=list[MarketTimingReportOut],
)
async def list_reports(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.get_market_timing_reports(db, brand_id)


@router.get(
    "/{brand_id}/macro-signal-events",
    response_model=list[MacroSignalEventOut],
)
async def list_macro_signal_events(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.get_macro_signal_events(db, brand_id)


@router.post(
    "/{brand_id}/market-timing/recompute",
    response_model=dict,
)
async def recompute_reports(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await svc.recompute_market_timing(db, brand_id)
    await log_action(
        db,
        "mxp.market_timing_reports_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="market_timing_report",
        details=result,
    )
    return result
