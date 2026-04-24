"""Publishing, performance metrics, attribution, signal ingestion."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.enums import JobStatus, Platform


class PublishJob(Base):
    __tablename__ = "publish_jobs"

    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=False, index=True
    )
    creator_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creator_accounts.id"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False, index=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING, index=True)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    platform_post_id: Mapped[Optional[str]] = mapped_column(String(255))
    platform_post_url: Mapped[Optional[str]] = mapped_column(String(1024))
    retries: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_details: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    publish_config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)


class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"

    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True, index=True
    )
    creator_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creator_accounts.id"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False, index=True)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    saves: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    ctr: Mapped[float] = mapped_column(Float, default=0.0)
    watch_time_seconds: Mapped[int] = mapped_column(Integer, default=0)
    avg_watch_pct: Mapped[float] = mapped_column(Float, default=0.0)
    followers_gained: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    revenue_source: Mapped[Optional[str]] = mapped_column(String(50))
    rpm: Mapped[float] = mapped_column(Float, default=0.0)
    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)


class AttributionEvent(Base):
    __tablename__ = "attribution_events"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), index=True
    )
    offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("offers.id"), index=True)
    creator_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creator_accounts.id"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_value: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    platform: Mapped[Optional[str]] = mapped_column(String(50))
    attribution_model: Mapped[str] = mapped_column(String(50), default="last_click")
    attribution_window_hours: Mapped[int] = mapped_column(Integer, default=720)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024))
    tracking_id: Mapped[Optional[str]] = mapped_column(String(255))
    raw_event: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class SignalIngestionRun(Base):
    __tablename__ = "signal_ingestion_runs"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    platform: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)
    records_fetched: Mapped[int] = mapped_column(Integer, default=0)
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    run_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
