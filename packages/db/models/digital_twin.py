"""Digital Twin / Simulation Layer — simulate decisions before execution."""

import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class SimulationRun(Base):
    __tablename__ = "dt_simulation_runs"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    run_name: Mapped[str] = mapped_column(String(255), nullable=False)
    scenario_count: Mapped[int] = mapped_column(Integer, default=0)
    best_scenario_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    total_expected_upside: Mapped[float] = mapped_column(Float, default=0.0)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SimulationScenario(Base):
    __tablename__ = "dt_scenarios"
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dt_simulation_runs.id"), nullable=False, index=True
    )
    scenario_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    option_label: Mapped[str] = mapped_column(String(255), nullable=False)
    compared_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    expected_upside: Mapped[float] = mapped_column(Float, default=0.0)
    expected_cost: Mapped[float] = mapped_column(Float, default=0.0)
    expected_risk: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    time_to_signal_days: Mapped[int] = mapped_column(Integer, default=14)
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SimulationAssumption(Base):
    __tablename__ = "dt_assumptions"
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dt_scenarios.id"), nullable=False, index=True
    )
    assumption_key: Mapped[str] = mapped_column(String(120), nullable=False)
    assumption_value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SimulationOutcome(Base):
    __tablename__ = "dt_outcomes"
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dt_scenarios.id"), nullable=False, index=True
    )
    metric: Mapped[str] = mapped_column(String(60), nullable=False)
    predicted_value: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    risk_adjusted_value: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SimulationRecommendation(Base):
    __tablename__ = "dt_recommendations"
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dt_simulation_runs.id"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    scenario_type: Mapped[str] = mapped_column(String(60), nullable=False)
    expected_profit_delta: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    missing_evidence: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
