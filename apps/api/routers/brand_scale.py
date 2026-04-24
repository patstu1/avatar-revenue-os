"""Phase 5: scale recommendations & portfolio allocations under /brands/{id}/…"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.scale import PortfolioAllocationResponse, ScaleRecommendationResponse
from apps.api.services import scale_service as ss
from apps.api.services.audit_service import log_action
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, user, db: DBSession) -> Brand:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")
    return brand


@router.get("/{brand_id}/scale-recommendations", response_model=list[ScaleRecommendationResponse])
async def list_scale_recommendations(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    rows = await ss.get_scale_recommendations(db, brand_id)
    return rows


@router.post("/{brand_id}/scale-recommendations/recompute", response_model=list[ScaleRecommendationResponse])
async def recompute_scale_recommendations(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    rows = await ss.recompute_scale_recommendations(db, brand_id, user_id=current_user.id, sync_metrics=True)
    await log_action(
        db,
        "scale.recommendations_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="scale_recommendation",
        details={"count": len(rows)},
    )
    return rows


@router.get("/{brand_id}/portfolio-allocations", response_model=list[PortfolioAllocationResponse])
async def list_portfolio_allocations(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    rows = await ss.get_portfolio_allocations(db, brand_id)
    return rows


@router.post("/{brand_id}/portfolio-allocations/recompute", response_model=list[PortfolioAllocationResponse])
async def recompute_portfolio_allocations(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    rows, _pid = await ss.recompute_portfolio_allocations(db, brand_id)
    await log_action(
        db,
        "portfolio.allocations_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="portfolio_allocation",
        details={"count": len(rows)},
    )
    return rows
