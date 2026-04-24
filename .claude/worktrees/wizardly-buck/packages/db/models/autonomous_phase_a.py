"""Autonomous Execution Phase A: signal scanning, queue, warm-up, output & maturity."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class SignalScanRun(Base):
    __tablename__ = "signal_scan_runs"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    scan_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="running")
    signals_detected: Mapped[int] = mapped_column(Integer, default=0)
    signals_actionable: Mapped[int] = mapped_column(Integer, default=0)
    scan_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scan_metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class NormalizedSignalEvent(Base):
    __tablename__ = "normalized_signal_events"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    scan_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("signal_scan_runs.id"), nullable=True, index=True
    )
    signal_type: Mapped[str] = mapped_column(String(100), nullable=False)
    signal_source: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_payload_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    normalized_title: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    freshness_score: Mapped[float] = mapped_column(Float, default=0.0)
    monetization_relevance: Mapped[float] = mapped_column(Float, default=0.0)
    urgency_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_actionable: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AutoQueueItem(Base):
    __tablename__ = "auto_queue_items"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    signal_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("normalized_signal_events.id"), nullable=True, index=True
    )
    queue_item_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creator_accounts.id"), nullable=True, index=True
    )
    target_account_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    niche: Mapped[str] = mapped_column(String(255), nullable=False)
    sub_niche: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content_family: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    monetization_path: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    urgency_score: Mapped[float] = mapped_column(Float, default=0.0)
    queue_status: Mapped[str] = mapped_column(String(50), default="pending")
    suppression_flags_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    hold_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AccountWarmupPlan(Base):
    __tablename__ = "account_warmup_plans"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creator_accounts.id"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    warmup_phase: Mapped[str] = mapped_column(String(50), default="phase_1_warmup")
    initial_posts_per_week: Mapped[int] = mapped_column(Integer, default=1)
    current_posts_per_week: Mapped[int] = mapped_column(Integer, default=1)
    target_posts_per_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    warmup_start_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    warmup_end_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    engagement_target: Mapped[float] = mapped_column(Float, default=0.02)
    trust_target: Mapped[float] = mapped_column(Float, default=0.5)
    content_mix_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    failure_signals_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ramp_conditions_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AccountOutputReport(Base):
    __tablename__ = "account_output_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creator_accounts.id"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    current_output_per_week: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_output_per_week: Mapped[float] = mapped_column(Float, default=0.0)
    max_safe_output_per_week: Mapped[float] = mapped_column(Float, default=0.0)
    max_profitable_output_per_week: Mapped[float] = mapped_column(Float, default=0.0)
    throttle_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_increase_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    monetization_response_score: Mapped[float] = mapped_column(Float, default=0.0)
    account_health_score: Mapped[float] = mapped_column(Float, default=0.0)
    saturation_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AccountMaturityReport(Base):
    __tablename__ = "account_maturity_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creator_accounts.id"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    maturity_state: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    days_in_current_state: Mapped[int] = mapped_column(Integer, default=0)
    posts_published: Mapped[int] = mapped_column(Integer, default=0)
    avg_engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    follower_velocity: Mapped[float] = mapped_column(Float, default=0.0)
    health_score: Mapped[float] = mapped_column(Float, default=0.0)
    transition_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_expected_transition: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PlatformWarmupPolicy(Base):
    __tablename__ = "platform_warmup_policies"

    platform: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    initial_posts_per_week_min: Mapped[int] = mapped_column(Integer, default=1)
    initial_posts_per_week_max: Mapped[int] = mapped_column(Integer, default=3)
    warmup_duration_weeks_min: Mapped[int] = mapped_column(Integer, default=2)
    warmup_duration_weeks_max: Mapped[int] = mapped_column(Integer, default=4)
    steady_state_posts_per_week_min: Mapped[int] = mapped_column(Integer, default=3)
    steady_state_posts_per_week_max: Mapped[int] = mapped_column(Integer, default=14)
    max_safe_posts_per_day: Mapped[int] = mapped_column(Integer, default=3)
    ramp_conditions_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    account_health_signals_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    spam_risk_signals_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    trust_risk_signals_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    scale_ready_conditions_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ramp_behavior: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OutputRampEvent(Base):
    __tablename__ = "output_ramp_events"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creator_accounts.id"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    from_output_per_week: Mapped[float] = mapped_column(Float, default=0.0)
    to_output_per_week: Mapped[float] = mapped_column(Float, default=0.0)
    trigger_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
