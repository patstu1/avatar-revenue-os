"""Pydantic schemas for Cinema Studio module."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# StudioProject
# ---------------------------------------------------------------------------

class StudioProjectCreate(BaseModel):
    title: str
    description: Optional[str] = None
    genre: str = "drama"
    status: str = "draft"
    thumbnail_url: Optional[str] = None
    offer_id: Optional[uuid.UUID] = None
    target_platform: Optional[str] = None


class StudioProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None
    status: Optional[str] = None
    thumbnail_url: Optional[str] = None
    offer_id: Optional[uuid.UUID] = None
    target_platform: Optional[str] = None


class StudioProjectResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    title: str
    description: Optional[str]
    genre: str
    status: str
    thumbnail_url: Optional[str]
    offer_id: Optional[uuid.UUID]
    target_platform: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# StudioScene
# ---------------------------------------------------------------------------

class StudioSceneCreate(BaseModel):
    project_id: Optional[uuid.UUID] = None
    title: str
    prompt: str
    negative_prompt: Optional[str] = None
    camera_shot: str = "medium"
    camera_movement: str = "static"
    lighting: str = "natural"
    mood: str = "cinematic"
    style_preset_id: Optional[uuid.UUID] = None
    duration_seconds: float = 5.0
    aspect_ratio: str = "16:9"
    character_ids: Optional[list[uuid.UUID]] = Field(default_factory=list)
    order_index: int = 0


class StudioSceneUpdate(BaseModel):
    project_id: Optional[uuid.UUID] = None
    title: Optional[str] = None
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    camera_shot: Optional[str] = None
    camera_movement: Optional[str] = None
    lighting: Optional[str] = None
    mood: Optional[str] = None
    style_preset_id: Optional[uuid.UUID] = None
    duration_seconds: Optional[float] = None
    aspect_ratio: Optional[str] = None
    character_ids: Optional[list[uuid.UUID]] = None
    order_index: Optional[int] = None
    status: Optional[str] = None


class StudioSceneResponse(BaseModel):
    id: uuid.UUID
    project_id: Optional[uuid.UUID]
    brand_id: uuid.UUID
    title: str
    prompt: str
    negative_prompt: Optional[str]
    camera_shot: str
    camera_movement: str
    lighting: str
    mood: str
    style_preset_id: Optional[uuid.UUID]
    duration_seconds: float
    aspect_ratio: str
    character_ids: Optional[list]
    order_index: int
    status: str
    thumbnail_url: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# CharacterBible
# ---------------------------------------------------------------------------

class CharacterBibleCreate(BaseModel):
    name: str
    description: str
    gender: str = "other"
    age: Optional[int] = None
    ethnicity: Optional[str] = None
    hair_color: Optional[str] = None
    hair_style: Optional[str] = None
    eye_color: Optional[str] = None
    build: Optional[str] = None
    personality: Optional[str] = None
    role: str = "supporting"
    image_url: Optional[str] = None
    tags: Optional[list[str]] = Field(default_factory=list)


class CharacterBibleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    ethnicity: Optional[str] = None
    hair_color: Optional[str] = None
    hair_style: Optional[str] = None
    eye_color: Optional[str] = None
    build: Optional[str] = None
    personality: Optional[str] = None
    role: Optional[str] = None
    image_url: Optional[str] = None
    tags: Optional[list[str]] = None


class CharacterBibleResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    name: str
    description: str
    gender: str
    age: Optional[int]
    ethnicity: Optional[str]
    hair_color: Optional[str]
    hair_style: Optional[str]
    eye_color: Optional[str]
    build: Optional[str]
    personality: Optional[str]
    role: str
    image_url: Optional[str]
    tags: Optional[list]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Portrait + Voice generation
# ---------------------------------------------------------------------------

class VoiceGenerationRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"


class PortraitGenerationResponse(BaseModel):
    character_id: uuid.UUID
    image_url: str
    prompt_used: str
    provider: str = "gpt-image-1"


class VoiceGenerationResponse(BaseModel):
    character_id: uuid.UUID
    character_name: str
    voice_id: str
    char_count: int
    content_type: str


# ---------------------------------------------------------------------------
# StylePreset
# ---------------------------------------------------------------------------

class StylePresetCreate(BaseModel):
    name: str
    description: str
    category: str = "cinematic"
    preview_url: Optional[str] = None
    tags: Optional[list[str]] = Field(default_factory=list)
    is_popular: bool = False


class StylePresetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    preview_url: Optional[str] = None
    tags: Optional[list[str]] = None
    is_popular: Optional[bool] = None


class StylePresetResponse(BaseModel):
    id: uuid.UUID
    brand_id: Optional[uuid.UUID]
    name: str
    description: str
    category: str
    preview_url: Optional[str]
    tags: Optional[list]
    is_popular: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# StudioGeneration
# ---------------------------------------------------------------------------

class GenerationTrigger(BaseModel):
    model: str = "runway"
    seed: Optional[int] = None
    steps: int = 50
    guidance: float = 7.5


class StudioGenerationResponse(BaseModel):
    id: uuid.UUID
    scene_id: uuid.UUID
    brand_id: uuid.UUID
    media_job_id: Optional[uuid.UUID]
    status: str
    progress: int
    video_url: Optional[str]
    thumbnail_url: Optional[str]
    error_message: Optional[str]
    model: str
    seed: Optional[int]
    steps: int
    guidance: float
    duration_seconds: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# StudioActivity
# ---------------------------------------------------------------------------

class StudioActivityResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    activity_type: str
    entity_id: uuid.UUID
    entity_name: str
    activity_metadata: Optional[dict]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------

class RevenueItemResponse(BaseModel):
    media_job_id: str
    lane: str
    monetization_method: str
    offer_name: Optional[str] = None
    offer_url: Optional[str] = None
    revenue_estimate: float = 0.0
    content_family: Optional[str] = None


class PublishTruth(BaseModel):
    content_approved: int = 0
    content_published: int = 0
    content_pending_media: int = 0
    content_media_complete: int = 0
    content_qa_complete: int = 0
    content_draft: int = 0
    publish_jobs_pending: int = 0
    publish_jobs_submitted: int = 0
    publish_jobs_queued: int = 0
    publish_jobs_published: int = 0
    publish_jobs_failed: int = 0
    publish_jobs_scheduled: int = 0


class StudioDashboardStats(BaseModel):
    total_projects: int = 0
    total_scenes: int = 0
    total_characters: int = 0
    total_generations: int = 0
    completed_generations: int = 0
    processing_generations: int = 0
    failed_generations: int = 0
    recent_activity: list[StudioActivityResponse] = Field(default_factory=list)
    lane_distribution: dict = Field(default_factory=dict)
    monetization_distribution: dict = Field(default_factory=dict)
    revenue_items: list[RevenueItemResponse] = Field(default_factory=list)
    publish_truth: PublishTruth = Field(default_factory=PublishTruth)
