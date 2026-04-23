"""Live Execution Closure Phase 1 — analytics, experiment truth, CRM/ESP/SMS."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


# ── A. Analytics / Attribution ─────────────────────────────────────────

class AnalyticsImport(Base):
    """A batch import of external analytics data."""
    __tablename__ = "analytics_imports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_category: Mapped[str] = mapped_column(String(40), default="social", index=True)
    events_imported: Mapped[int] = mapped_column(Integer, default=0)
    events_matched: Mapped[int] = mapped_column(Integer, default=0)
    events_new: Mapped[int] = mapped_column(Integer, default=0)
    import_mode: Mapped[str] = mapped_column(String(30), default="full", index=True)
    raw_payload_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="completed", index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AnalyticsEvent(Base):
    """Individual external analytics event (view, click, engagement, etc.)."""
    __tablename__ = "analytics_events"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    import_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("analytics_imports.id"), nullable=True, index=True)
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True, index=True)
    creator_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("creator_accounts.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    external_post_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    metric_value: Mapped[float] = mapped_column(Float, default=0.0)
    truth_level: Mapped[str] = mapped_column(String(30), default="live_import", index=True)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ConversionImport(Base):
    """A batch import of conversion/revenue events."""
    __tablename__ = "conversion_imports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_category: Mapped[str] = mapped_column(String(40), default="checkout", index=True)
    conversions_imported: Mapped[int] = mapped_column(Integer, default=0)
    revenue_imported: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="completed", index=True)
    raw_payload_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ConversionEvent(Base):
    """Individual conversion event — purchase, signup, lead, affiliate payout, etc."""
    __tablename__ = "conversion_events"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    import_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("conversion_imports.id"), nullable=True, index=True)
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True, index=True)
    offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("offers.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    conversion_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    profit: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    external_order_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    truth_level: Mapped[str] = mapped_column(String(30), default="live_import", index=True)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ── B. Experiment Truth ────────────────────────────────────────────────

class ExperimentObservationImport(Base):
    """A batch import of live experiment observations."""
    __tablename__ = "experiment_observation_imports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    observations_imported: Mapped[int] = mapped_column(Integer, default=0)
    observations_matched: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="completed", index=True)
    raw_payload_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ExperimentLiveResult(Base):
    """Live observation result that can override or complement proxy experiment outcomes."""
    __tablename__ = "experiment_live_results"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    import_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("experiment_observation_imports.id"), nullable=True, index=True)
    experiment_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("experiments.id"), nullable=True, index=True)
    variant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("experiment_variants.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    observation_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, default=0.0)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    truth_level: Mapped[str] = mapped_column(String(30), default="live_import", index=True)
    previous_truth_level: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ── C. CRM / ESP / SMS ────────────────────────────────────────────────

class CrmContact(Base):
    """A contact synced to or from an external CRM/ESP."""
    __tablename__ = "crm_contacts"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tags_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    segment: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    lifecycle_stage: Mapped[str] = mapped_column(String(60), default="subscriber", index=True)
    source: Mapped[str] = mapped_column(String(80), default="manual", index=True)
    sync_status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    last_synced_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CrmSync(Base):
    """A batch CRM sync operation."""
    __tablename__ = "crm_syncs"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(20), default="push", index=True)
    contacts_synced: Mapped[int] = mapped_column(Integer, default=0)
    contacts_created: Mapped[int] = mapped_column(Integer, default=0)
    contacts_updated: Mapped[int] = mapped_column(Integer, default=0)
    contacts_failed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="completed", index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class EmailSendRequest(Base):
    """An email send request queued for execution."""
    __tablename__ = "email_send_requests"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    contact_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("crm_contacts.id"), nullable=True, index=True)
    to_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    template_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sequence_step: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    provider: Mapped[str] = mapped_column(String(80), default="smtp", index=True)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    sent_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SmsSendRequest(Base):
    """An SMS send request queued for execution."""
    __tablename__ = "sms_send_requests"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    contact_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("crm_contacts.id"), nullable=True, index=True)
    to_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    message_body: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_step: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    provider: Mapped[str] = mapped_column(String(80), default="twilio", index=True)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    sent_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    external_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MessagingBlocker(Base):
    """Tracks blockers preventing CRM/email/SMS execution."""
    __tablename__ = "messaging_blockers"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    blocker_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(30), default="high", index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    operator_action_needed: Mapped[str] = mapped_column(Text, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
