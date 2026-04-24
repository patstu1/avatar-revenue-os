"""Autonomous Content Farm models — niche scores, warmup plans, fleet status, voice profiles."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class NicheScore(Base):
    """Scored niche + platform combination for content farm targeting."""
    __tablename__ = "af_niche_scores"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    niche: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    composite_score: Mapped[float] = mapped_column(Float, default=0.0)
    monetization_score: Mapped[float] = mapped_column(Float, default=0.0)
    opportunity_score: Mapped[float] = mapped_column(Float, default=0.0)
    trend_velocity: Mapped[float] = mapped_column(Float, default=0.0)
    competition: Mapped[float] = mapped_column(Float, default=0.0)
    avg_cpm: Mapped[float] = mapped_column(Float, default=0.0)
    affiliate_density: Mapped[float] = mapped_column(Float, default=0.0)
    evergreen: Mapped[bool] = mapped_column(Boolean, default=False)
    keywords: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AccountWarmupPlan(Base):
    """Warmup plan for a specific creator account."""
    __tablename__ = "af_warmup_plans"

    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("creator_accounts.id"), nullable=False, index=True)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    current_phase: Mapped[str] = mapped_column(String(30), default="seed")
    age_days: Mapped[int] = mapped_column(Integer, default=0)
    max_posts_per_day: Mapped[int] = mapped_column(Integer, default=0)
    monetization_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    shadow_ban_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    shadow_ban_severity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    cooldown_until: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    posts_today: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class FleetStatusReport(Base):
    """Periodic fleet status snapshot across all accounts."""
    __tablename__ = "af_fleet_reports"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    total_accounts: Mapped[int] = mapped_column(Integer, default=0)
    accounts_warming: Mapped[int] = mapped_column(Integer, default=0)
    accounts_scaling: Mapped[int] = mapped_column(Integer, default=0)
    accounts_plateaued: Mapped[int] = mapped_column(Integer, default=0)
    accounts_suspended: Mapped[int] = mapped_column(Integer, default=0)
    accounts_retired: Mapped[int] = mapped_column(Integer, default=0)
    total_posts_today: Mapped[int] = mapped_column(Integer, default=0)
    total_revenue_30d: Mapped[float] = mapped_column(Float, default=0.0)
    expansion_recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    expansion_details: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AccountVoiceProfile(Base):
    """Persistent voice differentiation profile for an account."""
    __tablename__ = "af_voice_profiles"

    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("creator_accounts.id"), nullable=False, index=True, unique=True)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    style: Mapped[str] = mapped_column(String(60), nullable=False)
    vocabulary_level: Mapped[str] = mapped_column(String(30), nullable=False)
    emoji_usage: Mapped[str] = mapped_column(String(20), default="minimal")
    preferred_hook_style: Mapped[str] = mapped_column(String(40), nullable=False)
    cta_style: Mapped[str] = mapped_column(String(40), nullable=False)
    paragraph_style: Mapped[str] = mapped_column(String(40), nullable=False)
    signature_phrases: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    tone_keywords: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    avoid_keywords: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    full_profile: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ContentRepurposeRecord(Base):
    """Tracks repurposed content derivatives."""
    __tablename__ = "af_repurpose_records"

    source_content_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=False, index=True)
    derived_brief_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("content_briefs.id"), nullable=False, index=True)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    target_platform: Mapped[str] = mapped_column(String(60), nullable=False)
    target_content_type: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CompetitorAccount(Base):
    """Competitor account being monitored."""
    __tablename__ = "af_competitor_accounts"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(60), nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    niche: Mapped[str] = mapped_column(String(120), nullable=False)
    follower_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    posting_frequency: Mapped[float] = mapped_column(Float, default=0.0)
    monetization_methods: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    content_gaps: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    last_scanned_at: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class DailyIntelligenceReport(Base):
    """Daily system intelligence summary for operator."""
    __tablename__ = "af_daily_reports"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    report_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    content_created: Mapped[int] = mapped_column(Integer, default=0)
    content_approved: Mapped[int] = mapped_column(Integer, default=0)
    content_published: Mapped[int] = mapped_column(Integer, default=0)
    content_quality_blocked: Mapped[int] = mapped_column(Integer, default=0)
    total_impressions: Mapped[int] = mapped_column(Integer, default=0)
    total_engagement: Mapped[int] = mapped_column(Integer, default=0)
    total_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    top_performing_content: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    niche_performance: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    fleet_status: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    recommendations: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
