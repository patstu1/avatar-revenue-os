"""Revenue Ceiling Phase C — recurring revenue, sponsor inventory, trust, monetization mix, paid promotion."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.revenue_ceiling_phase_c import (
    MonetizationMixReportOut,
    PaidPromotionCandidateOut,
    RecurringRevenueModelOut,
    SponsorInventoryItemOut,
    SponsorPackageRecommendationOut,
    TrustConversionReportOut,
)
from apps.api.services import revenue_ceiling_phase_c_service as rcc
from apps.api.services.audit_service import log_action
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, user, db: DBSession) -> Brand:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")
    return brand


# ---------------------------------------------------------------------------
# Recurring Revenue
# ---------------------------------------------------------------------------

@router.get("/{brand_id}/recurring-revenue", response_model=list[RecurringRevenueModelOut])
async def list_recurring_revenue(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rcc.get_recurring_revenue(db, brand_id)


@router.post("/{brand_id}/recurring-revenue/recompute")
async def recompute_recurring_revenue(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await rcc.recompute_recurring_revenue(db, brand_id)
    await log_action(
        db,
        "revenue_ceiling_c.recurring_revenue_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="recurring_revenue_model",
        details=result,
    )
    return result


# ---------------------------------------------------------------------------
# Sponsor Inventory
# ---------------------------------------------------------------------------

@router.get("/{brand_id}/sponsor-inventory", response_model=list[SponsorInventoryItemOut])
async def list_sponsor_inventory(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rcc.get_sponsor_inventory(db, brand_id)


@router.post("/{brand_id}/sponsor-inventory/recompute")
async def recompute_sponsor_inventory(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await rcc.recompute_sponsor_inventory(db, brand_id)
    await log_action(
        db,
        "revenue_ceiling_c.sponsor_inventory_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="sponsor_inventory",
        details=result,
    )
    return result


# ---------------------------------------------------------------------------
# Sponsor Package Recommendations
# ---------------------------------------------------------------------------

@router.get(
    "/{brand_id}/sponsor-package-recommendations",
    response_model=list[SponsorPackageRecommendationOut],
)
async def list_sponsor_package_recommendations(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession
):
    await _require_brand(brand_id, current_user, db)
    return await rcc.get_sponsor_package_recommendations(db, brand_id)


# ---------------------------------------------------------------------------
# Paid Promotion Candidates
# ---------------------------------------------------------------------------

@router.get("/{brand_id}/paid-promotion-candidates", response_model=list[PaidPromotionCandidateOut])
async def list_paid_promotion_candidates(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession
):
    await _require_brand(brand_id, current_user, db)
    return await rcc.get_paid_promotion_candidates(db, brand_id)


@router.post("/{brand_id}/paid-promotion-candidates/recompute")
async def recompute_paid_promotion_candidates(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await rcc.recompute_paid_promotion_candidates(db, brand_id)
    await log_action(
        db,
        "revenue_ceiling_c.paid_promotion_candidates_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="paid_promotion_candidate",
        details=result,
    )
    return result


# ---------------------------------------------------------------------------
# Trust Conversion
# ---------------------------------------------------------------------------

@router.get("/{brand_id}/trust-conversion", response_model=list[TrustConversionReportOut])
async def list_trust_conversion(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rcc.get_trust_conversion(db, brand_id)


@router.post("/{brand_id}/trust-conversion/recompute")
async def recompute_trust_conversion(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await rcc.recompute_trust_conversion(db, brand_id)
    await log_action(
        db,
        "revenue_ceiling_c.trust_conversion_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="trust_conversion_report",
        details=result,
    )
    return result


# ---------------------------------------------------------------------------
# Monetization Mix
# ---------------------------------------------------------------------------

@router.get("/{brand_id}/monetization-mix", response_model=list[MonetizationMixReportOut])
async def list_monetization_mix(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rcc.get_monetization_mix(db, brand_id)


@router.post("/{brand_id}/monetization-mix/recompute")
async def recompute_monetization_mix(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await rcc.recompute_monetization_mix(db, brand_id)
    await log_action(
        db,
        "revenue_ceiling_c.monetization_mix_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="monetization_mix_report",
        details=result,
    )
    return result
