"""Autonomous Execution Phase D: agent orchestration, revenue pressure, overrides, blockers, escalations."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    agent_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    run_status: Mapped[str] = mapped_column(String(50), default="running")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    input_context_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    output_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    commands_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False, index=True
    )
    sender_agent: Mapped[str] = mapped_column(String(120), nullable=False)
    receiver_agent: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    message_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RevenuePressureReport(Base):
    __tablename__ = "revenue_pressure_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    next_commands_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    next_launches_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    biggest_blocker: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    biggest_missed_opportunity: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    biggest_weak_lane_to_kill: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    underused_monetization_class: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    underbuilt_platform: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    missing_account_suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unexploited_winner: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    leaking_funnel: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    inactive_asset_class: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    pressure_score: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OverridePolicy(Base):
    __tablename__ = "override_policies"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    action_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    override_mode: Mapped[str] = mapped_column(String(50), default="guarded")
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.7)
    approval_needed: Mapped[bool] = mapped_column(Boolean, default=False)
    rollback_available: Mapped[bool] = mapped_column(Boolean, default=False)
    rollback_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hard_stop_rule: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    audit_trail_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class EscalationEvent(Base):
    __tablename__ = "escalation_events"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    command: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_data_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    urgency: Mapped[str] = mapped_column(String(50), default="medium")
    expected_upside: Mapped[float] = mapped_column(Float, default=0.0)
    expected_cost: Mapped[float] = mapped_column(Float, default=0.0)
    time_to_signal: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    time_to_profit: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    risk: Mapped[str] = mapped_column(String(80), default="low")
    required_resources: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    consequence_if_ignored: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BlockerDetectionReport(Base):
    __tablename__ = "blocker_detection_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    blocker: Mapped[str] = mapped_column(String(200), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), default="medium")
    affected_scope: Mapped[str] = mapped_column(String(300), nullable=False)
    operator_action_needed: Mapped[str] = mapped_column(Text, nullable=False)
    deadline_or_urgency: Mapped[str] = mapped_column(String(120), default="within_24h")
    consequence_if_ignored: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="open")
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OperatorCommand(Base):
    __tablename__ = "operator_commands"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    escalation_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("escalation_events.id"), nullable=True, index=True
    )
    blocker_report_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("blocker_detection_reports.id"), nullable=True, index=True
    )
    command_text: Mapped[str] = mapped_column(Text, nullable=False)
    command_type: Mapped[str] = mapped_column(String(120), nullable=False)
    urgency: Mapped[str] = mapped_column(String(50), default="medium")
    status: Mapped[str] = mapped_column(String(50), default="pending")
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
