"""Autonomous Execution Phase B: execution policies, content runner, distribution, monetization routing, suppression."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class ExecutionPolicy(Base):
    __tablename__ = "execution_policies"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(50), default="guarded")
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.7)
    risk_level: Mapped[str] = mapped_column(String(50), default="medium")
    cost_class: Mapped[str] = mapped_column(String(50), default="low")
    compliance_sensitivity: Mapped[str] = mapped_column(String(50), default="standard")
    platform_sensitivity: Mapped[str] = mapped_column(String(50), default="standard")
    budget_impact: Mapped[str] = mapped_column(String(50), default="none")
    account_health_impact: Mapped[str] = mapped_column(String(50), default="neutral")
    approval_requirement: Mapped[str] = mapped_column(String(100), default="none")
    rollback_rule: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    kill_switch_class: Mapped[str] = mapped_column(String(50), default="soft")
    policy_metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AutonomousRun(Base):
    __tablename__ = "autonomous_runs"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    queue_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auto_queue_items.id"), nullable=True, index=True
    )
    target_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creator_accounts.id"), nullable=True, index=True
    )
    target_platform: Mapped[str] = mapped_column(String(50), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(50), default="guarded")
    run_status: Mapped[str] = mapped_column(String(50), default="pending")
    current_step: Mapped[str] = mapped_column(String(100), default="queued")
    content_brief_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_briefs.id"), nullable=True
    )
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True
    )
    publish_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publish_jobs.id"), nullable=True
    )
    distribution_plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("distribution_plans.id"), nullable=True
    )
    monetization_route_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("monetization_routes.id"), nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    run_metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AutonomousRunStep(Base):
    __tablename__ = "autonomous_run_steps"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("autonomous_runs.id"), nullable=False, index=True
    )
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_status: Mapped[str] = mapped_column(String(50), default="pending")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    input_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    output_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class DistributionPlan(Base):
    __tablename__ = "distribution_plans"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    source_concept: Mapped[str] = mapped_column(String(500), nullable=False)
    source_content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True
    )
    target_platforms_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    derivative_types_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    platform_priority_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    cadence_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    publish_timing_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    duplication_guard_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    plan_status: Mapped[str] = mapped_column(String(50), default="draft")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MonetizationRoute(Base):
    __tablename__ = "monetization_routes"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True, index=True
    )
    queue_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auto_queue_items.id"), nullable=True
    )
    route_class: Mapped[str] = mapped_column(String(100), nullable=False)
    selected_route: Mapped[str] = mapped_column(String(200), nullable=False)
    funnel_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    follow_up_requirements_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    revenue_estimate: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    route_status: Mapped[str] = mapped_column(String(50), default="proposed")
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SuppressionExecution(Base):
    __tablename__ = "suppression_executions"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    suppression_type: Mapped[str] = mapped_column(String(100), nullable=False)
    affected_scope: Mapped[str] = mapped_column(String(200), nullable=False)
    affected_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    trigger_reason: Mapped[str] = mapped_column(Text, nullable=False)
    duration_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    lift_condition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    suppression_status: Mapped[str] = mapped_column(String(50), default="active")
    lifted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ExecutionFailure(Base):
    __tablename__ = "execution_failures"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("autonomous_runs.id"), nullable=True, index=True
    )
    failure_type: Mapped[str] = mapped_column(String(100), nullable=False)
    failure_step: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    error_context_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    recovery_action: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    recovery_status: Mapped[str] = mapped_column(String(50), default="pending")
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
