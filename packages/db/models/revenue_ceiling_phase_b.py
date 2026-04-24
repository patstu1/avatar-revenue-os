"""Revenue Ceiling Phase B: high-ticket, productization, revenue density, upsell."""

import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class HighTicketOpportunity(Base):
    __tablename__ = "high_ticket_opportunities"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    opportunity_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("offers.id"), nullable=True, index=True
    )
    source_content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True, index=True
    )
    eligibility_score: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_offer_path: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    recommended_cta: Mapped[Optional[str]] = mapped_column(Text)
    expected_close_rate_proxy: Mapped[float] = mapped_column(Float, default=0.0)
    expected_deal_value: Mapped[float] = mapped_column(Float, default=0.0)
    expected_profit: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProductOpportunity(Base):
    __tablename__ = "product_opportunities"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    opportunity_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    product_recommendation: Mapped[str] = mapped_column(String(500), default="")
    product_type: Mapped[str] = mapped_column(String(120), default="")
    target_audience: Mapped[Optional[str]] = mapped_column(Text)
    price_range_min: Mapped[float] = mapped_column(Float, default=0.0)
    price_range_max: Mapped[float] = mapped_column(Float, default=0.0)
    expected_launch_value: Mapped[float] = mapped_column(Float, default=0.0)
    expected_recurring_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    build_complexity: Mapped[str] = mapped_column(String(40), default="medium")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RevenueDensityReport(Base):
    __tablename__ = "revenue_density_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=False, index=True
    )
    revenue_per_content_item: Mapped[float] = mapped_column(Float, default=0.0)
    revenue_per_1k_impressions: Mapped[float] = mapped_column(Float, default=0.0)
    profit_per_1k_impressions: Mapped[float] = mapped_column(Float, default=0.0)
    profit_per_audience_member: Mapped[float] = mapped_column(Float, default=0.0)
    monetization_depth_score: Mapped[float] = mapped_column(Float, default=0.0)
    repeat_monetization_score: Mapped[float] = mapped_column(Float, default=0.0)
    ceiling_score: Mapped[float] = mapped_column(Float, default=0.0)
    recommendation: Mapped[Optional[str]] = mapped_column(Text)


class UpsellRecommendation(Base):
    __tablename__ = "upsell_recommendations"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    opportunity_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    anchor_offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("offers.id"), nullable=True, index=True
    )
    anchor_content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True, index=True
    )
    best_next_offer: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    best_timing: Mapped[str] = mapped_column(String(120), default="")
    best_channel: Mapped[str] = mapped_column(String(80), default="")
    expected_take_rate: Mapped[float] = mapped_column(Float, default=0.0)
    expected_incremental_value: Mapped[float] = mapped_column(Float, default=0.0)
    best_upsell_sequencing: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
