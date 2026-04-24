"""Pydantic schemas for Live Execution Phase 2 + Buffer Expansion."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

# ── Webhook / Event Ingestion ──────────────────────────────────────────


class WebhookEventCreate(BaseModel):
    source: str
    source_category: str = "unknown"
    event_type: str
    external_event_id: str | None = None
    raw_payload: dict[str, Any] | None = None
    idempotency_key: str | None = None


class WebhookEventOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID | None = None
    source: str
    source_category: str
    event_type: str
    external_event_id: str | None = None
    processed: bool
    processing_result: str | None = None
    error_message: str | None = None
    idempotency_key: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class ExternalEventIngestionOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    source: str
    source_category: str
    ingestion_mode: str
    events_received: int
    events_processed: int
    events_skipped: int
    events_failed: int
    status: str
    error_message: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Sequence Trigger Actions ───────────────────────────────────────────


class SequenceTriggerActionOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    trigger_source: str
    trigger_event_type: str
    action_type: str
    action_target: str | None = None
    status: str
    executed_at: str | None = None
    error_message: str | None = None
    retry_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# ── Payment Connector ──────────────────────────────────────────────────


class PaymentConnectorSyncOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    provider: str
    sync_mode: str
    orders_imported: int
    revenue_imported: float
    refunds_imported: int
    status: str
    credential_status: str
    error_message: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Platform Analytics Sync ────────────────────────────────────────────


class PlatformAnalyticsSyncOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    source: str
    source_category: str
    sync_mode: str
    metrics_imported: int
    content_items_matched: int
    attribution_refreshed: bool
    reconciliation_status: str
    credential_status: str
    blocker_state: str | None = None
    operator_action: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Ad Reporting Imports ───────────────────────────────────────────────


class AdReportingImportOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    ad_platform: str
    report_type: str
    campaigns_imported: int
    spend_imported: float
    impressions_imported: int
    clicks_imported: int
    conversions_imported: int
    revenue_attributed: float
    source_classification: str
    reconciliation_status: str
    credential_status: str
    blocker_state: str | None = None
    operator_action: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Buffer Execution Truth ─────────────────────────────────────────────


class BufferExecutionTruthOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    buffer_publish_job_id: uuid.UUID
    content_item_id: uuid.UUID | None = None
    truth_state: str
    previous_truth_state: str | None = None
    is_duplicate: bool
    is_stale: bool
    stale_since: str | None = None
    conflict_detected: bool
    conflict_description: str | None = None
    operator_action: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class BufferExecutionEventOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    buffer_publish_job_id: uuid.UUID
    event_type: str
    from_state: str | None = None
    to_state: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Buffer Retries ─────────────────────────────────────────────────────


class BufferRetryRecordOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    buffer_publish_job_id: uuid.UUID
    attempt_number: int
    retry_reason: str
    backoff_seconds: int
    next_retry_at: str | None = None
    outcome: str
    escalated: bool
    error_message: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Buffer Capability Checks ──────────────────────────────────────────


class BufferCapabilityCheckOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    buffer_profile_id_fk: uuid.UUID
    profile_ready: bool
    credential_valid: bool
    missing_profile_mapping: bool
    inactive_profile: bool
    platform_supported: bool
    unsupported_modes: list[str] | None = None
    blocker_summary: str | None = None
    operator_action: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Shared ─────────────────────────────────────────────────────────────


class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0
    status: str = "completed"
