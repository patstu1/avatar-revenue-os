"""Cinema Studio: projects, scenes, characters, style presets, generations."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class StudioProject(Base):
    __tablename__ = "studio_projects"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    genre: Mapped[str] = mapped_column(String(100), default="drama")
    status: Mapped[str] = mapped_column(String(50), default="draft")
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1024))
    offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("offers.id"), index=True
    )
    target_platform: Mapped[Optional[str]] = mapped_column(String(50))


class StudioScene(Base):
    __tablename__ = "studio_scenes"

    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("studio_projects.id", ondelete="SET NULL"), index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    negative_prompt: Mapped[Optional[str]] = mapped_column(Text)
    camera_shot: Mapped[str] = mapped_column(String(50), default="medium")
    camera_movement: Mapped[str] = mapped_column(String(50), default="static")
    lighting: Mapped[str] = mapped_column(String(50), default="natural")
    mood: Mapped[str] = mapped_column(String(50), default="cinematic")
    style_preset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("style_presets.id"), index=True
    )
    duration_seconds: Mapped[float] = mapped_column(Float, default=5.0)
    aspect_ratio: Mapped[str] = mapped_column(String(20), default="16:9")
    character_ids: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1024))


class CharacterBible(Base):
    __tablename__ = "character_bibles"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    gender: Mapped[str] = mapped_column(String(50), default="other")
    age: Mapped[Optional[int]] = mapped_column(Integer)
    ethnicity: Mapped[Optional[str]] = mapped_column(String(100))
    hair_color: Mapped[Optional[str]] = mapped_column(String(50))
    hair_style: Mapped[Optional[str]] = mapped_column(String(100))
    eye_color: Mapped[Optional[str]] = mapped_column(String(50))
    build: Mapped[Optional[str]] = mapped_column(String(100))
    personality: Mapped[Optional[str]] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(100), default="supporting")
    image_url: Mapped[Optional[str]] = mapped_column(String(1024))
    tags: Mapped[Optional[list]] = mapped_column(JSONB, default=list)


class StylePreset(Base):
    __tablename__ = "style_presets"

    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="cinematic")
    preview_url: Mapped[Optional[str]] = mapped_column(String(1024))
    tags: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    is_popular: Mapped[bool] = mapped_column(Boolean, default=False)


class StudioGeneration(Base):
    __tablename__ = "studio_generations"

    scene_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("studio_scenes.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    media_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_jobs.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(50), default="pending")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    video_url: Mapped[Optional[str]] = mapped_column(String(1024))
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1024))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(100), default="runway")
    seed: Mapped[Optional[int]] = mapped_column(Integer)
    steps: Mapped[int] = mapped_column(Integer, default=50)
    guidance: Mapped[float] = mapped_column(Float, default=7.5)
    duration_seconds: Mapped[float] = mapped_column(Float, default=5.0)


class StudioActivity(Base):
    __tablename__ = "studio_activity"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    activity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_name: Mapped[str] = mapped_column(String(500), nullable=False)
    activity_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, default=dict)
