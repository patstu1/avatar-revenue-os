"""Revenue ceiling endpoints: offer stacks, funnel paths, owned audience,
productization, monetization density.

POST recompute writes. All GETs are read-only.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.revenue_intel import MonetizationRecRow
from apps.api.services import revenue_service as rsvc
from apps.api.services.audit_service import log_action
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, user, db: DBSession) -> Brand:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")
    return brand


@router.post("/{brand_id}/revenue-intel/recompute")
async def recompute_revenue_intel(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await rsvc.recompute_revenue_intel(db, brand_id, user_id=current_user.id)
    await log_action(
        db,
        "revenue_intel.recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="revenue_intel",
        details=result,
    )
    return result


@router.get("/{brand_id}/offer-stacks", response_model=list[MonetizationRecRow])
async def list_offer_stacks(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rsvc.get_offer_stacks(db, brand_id)


@router.get("/{brand_id}/funnel-paths", response_model=list[MonetizationRecRow])
async def list_funnel_paths(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rsvc.get_funnel_paths(db, brand_id)


@router.get("/{brand_id}/owned-audience-value", response_model=list[MonetizationRecRow])
async def list_owned_audience(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rsvc.get_owned_audience_value(db, brand_id)


@router.get("/{brand_id}/productization", response_model=list[MonetizationRecRow])
async def list_productization(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rsvc.get_productization(db, brand_id)


@router.get("/{brand_id}/monetization-density", response_model=list[MonetizationRecRow])
async def list_density(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rsvc.get_monetization_density(db, brand_id)
