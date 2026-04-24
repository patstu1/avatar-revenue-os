"""Onboarding API — Quick-start endpoints for new users."""

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from apps.api.deps import CurrentUser, DBSession
from apps.api.services import onboarding_service

router = APIRouter()


class QuickBrandCreate(BaseModel):
    name: str
    niche: str
    target_audience: str = ""


class QuickOfferCreate(BaseModel):
    brand_id: uuid.UUID
    name: str
    monetization_method: str
    offer_url: str = ""
    payout_amount: float = 0.0


@router.post("/quick-brand", status_code=status.HTTP_201_CREATED)
async def quick_create_brand(
    body: QuickBrandCreate,
    current_user: CurrentUser,
    db: DBSession,
):
    """Quick brand creation for onboarding — minimal fields."""
    try:
        brand = await onboarding_service.quick_create_brand(
            db,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            name=body.name,
            niche=body.niche,
            target_audience=body.target_audience,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "id": str(brand.id),
        "name": brand.name,
        "slug": brand.slug,
        "niche": brand.niche,
    }


@router.post("/quick-offer", status_code=status.HTTP_201_CREATED)
async def quick_create_offer(
    body: QuickOfferCreate,
    current_user: CurrentUser,
    db: DBSession,
):
    """Quick offer creation for onboarding."""
    try:
        offer = await onboarding_service.quick_create_offer(
            db,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            brand_id=body.brand_id,
            name=body.name,
            monetization_method=body.monetization_method,
            offer_url=body.offer_url,
            payout_amount=body.payout_amount,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "id": str(offer.id),
        "name": offer.name,
        "monetization_method": offer.monetization_method.value,
    }


@router.post("/quick-generate/{brand_id}")
async def quick_generate_content(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Generate first content piece using free credits — the aha moment."""
    try:
        result = await onboarding_service.quick_generate(
            db,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            brand_id=brand_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


@router.get("/status")
async def onboarding_status(
    current_user: CurrentUser,
    db: DBSession,
):
    """Check onboarding completion status."""
    return await onboarding_service.get_onboarding_status(
        db,
        organization_id=current_user.organization_id,
    )
