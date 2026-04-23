"""Capacity and queue allocation models — production throughput and throttle decisions."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class CapacityReport(Base):
    __tablename__ = "capacity_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    capacity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    current_capacity: Mapped[float] = mapped_column(Float, default=0.0)
    used_capacity: Mapped[float] = mapped_column(Float, default=0.0)
    constrained_scope_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    recommended_volume: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_throttle: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    expected_profit_impact: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    explanation_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class QueueAllocationDecision(Base):
    __tablename__ = "queue_allocation_decisions"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    queue_name: Mapped[str] = mapped_column(String(100), nullable=False)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    allocated_capacity: Mapped[float] = mapped_column(Float, default=0.0)
    deferred_capacity: Mapped[float] = mapped_column(Float, default=0.0)
    reason_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
