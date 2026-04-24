"""AI Personality (Persona) management endpoints."""
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from apps.api.deps import CurrentUser, DBSession
from apps.api.services.audit_service import log_action
from apps.api.services.crud_service import CRUDService
from packages.db.models.core import Brand
from packages.db.models.ai_personality import AIPersonality

router = APIRouter()
persona_service = CRUDService(AIPersonality)
brand_service = CRUDService(Brand)


class PersonaCreate(BaseModel):
    brand_id: uuid.UUID
    account_id: uuid.UUID
    character_name: str
    character_tagline: Optional[str] = None
    character_backstory: Optional[str] = None
    character_archetype: str = "expert"
    communication_style: str = "direct"
    humor_level: str = "moderate"
    energy_level: str = "high"
    formality_level: str = "casual"
    personality_traits: list[str] = Field(default_factory=list)
    catchphrases: list[str] = Field(default_factory=list)
    voice_provider: Optional[str] = None
    voice_id: Optional[str] = None
    voice_description: Optional[str] = None
    visual_style: Optional[str] = None
    favorite_topics: list[str] = Field(default_factory=list)
    expertise_areas: list[str] = Field(default_factory=list)
    content_philosophy: Optional[str] = None


class PersonaUpdate(BaseModel):
    character_name: Optional[str] = None
    character_tagline: Optional[str] = None
    character_backstory: Optional[str] = None
    character_archetype: Optional[str] = None
    communication_style: Optional[str] = None
    humor_level: Optional[str] = None
    energy_level: Optional[str] = None
    formality_level: Optional[str] = None
    personality_traits: Optional[list[str]] = None
    catchphrases: Optional[list[str]] = None
    voice_provider: Optional[str] = None
    voice_id: Optional[str] = None
    voice_description: Optional[str] = None
    visual_style: Optional[str] = None
    favorite_topics: Optional[list[str]] = None
    expertise_areas: Optional[list[str]] = None
    content_philosophy: Optional[str] = None
    is_active: Optional[bool] = None


class PersonaResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    account_id: uuid.UUID
    character_name: str
    character_tagline: Optional[str] = None
    character_backstory: Optional[str] = None
    character_archetype: str
    communication_style: str
    humor_level: str
    energy_level: str
    formality_level: str
    personality_traits: list = Field(default_factory=list)
    catchphrases: list = Field(default_factory=list)
    voice_provider: Optional[str] = None
    voice_id: Optional[str] = None
    voice_description: Optional[str] = None
    visual_style: Optional[str] = None
    favorite_topics: list = Field(default_factory=list)
    expertise_areas: list = Field(default_factory=list)
    content_philosophy: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


@router.post("/", response_model=PersonaResponse, status_code=status.HTTP_201_CREATED)
async def create_persona(body: PersonaCreate, current_user: CurrentUser, db: DBSession):
    brand = await brand_service.get(db, body.brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    persona = await persona_service.create(db, **body.model_dump())
    await log_action(
        db, "persona.created",
        organization_id=current_user.organization_id, brand_id=body.brand_id,
        user_id=current_user.id, actor_type="human",
        entity_type="ai_personality", entity_id=persona.id,
    )
    return persona


@router.get("/", response_model=list[PersonaResponse])
async def list_personas(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession, page: int = Query(1, ge=1)):
    brand = await brand_service.get(db, brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    result = await persona_service.list(db, filters={"brand_id": brand_id}, page=page)
    return result["items"]


@router.patch("/{persona_id}", response_model=PersonaResponse)
async def update_persona(persona_id: uuid.UUID, body: PersonaUpdate, current_user: CurrentUser, db: DBSession):
    try:
        persona = await persona_service.get_or_404(db, persona_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Persona not found")
    brand = await brand_service.get(db, persona.brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(persona, key, value)
    await db.flush()
    await db.refresh(persona)
    return persona


@router.delete("/{persona_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_persona(persona_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    try:
        persona = await persona_service.get_or_404(db, persona_id)
    except ValueError:
        raise HTTPException(status_code=404)
    brand = await brand_service.get(db, persona.brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    await persona_service.delete(db, persona_id)
