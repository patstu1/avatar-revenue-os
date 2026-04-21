"""Expansion Pack 2 Phase C: referral, competitive gap, sponsor sales, profit guardrail."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class ReferralProgramRecommendation(Base):
    __tablename__ = "referral_program_recommendations"

    __table_args__ = (
        UniqueConstraint("brand_id", "customer_segment", name="uq_referral_brand_segment"),
    )

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    customer_segment: Mapped[str] = mapped_column(String(255), nullable=False)
    recommendation_type: Mapped[str] = mapped_column(String(80), nullable=False)
    referral_bonus: Mapped[float] = mapped_column(Float, default=0.0)
    referred_bonus: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_conversion_rate: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_revenue_impact: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CompetitiveGapReport(Base):
    __tablename__ = "competitive_gap_reports"

    __table_args__ = (
        UniqueConstraint("brand_id", "competitor_name", "offer_id", name="uq_gap_brand_competitor_offer"),
    )

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("offers.id"), nullable=True, index=True
    )
    competitor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    gap_type: Mapped[str] = mapped_column(String(80), nullable=False)
    gap_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(80), nullable=False)
    estimated_impact: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SponsorTarget(Base):
    __tablename__ = "sponsor_targets"

    __table_args__ = (
        UniqueConstraint("brand_id", "target_company_name", name="uq_sponsor_brand_company"),
    )

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    target_company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_info: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    estimated_deal_value: Mapped[float] = mapped_column(Float, default=0.0)
    fit_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Batch 10: front-half avenue attribution carried into the outreach
    # stream and onward to Thread/Message/Draft/Proposal.
    avenue_slug: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SponsorOutreachSequence(Base):
    __tablename__ = "sponsor_outreach_sequences"

    __table_args__ = (
        UniqueConstraint("sponsor_target_id", "sequence_name", name="uq_outreach_target_sequence"),
    )

    sponsor_target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sponsor_targets.id"), nullable=False, index=True
    )
    sequence_name: Mapped[str] = mapped_column(String(255), nullable=False)
    steps: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    estimated_response_rate: Mapped[float] = mapped_column(Float, default=0.0)
    expected_value: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Batch 10: avenue carried from the originating SponsorTarget.
    avenue_slug: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProfitGuardrailReport(Base):
    __tablename__ = "profit_guardrail_reports"

    __table_args__ = (
        UniqueConstraint("brand_id", "metric_name", name="uq_guardrail_brand_metric"),
    )

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False)
    current_value: Mapped[float] = mapped_column(Float, default=0.0)
    threshold_value: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    action_recommended: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estimated_impact: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
