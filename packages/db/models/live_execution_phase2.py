"""Live Execution Phase 2 + Buffer Execution Expansion models."""

import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base

# ── A. Webhook / Event Ingestion ──────────────────────────────────────


class WebhookEvent(Base):
    """Inbound webhook event from any external source (Stripe, Buffer, CRM, ESP, etc.)."""

    __tablename__ = "webhook_events"

    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    external_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    processing_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ExternalEventIngestion(Base):
    """Summarises a batch or real-time ingestion run from a specific source."""

    __tablename__ = "external_event_ingestions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    ingestion_mode: Mapped[str] = mapped_column(String(30), default="webhook", index=True)
    events_received: Mapped[int] = mapped_column(Integer, default=0)
    events_processed: Mapped[int] = mapped_column(Integer, default=0)
    events_skipped: Mapped[int] = mapped_column(Integer, default=0)
    events_failed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="completed", index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ── B. Sequence Trigger Actions ───────────────────────────────────────


class SequenceTriggerAction(Base):
    """An automated action triggered by an event (conversion, CRM change, etc.)."""

    __tablename__ = "sequence_trigger_actions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    trigger_source: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    trigger_event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    trigger_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    action_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    action_target: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    action_payload: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    executed_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ── C. Payment / Checkout Connector ──────────────────────────────────


class PaymentConnectorSync(Base):
    """Tracks a sync operation from a payment provider (Stripe, Shopify, etc.)."""

    __tablename__ = "payment_connector_syncs"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    sync_mode: Mapped[str] = mapped_column(String(30), default="incremental", index=True)
    orders_imported: Mapped[int] = mapped_column(Integer, default=0)
    revenue_imported: Mapped[float] = mapped_column(Float, default=0.0)
    refunds_imported: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="completed", index=True)
    credential_status: Mapped[str] = mapped_column(String(30), default="not_configured", index=True)
    last_cursor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ── D. Platform Analytics Sync ───────────────────────────────────────


class PlatformAnalyticsSync(Base):
    """Tracks a scheduled or manual analytics pull from a platform/Buffer."""

    __tablename__ = "platform_analytics_syncs"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    sync_mode: Mapped[str] = mapped_column(String(30), default="scheduled", index=True)
    metrics_imported: Mapped[int] = mapped_column(Integer, default=0)
    content_items_matched: Mapped[int] = mapped_column(Integer, default=0)
    attribution_refreshed: Mapped[bool] = mapped_column(Boolean, default=False)
    reconciliation_status: Mapped[str] = mapped_column(String(30), default="clean", index=True)
    credential_status: Mapped[str] = mapped_column(String(30), default="not_configured", index=True)
    blocker_state: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    operator_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ── E. Ad Reporting Imports ──────────────────────────────────────────


class AdReportingImport(Base):
    """Tracks an import of ad platform reporting data (Meta, Google, TikTok)."""

    __tablename__ = "ad_reporting_imports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    ad_platform: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(80), default="campaign_summary", index=True)
    campaigns_imported: Mapped[int] = mapped_column(Integer, default=0)
    spend_imported: Mapped[float] = mapped_column(Float, default=0.0)
    impressions_imported: Mapped[int] = mapped_column(Integer, default=0)
    clicks_imported: Mapped[int] = mapped_column(Integer, default=0)
    conversions_imported: Mapped[int] = mapped_column(Integer, default=0)
    revenue_attributed: Mapped[float] = mapped_column(Float, default=0.0)
    source_classification: Mapped[str] = mapped_column(String(40), default="ads", index=True)
    reconciliation_status: Mapped[str] = mapped_column(String(30), default="clean", index=True)
    credential_status: Mapped[str] = mapped_column(String(30), default="not_configured", index=True)
    blocker_state: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    operator_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ── F. Buffer Execution Truth ────────────────────────────────────────


class BufferExecutionTruth(Base):
    """Per-job execution truth model tracking the full Buffer lifecycle."""

    __tablename__ = "buffer_execution_truth"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    buffer_publish_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("buffer_publish_jobs.id"), nullable=False, index=True
    )
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True, index=True
    )
    truth_state: Mapped[str] = mapped_column(String(40), default="queued_internally", index=True)
    previous_truth_state: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False)
    stale_since: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    conflict_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    conflict_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    operator_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BufferExecutionEvent(Base):
    """An event in the Buffer job lifecycle (state transitions, retries, errors)."""

    __tablename__ = "buffer_execution_events"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    buffer_publish_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("buffer_publish_jobs.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    from_state: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    to_state: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BufferRetryRecord(Base):
    """Tracks retry attempts and backoff for a Buffer publish job."""

    __tablename__ = "buffer_retry_records"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    buffer_publish_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("buffer_publish_jobs.id"), nullable=False, index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    retry_reason: Mapped[str] = mapped_column(String(120), nullable=False)
    backoff_seconds: Mapped[int] = mapped_column(Integer, default=60)
    next_retry_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    outcome: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BufferCapabilityCheck(Base):
    """Profile readiness and platform capability check for a Buffer profile."""

    __tablename__ = "buffer_capability_checks"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    buffer_profile_id_fk: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("buffer_profiles.id"), nullable=False, index=True
    )
    profile_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    credential_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    missing_profile_mapping: Mapped[bool] = mapped_column(Boolean, default=False)
    inactive_profile: Mapped[bool] = mapped_column(Boolean, default=False)
    platform_supported: Mapped[bool] = mapped_column(Boolean, default=True)
    unsupported_modes: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    capabilities_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    blocker_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    operator_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
