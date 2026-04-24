"""Causal Attribution Layer — distinguish signal from noise in performance changes."""

import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class CausalAttributionReport(Base):
    __tablename__ = "ca_attribution_reports"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    target_metric: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    magnitude: Mapped[float] = mapped_column(Float, default=0.0)
    top_driver: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    total_hypotheses: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CausalSignal(Base):
    __tablename__ = "ca_signals"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ca_attribution_reports.id"), nullable=False, index=True
    )
    signal_type: Mapped[str] = mapped_column(String(40), nullable=False)
    scope: Mapped[str] = mapped_column(String(60), nullable=False)
    before_value: Mapped[float] = mapped_column(Float, default=0.0)
    after_value: Mapped[float] = mapped_column(Float, default=0.0)
    change_pct: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CausalHypothesis(Base):
    __tablename__ = "ca_hypotheses"
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ca_attribution_reports.id"), nullable=False, index=True
    )
    driver_type: Mapped[str] = mapped_column(String(60), nullable=False)
    driver_name: Mapped[str] = mapped_column(String(255), nullable=False)
    estimated_lift_pct: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    competing_explanations: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    evidence_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CausalConfidenceReport(Base):
    __tablename__ = "ca_confidence_reports"
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ca_attribution_reports.id"), nullable=False, index=True
    )
    hypothesis_count: Mapped[int] = mapped_column(Integer, default=0)
    high_confidence_count: Mapped[int] = mapped_column(Integer, default=0)
    noise_flagged_count: Mapped[int] = mapped_column(Integer, default=0)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CausalCreditAllocation(Base):
    __tablename__ = "ca_credit_allocations"
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ca_attribution_reports.id"), nullable=False, index=True
    )
    driver_name: Mapped[str] = mapped_column(String(255), nullable=False)
    credit_pct: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    promote_cautiously: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
