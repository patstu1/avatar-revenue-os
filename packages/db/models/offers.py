"""Offer catalog, sponsors, LTV, and audience segment models."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.enums import MonetizationMethod


class Offer(Base):
    __tablename__ = "offers"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    monetization_method: Mapped[MonetizationMethod] = mapped_column(
        Enum(MonetizationMethod), nullable=False, index=True
    )
    offer_url: Mapped[Optional[str]] = mapped_column(String(1024))
    payout_amount: Mapped[float] = mapped_column(Float, default=0.0)
    payout_type: Mapped[str] = mapped_column(String(50), default="cpa")
    epc: Mapped[float] = mapped_column(Float, default=0.0)
    conversion_rate: Mapped[float] = mapped_column(Float, default=0.0)
    cookie_duration_days: Mapped[Optional[int]] = mapped_column(Integer)
    recurring_commission: Mapped[bool] = mapped_column(Boolean, default=False)
    average_order_value: Mapped[float] = mapped_column(Float, default=0.0)
    audience_fit_tags: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    geo_restrictions: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    platform_restrictions: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)


class SponsorProfile(Base):
    __tablename__ = "sponsor_profiles"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    sponsor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    industry: Mapped[Optional[str]] = mapped_column(String(255))
    budget_range_min: Mapped[Optional[float]] = mapped_column(Float)
    budget_range_max: Mapped[Optional[float]] = mapped_column(Float)
    preferred_platforms: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    preferred_content_types: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SponsorOpportunity(Base):
    __tablename__ = "sponsor_opportunities"

    sponsor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sponsor_profiles.id"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    deal_value: Mapped[float] = mapped_column(Float, default=0.0)
    deliverables: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="prospect")
    notes: Mapped[Optional[str]] = mapped_column(Text)


class LtvModel(Base):
    __tablename__ = "ltv_models"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    segment_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_type: Mapped[str] = mapped_column(String(100), default="rules_based")
    parameters: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    estimated_ltv_30d: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_ltv_90d: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_ltv_365d: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    last_trained_at: Mapped[Optional[str]] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AudienceSegment(Base):
    __tablename__ = "audience_segments"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    segment_criteria: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    estimated_size: Mapped[int] = mapped_column(Integer, default=0)
    revenue_contribution: Mapped[float] = mapped_column(Float, default=0.0)
    conversion_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_ltv: Mapped[float] = mapped_column(Float, default=0.0)
    platforms: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
