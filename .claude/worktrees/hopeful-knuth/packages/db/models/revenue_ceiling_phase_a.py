"""Revenue Ceiling Phase A: offer ladders, owned audience, sequences, funnel metrics/leaks."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class OfferLadder(Base):
    __tablename__ = "offer_ladders"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    opportunity_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True, index=True)
    offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("offers.id"), nullable=True)
    top_of_funnel_asset: Mapped[str] = mapped_column(String(500), default="")
    first_monetization_step: Mapped[str] = mapped_column(Text, default="")
    second_monetization_step: Mapped[str] = mapped_column(Text, default="")
    upsell_path: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    retention_path: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    fallback_path: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    ladder_recommendation: Mapped[Optional[str]] = mapped_column(Text)
    expected_first_conversion_value: Mapped[float] = mapped_column(Float, default=0.0)
    expected_downstream_value: Mapped[float] = mapped_column(Float, default=0.0)
    expected_ltv_contribution: Mapped[float] = mapped_column(Float, default=0.0)
    friction_level: Mapped[str] = mapped_column(String(30), default="medium")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OwnedAudienceAsset(Base):
    __tablename__ = "owned_audience_assets"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    channel_name: Mapped[str] = mapped_column(String(255), default="")
    content_family: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    objective_per_family: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    cta_variants: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    estimated_channel_value: Mapped[float] = mapped_column(Float, default=0.0)
    direct_vs_capture_score: Mapped[float] = mapped_column(Float, default=0.5)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OwnedAudienceEvent(Base):
    __tablename__ = "owned_audience_events"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id"), index=True)
    asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("owned_audience_assets.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    value_contribution: Mapped[float] = mapped_column(Float, default=0.0)
    source_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)


class MessageSequence(Base):
    __tablename__ = "message_sequences"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    sequence_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(30), default="email")
    title: Mapped[str] = mapped_column(String(500), default="")
    sponsor_safe: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MessageSequenceStep(Base):
    __tablename__ = "message_sequence_steps"

    sequence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("message_sequences.id"), nullable=False, index=True)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default="email")
    subject_or_title: Mapped[Optional[str]] = mapped_column(String(500))
    body_template: Mapped[Optional[str]] = mapped_column(Text)
    delay_hours_after_previous: Mapped[int] = mapped_column(Integer, default=0)


class FunnelStageMetric(Base):
    __tablename__ = "funnel_stage_metrics"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    content_family: Mapped[str] = mapped_column(String(120), default="default", index=True)
    stage: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    metric_value: Mapped[float] = mapped_column(Float, default=0.0)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    period_start: Mapped[Optional[str]] = mapped_column(String(40))
    period_end: Mapped[Optional[str]] = mapped_column(String(40))


class FunnelLeakFix(Base):
    __tablename__ = "funnel_leak_fixes"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    leak_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    affected_funnel_stage: Mapped[str] = mapped_column(String(80), default="")
    affected_content_family: Mapped[Optional[str]] = mapped_column(String(120))
    suspected_cause: Mapped[Optional[str]] = mapped_column(Text)
    recommended_fix: Mapped[Optional[str]] = mapped_column(Text)
    expected_upside: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    urgency: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
