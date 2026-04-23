"""Buffer Distribution Layer — 5 tables for Buffer-as-primary social distribution."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.enums import Platform


class BufferProfile(Base):
    """Maps a creator account to a Buffer-connected profile/channel."""
    __tablename__ = "buffer_profiles"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    creator_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("creator_accounts.id"), nullable=True, index=True)
    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False, index=True)
    buffer_profile_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    credential_status: Mapped[str] = mapped_column(String(30), default="not_connected", index=True)
    last_sync_status: Mapped[str] = mapped_column(String(30), default="never", index=True)
    last_sync_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    config_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BufferPublishJob(Base):
    """A single publish handoff to Buffer for a content item / distribution plan entry."""
    __tablename__ = "buffer_publish_jobs"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    buffer_profile_id_fk: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("buffer_profiles.id"), nullable=False, index=True)
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True, index=True)
    distribution_plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("distribution_plans.id"), nullable=True, index=True)
    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False, index=True)
    publish_mode: Mapped[str] = mapped_column(String(30), default="queue", index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    payload_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    buffer_post_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    distributor_name: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)
    distributor_post_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    scheduled_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    published_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BufferPublishAttempt(Base):
    """Tracks each API call attempt to Buffer for a publish job."""
    __tablename__ = "buffer_publish_attempts"

    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("buffer_publish_jobs.id"), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    request_payload_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    response_status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_body_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class BufferStatusSync(Base):
    """Periodic sync of Buffer post statuses back into our system."""
    __tablename__ = "buffer_status_syncs"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    jobs_checked: Mapped[int] = mapped_column(Integer, default=0)
    jobs_updated: Mapped[int] = mapped_column(Integer, default=0)
    jobs_failed: Mapped[int] = mapped_column(Integer, default=0)
    jobs_published: Mapped[int] = mapped_column(Integer, default=0)
    sync_mode: Mapped[str] = mapped_column(String(30), default="pull")
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BufferBlocker(Base):
    """Tracks blockers preventing Buffer distribution for a brand/profile."""
    __tablename__ = "buffer_blockers"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    buffer_profile_id_fk: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("buffer_profiles.id"), nullable=True, index=True)
    blocker_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(30), default="high", index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    operator_action_needed: Mapped[str] = mapped_column(Text, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
