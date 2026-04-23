"""Pydantic schemas for Phase 3 content pipeline endpoints."""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class BriefResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    title: str
    content_type: str
    target_platform: Optional[str]
    hook: Optional[str]
    angle: Optional[str]
    key_points: Optional[list]
    cta_strategy: Optional[str]
    monetization_integration: Optional[str]
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}


class BriefUpdate(BaseModel):
    title: Optional[str] = None
    hook: Optional[str] = None
    angle: Optional[str] = None
    key_points: Optional[list] = None
    cta_strategy: Optional[str] = None
    target_platform: Optional[str] = None
    tone_guidance: Optional[str] = None
    status: Optional[str] = None


class ScriptResponse(BaseModel):
    id: uuid.UUID
    brief_id: uuid.UUID
    brand_id: uuid.UUID
    version: int
    title: str
    hook_text: Optional[str]
    body_text: str
    cta_text: Optional[str]
    full_script: str
    estimated_duration_seconds: Optional[int]
    word_count: int
    generation_model: Optional[str]
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}


class ScriptUpdate(BaseModel):
    hook_text: Optional[str] = None
    body_text: Optional[str] = None
    cta_text: Optional[str] = None
    full_script: Optional[str] = None
    status: Optional[str] = None


class MediaJobResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    script_id: Optional[uuid.UUID] = None
    job_type: str
    status: str
    provider: Optional[str] = None
    provider_job_id: Optional[str] = None
    quality_tier: str = "standard"
    retry_count: int = 0
    error_message: Optional[str] = None
    output_url: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class QAReportResponse(BaseModel):
    id: uuid.UUID
    content_item_id: uuid.UUID
    qa_status: str
    originality_score: float
    compliance_score: float
    brand_alignment_score: float
    technical_quality_score: float
    audio_quality_score: float
    visual_quality_score: float
    composite_score: float
    issues_found: Optional[list]
    recommendations: Optional[list]
    automated_checks: Optional[dict]
    explanation: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


class SimilarityReportResponse(BaseModel):
    id: uuid.UUID
    content_item_id: uuid.UUID
    compared_against_count: int
    max_similarity_score: float
    avg_similarity_score: float
    is_too_similar: bool
    threshold_used: float
    explanation: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


class ApprovalResponse(BaseModel):
    id: uuid.UUID
    content_item_id: uuid.UUID
    status: str
    decision_mode: str
    auto_approved: bool
    review_notes: Optional[str]
    reviewed_at: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


class ApprovalAction(BaseModel):
    notes: str = ""


class ScheduleRequest(BaseModel):
    creator_account_id: uuid.UUID
    platform: str
    scheduled_at: Optional[datetime] = None


class PublishJobResponse(BaseModel):
    id: uuid.UUID
    content_item_id: uuid.UUID
    creator_account_id: uuid.UUID
    platform: str
    status: str
    scheduled_at: Optional[datetime]
    published_at: Optional[datetime]
    platform_post_url: Optional[str]
    retries: int
    error_message: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


class ContentItemResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    brief_id: Optional[uuid.UUID]
    script_id: Optional[uuid.UUID]
    title: str
    content_type: str
    platform: Optional[str]
    status: str
    monetization_method: Optional[str]
    offer_id: Optional[uuid.UUID]
    total_cost: float
    created_at: datetime
    model_config = {"from_attributes": True}
