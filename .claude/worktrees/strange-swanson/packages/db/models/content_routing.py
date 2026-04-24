"""Content Routing — routing decisions and cost tracking."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class ContentRoutingDecision(Base):
    __tablename__ = "content_routing_decisions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    content_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    quality_tier: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    routed_provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    is_promoted: Mapped[bool] = mapped_column(Boolean, default=False)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    actual_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    success: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ContentRoutingCostReport(Base):
    __tablename__ = "content_routing_cost_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    report_date: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    total_decisions: Mapped[int] = mapped_column(Integer, default=0)
    by_provider: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    by_tier: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    by_content_type: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
