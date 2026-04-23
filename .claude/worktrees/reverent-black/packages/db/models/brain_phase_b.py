"""Brain Architecture Pack — Phase B tables: decisions, policies, confidence, cost/upside, arbitration."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class BrainDecision(Base):
    __tablename__ = "brain_decisions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    decision_class: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    target_scope: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    target_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    selected_action: Mapped[str] = mapped_column(Text, nullable=False)
    alternatives_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    policy_mode: Mapped[str] = mapped_column(String(30), default="guarded", index=True)
    expected_upside: Mapped[float] = mapped_column(Float, default=0.0)
    expected_cost: Mapped[float] = mapped_column(Float, default=0.0)
    downstream_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    inputs_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PolicyEvaluation(Base):
    __tablename__ = "policy_evaluations"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    decision_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brain_decisions.id"), nullable=True, index=True)
    action_ref: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    policy_mode: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    approval_needed: Mapped[bool] = mapped_column(Boolean, default=False)
    hard_stop_rule: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rollback_rule: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    cost_impact: Mapped[float] = mapped_column(Float, default=0.0)
    inputs_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ConfidenceReport(Base):
    __tablename__ = "confidence_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    decision_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brain_decisions.id"), nullable=True, index=True)
    scope_label: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_band: Mapped[str] = mapped_column(String(30), default="medium")
    signal_strength: Mapped[float] = mapped_column(Float, default=0.0)
    historical_precedent: Mapped[float] = mapped_column(Float, default=0.0)
    saturation_risk: Mapped[float] = mapped_column(Float, default=0.0)
    memory_support: Mapped[float] = mapped_column(Float, default=0.0)
    data_completeness: Mapped[float] = mapped_column(Float, default=0.0)
    execution_history: Mapped[float] = mapped_column(Float, default=0.0)
    blocker_severity: Mapped[float] = mapped_column(Float, default=0.0)
    uncertainty_factors_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class UpsideCostEstimate(Base):
    __tablename__ = "upside_cost_estimates"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    decision_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brain_decisions.id"), nullable=True, index=True)
    scope_label: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    expected_upside: Mapped[float] = mapped_column(Float, default=0.0)
    expected_cost: Mapped[float] = mapped_column(Float, default=0.0)
    expected_payback_days: Mapped[int] = mapped_column(Integer, default=0)
    operational_burden: Mapped[float] = mapped_column(Float, default=0.0)
    concentration_risk: Mapped[float] = mapped_column(Float, default=0.0)
    net_value: Mapped[float] = mapped_column(Float, default=0.0)
    inputs_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ArbitrationReport(Base):
    __tablename__ = "arbitration_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    ranked_priorities_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    chosen_winner_class: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    chosen_winner_label: Mapped[str] = mapped_column(Text, nullable=False)
    rejected_actions_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    competing_count: Mapped[int] = mapped_column(Integer, default=0)
    net_value_chosen: Mapped[float] = mapped_column(Float, default=0.0)
    inputs_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
