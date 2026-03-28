import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OrganizationCreate(BaseModel):
    name: str
    slug: str
    plan: str = "free"


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class BrandCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    niche: Optional[str] = None
    sub_niche: Optional[str] = None
    target_audience: Optional[str] = None
    tone_of_voice: Optional[str] = None
    brand_guidelines: Optional[dict] = None
    decision_mode: str = "guarded_auto"


class BrandResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: str
    description: Optional[str]
    niche: Optional[str]
    sub_niche: Optional[str]
    decision_mode: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AvatarCreate(BaseModel):
    brand_id: uuid.UUID
    name: str
    persona_description: Optional[str] = None
    voice_style: Optional[str] = None
    visual_style: Optional[str] = None
    default_language: str = "en"
    personality_traits: Optional[dict] = None
    speaking_patterns: Optional[dict] = None


class AvatarResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    name: str
    persona_description: Optional[str]
    voice_style: Optional[str]
    visual_style: Optional[str]
    default_language: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class OfferCreate(BaseModel):
    brand_id: uuid.UUID
    name: str
    description: Optional[str] = None
    monetization_method: str
    offer_url: Optional[str] = None
    payout_amount: float = 0.0
    payout_type: str = "cpa"
    epc: float = 0.0
    conversion_rate: float = 0.0
    average_order_value: float = 0.0
    audience_fit_tags: Optional[list] = None
    priority: int = 0


class OfferResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    name: str
    description: Optional[str]
    monetization_method: str
    payout_amount: float
    epc: float
    conversion_rate: float
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CreatorAccountCreate(BaseModel):
    brand_id: uuid.UUID
    avatar_id: Optional[uuid.UUID] = None
    platform: str
    account_type: str = "organic"
    platform_username: str
    niche_focus: Optional[str] = None
    sub_niche_focus: Optional[str] = None
    language: str = "en"
    geography: Optional[str] = None
    monetization_focus: Optional[str] = None
    posting_capacity_per_day: int = 1


class CreatorAccountResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    avatar_id: Optional[uuid.UUID]
    platform: str
    account_type: str
    platform_username: str
    account_health: str
    total_revenue: float
    total_profit: float
    profit_per_post: float
    revenue_per_mille: float
    ctr: float
    conversion_rate: float
    follower_count: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ContentBriefCreate(BaseModel):
    brand_id: uuid.UUID
    topic_candidate_id: Optional[uuid.UUID] = None
    offer_id: Optional[uuid.UUID] = None
    creator_account_id: Optional[uuid.UUID] = None
    title: str
    content_type: str
    target_platform: Optional[str] = None
    hook: Optional[str] = None
    angle: Optional[str] = None
    key_points: Optional[list] = None
    cta_strategy: Optional[str] = None
    monetization_integration: Optional[str] = None
    target_duration_seconds: Optional[int] = None


class ContentBriefResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    title: str
    content_type: str
    target_platform: Optional[str]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    pages: int
