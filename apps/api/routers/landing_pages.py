"""Landing Page Engine API."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.landing_pages import LandingPageOut, LPQualityOut, LPVariantOut, RecomputeSummaryOut
from apps.api.services import landing_page_service as svc
from packages.db.models.core import Brand

router = APIRouter()


async def _rb(brand_id, current_user, db):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Brand not accessible")


@router.get("/{brand_id}/landing-pages", response_model=list[LandingPageOut])
async def list_pages(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db)
    return await svc.list_pages(db, brand_id)


@router.post("/{brand_id}/landing-pages/recompute", response_model=RecomputeSummaryOut)
async def recompute(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _rb(brand_id, current_user, db)
    result = await svc.recompute_landing_pages(db, brand_id)
    await db.commit()
    return RecomputeSummaryOut(**result)


@router.get("/{brand_id}/landing-page-variants", response_model=list[LPVariantOut])
async def list_variants(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db)
    return await svc.list_variants(db, brand_id)


@router.get("/{brand_id}/landing-page-quality", response_model=list[LPQualityOut])
async def list_quality(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db)
    return await svc.list_quality(db, brand_id)


@router.post("/{brand_id}/landing-pages/{page_id}/publish")
async def publish_page(
    brand_id: uuid.UUID,
    page_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
    publish_method: str = "manual",
    destination_url: str = "",
):
    await _rb(brand_id, current_user, db)
    result = await svc.publish_page(db, page_id, publish_method, destination_url)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("reason"))
    await db.commit()
    return result
