"""API routers for Creator Revenue Avenues Phase A."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_current_user, get_db
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.creator_revenue import (
    AvenueExecutionTruthOut,
    CreatorRevenueBlockerOut,
    CreatorRevenueEventOut,
    CreatorRevenueOpportunityOut,
    DataProductActionOut,
    HubSummaryOut,
    LicensingActionOut,
    LiveEventActionOut,
    MerchActionOut,
    OwnedAffiliateProgramActionOut,
    PremiumAccessActionOut,
    RecomputeSummaryOut,
    ServiceConsultingActionOut,
    SyndicationActionOut,
    UgcServiceActionOut,
)
from apps.api.services import creator_revenue_service as svc

router = APIRouter()


@router.get("/{brand_id}/creator-revenue-opportunities", response_model=list[CreatorRevenueOpportunityOut])
async def get_opportunities(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    return await svc.list_opportunities(db, brand_id)


@router.post("/{brand_id}/creator-revenue-opportunities/recompute", response_model=RecomputeSummaryOut)
async def recompute_opportunities(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
    _rl=Depends(recompute_rate_limit),
):
    result = await svc.recompute_opportunities(db, brand_id)
    return RecomputeSummaryOut(**result)


@router.get("/{brand_id}/ugc-services", response_model=list[UgcServiceActionOut])
async def get_ugc_services(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    return await svc.list_ugc_services(db, brand_id)


@router.post("/{brand_id}/ugc-services/recompute", response_model=RecomputeSummaryOut)
async def recompute_ugc_services(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
    _rl=Depends(recompute_rate_limit),
):
    result = await svc.recompute_ugc_services(db, brand_id)
    return RecomputeSummaryOut(**result)


@router.get("/{brand_id}/service-consulting", response_model=list[ServiceConsultingActionOut])
async def get_service_consulting(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    return await svc.list_service_consulting(db, brand_id)


@router.post("/{brand_id}/service-consulting/recompute", response_model=RecomputeSummaryOut)
async def recompute_service_consulting(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
    _rl=Depends(recompute_rate_limit),
):
    result = await svc.recompute_service_consulting(db, brand_id)
    return RecomputeSummaryOut(**result)


@router.get("/{brand_id}/premium-access", response_model=list[PremiumAccessActionOut])
async def get_premium_access(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    return await svc.list_premium_access(db, brand_id)


@router.post("/{brand_id}/premium-access/recompute", response_model=RecomputeSummaryOut)
async def recompute_premium_access(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
    _rl=Depends(recompute_rate_limit),
):
    result = await svc.recompute_premium_access(db, brand_id)
    return RecomputeSummaryOut(**result)


@router.get("/{brand_id}/licensing", response_model=list[LicensingActionOut])
async def get_licensing(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    return await svc.list_licensing(db, brand_id)


@router.post("/{brand_id}/licensing/recompute", response_model=RecomputeSummaryOut)
async def recompute_licensing(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
    _rl=Depends(recompute_rate_limit),
):
    result = await svc.recompute_licensing(db, brand_id)
    return RecomputeSummaryOut(**result)


@router.get("/{brand_id}/syndication", response_model=list[SyndicationActionOut])
async def get_syndication(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    return await svc.list_syndication(db, brand_id)


@router.post("/{brand_id}/syndication/recompute", response_model=RecomputeSummaryOut)
async def recompute_syndication(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
    _rl=Depends(recompute_rate_limit),
):
    result = await svc.recompute_syndication(db, brand_id)
    return RecomputeSummaryOut(**result)


@router.get("/{brand_id}/data-products", response_model=list[DataProductActionOut])
async def get_data_products(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    return await svc.list_data_products(db, brand_id)


@router.post("/{brand_id}/data-products/recompute", response_model=RecomputeSummaryOut)
async def recompute_data_products(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
    _rl=Depends(recompute_rate_limit),
):
    result = await svc.recompute_data_products(db, brand_id)
    return RecomputeSummaryOut(**result)


@router.get("/{brand_id}/merch", response_model=list[MerchActionOut])
async def get_merch(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    return await svc.list_merch(db, brand_id)


@router.post("/{brand_id}/merch/recompute", response_model=RecomputeSummaryOut)
async def recompute_merch(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
    _rl=Depends(recompute_rate_limit),
):
    result = await svc.recompute_merch(db, brand_id)
    return RecomputeSummaryOut(**result)


@router.get("/{brand_id}/live-events", response_model=list[LiveEventActionOut])
async def get_live_events(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    return await svc.list_live_events(db, brand_id)


@router.post("/{brand_id}/live-events/recompute", response_model=RecomputeSummaryOut)
async def recompute_live_events(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
    _rl=Depends(recompute_rate_limit),
):
    result = await svc.recompute_live_events(db, brand_id)
    return RecomputeSummaryOut(**result)


@router.get("/{brand_id}/owned-affiliate-program", response_model=list[OwnedAffiliateProgramActionOut])
async def get_owned_affiliate_program(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    return await svc.list_owned_affiliate_program(db, brand_id)


@router.post("/{brand_id}/owned-affiliate-program/recompute", response_model=RecomputeSummaryOut)
async def recompute_owned_affiliate_program(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
    _rl=Depends(recompute_rate_limit),
):
    result = await svc.recompute_owned_affiliate_program(db, brand_id)
    return RecomputeSummaryOut(**result)


@router.get("/{brand_id}/creator-revenue-hub", response_model=HubSummaryOut)
async def get_hub(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    return await svc.get_hub(db, brand_id)


@router.post("/{brand_id}/creator-revenue-hub/recompute", response_model=RecomputeSummaryOut)
async def recompute_hub(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
    _rl=Depends(recompute_rate_limit),
):
    result = await svc.recompute_hub(db, brand_id)
    return RecomputeSummaryOut(**result)


@router.get("/{brand_id}/creator-revenue-truth", response_model=list[AvenueExecutionTruthOut])
async def get_truth(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    return await svc.list_truth(db, brand_id)


@router.get("/{brand_id}/creator-revenue-blockers", response_model=list[CreatorRevenueBlockerOut])
async def get_blockers(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    return await svc.list_blockers(db, brand_id)


@router.post("/{brand_id}/creator-revenue-blockers/recompute", response_model=RecomputeSummaryOut)
async def recompute_blockers(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
    _rl=Depends(recompute_rate_limit),
):
    result = await svc.recompute_blockers(db, brand_id)
    return RecomputeSummaryOut(**result)


@router.get("/{brand_id}/creator-revenue-events", response_model=list[CreatorRevenueEventOut])
async def get_events(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    return await svc.list_events(db, brand_id)
