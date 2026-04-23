"""Async media job tracking — voice, avatar, video, image, music generation.

Tracks every external media generation request from dispatch through
provider callback to pipeline continuation. Provider-agnostic: the
integration_manager decides which provider to use; this model stores the
result regardless of provider.
"""
import uuid
from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class MediaJob(Base):
    __tablename__ = "media_jobs"

    # ── Ownership / context ──────────────────────────────────────────
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    script_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scripts.id"), nullable=True, index=True,
    )
    avatar_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avatars.id"), nullable=True, index=True,
    )

    # ── Job classification ───────────────────────────────────────────
    job_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="voice | avatar | video | image | music",
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="dispatched", index=True,
        comment="dispatched | processing | completed | failed",
    )
    provider: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True,
        comment="Provider key assigned by integration_manager (e.g. heygen, elevenlabs, runway)",
    )
    provider_job_id: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, index=True, unique=True,
        comment="External job/request ID from the provider",
    )

    # ── Payloads ─────────────────────────────────────────────────────
    input_config: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment="Full request payload sent to provider",
    )
    output_config: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment="Full response/callback payload from provider",
    )
    output_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id"), nullable=True,
        comment="Reference to the generated asset",
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_details: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment="Structured error information from provider",
    )

    # ── Retry tracking ───────────────────────────────────────────────
    retries: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, server_default="3", nullable=False)

    # ── Cost & timing ────────────────────────────────────────────────
    cost: Mapped[float] = mapped_column(Float, server_default="0", nullable=False)
    dispatched_at: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    started_at: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    completed_at: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
