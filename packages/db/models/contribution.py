"""Contribution and attribution models — multi-touch attribution reports."""

import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class ContributionReport(Base):
    __tablename__ = "contribution_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    attribution_model: Mapped[str] = mapped_column(String(100), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(100), nullable=False)
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    estimated_contribution_value: Mapped[float] = mapped_column(Float, default=0.0)
    contribution_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    caveats_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    explanation_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AttributionModelRun(Base):
    __tablename__ = "attribution_model_runs"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    model_type: Mapped[str] = mapped_column(String(100), nullable=False)
    scope_definition_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    summary_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
