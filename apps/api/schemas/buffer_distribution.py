"""Pydantic schemas for Buffer Distribution Layer."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class BufferProfileCreate(BaseModel):
    creator_account_id: UUID | None = None
    platform: str
    buffer_profile_id: str | None = None
    display_name: str
    credential_status: str = "not_connected"
    config_json: dict | None = None


class BufferProfileUpdate(BaseModel):
    buffer_profile_id: str | None = None
    display_name: str | None = None
    credential_status: str | None = None
    config_json: dict | None = None
    is_active: bool | None = None


class BufferProfileOut(BaseModel):
    id: UUID
    brand_id: UUID
    creator_account_id: UUID | None = None
    platform: str
    buffer_profile_id: str | None = None
    display_name: str
    credential_status: str
    last_sync_status: str
    last_sync_at: str | None = None
    config_json: Any | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class BufferPublishJobOut(BaseModel):
    id: UUID
    brand_id: UUID
    buffer_profile_id_fk: UUID
    content_item_id: UUID | None = None
    distribution_plan_id: UUID | None = None
    platform: str
    publish_mode: str
    status: str
    payload_json: Any | None = None
    buffer_post_id: str | None = None
    scheduled_at: str | None = None
    published_at: str | None = None
    error_message: str | None = None
    retry_count: int
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class BufferPublishAttemptOut(BaseModel):
    id: UUID
    job_id: UUID
    attempt_number: int
    response_status_code: int | None = None
    success: bool
    error_message: str | None = None
    duration_ms: int | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class BufferStatusSyncOut(BaseModel):
    id: UUID
    brand_id: UUID
    jobs_checked: int
    jobs_updated: int
    jobs_failed: int
    jobs_published: int
    sync_mode: str
    details_json: Any | None = None
    is_active: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class BufferBlockerOut(BaseModel):
    id: UUID
    brand_id: UUID
    buffer_profile_id_fk: UUID | None = None
    blocker_type: str
    severity: str
    description: str
    operator_action_needed: str
    resolved: bool
    is_active: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class RecomputeSummaryOut(BaseModel):
    status: str
    detail: str
    counts: Any | None = None
