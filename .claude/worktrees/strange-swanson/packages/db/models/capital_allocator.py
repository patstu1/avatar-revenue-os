"""Portfolio Capital Allocator — active resource allocation system."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class CapitalAllocationReport(Base):
    __tablename__ = "ca_allocation_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    total_budget: Mapped[float] = mapped_column(Float, default=0.0)
    allocated_budget: Mapped[float] = mapped_column(Float, default=0.0)
    experiment_reserve: Mapped[float] = mapped_column(Float, default=0.0)
    hero_spend: Mapped[float] = mapped_column(Float, default=0.0)
    bulk_spend: Mapped[float] = mapped_column(Float, default=0.0)
    target_count: Mapped[int] = mapped_column(Integer, default=0)
    starved_count: Mapped[int] = mapped_column(Integer, default=0)
    summary_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AllocationTarget(Base):
    __tablename__ = "ca_allocation_targets"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ca_allocation_reports.id"), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    target_key: Mapped[str] = mapped_column(String(255), nullable=False)
    target_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    expected_return: Mapped[float] = mapped_column(Float, default=0.0)
    expected_cost: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    account_health: Mapped[float] = mapped_column(Float, default=1.0)
    fatigue_score: Mapped[float] = mapped_column(Float, default=0.0)
    pattern_win_score: Mapped[float] = mapped_column(Float, default=0.0)
    provider_tier: Mapped[str] = mapped_column(String(20), default="bulk")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CAAllocationDecision(Base):
    __tablename__ = "ca_allocation_decisions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ca_allocation_reports.id"), nullable=False, index=True)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ca_allocation_targets.id"), nullable=False, index=True)
    allocated_budget: Mapped[float] = mapped_column(Float, default=0.0)
    allocated_volume: Mapped[int] = mapped_column(Integer, default=0)
    provider_tier: Mapped[str] = mapped_column(String(20), default="bulk")
    allocation_pct: Mapped[float] = mapped_column(Float, default=0.0)
    starved: Mapped[bool] = mapped_column(Boolean, default=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CAAllocationConstraint(Base):
    __tablename__ = "ca_allocation_constraints"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    constraint_type: Mapped[str] = mapped_column(String(60), nullable=False)
    constraint_key: Mapped[str] = mapped_column(String(255), nullable=False)
    min_value: Mapped[float] = mapped_column(Float, default=0.0)
    max_value: Mapped[float] = mapped_column(Float, default=1.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CAAllocationRebalance(Base):
    __tablename__ = "ca_allocation_rebalances"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ca_allocation_reports.id"), nullable=False, index=True)
    rebalance_reason: Mapped[str] = mapped_column(String(120), nullable=False)
    changes_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    targets_starved: Mapped[int] = mapped_column(Integer, default=0)
    targets_boosted: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
