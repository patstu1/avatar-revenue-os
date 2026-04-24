"""Schemas for avatar/voice provider profiles and provider usage costs."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AvatarProviderProfileCreate(BaseModel):
    avatar_id: uuid.UUID
    provider: str  # tavus, heygen, fallback
    provider_avatar_id: Optional[str] = None
    provider_config: Optional[dict] = None
    capabilities: Optional[dict] = None
    is_primary: bool = False
    is_fallback: bool = False
    cost_per_minute: Optional[float] = None


class AvatarProviderProfileUpdate(BaseModel):
    provider_avatar_id: Optional[str] = None
    provider_config: Optional[dict] = None
    capabilities: Optional[dict] = None
    is_primary: Optional[bool] = None
    is_fallback: Optional[bool] = None
    health_status: Optional[str] = None
    cost_per_minute: Optional[float] = None


class AvatarProviderProfileResponse(BaseModel):
    id: uuid.UUID
    avatar_id: uuid.UUID
    provider: str
    provider_avatar_id: Optional[str]
    provider_config: Optional[dict]
    capabilities: Optional[dict]
    is_primary: bool
    is_fallback: bool
    health_status: str
    last_health_check_at: Optional[datetime]
    cost_per_minute: Optional[float]
    created_at: datetime

    model_config = {"from_attributes": True}


class VoiceProviderProfileCreate(BaseModel):
    avatar_id: uuid.UUID
    provider: str  # elevenlabs, openai_realtime, fallback
    provider_voice_id: Optional[str] = None
    provider_config: Optional[dict] = None
    capabilities: Optional[dict] = None
    is_primary: bool = False
    is_fallback: bool = False
    cost_per_minute: Optional[float] = None


class VoiceProviderProfileUpdate(BaseModel):
    provider_voice_id: Optional[str] = None
    provider_config: Optional[dict] = None
    capabilities: Optional[dict] = None
    is_primary: Optional[bool] = None
    is_fallback: Optional[bool] = None
    health_status: Optional[str] = None
    cost_per_minute: Optional[float] = None


class VoiceProviderProfileResponse(BaseModel):
    id: uuid.UUID
    avatar_id: uuid.UUID
    provider: str
    provider_voice_id: Optional[str]
    provider_config: Optional[dict]
    capabilities: Optional[dict]
    is_primary: bool
    is_fallback: bool
    health_status: str
    last_health_check_at: Optional[datetime]
    cost_per_minute: Optional[float]
    created_at: datetime

    model_config = {"from_attributes": True}


class ProviderUsageCostResponse(BaseModel):
    id: uuid.UUID
    brand_id: Optional[uuid.UUID]
    provider: str
    provider_type: str
    operation: str
    input_units: int
    output_units: int
    cost: float
    currency: str
    related_job_id: Optional[uuid.UUID]
    created_at: datetime

    model_config = {"from_attributes": True}
