"""Expansion Pack 2 Phase A — lead opportunities, closer actions, owned offer recommendations."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.expansion_pack2_phase_a import (
    CloserActionOut,
    LeadOpportunityOut,
    LeadQualificationReportOut,
    OwnedOfferRecommendationOut,
)
from apps.api.services import expansion_pack2_phase_a_service as ep2a
from apps.api.services.audit_service import log_action
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, user, db: DBSession) -> Brand:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")
    return brand


# ---------------------------------------------------------------------------
# Lead Opportunities
# ---------------------------------------------------------------------------


@router.get("/{brand_id}/lead-opportunities", response_model=list[LeadOpportunityOut])
async def list_lead_opportunities(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession
):
    await _require_brand(brand_id, current_user, db)
    return await ep2a.get_lead_opportunities(db, brand_id)


# ---------------------------------------------------------------------------
# Closer Actions
# ---------------------------------------------------------------------------


@router.get(
    "/{brand_id}/lead-opportunities/closer-actions",
    response_model=list[CloserActionOut],
)
async def list_closer_actions(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession
):
    await _require_brand(brand_id, current_user, db)
    return await ep2a.get_closer_actions(db, brand_id)


# ---------------------------------------------------------------------------
# Lead Qualification Report
# ---------------------------------------------------------------------------


@router.get("/{brand_id}/lead-qualification", response_model=list[LeadQualificationReportOut])
async def list_lead_qualification(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession
):
    await _require_brand(brand_id, current_user, db)
    return await ep2a.get_lead_qualification_report(db, brand_id)


@router.post("/{brand_id}/lead-qualification/recompute")
async def recompute_lead_qualification(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await ep2a.recompute_lead_qualification(db, brand_id)
    await log_action(
        db,
        "ep2a.lead_qualification_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="lead_qualification_report",
        details=result,
    )
    return result


# ---------------------------------------------------------------------------
# Owned Offer Recommendations
# ---------------------------------------------------------------------------


@router.get(
    "/{brand_id}/owned-offer-recommendations",
    response_model=list[OwnedOfferRecommendationOut],
)
async def list_owned_offer_recommendations(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession
):
    await _require_brand(brand_id, current_user, db)
    return await ep2a.get_owned_offer_recommendations(db, brand_id)


@router.post("/{brand_id}/owned-offer-recommendations/recompute")
async def recompute_owned_offer_recommendations(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await ep2a.recompute_owned_offer_recommendations(db, brand_id)
    await log_action(
        db,
        "ep2a.owned_offer_recommendations_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="owned_offer_recommendation",
        details=result,
    )
    return result
