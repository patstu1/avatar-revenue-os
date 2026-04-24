"""Revenue Ceiling Phase C: recurring revenue, sponsor inventory, trust, monetization mix, paid promotion."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class RecurringRevenueModel(Base):
    __tablename__ = "recurring_revenue_models"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    recurring_potential_score: Mapped[float] = mapped_column(Float, default=0.0)
    best_recurring_offer_type: Mapped[str] = mapped_column(String(120))
    audience_fit: Mapped[float] = mapped_column(Float, default=0.0)
    churn_risk_proxy: Mapped[float] = mapped_column(Float, default=0.0)
    expected_monthly_value: Mapped[float] = mapped_column(Float, default=0.0)
    expected_annual_value: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SponsorInventory(Base):
    __tablename__ = "sponsor_inventory"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True, index=True
    )
    sponsor_fit_score: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_package_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    estimated_package_price: Mapped[float] = mapped_column(Float, default=0.0)
    sponsor_category: Mapped[str] = mapped_column(String(120))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SponsorPackageRecommendation(Base):
    __tablename__ = "sponsor_package_recommendations"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    recommended_package: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    sponsor_fit_score: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_package_price: Mapped[float] = mapped_column(Float, default=0.0)
    sponsor_category: Mapped[str] = mapped_column(String(120), default="general")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TrustConversionReport(Base):
    __tablename__ = "trust_conversion_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    trust_deficit_score: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_proof_blocks: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    missing_trust_elements: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    expected_uplift: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MonetizationMixReport(Base):
    __tablename__ = "monetization_mix_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    current_revenue_mix: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    dependency_risk: Mapped[float] = mapped_column(Float, default=0.0)
    underused_monetization_paths: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    next_best_mix: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    expected_margin_uplift: Mapped[float] = mapped_column(Float, default=0.0)
    expected_ltv_uplift: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PaidPromotionCandidate(Base):
    __tablename__ = "paid_promotion_candidates"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=False, index=True
    )
    organic_winner_evidence: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    gate_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
