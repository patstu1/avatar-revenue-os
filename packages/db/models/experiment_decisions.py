"""Experiment decision and outcome models — A/B test prioritisation and promotion/suppression."""

import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class ExperimentDecision(Base):
    __tablename__ = "experiment_decisions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    experiment_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_scope_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    hypothesis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_upside: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_gap: Mapped[float] = mapped_column(Float, default=0.0)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_allocation: Mapped[float] = mapped_column(Float, default=0.10)
    promotion_rule_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    suppression_rule_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    explanation_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="proposed")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ExperimentOutcome(Base):
    __tablename__ = "experiment_outcomes"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    experiment_decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiment_decisions.id"), nullable=False, index=True
    )
    observation_source: Mapped[str] = mapped_column(String(40), default="synthetic_proxy", nullable=False)
    outcome_type: Mapped[str] = mapped_column(String(50), nullable=False)
    winner_variant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    loser_variant_ids_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    observed_uplift: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_next_action: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    explanation_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class ExperimentOutcomeAction(Base):
    """Execution-ready downstream actions derived from an experiment outcome (operator queue)."""

    __tablename__ = "experiment_outcome_actions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    experiment_outcome_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("experiment_outcomes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    execution_status: Mapped[str] = mapped_column(String(40), default="pending_operator", nullable=False)
    structured_payload_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    operator_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
