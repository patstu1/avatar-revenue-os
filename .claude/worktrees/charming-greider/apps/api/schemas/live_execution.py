"""Pydantic schemas for Live Execution Closure Phase 1."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Analytics ──────────────────────────────────────────────────────────

class AnalyticsImportCreate(BaseModel):
    source: str
    source_category: str = "social"
    events: list[dict[str, Any]] = Field(default_factory=list)

class AnalyticsImportOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    source: str
    source_category: str
    events_imported: int
    events_matched: int
    events_new: int
    import_mode: str
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

class AnalyticsEventOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    import_id: Optional[uuid.UUID] = None
    content_item_id: Optional[uuid.UUID] = None
    creator_account_id: Optional[uuid.UUID] = None
    source: str
    event_type: str
    platform: Optional[str] = None
    external_post_id: Optional[str] = None
    metric_value: float
    truth_level: str
    created_at: datetime
    class Config:
        from_attributes = True


# ── Conversions ────────────────────────────────────────────────────────

class ConversionImportCreate(BaseModel):
    source: str
    source_category: str = "checkout"
    conversions: list[dict[str, Any]] = Field(default_factory=list)

class ConversionImportOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    source: str
    source_category: str
    conversions_imported: int
    revenue_imported: float
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

class ConversionEventOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    import_id: Optional[uuid.UUID] = None
    content_item_id: Optional[uuid.UUID] = None
    offer_id: Optional[uuid.UUID] = None
    source: str
    conversion_type: str
    revenue: float
    cost: float
    profit: float
    currency: str
    truth_level: str
    created_at: datetime
    class Config:
        from_attributes = True


# ── Experiment Truth ───────────────────────────────────────────────────

class ExperimentObservationImportCreate(BaseModel):
    source: str
    observations: list[dict[str, Any]] = Field(default_factory=list)

class ExperimentObservationImportOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    source: str
    observations_imported: int
    observations_matched: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

class ExperimentLiveResultOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    import_id: Optional[uuid.UUID] = None
    experiment_id: Optional[uuid.UUID] = None
    variant_id: Optional[uuid.UUID] = None
    source: str
    observation_type: str
    metric_name: str
    metric_value: float
    sample_size: int
    confidence: float
    truth_level: str
    previous_truth_level: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True


# ── CRM / Contacts ────────────────────────────────────────────────────

class CrmContactCreate(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None
    segment: Optional[str] = None
    lifecycle_stage: str = "subscriber"
    source: str = "manual"
    tags: list[str] = Field(default_factory=list)

class CrmContactOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    external_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None
    segment: Optional[str] = None
    lifecycle_stage: str
    source: str
    sync_status: str
    created_at: datetime
    class Config:
        from_attributes = True

class CrmSyncOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    provider: str
    direction: str
    contacts_synced: int
    contacts_created: int
    contacts_updated: int
    contacts_failed: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True


# ── Email ──────────────────────────────────────────────────────────────

class EmailSendCreate(BaseModel):
    to_email: str
    subject: str
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    template_id: Optional[str] = None
    sequence_step: Optional[str] = None
    provider: str = "smtp"
    contact_id: Optional[uuid.UUID] = None

class EmailSendOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    contact_id: Optional[uuid.UUID] = None
    to_email: str
    subject: str
    provider: str
    status: str
    sent_at: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int
    created_at: datetime
    class Config:
        from_attributes = True


# ── SMS ────────────────────────────────────────────────────────────────

class SmsSendCreate(BaseModel):
    to_phone: str
    message_body: str
    sequence_step: Optional[str] = None
    provider: str = "twilio"
    contact_id: Optional[uuid.UUID] = None

class SmsSendOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    contact_id: Optional[uuid.UUID] = None
    to_phone: str
    message_body: str
    provider: str
    status: str
    sent_at: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int
    created_at: datetime
    class Config:
        from_attributes = True


# ── Messaging Blockers ────────────────────────────────────────────────

class MessagingBlockerOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    blocker_type: str
    channel: str
    severity: str
    description: str
    operator_action_needed: str
    resolved: bool
    created_at: datetime
    class Config:
        from_attributes = True


# ── Shared ────────────────────────────────────────────────────────────

class RecomputeSummaryOut(BaseModel):
    created: int = 0
    updated: int = 0
    details: Optional[str] = None
