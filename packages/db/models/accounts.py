"""Creator account and portfolio models."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.enums import AccountType, HealthStatus, Platform


class CreatorAccount(Base):
    __tablename__ = "creator_accounts"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    avatar_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("avatars.id"), index=True)
    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False, index=True)
    account_type: Mapped[AccountType] = mapped_column(Enum(AccountType), default=AccountType.ORGANIC)
    platform_username: Mapped[str] = mapped_column(String(255), nullable=False)
    platform_account_id: Mapped[Optional[str]] = mapped_column(String(255))
    niche_focus: Mapped[Optional[str]] = mapped_column(String(255))
    sub_niche_focus: Mapped[Optional[str]] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(10), default="en")
    geography: Mapped[Optional[str]] = mapped_column(String(100))
    monetization_focus: Mapped[Optional[str]] = mapped_column(String(100))

    posting_capacity_per_day: Mapped[int] = mapped_column(Integer, default=1)
    hourly_post_limit: Mapped[int] = mapped_column(
        Integer,
        default=5,
        comment="Max posts per hour for this account. Platform-specific rate limiting.",
    )
    account_health: Mapped[HealthStatus] = mapped_column(Enum(HealthStatus), default=HealthStatus.HEALTHY)
    originality_drift_score: Mapped[float] = mapped_column(Float, default=0.0)
    fatigue_score: Mapped[float] = mapped_column(Float, default=0.0)
    saturation_score: Mapped[float] = mapped_column(Float, default=0.0)

    total_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    total_profit: Mapped[float] = mapped_column(Float, default=0.0)
    profit_per_post: Mapped[float] = mapped_column(Float, default=0.0)
    revenue_per_mille: Mapped[float] = mapped_column(Float, default=0.0)
    ctr: Mapped[float] = mapped_column(Float, default=0.0)
    conversion_rate: Mapped[float] = mapped_column(Float, default=0.0)
    follower_count: Mapped[int] = mapped_column(Integer, default=0)
    follower_growth_rate: Mapped[float] = mapped_column(Float, default=0.0)
    diminishing_returns_score: Mapped[float] = mapped_column(Float, default=0.0)
    cannibalization_risk: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    scale_role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)

    platform_access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    platform_refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    platform_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    platform_external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    credential_status: Mapped[str] = mapped_column(String(30), default="not_connected")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AccountPortfolio(Base):
    __tablename__ = "account_portfolios"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    strategy: Mapped[Optional[str]] = mapped_column(Text)
    total_accounts: Mapped[int] = mapped_column(Integer, default=0)
    total_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    total_profit: Mapped[float] = mapped_column(Float, default=0.0)
    portfolio_health: Mapped[HealthStatus] = mapped_column(Enum(HealthStatus), default=HealthStatus.HEALTHY)
    allocation_config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
