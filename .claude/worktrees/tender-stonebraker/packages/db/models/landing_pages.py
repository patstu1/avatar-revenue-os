"""Landing Page Engine — create, version, score, route monetization pages."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class LandingPage(Base):
    __tablename__ = "lp_pages"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    page_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("offers.id"), nullable=True)
    monetization_target: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    subheadline: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    hook_angle: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    proof_blocks: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    objection_blocks: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    cta_blocks: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    disclosure_blocks: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    media_blocks: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    tracking_params: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    destination_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    publish_status: Mapped[str] = mapped_column(String(30), default="unpublished")
    truth_label: Mapped[str] = mapped_column(String(40), default="recommendation_only")
    performance_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    blocker_state: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class LandingPageVariant(Base):
    __tablename__ = "lp_variants"

    page_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lp_pages.id"), nullable=False, index=True)
    variant_label: Mapped[str] = mapped_column(String(120), nullable=False)
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    subheadline: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    hook_angle: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    cta_blocks: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    is_control: Mapped[bool] = mapped_column(Boolean, default=False)
    conversion_rate: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class LandingPageBlock(Base):
    __tablename__ = "lp_blocks"

    page_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lp_pages.id"), nullable=False, index=True)
    block_type: Mapped[str] = mapped_column(String(40), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    content_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class LandingPageQualityReport(Base):
    __tablename__ = "lp_quality_reports"

    page_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lp_pages.id"), nullable=False, index=True)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    trust_score: Mapped[float] = mapped_column(Float, default=0.0)
    conversion_fit: Mapped[float] = mapped_column(Float, default=0.0)
    objection_coverage: Mapped[float] = mapped_column(Float, default=0.0)
    verdict: Mapped[str] = mapped_column(String(10), default="unscored")
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class LandingPagePublishRecord(Base):
    __tablename__ = "lp_publish_records"

    page_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lp_pages.id"), nullable=False, index=True)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    published_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    publish_method: Mapped[str] = mapped_column(String(40), default="manual")
    truth_label: Mapped[str] = mapped_column(String(40), default="recommendation_only")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
