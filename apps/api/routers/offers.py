"""Offer catalog endpoints."""
import uuid

from fastapi import APIRouter, HTTPException, Query, status

from apps.api.deps import CurrentUser, DBSession
from apps.api.schemas.core import OfferCreate, OfferResponse
from apps.api.services.audit_service import log_action
from apps.api.services.crud_service import CRUDService
from packages.db.models.core import Brand
from packages.db.models.offers import Offer

router = APIRouter()
offer_service = CRUDService(Offer)
brand_service = CRUDService(Brand)


@router.post("/", response_model=OfferResponse, status_code=status.HTTP_201_CREATED)
async def create_offer(body: OfferCreate, current_user: CurrentUser, db: DBSession):
    brand = await brand_service.get(db, body.brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    offer = await offer_service.create(db, **body.model_dump())
    await log_action(db, "offer.created", brand_id=body.brand_id, user_id=current_user.id, actor_type="human", entity_type="offer", entity_id=offer.id)
    return offer


@router.get("/", response_model=list[OfferResponse])
async def list_offers(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession, page: int = Query(1, ge=1)):
    brand = await brand_service.get(db, brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    result = await offer_service.list(db, filters={"brand_id": brand_id}, page=page)
    return result["items"]


@router.get("/{offer_id}", response_model=OfferResponse)
async def get_offer(offer_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    try:
        return await offer_service.get_or_404(db, offer_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Offer not found")


@router.delete("/{offer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_offer(offer_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    deleted = await offer_service.delete(db, offer_id)
    if not deleted:
        raise HTTPException(status_code=404)
    await log_action(db, "offer.deleted", user_id=current_user.id, actor_type="human", entity_type="offer", entity_id=offer_id)
