"""Offer Lab — offer development, variants, pricing, bundles, upsells, learning."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class OfferLabOffer(Base):
    __tablename__ = "ol_offers"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    source_offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("offers.id"), nullable=True)
    offer_name: Mapped[str] = mapped_column(String(500), nullable=False)
    offer_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    audience_segment: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    problem_solved: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    value_promise: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    primary_angle: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    secondary_angle: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    trust_requirement: Mapped[str] = mapped_column(String(20), default="medium")
    risk_level: Mapped[str] = mapped_column(String(20), default="low")
    price_point: Mapped[float] = mapped_column(Float, default=0.0)
    margin_estimate: Mapped[float] = mapped_column(Float, default=0.0)
    monetization_method: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    platform_fit: Mapped[float] = mapped_column(Float, default=0.5)
    funnel_stage_fit: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    content_form_fit: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    expected_upside: Mapped[float] = mapped_column(Float, default=0.0)
    expected_cost: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    rank_score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    truth_label: Mapped[str] = mapped_column(String(40), default="recommendation_only")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OfferLabVariant(Base):
    __tablename__ = "ol_variants"
    offer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ol_offers.id"), nullable=False, index=True)
    variant_type: Mapped[str] = mapped_column(String(40), nullable=False)
    variant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    angle: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    price_point: Mapped[float] = mapped_column(Float, default=0.0)
    value_promise: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_control: Mapped[bool] = mapped_column(Boolean, default=False)
    performance_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OfferLabPricingTest(Base):
    __tablename__ = "ol_pricing_tests"
    offer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ol_offers.id"), nullable=False, index=True)
    test_price: Mapped[float] = mapped_column(Float, nullable=False)
    control_price: Mapped[float] = mapped_column(Float, nullable=False)
    conversion_at_test: Mapped[float] = mapped_column(Float, default=0.0)
    conversion_at_control: Mapped[float] = mapped_column(Float, default=0.0)
    revenue_at_test: Mapped[float] = mapped_column(Float, default=0.0)
    revenue_at_control: Mapped[float] = mapped_column(Float, default=0.0)
    winner: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OfferLabPositioningTest(Base):
    __tablename__ = "ol_positioning_tests"
    offer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ol_offers.id"), nullable=False, index=True)
    test_angle: Mapped[str] = mapped_column(String(60), nullable=False)
    control_angle: Mapped[str] = mapped_column(String(60), nullable=False)
    test_conversion: Mapped[float] = mapped_column(Float, default=0.0)
    control_conversion: Mapped[float] = mapped_column(Float, default=0.0)
    winner: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OfferLabBundle(Base):
    __tablename__ = "ol_bundles"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    bundle_name: Mapped[str] = mapped_column(String(255), nullable=False)
    offer_ids: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    combined_price: Mapped[float] = mapped_column(Float, default=0.0)
    savings_pct: Mapped[float] = mapped_column(Float, default=0.0)
    expected_uplift: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OfferLabUpsell(Base):
    __tablename__ = "ol_upsells"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    primary_offer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ol_offers.id"), nullable=False)
    upsell_offer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ol_offers.id"), nullable=False)
    upsell_type: Mapped[str] = mapped_column(String(20), default="upsell")
    expected_take_rate: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OfferLabDownsell(Base):
    __tablename__ = "ol_downsells"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    primary_offer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ol_offers.id"), nullable=False)
    downsell_offer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ol_offers.id"), nullable=False)
    expected_save_rate: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OfferLabCrossSell(Base):
    __tablename__ = "ol_cross_sells"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    source_offer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ol_offers.id"), nullable=False)
    cross_offer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ol_offers.id"), nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OfferLabBlocker(Base):
    __tablename__ = "ol_blockers"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("ol_offers.id"), nullable=True)
    blocker_type: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OfferLabLearning(Base):
    __tablename__ = "ol_learning"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    offer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ol_offers.id"), nullable=False, index=True)
    learning_type: Mapped[str] = mapped_column(String(40), nullable=False)
    measured_metric: Mapped[str] = mapped_column(String(60), nullable=False)
    measured_value: Mapped[float] = mapped_column(Float, default=0.0)
    previous_value: Mapped[float] = mapped_column(Float, default=0.0)
    insight: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
