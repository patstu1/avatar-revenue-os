"""Async media job tracking — voice, avatar, video, image, music generation.

Tracks every external media generation request from dispatch through
provider callback to pipeline continuation. Provider-agnostic: the
integration_manager decides which provider to use; this model stores the
result regardless of provider.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class MediaJob(Base):
    __tablename__ = "media_jobs"

    # ── Ownership / context ──────────────────────────────────────────
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True, index=True,
    )
    script_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scripts.id"), nullable=True, index=True,
    )

    # ── Job classification ───────────────────────────────────────────
    job_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="voice | avatar | video | image | music",
    )
    provider: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True,
        comment="Provider key assigned by integration_manager (e.g. heygen, elevenlabs, runway)",
    )
    quality_tier: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="standard",
        comment="standard | premium | ultra — drives provider selection",
    )

    # ── Provider tracking ────────────────────────────────────────────
    provider_job_id: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, index=True, unique=True,
        comment="External job/request ID from the provider",
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="dispatched", index=True,
        comment="dispatched | processing | completed | failed",
    )

    # ── Payloads ─────────────────────────────────────────────────────
    input_payload: Mapped[Optional[dict]] = mapped_column(
        JSONB, server_default="'{}'::jsonb", nullable=True,
        comment="Full request payload sent to provider",
    )
    output_payload: Mapped[Optional[dict]] = mapped_column(
        JSONB, server_default="'{}'::jsonb", nullable=True,
        comment="Full response/callback payload from provider",
    )
    output_url: Mapped[Optional[str]] = mapped_column(
        String(2048), nullable=True,
        comment="Direct URL to the generated media asset",
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Timestamps ───────────────────────────────────────────────────
    dispatched_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # ── Retry tracking (informational — NOT a cap) ───────────────────
    retry_count: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)

    # ── Pipeline continuation ────────────────────────────────────────
    next_pipeline_task: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
        comment="Celery task name to fire on completion (e.g. workers.video_worker.tasks.stitch_video)",
    )
    next_pipeline_args: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment="kwargs passed to next_pipeline_task on dispatch",
    )
