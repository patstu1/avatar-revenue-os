"""Brain Architecture Pack — Phase D tables: meta-monitoring, self-correction, readiness, escalation."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class MetaMonitoringReport(Base):
    __tablename__ = "meta_monitoring_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    health_score: Mapped[float] = mapped_column(Float, default=0.0)
    health_band: Mapped[str] = mapped_column(String(30), default="medium", index=True)
    decision_quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_drift_score: Mapped[float] = mapped_column(Float, default=0.0)
    policy_drift_score: Mapped[float] = mapped_column(Float, default=0.0)
    execution_failure_rate: Mapped[float] = mapped_column(Float, default=0.0)
    memory_quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    escalation_rate: Mapped[float] = mapped_column(Float, default=0.0)
    queue_congestion: Mapped[float] = mapped_column(Float, default=0.0)
    dead_agent_count: Mapped[int] = mapped_column(Integer, default=0)
    low_signal_count: Mapped[int] = mapped_column(Integer, default=0)
    wasted_action_count: Mapped[int] = mapped_column(Integer, default=0)
    weak_areas_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    recommended_corrections_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    inputs_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SelfCorrectionAction(Base):
    __tablename__ = "self_correction_actions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    correction_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    effect_target: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(30), default="medium", index=True)
    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    payload_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ReadinessBrainReport(Base):
    __tablename__ = "readiness_brain_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    readiness_score: Mapped[float] = mapped_column(Float, default=0.0)
    readiness_band: Mapped[str] = mapped_column(String(30), default="not_ready", index=True)
    blockers_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    allowed_actions_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    forbidden_actions_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    inputs_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BrainEscalation(Base):
    __tablename__ = "brain_escalations"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    escalation_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    urgency: Mapped[str] = mapped_column(String(30), default="medium", index=True)
    expected_upside_unlocked: Mapped[float] = mapped_column(Float, default=0.0)
    expected_cost_of_delay: Mapped[float] = mapped_column(Float, default=0.0)
    affected_scope: Mapped[str] = mapped_column(String(200), nullable=False)
    supporting_data_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
