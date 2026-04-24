"""Expansion Pack 2 Phase B: pricing, bundling, retention, reactivation."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class PricingRecommendation(Base):
    __tablename__ = "pricing_recommendations"

    __table_args__ = (UniqueConstraint("brand_id", "offer_id", name="uq_pricing_brand_offer"),)

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    offer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("offers.id"), nullable=False, index=True)
    recommendation_type: Mapped[str] = mapped_column(String(80), nullable=False)
    current_price: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_price: Mapped[float] = mapped_column(Float, default=0.0)
    price_elasticity: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_revenue_impact: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BundleRecommendation(Base):
    __tablename__ = "bundle_recommendations"

    __table_args__ = (UniqueConstraint("brand_id", "bundle_name", name="uq_bundle_brand_name"),)

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    bundle_name: Mapped[str] = mapped_column(String(255), nullable=False)
    offer_ids: Mapped[list[uuid.UUID]] = mapped_column(JSONB, default=list)
    recommended_bundle_price: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_upsell_rate: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_revenue_impact: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RetentionRecommendation(Base):
    __tablename__ = "retention_recommendations"

    __table_args__ = (UniqueConstraint("brand_id", "customer_segment", name="uq_retention_brand_segment"),)

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    customer_segment: Mapped[str] = mapped_column(String(255), nullable=False)
    recommendation_type: Mapped[str] = mapped_column(String(80), nullable=False)
    action_details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    estimated_retention_lift: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ReactivationCampaign(Base):
    __tablename__ = "reactivation_campaigns"

    __table_args__ = (UniqueConstraint("brand_id", "campaign_name", name="uq_reactivation_brand_campaign"),)

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    campaign_name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_segment: Mapped[str] = mapped_column(String(255), nullable=False)
    campaign_type: Mapped[str] = mapped_column(String(80), nullable=False)
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    estimated_reactivation_rate: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_revenue_impact: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
