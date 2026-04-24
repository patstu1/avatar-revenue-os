"""Topic discovery, niche clusters, trend signals."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.enums import SignalStrength


class TopicSource(Base):
    __tablename__ = "topic_sources"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024))
    source_config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    platform: Mapped[Optional[str]] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_scraped_at: Mapped[Optional[str]] = mapped_column(String(50))


class TopicCandidate(Base):
    __tablename__ = "topic_candidates"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topic_sources.id"), index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    keywords: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    category: Mapped[Optional[str]] = mapped_column(String(255))
    estimated_search_volume: Mapped[int] = mapped_column(Integer, default=0)
    competition_level: Mapped[Optional[str]] = mapped_column(String(50))
    trend_velocity: Mapped[float] = mapped_column(Float, default=0.0)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_rejected: Mapped[bool] = mapped_column(Boolean, default=False)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(255))


class NicheCluster(Base):
    __tablename__ = "niche_clusters"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    cluster_name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_niche: Mapped[Optional[str]] = mapped_column(String(255))
    keywords: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    estimated_audience_size: Mapped[int] = mapped_column(Integer, default=0)
    monetization_potential: Mapped[float] = mapped_column(Float, default=0.0)
    competition_density: Mapped[float] = mapped_column(Float, default=0.0)
    content_gap_score: Mapped[float] = mapped_column(Float, default=0.0)
    saturation_level: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_entry_angle: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TrendSignal(Base):
    __tablename__ = "trend_signals"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    platform: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    signal_type: Mapped[str] = mapped_column(String(100), nullable=False)
    keyword: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    volume: Mapped[int] = mapped_column(Integer, default=0)
    velocity: Mapped[float] = mapped_column(Float, default=0.0)
    strength: Mapped[SignalStrength] = mapped_column(
        Enum(SignalStrength), default=SignalStrength.WEAK
    )
    peak_predicted_at: Mapped[Optional[str]] = mapped_column(String(50))
    metadata_blob: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_actionable: Mapped[bool] = mapped_column(Boolean, default=False)


class TopicSignal(Base):
    __tablename__ = "topic_signals"

    topic_candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topic_candidates.id"), nullable=False, index=True
    )
    trend_signal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trend_signals.id"), index=True
    )
    signal_type: Mapped[str] = mapped_column(String(100), nullable=False)
    signal_value: Mapped[float] = mapped_column(Float, default=0.0)
    signal_source: Mapped[Optional[str]] = mapped_column(String(255))
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
