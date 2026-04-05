"""Content pipeline: briefs, scripts, variants, assets, media jobs, content items."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.enums import ContentType, JobStatus


class ContentBrief(Base):
    __tablename__ = "content_briefs"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic_candidate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topic_candidates.id"), index=True
    )
    offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("offers.id"), index=True
    )
    creator_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creator_accounts.id"), index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[ContentType] = mapped_column(Enum(ContentType), nullable=False)
    target_platform: Mapped[Optional[str]] = mapped_column(String(50))
    hook: Mapped[Optional[str]] = mapped_column(Text)
    angle: Mapped[Optional[str]] = mapped_column(Text)
    key_points: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    cta_strategy: Mapped[Optional[str]] = mapped_column(Text)
    monetization_integration: Mapped[Optional[str]] = mapped_column(Text)
    target_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    tone_guidance: Mapped[Optional[str]] = mapped_column(Text)
    visual_guidance: Mapped[Optional[str]] = mapped_column(Text)
    seo_keywords: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    brief_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="draft")


class Script(Base):
    __tablename__ = "scripts"

    brief_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_briefs.id"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    hook_text: Mapped[Optional[str]] = mapped_column(Text)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    cta_text: Mapped[Optional[str]] = mapped_column(Text)
    full_script: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    generation_model: Mapped[Optional[str]] = mapped_column(String(100))
    generation_prompt_hash: Mapped[Optional[str]] = mapped_column(String(64))
    generation_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="draft")


class ScriptVariant(Base):
    __tablename__ = "script_variants"

    script_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scripts.id"), nullable=False, index=True
    )
    variant_type: Mapped[str] = mapped_column(String(100), nullable=False)
    variant_label: Mapped[str] = mapped_column(String(255), nullable=False)
    modified_text: Mapped[str] = mapped_column(Text, nullable=False)
    changes_summary: Mapped[Optional[str]] = mapped_column(Text)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False)


class Asset(Base):
    __tablename__ = "assets"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), index=True
    )
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float)
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    storage_provider: Mapped[str] = mapped_column(String(50), default="s3")
    metadata_blob: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)


# MediaJob has been moved to packages.db.models.media_jobs
# Kept here as a re-export for backward compatibility
from packages.db.models.media_jobs import MediaJob  # noqa: F401


class ContentItem(Base):
    __tablename__ = "content_items"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brief_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_briefs.id"), index=True
    )
    script_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scripts.id"), index=True
    )
    creator_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creator_accounts.id"), index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    content_type: Mapped[ContentType] = mapped_column(Enum(ContentType), nullable=False)
    platform: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    tags: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    hashtags: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    thumbnail_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    video_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    monetization_method: Mapped[Optional[str]] = mapped_column(String(50))
    offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("offers.id")
    )
    offer_stack: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    cta_type: Mapped[Optional[str]] = mapped_column(String(60))
    offer_angle: Mapped[Optional[str]] = mapped_column(String(60))
    hook_type: Mapped[Optional[str]] = mapped_column(String(60))
    creative_structure: Mapped[Optional[str]] = mapped_column(String(60))
    audience_response_profile: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    monetization_density_score: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
