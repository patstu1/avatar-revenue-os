"""Expansion Pack 2 Phase A: lead qualification, closer actions, owned offer recommendations."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class LeadOpportunity(Base):
    __tablename__ = "lead_opportunities"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    lead_source: Mapped[str] = mapped_column(String(80), default="")
    message_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    urgency_score: Mapped[float] = mapped_column(Float, default=0.0)
    budget_proxy_score: Mapped[float] = mapped_column(Float, default=0.0)
    sophistication_score: Mapped[float] = mapped_column(Float, default=0.0)
    offer_fit_score: Mapped[float] = mapped_column(Float, default=0.0)
    trust_readiness_score: Mapped[float] = mapped_column(Float, default=0.0)
    composite_score: Mapped[float] = mapped_column(Float, default=0.0)
    qualification_tier: Mapped[str] = mapped_column(String(20), default="cold")
    sales_stage: Mapped[str] = mapped_column(String(30), default="new_lead", index=True)
    client_stage: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)
    package_slug: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    recommended_action: Mapped[str] = mapped_column(String(80), default="")
    expected_value: Mapped[float] = mapped_column(Float, default=0.0)
    likelihood_to_close: Mapped[float] = mapped_column(Float, default=0.0)
    channel_preference: Mapped[str] = mapped_column(String(50), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CloserAction(Base):
    __tablename__ = "closer_actions"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    lead_opportunity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lead_opportunities.id"), nullable=True, index=True
    )
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    channel: Mapped[str] = mapped_column(String(30), default="")
    subject_or_opener: Mapped[str] = mapped_column(String(500), default="")
    timing: Mapped[str] = mapped_column(String(30), default="24h")
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class LeadQualificationReport(Base):
    __tablename__ = "lead_qualification_reports"

    __table_args__ = (UniqueConstraint("brand_id", name="uq_lead_qual_brand"),)

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    total_leads_scored: Mapped[int] = mapped_column(Integer, default=0)
    hot_leads: Mapped[int] = mapped_column(Integer, default=0)
    warm_leads: Mapped[int] = mapped_column(Integer, default=0)
    cold_leads: Mapped[int] = mapped_column(Integer, default=0)
    avg_composite_score: Mapped[float] = mapped_column(Float, default=0.0)
    avg_expected_value: Mapped[float] = mapped_column(Float, default=0.0)
    top_channel: Mapped[str] = mapped_column(String(50), default="")
    top_recommended_action: Mapped[str] = mapped_column(String(80), default="")
    signal_summary: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OwnedOfferRecommendation(Base):
    __tablename__ = "owned_offer_recommendations"

    __table_args__ = (
        UniqueConstraint("brand_id", "opportunity_key", name="uq_owned_offer_brand_key"),
    )

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    opportunity_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(String(80), nullable=False)
    detected_signal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended_offer_type: Mapped[str] = mapped_column(String(80), default="")
    offer_name_suggestion: Mapped[str] = mapped_column(String(500), default="")
    price_point_min: Mapped[float] = mapped_column(Float, default=0.0)
    price_point_max: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_demand_score: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_first_month_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    audience_fit: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    build_priority: Mapped[str] = mapped_column(String(20), default="medium")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
