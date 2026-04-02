"""Expansion Pack 2 Phase B — pricing, bundling, retention, reactivation endpoints."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.expansion_pack2_phase_b import (
    PricingRecommendationOut,
    BundleRecommendationOut,
    RetentionRecommendationOut,
    ReactivationCampaignOut,
)
from apps.api.services import expansion_pack2_phase_b_service as ep2b
from apps.api.services.audit_service import log_action
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")


# ---------------------------------------------------------------------------
# Pricing Recommendations
# ---------------------------------------------------------------------------


@router.get(
    "/{brand_id}/pricing-recommendations",
    response_model=list[PricingRecommendationOut],
)
async def list_pricing_recommendations(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession
):
    await _require_brand(brand_id, current_user, db)
    return await ep2b.get_pricing_recommendations(db, brand_id)


@router.post(
    "/{brand_id}/pricing-recommendations/recompute",
    response_model=dict,
)
async def recompute_pricing_recommendations(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await ep2b.recompute_pricing_recommendations(db, brand_id)
    await log_action(
        db,
        "ep2b.pricing_recommendations_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="pricing_recommendation",
        details=result,
    )
    return result


# ---------------------------------------------------------------------------
# Bundle Recommendations
# ---------------------------------------------------------------------------


@router.get(
    "/{brand_id}/bundle-recommendations",
    response_model=list[BundleRecommendationOut],
)
async def list_bundle_recommendations(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession
):
    await _require_brand(brand_id, current_user, db)
    return await ep2b.get_bundle_recommendations(db, brand_id)


@router.post(
    "/{brand_id}/bundle-recommendations/recompute",
    response_model=dict,
)
async def recompute_bundle_recommendations(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await ep2b.recompute_bundle_recommendations(db, brand_id)
    await log_action(
        db,
        "ep2b.bundle_recommendations_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="bundle_recommendation",
        details=result,
    )
    return result


# ---------------------------------------------------------------------------
# Retention Recommendations
# ---------------------------------------------------------------------------


@router.get(
    "/{brand_id}/retention-recommendations",
    response_model=list[RetentionRecommendationOut],
)
async def list_retention_recommendations(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession
):
    await _require_brand(brand_id, current_user, db)
    return await ep2b.get_retention_recommendations(db, brand_id)


@router.post(
    "/{brand_id}/retention-recommendations/recompute",
    response_model=dict,
)
async def recompute_retention_recommendations(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await ep2b.recompute_retention_recommendations(db, brand_id)
    await log_action(
        db,
        "ep2b.retention_recommendations_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="retention_recommendation",
        details=result,
    )
    return result


# ---------------------------------------------------------------------------
# Reactivation Campaigns
# ---------------------------------------------------------------------------


@router.get(
    "/{brand_id}/reactivation-campaigns",
    response_model=list[ReactivationCampaignOut],
)
async def list_reactivation_campaigns(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession
):
    await _require_brand(brand_id, current_user, db)
    return await ep2b.get_reactivation_campaigns(db, brand_id)


@router.post(
    "/{brand_id}/reactivation-campaigns/recompute",
    response_model=dict,
)
async def recompute_reactivation_campaigns(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await ep2b.recompute_reactivation_campaigns(db, brand_id)
    await log_action(
        db,
        "ep2b.reactivation_campaigns_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="reactivation_campaign",
        details=result,
    )
    return result
