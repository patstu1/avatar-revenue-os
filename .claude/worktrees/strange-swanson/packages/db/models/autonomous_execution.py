"""Autonomous execution control plane — policies, runs, blocker escalations (Phase A)."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class AutomationExecutionPolicy(Base):
    """Per-brand automation policy: mode, thresholds, kill-switch, approval gates."""

    __tablename__ = "automation_execution_policies"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, unique=True, index=True
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )
    operating_mode: Mapped[str] = mapped_column(
        String(40), nullable=False, default="guarded_autonomous"
    )
    min_confidence_auto_execute: Mapped[float] = mapped_column(Float, default=0.72)
    min_confidence_publish: Mapped[float] = mapped_column(Float, default=0.78)
    kill_switch_engaged: Mapped[bool] = mapped_column(Boolean, default=False)
    max_auto_cost_usd_per_action: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    require_approval_above_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    approval_gates_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    extra_policy_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AutomationExecutionRun(Base):
    """Append-only-style record of an automation attempt for a loop step."""

    __tablename__ = "automation_execution_runs"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    loop_step: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    policy_snapshot_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    input_payload_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    output_payload_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    blocked_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approval_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    parent_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("automation_execution_runs.id"), nullable=True
    )
    rollback_of_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("automation_execution_runs.id"), nullable=True
    )


class ExecutionBlockerEscalation(Base):
    """Structured blocker with exact operator steps (not vague advice)."""

    __tablename__ = "execution_blocker_escalations"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    blocker_category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    exact_operator_steps_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    linked_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("automation_execution_runs.id"), nullable=True, index=True
    )
    risk_flags_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    cost_exposure_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    resolution_status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    resolved_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resolved_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notification_enqueued_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
