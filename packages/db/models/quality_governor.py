"""Quality Governor — pre-publish content quality control gate."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class QualityGovernorReport(Base):
    __tablename__ = "qg_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    content_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=False, index=True)
    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    verdict: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    publish_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reasons: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class QualityDimensionScore(Base):
    __tablename__ = "qg_dimension_scores"

    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("qg_reports.id"), nullable=False, index=True)
    dimension: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    max_score: Mapped[float] = mapped_column(Float, default=1.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class QualityBlock(Base):
    __tablename__ = "qg_blocks"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    content_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=False, index=True)
    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("qg_reports.id"), nullable=False, index=True)
    block_reason: Mapped[str] = mapped_column(String(120), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="hard")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class QualityImprovementAction(Base):
    __tablename__ = "qg_improvement_actions"

    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("qg_reports.id"), nullable=False, index=True)
    dimension: Mapped[str] = mapped_column(String(40), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
