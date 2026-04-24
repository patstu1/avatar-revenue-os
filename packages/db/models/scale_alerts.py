"""Scale alerts, launch candidates, blocker reports, notifications, launch readiness."""

import uuid
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class OperatorAlert(Base):
    __tablename__ = "operator_alerts"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    alert_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    urgency: Mapped[float] = mapped_column(Float, default=0.0)
    expected_upside: Mapped[float] = mapped_column(Float, default=0.0)
    expected_cost: Mapped[float] = mapped_column(Float, default=0.0)
    expected_time_to_signal_days: Mapped[int] = mapped_column(Integer, default=14)
    supporting_metrics: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    blocking_factors: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    linked_scale_recommendation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scale_recommendations.id"), nullable=True
    )
    linked_launch_candidate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("launch_candidates.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(30), default="unread", index=True)
    acknowledged_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resolved_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class LaunchCandidate(Base):
    __tablename__ = "launch_candidates"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    candidate_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    primary_platform: Mapped[str] = mapped_column(String(50), nullable=False)
    secondary_platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    niche: Mapped[str] = mapped_column(String(255), nullable=False)
    sub_niche: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    language: Mapped[str] = mapped_column(String(20), default="en")
    geography: Mapped[str] = mapped_column(String(100), default="US")
    avatar_persona_strategy: Mapped[Optional[str]] = mapped_column(Text)
    monetization_path: Mapped[Optional[str]] = mapped_column(Text)
    content_style: Mapped[Optional[str]] = mapped_column(Text)
    posting_strategy: Mapped[Optional[str]] = mapped_column(Text)
    expected_monthly_revenue_min: Mapped[float] = mapped_column(Float, default=0.0)
    expected_monthly_revenue_max: Mapped[float] = mapped_column(Float, default=0.0)
    expected_launch_cost: Mapped[float] = mapped_column(Float, default=0.0)
    expected_time_to_signal_days: Mapped[int] = mapped_column(Integer, default=30)
    expected_time_to_profit_days: Mapped[int] = mapped_column(Integer, default=90)
    cannibalization_risk: Mapped[float] = mapped_column(Float, default=0.0)
    audience_separation_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    urgency: Mapped[float] = mapped_column(Float, default=0.0)
    supporting_reasons: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    required_resources: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    launch_blockers: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    linked_scale_recommendation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scale_recommendations.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ScaleBlockerReport(Base):
    __tablename__ = "scale_blocker_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    blocker_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    recommended_fix: Mapped[Optional[str]] = mapped_column(Text)
    current_value: Mapped[float] = mapped_column(Float, default=0.0)
    threshold_value: Mapped[float] = mapped_column(Float, default=0.0)
    evidence: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    alert_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("operator_alerts.id"), index=True
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    recipient: Mapped[Optional[str]] = mapped_column(String(255))
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    delivered_at: Mapped[Optional[str]] = mapped_column(String(50))


class LaunchReadinessReport(Base):
    __tablename__ = "launch_readiness_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    launch_readiness_score: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(String(50), default="monitor")
    gating_factors: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    components: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class GrowthCommand(Base):
    __tablename__ = "growth_commands"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    command_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=50)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    exact_instruction: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(Text)
    comparison: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    platform_fit: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    niche_fit: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    monetization_path: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    cannibalization_analysis: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    success_threshold: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    failure_threshold: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    expected_upside: Mapped[float] = mapped_column(Float, default=0.0)
    expected_cost: Mapped[float] = mapped_column(Float, default=0.0)
    expected_time_to_signal_days: Mapped[int] = mapped_column(Integer, default=14)
    expected_time_to_profit_days: Mapped[int] = mapped_column(Integer, default=60)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    urgency: Mapped[float] = mapped_column(Float, default=0.0)
    blocking_factors: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    first_week_plan: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    linked_launch_candidate_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    linked_scale_recommendation_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    evidence: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    execution_spec: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    required_resources: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    superseded_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    superseded_by_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("growth_command_runs.id"), nullable=True
    )
    created_in_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("growth_command_runs.id"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    command_priority: Mapped[int] = mapped_column(Integer, default=50)
    action_deadline: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), nullable=True)
    platform: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    account_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    niche: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sub_niche: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    persona_strategy_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    monetization_strategy_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    output_requirements_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    success_threshold_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    failure_threshold_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    expected_revenue_min: Mapped[float] = mapped_column(Float, default=0.0)
    expected_revenue_max: Mapped[float] = mapped_column(Float, default=0.0)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    blockers_json: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    explanation_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    consequence_if_ignored_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    lifecycle_status: Mapped[str] = mapped_column(String(30), default="active", index=True)


class GrowthCommandRun(Base):
    """Audit row for each POST /growth-commands/recompute (Phase A)."""

    __tablename__ = "growth_command_runs"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    triggered_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(30), default="completed", nullable=False)
    commands_generated: Mapped[int] = mapped_column(Integer, default=0)
    command_types: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    portfolio_balance_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    whitespace_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    portfolio_directive: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
