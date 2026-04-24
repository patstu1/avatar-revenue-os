"""MXP Offer Lifecycle — health tracking, state transitions, decay detection."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.mxp_offer_lifecycle import OfferLifecycleEventOut, OfferLifecycleReportOut
from apps.api.services import offer_lifecycle_service as svc
from apps.api.services.audit_service import log_action
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")


@router.get(
    "/{brand_id}/offer-lifecycle-reports",
    response_model=list[OfferLifecycleReportOut],
)
async def list_reports(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.get_offer_lifecycle_reports(db, brand_id)


@router.get(
    "/{brand_id}/offer-lifecycle-events",
    response_model=list[OfferLifecycleEventOut],
)
async def list_events(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.get_offer_lifecycle_events(db, brand_id)


@router.post(
    "/{brand_id}/offer-lifecycle-reports/recompute",
    response_model=dict,
)
async def recompute_reports(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await svc.recompute_offer_lifecycle(db, brand_id)
    await log_action(
        db,
        "mxp.offer_lifecycle_reports_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="offer_lifecycle_report",
        details=result,
    )
    return result
