"""Winning-Pattern Memory — reusable strategic memory layer."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class WinningPatternMemory(Base):
    __tablename__ = "winning_pattern_memory"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    pattern_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    pattern_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    pattern_signature: Mapped[str] = mapped_column(String(500), nullable=False)
    platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    niche: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    sub_niche: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content_form: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("offers.id"), nullable=True)
    monetization_method: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, index=True)
    performance_band: Mapped[str] = mapped_column(String(20), default="standard", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    win_score: Mapped[float] = mapped_column(Float, default=0.0)
    decay_score: Mapped[float] = mapped_column(Float, default=0.0)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class WinningPatternEvidence(Base):
    __tablename__ = "winning_pattern_evidence"

    pattern_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("winning_pattern_memory.id"), nullable=False, index=True)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True, index=True)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    saves: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    watch_time_seconds: Mapped[int] = mapped_column(Integer, default=0)
    conversion_rate: Mapped[float] = mapped_column(Float, default=0.0)
    epc: Mapped[float] = mapped_column(Float, default=0.0)
    aov: Mapped[float] = mapped_column(Float, default=0.0)
    profit: Mapped[float] = mapped_column(Float, default=0.0)
    revenue_density: Mapped[float] = mapped_column(Float, default=0.0)
    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class WinningPatternCluster(Base):
    __tablename__ = "winning_pattern_clusters"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    cluster_name: Mapped[str] = mapped_column(String(255), nullable=False)
    cluster_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    pattern_ids: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    avg_win_score: Mapped[float] = mapped_column(Float, default=0.0)
    pattern_count: Mapped[int] = mapped_column(Integer, default=0)
    platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class LosingPatternMemory(Base):
    __tablename__ = "losing_pattern_memory"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    pattern_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    pattern_name: Mapped[str] = mapped_column(String(255), nullable=False)
    pattern_signature: Mapped[str] = mapped_column(String(500), nullable=False)
    platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    fail_score: Mapped[float] = mapped_column(Float, default=0.0)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    suppress_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PatternReuseRecommendation(Base):
    __tablename__ = "pattern_reuse_recommendations"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    pattern_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("winning_pattern_memory.id"), nullable=False, index=True)
    target_platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_content_form: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    expected_uplift: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PatternDecayReport(Base):
    __tablename__ = "pattern_decay_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    pattern_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("winning_pattern_memory.id"), nullable=False, index=True)
    decay_rate: Mapped[float] = mapped_column(Float, default=0.0)
    decay_reason: Mapped[str] = mapped_column(String(120), nullable=False)
    previous_win_score: Mapped[float] = mapped_column(Float, default=0.0)
    current_win_score: Mapped[float] = mapped_column(Float, default=0.0)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
