"""Trend / Viral Opportunity Engine — continuous opportunity detection."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class TrendSignalEvent(Base):
    __tablename__ = "tv_signals"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    signal_strength: Mapped[float] = mapped_column(Float, default=0.0)
    velocity: Mapped[float] = mapped_column(Float, default=0.0)
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    truth_label: Mapped[str] = mapped_column(String(40), default="internal_proxy")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TrendVelocityReport(Base):
    __tablename__ = "tv_velocity"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    current_velocity: Mapped[float] = mapped_column(Float, default=0.0)
    previous_velocity: Mapped[float] = mapped_column(Float, default=0.0)
    acceleration: Mapped[float] = mapped_column(Float, default=0.0)
    breakout: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ViralOpportunity(Base):
    __tablename__ = "tv_opportunities"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(60), nullable=False)
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    velocity_score: Mapped[float] = mapped_column(Float, default=0.0)
    novelty_score: Mapped[float] = mapped_column(Float, default=0.0)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    revenue_potential_score: Mapped[float] = mapped_column(Float, default=0.0)
    platform_fit_score: Mapped[float] = mapped_column(Float, default=0.0)
    account_fit_score: Mapped[float] = mapped_column(Float, default=0.0)
    content_form_fit_score: Mapped[float] = mapped_column(Float, default=0.0)
    saturation_risk: Mapped[float] = mapped_column(Float, default=0.0)
    compliance_risk: Mapped[float] = mapped_column(Float, default=0.0)
    opportunity_type: Mapped[str] = mapped_column(String(40), default="growth")
    recommended_platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    recommended_account_role: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    recommended_content_form: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    recommended_monetization: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    urgency: Mapped[float] = mapped_column(Float, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    composite_score: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    blocker_state: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    truth_label: Mapped[str] = mapped_column(String(40), default="internal_proxy")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TrendOpportunityScore(Base):
    __tablename__ = "tv_opp_scores"
    opportunity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tv_opportunities.id"), nullable=False, index=True)
    dimension: Mapped[str] = mapped_column(String(40), nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TrendDuplicate(Base):
    __tablename__ = "tv_duplicates"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    original_topic: Mapped[str] = mapped_column(String(500), nullable=False)
    duplicate_topic: Mapped[str] = mapped_column(String(500), nullable=False)
    similarity: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TrendSuppressionRule(Base):
    __tablename__ = "tv_suppressions"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    suppression_type: Mapped[str] = mapped_column(String(40), nullable=False)
    pattern: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TrendBlocker(Base):
    __tablename__ = "tv_blockers"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    opportunity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("tv_opportunities.id"), nullable=True)
    blocker_type: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TrendSourceHealth(Base):
    __tablename__ = "tv_source_health"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="healthy")
    last_signal_count: Mapped[int] = mapped_column(Integer, default=0)
    truth_label: Mapped[str] = mapped_column(String(40), default="internal_proxy")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
