"""Pydantic schemas for Buffer Distribution Layer."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class BufferProfileCreate(BaseModel):
    creator_account_id: Optional[UUID] = None
    platform: str
    buffer_profile_id: Optional[str] = None
    display_name: str
    credential_status: str = "not_connected"
    config_json: Optional[dict] = None


class BufferProfileUpdate(BaseModel):
    buffer_profile_id: Optional[str] = None
    display_name: Optional[str] = None
    credential_status: Optional[str] = None
    config_json: Optional[dict] = None
    is_active: Optional[bool] = None


class BufferProfileOut(BaseModel):
    id: UUID
    brand_id: UUID
    creator_account_id: Optional[UUID] = None
    platform: str
    buffer_profile_id: Optional[str] = None
    display_name: str
    credential_status: str
    last_sync_status: str
    last_sync_at: Optional[str] = None
    config_json: Optional[Any] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BufferPublishJobOut(BaseModel):
    id: UUID
    brand_id: UUID
    buffer_profile_id_fk: UUID
    content_item_id: Optional[UUID] = None
    distribution_plan_id: Optional[UUID] = None
    platform: str
    publish_mode: str
    status: str
    payload_json: Optional[Any] = None
    buffer_post_id: Optional[str] = None
    scheduled_at: Optional[str] = None
    published_at: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BufferPublishAttemptOut(BaseModel):
    id: UUID
    job_id: UUID
    attempt_number: int
    response_status_code: Optional[int] = None
    success: bool
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BufferStatusSyncOut(BaseModel):
    id: UUID
    brand_id: UUID
    jobs_checked: int
    jobs_updated: int
    jobs_failed: int
    jobs_published: int
    sync_mode: str
    details_json: Optional[Any] = None
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BufferBlockerOut(BaseModel):
    id: UUID
    brand_id: UUID
    buffer_profile_id_fk: Optional[UUID] = None
    blocker_type: str
    severity: str
    description: str
    operator_action_needed: str
    resolved: bool
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RecomputeSummaryOut(BaseModel):
    status: str
    detail: str
    counts: Optional[Any] = None
