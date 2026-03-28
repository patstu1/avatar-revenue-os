"""Avatar identity management endpoints."""
import uuid

from fastapi import APIRouter, HTTPException, Query, status

from apps.api.deps import CurrentUser, DBSession
from apps.api.schemas.core import AvatarCreate, AvatarResponse
from apps.api.services.audit_service import log_action
from apps.api.services.crud_service import CRUDService
from packages.db.models.core import Avatar, Brand

router = APIRouter()
avatar_service = CRUDService(Avatar)
brand_service = CRUDService(Brand)


@router.post("/", response_model=AvatarResponse, status_code=status.HTTP_201_CREATED)
async def create_avatar(body: AvatarCreate, current_user: CurrentUser, db: DBSession):
    brand = await brand_service.get(db, body.brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    avatar = await avatar_service.create(db, **body.model_dump())
    await log_action(db, "avatar.created", brand_id=body.brand_id, user_id=current_user.id, actor_type="human", entity_type="avatar", entity_id=avatar.id)
    return avatar


@router.get("/", response_model=list[AvatarResponse])
async def list_avatars(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession, page: int = Query(1, ge=1)):
    brand = await brand_service.get(db, brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    result = await avatar_service.list(db, filters={"brand_id": brand_id}, page=page)
    return result["items"]


@router.get("/{avatar_id}", response_model=AvatarResponse)
async def get_avatar(avatar_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    try:
        avatar = await avatar_service.get_or_404(db, avatar_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Avatar not found")
    return avatar
