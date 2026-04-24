"""Revenue Ceiling Phase B — high-ticket, productization, revenue density, upsell."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.revenue_ceiling_phase_b import (
    HighTicketOpportunityOut,
    ProductOpportunityOut,
    RevenueDensityReportOut,
    UpsellRecommendationOut,
)
from apps.api.services import revenue_ceiling_phase_b_service as rcb
from apps.api.services.audit_service import log_action
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, user, db: DBSession) -> Brand:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")
    return brand


@router.get("/{brand_id}/high-ticket-opportunities", response_model=list[HighTicketOpportunityOut])
async def list_high_ticket_opportunities(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rcb.get_high_ticket_opportunities(db, brand_id)


@router.post("/{brand_id}/high-ticket-opportunities/recompute")
async def recompute_high_ticket_opportunities(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await rcb.recompute_high_ticket_opportunities(db, brand_id)
    await log_action(
        db,
        "revenue_ceiling_b.high_ticket_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="high_ticket_opportunity",
        details=result,
    )
    return result


@router.get("/{brand_id}/product-opportunities", response_model=list[ProductOpportunityOut])
async def list_product_opportunities(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rcb.get_product_opportunities(db, brand_id)


@router.post("/{brand_id}/product-opportunities/recompute")
async def recompute_product_opportunities(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await rcb.recompute_product_opportunities(db, brand_id)
    await log_action(
        db,
        "revenue_ceiling_b.product_opportunities_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="product_opportunity",
        details=result,
    )
    return result


@router.get("/{brand_id}/revenue-density", response_model=list[RevenueDensityReportOut])
async def list_revenue_density(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rcb.get_revenue_density(db, brand_id)


@router.post("/{brand_id}/revenue-density/recompute")
async def recompute_revenue_density(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await rcb.recompute_revenue_density(db, brand_id)
    await log_action(
        db,
        "revenue_ceiling_b.revenue_density_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="revenue_density_report",
        details=result,
    )
    return result


@router.get("/{brand_id}/upsell-recommendations", response_model=list[UpsellRecommendationOut])
async def list_upsell_recommendations(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rcb.get_upsell_recommendations(db, brand_id)


@router.post("/{brand_id}/upsell-recommendations/recompute")
async def recompute_upsell_recommendations(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await rcb.recompute_upsell_recommendations(db, brand_id)
    await log_action(
        db,
        "revenue_ceiling_b.upsell_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="upsell_recommendation",
        details=result,
    )
    return result
