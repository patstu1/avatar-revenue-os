"""Opportunity-Cost Ranking — rank actions by what is lost by waiting."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class OpportunityCostReport(Base):
    __tablename__ = "oc_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    total_actions: Mapped[int] = mapped_column(Integer, default=0)
    top_action_type: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    total_opportunity_cost: Mapped[float] = mapped_column(Float, default=0.0)
    safe_to_wait_count: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RankedAction(Base):
    __tablename__ = "oc_ranked_actions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("oc_reports.id"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    action_key: Mapped[str] = mapped_column(String(255), nullable=False)
    target_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    expected_upside: Mapped[float] = mapped_column(Float, default=0.0)
    cost_of_delay: Mapped[float] = mapped_column(Float, default=0.0)
    urgency: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    composite_rank: Mapped[float] = mapped_column(Float, default=0.0)
    rank_position: Mapped[int] = mapped_column(Integer, default=0)
    safe_to_wait: Mapped[bool] = mapped_column(Boolean, default=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CostOfDelayModel(Base):
    __tablename__ = "oc_cost_of_delay"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(60), nullable=False)
    action_key: Mapped[str] = mapped_column(String(255), nullable=False)
    daily_cost: Mapped[float] = mapped_column(Float, default=0.0)
    weekly_cost: Mapped[float] = mapped_column(Float, default=0.0)
    decay_rate: Mapped[float] = mapped_column(Float, default=0.0)
    time_sensitivity: Mapped[str] = mapped_column(String(20), default="normal")
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
