"""Integration Registry — DB-backed encrypted credential storage + provider management.

Replaces .env-first credential management with a real control plane.
Credentials are stored encrypted in PostgreSQL, managed via API,
and loaded at runtime by services that need them.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class IntegrationProvider(Base):
    """A registered API provider with credentials and health status."""
    __tablename__ = "integration_providers"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    # Provider identity
    provider_key: Mapped[str] = mapped_column(
        String(60), nullable=False, index=True,
        comment="claude, gemini_flash, deepseek, groq, openai_image, imagen4, kling, runway, heygen, did, elevenlabs, fish_audio, voxtral, buffer, publer, ayrshare, stripe, serpapi, youtube_analytics, tiktok_analytics, instagram_analytics, smtp, imap"
    )
    provider_name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_category: Mapped[str] = mapped_column(
        String(40), nullable=False, index=True,
        comment="llm, image, video, avatar, voice, music, publishing, analytics, trends, email, inbox, payment"
    )

    # Credentials (encrypted at application layer before storage)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    oauth_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    oauth_refresh_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_config: Mapped[dict | None] = mapped_column(JSONB, default=dict,
        comment="Additional config: webhook_secret, account_id, region, model_name, etc."
    )

    # Status
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    priority_order: Mapped[int] = mapped_column(Integer, default=10,
        comment="Lower = higher priority. Primary=1, secondary=5, fallback=10"
    )

    # Health
    health_status: Mapped[str] = mapped_column(
        String(20), default="unknown",
        comment="healthy, degraded, down, unknown, unconfigured"
    )
    last_health_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_successful_call: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_count_24h: Mapped[int] = mapped_column(Integer, default=0)
    avg_latency_ms: Mapped[float | None] = mapped_column(Float)

    # Usage
    total_calls: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    # Tier routing
    quality_tier: Mapped[str] = mapped_column(
        String(20), default="standard",
        comment="hero, standard, bulk — determines when this provider is used"
    )
    cost_per_unit: Mapped[float] = mapped_column(Float, default=0.0,
        comment="Cost per token/image/second depending on provider type"
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        Index("ix_integration_providers_org_key", "organization_id", "provider_key", unique=True),
        Index("ix_integration_providers_org_cat", "organization_id", "provider_category"),
    )


class CreatorPlatformAccount(Base):
    """A creator's connected platform account with connection status."""
    __tablename__ = "creator_platform_accounts"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    creator_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True,
        comment="FK-less ref to creator_accounts.id"
    )

    # Platform identity
    platform: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    platform_username: Mapped[str | None] = mapped_column(String(200))
    platform_external_id: Mapped[str | None] = mapped_column(String(200))
    platform_url: Mapped[str | None] = mapped_column(String(500))

    # Connection
    connection_status: Mapped[str] = mapped_column(
        String(30), default="disconnected",
        comment="connected, disconnected, expired, error"
    )
    connected_via: Mapped[str | None] = mapped_column(
        String(40), comment="buffer, publer, ayrshare, direct_oauth"
    )
    publishing_profile_id: Mapped[str | None] = mapped_column(
        String(200), comment="Buffer profile ID, Publer account ID, etc."
    )

    # Role
    account_role: Mapped[str] = mapped_column(
        String(30), default="content",
        comment="content, sponsor, engagement, growth, test"
    )
    warmup_state: Mapped[str] = mapped_column(
        String(30), default="active",
        comment="warmup, active, scaling, paused, reduced"
    )
    monetization_role: Mapped[str | None] = mapped_column(
        String(40), comment="affiliate, sponsor, dtc, services, hybrid"
    )
    assigned_niche: Mapped[str | None] = mapped_column(String(100))
    assigned_archetype: Mapped[str | None] = mapped_column(String(60))

    # Metrics
    follower_count: Mapped[int] = mapped_column(Integer, default=0)
    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    posting_frequency: Mapped[str | None] = mapped_column(String(30), comment="daily, 3x_week, weekly, etc.")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        Index("ix_creator_platform_org_brand", "organization_id", "brand_id"),
    )
