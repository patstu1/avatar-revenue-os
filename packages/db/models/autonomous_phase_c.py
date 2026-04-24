"""Autonomous Execution Phase C: funnel, paid operator, sponsor, retention, recovery, self-healing."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class FunnelExecutionRun(Base):
    __tablename__ = "funnel_execution_runs"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    funnel_action: Mapped[str] = mapped_column(String(120), nullable=False)
    target_funnel_path: Mapped[str] = mapped_column(String(500), nullable=False)
    cta_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    capture_mode: Mapped[str] = mapped_column(String(80), default="owned_audience")
    execution_mode: Mapped[str] = mapped_column(String(50), default="guarded")
    expected_upside: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    run_status: Mapped[str] = mapped_column(String(50), default="proposed")
    diagnostics_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PaidOperatorRun(Base):
    __tablename__ = "paid_operator_runs"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    paid_action: Mapped[str] = mapped_column(String(120), nullable=False)
    budget_band: Mapped[str] = mapped_column(String(80), nullable=False)
    expected_cac: Mapped[float] = mapped_column(Float, default=0.0)
    expected_roi: Mapped[float] = mapped_column(Float, default=0.0)
    execution_mode: Mapped[str] = mapped_column(String(50), default="guarded")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    winner_score: Mapped[float] = mapped_column(Float, default=0.0)
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True, index=True
    )
    autonomous_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("autonomous_runs.id"), nullable=True, index=True
    )
    run_status: Mapped[str] = mapped_column(String(50), default="proposed")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PaidOperatorDecision(Base):
    __tablename__ = "paid_operator_decisions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    paid_operator_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("paid_operator_runs.id"), nullable=False, index=True
    )
    decision_type: Mapped[str] = mapped_column(String(80), nullable=False)
    budget_band: Mapped[str] = mapped_column(String(80), nullable=False)
    expected_cac: Mapped[float] = mapped_column(Float, default=0.0)
    expected_roi: Mapped[float] = mapped_column(Float, default=0.0)
    execution_mode: Mapped[str] = mapped_column(String(50), default="guarded")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_status: Mapped[str] = mapped_column(String(50), default="proposed")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SponsorAutonomousAction(Base):
    __tablename__ = "sponsor_autonomous_actions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    sponsor_action: Mapped[str] = mapped_column(String(120), nullable=False)
    package_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    target_category: Mapped[str] = mapped_column(String(200), nullable=False)
    target_list_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    pipeline_stage: Mapped[str] = mapped_column(String(80), default="prospect")
    expected_deal_value: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_status: Mapped[str] = mapped_column(String(50), default="proposed")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RetentionAutomationAction(Base):
    __tablename__ = "retention_automation_actions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    retention_action: Mapped[str] = mapped_column(String(120), nullable=False)
    target_segment: Mapped[str] = mapped_column(String(200), nullable=False)
    cohort_key: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    expected_incremental_value: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_status: Mapped[str] = mapped_column(String(50), default="proposed")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RecoveryEscalation(Base):
    __tablename__ = "recovery_escalations"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    incident_type: Mapped[str] = mapped_column(String(120), nullable=False)
    escalation_requirement: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), default="medium")
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    related_autonomous_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("autonomous_runs.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(50), default="open")
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SelfHealingAction(Base):
    __tablename__ = "self_healing_actions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    recovery_escalation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recovery_escalations.id"), nullable=True, index=True
    )
    incident_type: Mapped[str] = mapped_column(String(120), nullable=False)
    action_taken: Mapped[str] = mapped_column(String(200), nullable=False)
    action_mode: Mapped[str] = mapped_column(String(50), default="guarded")
    escalation_requirement: Mapped[str] = mapped_column(String(80), default="none")
    expected_mitigation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_status: Mapped[str] = mapped_column(String(50), default="proposed")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
