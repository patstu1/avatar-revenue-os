"""MXP Deal Desk — strategy recommendations for deals."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.mxp_deal_desk import DealDeskRecommendationOut
from apps.api.services import deal_desk_service as svc
from apps.api.services.audit_service import log_action
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")


@router.get(
    "/{brand_id}/deal-desk",
    response_model=list[DealDeskRecommendationOut],
)
async def list_deal_desk(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.get_deal_desk_recommendations(db, brand_id)


@router.post(
    "/{brand_id}/deal-desk/recompute",
    response_model=dict,
)
async def recompute_deal_desk(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await svc.recompute_deal_desk(db, brand_id)
    await log_action(
        db,
        "mxp.deal_desk_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="deal_desk_recommendation",
        details=result,
    )
    return result


# Backward-compatible aliases
@router.get(
    "/{brand_id}/deal-desk-recommendations",
    response_model=list[DealDeskRecommendationOut],
    include_in_schema=False,
)
async def list_deal_desk_legacy(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    return await list_deal_desk(brand_id, current_user, db)


@router.post(
    "/{brand_id}/deal-desk-recommendations/recompute",
    response_model=dict,
    include_in_schema=False,
)
async def recompute_deal_desk_legacy(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    return await recompute_deal_desk(brand_id, current_user, db, _rl)
