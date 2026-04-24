"""Affiliate Intelligence API."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.affiliate_intel import (
    AffiliateBlockerOut,
    AffiliateLeakOut,
    AffiliateLinkOut,
    AffiliateOfferOut,
    RecomputeSummaryOut,
)
from apps.api.services import affiliate_intel_service as svc
from packages.db.models.core import Brand

router = APIRouter()


async def _rb(bid, cu, db):
    b = (await db.execute(select(Brand).where(Brand.id == bid))).scalar_one_or_none()
    if not b or b.organization_id != cu.organization_id:
        raise HTTPException(status_code=403, detail="Brand not accessible")


@router.get("/{brand_id}/affiliate-offers", response_model=list[AffiliateOfferOut])
async def list_offers(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db)
    return await svc.list_offers(db, brand_id)


@router.post("/{brand_id}/affiliate-offers/recompute", response_model=RecomputeSummaryOut)
async def recompute(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _rb(brand_id, current_user, db)
    r = await svc.recompute_ranking(db, brand_id)
    await db.commit()
    return RecomputeSummaryOut(**r)


@router.get("/{brand_id}/affiliate-links", response_model=list[AffiliateLinkOut])
async def list_links(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db)
    return await svc.list_links(db, brand_id)


@router.get("/{brand_id}/affiliate-leaks", response_model=list[AffiliateLeakOut])
async def list_leaks(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db)
    return await svc.list_leaks(db, brand_id)


@router.get("/{brand_id}/affiliate-blockers", response_model=list[AffiliateBlockerOut])
async def list_blockers(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db)
    return await svc.list_blockers(db, brand_id)


@router.get("/{brand_id}/affiliate-ranking")
async def ranking(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db)
    return await svc.get_best_offer_for_content(db, brand_id)


@router.get("/{brand_id}/affiliate-commissions")
async def commissions(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db)
    return await svc.list_commissions(db, brand_id)


@router.get("/{brand_id}/affiliate-payouts")
async def payouts(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db)
    return await svc.list_payouts(db, brand_id)


@router.post("/{brand_id}/affiliate-sync")
async def sync_networks(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    from apps.api.services.affiliate_sync_service import sync_network_data

    await _rb(brand_id, current_user, db)
    result = await sync_network_data(db, brand_id)
    await db.commit()
    return result
