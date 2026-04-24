"""Avatar and voice provider profile endpoints."""

import uuid

from fastapi import APIRouter, HTTPException, status

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.schemas.providers import (
    AvatarProviderProfileCreate,
    AvatarProviderProfileResponse,
    AvatarProviderProfileUpdate,
    VoiceProviderProfileCreate,
    VoiceProviderProfileResponse,
    VoiceProviderProfileUpdate,
)
from apps.api.services.audit_service import log_action
from apps.api.services.crud_service import CRUDService
from packages.db.models.core import Avatar, AvatarProviderProfile, VoiceProviderProfile

router = APIRouter()
avatar_provider_service = CRUDService(AvatarProviderProfile)
voice_provider_service = CRUDService(VoiceProviderProfile)
avatar_service = CRUDService(Avatar)

SUPPORTED_AVATAR_PROVIDERS = {"tavus", "heygen", "fallback"}
SUPPORTED_VOICE_PROVIDERS = {"elevenlabs", "openai_realtime", "heygen", "fallback"}


@router.post("/avatar", response_model=AvatarProviderProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_avatar_provider(body: AvatarProviderProfileCreate, current_user: OperatorUser, db: DBSession):
    if body.provider not in SUPPORTED_AVATAR_PROVIDERS:
        raise HTTPException(
            status_code=400, detail=f"Unsupported avatar provider. Supported: {SUPPORTED_AVATAR_PROVIDERS}"
        )

    avatar = await avatar_service.get(db, body.avatar_id)
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found")

    profile = await avatar_provider_service.create(db, **body.model_dump())
    await log_action(
        db,
        "avatar_provider.created",
        user_id=current_user.id,
        actor_type="human",
        entity_type="avatar_provider_profile",
        entity_id=profile.id,
        details={"provider": body.provider, "avatar_id": str(body.avatar_id)},
    )
    return profile


@router.get("/avatar", response_model=list[AvatarProviderProfileResponse])
async def list_avatar_providers(avatar_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    result = await avatar_provider_service.list(db, filters={"avatar_id": avatar_id})
    return result["items"]


@router.patch("/avatar/{profile_id}", response_model=AvatarProviderProfileResponse)
async def update_avatar_provider(
    profile_id: uuid.UUID, body: AvatarProviderProfileUpdate, current_user: OperatorUser, db: DBSession
):
    try:
        updated = await avatar_provider_service.update(db, profile_id, **body.model_dump(exclude_unset=True))
    except ValueError:
        raise HTTPException(status_code=404, detail="Provider profile not found")
    await log_action(
        db,
        "avatar_provider.updated",
        user_id=current_user.id,
        actor_type="human",
        entity_type="avatar_provider_profile",
        entity_id=profile_id,
    )
    return updated


@router.delete("/avatar/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_avatar_provider(profile_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    if not await avatar_provider_service.delete(db, profile_id):
        raise HTTPException(status_code=404)
    await log_action(
        db,
        "avatar_provider.deleted",
        user_id=current_user.id,
        actor_type="human",
        entity_type="avatar_provider_profile",
        entity_id=profile_id,
    )


@router.post("/voice", response_model=VoiceProviderProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_voice_provider(body: VoiceProviderProfileCreate, current_user: OperatorUser, db: DBSession):
    if body.provider not in SUPPORTED_VOICE_PROVIDERS:
        raise HTTPException(
            status_code=400, detail=f"Unsupported voice provider. Supported: {SUPPORTED_VOICE_PROVIDERS}"
        )

    avatar = await avatar_service.get(db, body.avatar_id)
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found")

    profile = await voice_provider_service.create(db, **body.model_dump())
    await log_action(
        db,
        "voice_provider.created",
        user_id=current_user.id,
        actor_type="human",
        entity_type="voice_provider_profile",
        entity_id=profile.id,
        details={"provider": body.provider, "avatar_id": str(body.avatar_id)},
    )
    return profile


@router.get("/voice", response_model=list[VoiceProviderProfileResponse])
async def list_voice_providers(avatar_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    result = await voice_provider_service.list(db, filters={"avatar_id": avatar_id})
    return result["items"]


@router.patch("/voice/{profile_id}", response_model=VoiceProviderProfileResponse)
async def update_voice_provider(
    profile_id: uuid.UUID, body: VoiceProviderProfileUpdate, current_user: OperatorUser, db: DBSession
):
    try:
        updated = await voice_provider_service.update(db, profile_id, **body.model_dump(exclude_unset=True))
    except ValueError:
        raise HTTPException(status_code=404, detail="Provider profile not found")
    await log_action(
        db,
        "voice_provider.updated",
        user_id=current_user.id,
        actor_type="human",
        entity_type="voice_provider_profile",
        entity_id=profile_id,
    )
    return updated


@router.delete("/voice/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_voice_provider(profile_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    if not await voice_provider_service.delete(db, profile_id):
        raise HTTPException(status_code=404)
    await log_action(
        db,
        "voice_provider.deleted",
        user_id=current_user.id,
        actor_type="human",
        entity_type="voice_provider_profile",
        entity_id=profile_id,
    )
