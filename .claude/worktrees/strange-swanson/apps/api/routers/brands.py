"""Brand management endpoints."""
import uuid

from fastapi import APIRouter, HTTPException, Query, status

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.schemas.core import BrandCreate, BrandResponse, BrandUpdate
from apps.api.services.audit_service import log_action
from apps.api.services.crud_service import CRUDService
from packages.db.models.core import Brand

router = APIRouter()
brand_service = CRUDService(Brand)


@router.post("/", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
async def create_brand(body: BrandCreate, current_user: CurrentUser, db: DBSession):
    brand = await brand_service.create(
        db,
        organization_id=current_user.organization_id,
        **body.model_dump(),
    )
    await log_action(
        db, "brand.created",
        organization_id=current_user.organization_id,
        brand_id=brand.id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="brand",
        entity_id=brand.id,
    )
    return brand


@router.get("/", response_model=list[BrandResponse])
async def list_brands(
    current_user: CurrentUser,
    db: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    include_archived: bool = Query(
        False,
        description="Include archived (is_active=false) brands. Default false so operator views show only live brands.",
    ),
):
    """List brands for the current organization.

    Default: only active/live brands (is_active=true).
    Pass ?include_archived=true for admin/audit access to archived brands.
    """
    filters: dict = {"organization_id": current_user.organization_id}
    if not include_archived:
        filters["is_active"] = True
    result = await brand_service.list(db, page=page, page_size=page_size, filters=filters)
    return result["items"]


@router.get("/{brand_id}", response_model=BrandResponse)
async def get_brand(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    try:
        brand = await brand_service.get_or_404(db, brand_id)
    except ValueError:
        raise HTTPException(status_code=403, detail="Brand not accessible")
    if brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return brand


@router.patch("/{brand_id}", response_model=BrandResponse)
async def update_brand(brand_id: uuid.UUID, body: BrandUpdate, current_user: CurrentUser, db: DBSession):
    try:
        brand = await brand_service.get_or_404(db, brand_id)
    except ValueError:
        raise HTTPException(status_code=403, detail="Brand not accessible")
    if brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    updated = await brand_service.update(db, brand_id, **body.model_dump(exclude_unset=True))
    await log_action(db, "brand.updated", brand_id=brand_id, user_id=current_user.id, actor_type="human", entity_type="brand", entity_id=brand_id)
    return updated


@router.delete("/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_brand(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    """Soft delete a brand by setting is_active=False."""
    try:
        brand = await brand_service.get_or_404(db, brand_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Brand not found")
    if brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    await brand_service.update(db, brand_id, is_active=False)
    await log_action(
        db, "brand.deleted",
        organization_id=current_user.organization_id,
        brand_id=brand_id, user_id=current_user.id,
        actor_type="human", entity_type="brand", entity_id=brand_id,
    )
