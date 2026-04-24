"""QA reports, similarity reports, approval workflow."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.enums import ApprovalStatus, QAStatus


class QAReport(Base):
    __tablename__ = "qa_reports"

    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    qa_status: Mapped[QAStatus] = mapped_column(Enum(QAStatus), nullable=False, index=True)
    originality_score: Mapped[float] = mapped_column(Float, default=0.0)
    compliance_score: Mapped[float] = mapped_column(Float, default=0.0)
    brand_alignment_score: Mapped[float] = mapped_column(Float, default=0.0)
    technical_quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    audio_quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    visual_quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    composite_score: Mapped[float] = mapped_column(Float, default=0.0)
    issues_found: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    recommendations: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    automated_checks: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    explanation: Mapped[Optional[str]] = mapped_column(Text)


class SimilarityReport(Base):
    __tablename__ = "similarity_reports"

    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    compared_against_count: Mapped[int] = mapped_column(Integer, default=0)
    max_similarity_score: Mapped[float] = mapped_column(Float, default=0.0)
    avg_similarity_score: Mapped[float] = mapped_column(Float, default=0.0)
    most_similar_content_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    similarity_details: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    is_too_similar: Mapped[bool] = mapped_column(Boolean, default=False)
    threshold_used: Mapped[float] = mapped_column(Float, default=0.85)
    explanation: Mapped[Optional[str]] = mapped_column(Text)


class Approval(Base):
    __tablename__ = "approvals"

    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    requested_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus), default=ApprovalStatus.PENDING, index=True
    )
    decision_mode: Mapped[str] = mapped_column(String(50), default="guarded_auto")
    auto_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    review_notes: Mapped[Optional[str]] = mapped_column(Text)
    qa_report_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("qa_reports.id")
    )
    similarity_report_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("similarity_reports.id")
    )
    reviewed_at: Mapped[Optional[str]] = mapped_column(String(50))
