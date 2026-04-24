"""Avatar identity management endpoints with RBAC."""

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.schemas.core import AvatarCreate, AvatarResponse
from apps.api.services.audit_service import log_action
from apps.api.services.crud_service import CRUDService
from packages.db.models.core import Avatar, Brand

router = APIRouter()
avatar_service = CRUDService(Avatar)
brand_service = CRUDService(Brand)


async def _verify_brand_access(brand_id: uuid.UUID, user, db):
    brand = await brand_service.get(db, brand_id)
    if not brand or brand.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")
    return brand


@router.post("/", response_model=AvatarResponse, status_code=status.HTTP_201_CREATED)
async def create_avatar(body: AvatarCreate, current_user: OperatorUser, db: DBSession):
    await _verify_brand_access(body.brand_id, current_user, db)
    avatar = await avatar_service.create(db, **body.model_dump())
    await log_action(
        db,
        "avatar.created",
        organization_id=current_user.organization_id,
        brand_id=body.brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="avatar",
        entity_id=avatar.id,
    )
    return avatar


@router.get("/", response_model=list[AvatarResponse])
async def list_avatars(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession, page: int = Query(1, ge=1)):
    await _verify_brand_access(brand_id, current_user, db)
    result = await avatar_service.list(db, filters={"brand_id": brand_id}, page=page)
    return result["items"]


@router.get("/{avatar_id}", response_model=AvatarResponse)
async def get_avatar(avatar_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    try:
        return await avatar_service.get_or_404(db, avatar_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Avatar not found")


@router.patch("/{avatar_id}", response_model=AvatarResponse)
async def update_avatar(avatar_id: uuid.UUID, body: AvatarCreate, current_user: OperatorUser, db: DBSession):
    try:
        avatar = await avatar_service.get_or_404(db, avatar_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Avatar not found")
    await _verify_brand_access(avatar.brand_id, current_user, db)
    updated = await avatar_service.update(db, avatar_id, **body.model_dump(exclude_unset=True))
    await log_action(
        db,
        "avatar.updated",
        organization_id=current_user.organization_id,
        brand_id=avatar.brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="avatar",
        entity_id=avatar_id,
    )
    return updated


@router.delete("/{avatar_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_avatar(avatar_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    if not await avatar_service.delete(db, avatar_id):
        raise HTTPException(status_code=404)
    await log_action(
        db,
        "avatar.deleted",
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="avatar",
        entity_id=avatar_id,
    )
