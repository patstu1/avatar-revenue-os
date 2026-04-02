"""Offer Lab API."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.offer_lab import OLOfferOut, OLVariantOut, OLBundleOut, OLBlockerOut, OLLearningOut, RecomputeSummaryOut
from apps.api.services import offer_lab_service as svc
from packages.db.models.core import Brand

router = APIRouter()

async def _rb(bid, cu, db):
    b = (await db.execute(select(Brand).where(Brand.id == bid))).scalar_one_or_none()
    if not b or b.organization_id != cu.organization_id: raise HTTPException(status_code=404, detail="Brand not found")

@router.get("/{brand_id}/offer-lab/offers", response_model=list[OLOfferOut])
async def offers(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_offers(db, brand_id)

@router.post("/{brand_id}/offer-lab/offers/recompute", response_model=RecomputeSummaryOut)
async def recompute(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _rb(brand_id, current_user, db); r = await svc.recompute_offer_lab(db, brand_id); await db.commit(); return RecomputeSummaryOut(**r)

@router.get("/{brand_id}/offer-lab/variants", response_model=list[OLVariantOut])
async def variants(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_variants(db, brand_id)

@router.get("/{brand_id}/offer-lab/bundles", response_model=list[OLBundleOut])
async def bundles(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_bundles(db, brand_id)

@router.get("/{brand_id}/offer-lab/blockers", response_model=list[OLBlockerOut])
async def blockers(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_blockers(db, brand_id)

@router.get("/{brand_id}/offer-lab/learning", response_model=list[OLLearningOut])
async def learning(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_learning(db, brand_id)
