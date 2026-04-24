"""Opportunity scoring, profit forecasts, offer fit, recommendations, saturation."""

import uuid
from typing import Optional

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.enums import ConfidenceLevel, RecommendedAction, SignalClassification


class OpportunityScore(Base):
    __tablename__ = "opportunity_scores"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    topic_candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topic_candidates.id"), nullable=False, index=True
    )
    composite_score: Mapped[float] = mapped_column(Float, nullable=False)
    trend_score: Mapped[float] = mapped_column(Float, default=0.0)
    audience_fit_score: Mapped[float] = mapped_column(Float, default=0.0)
    monetization_score: Mapped[float] = mapped_column(Float, default=0.0)
    competition_score: Mapped[float] = mapped_column(Float, default=0.0)
    originality_score: Mapped[float] = mapped_column(Float, default=0.0)
    saturation_penalty: Mapped[float] = mapped_column(Float, default=0.0)
    fatigue_penalty: Mapped[float] = mapped_column(Float, default=0.0)
    score_components: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    formula_version: Mapped[str] = mapped_column(String(50), default="v1")
    confidence: Mapped[ConfidenceLevel] = mapped_column(Enum(ConfidenceLevel), default=ConfidenceLevel.MEDIUM)
    explanation: Mapped[Optional[str]] = mapped_column(Text)


class ProfitForecast(Base):
    __tablename__ = "profit_forecasts"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    topic_candidate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topic_candidates.id"), index=True
    )
    offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("offers.id"), index=True)
    creator_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creator_accounts.id"), index=True
    )
    estimated_impressions: Mapped[int] = mapped_column(Integer, default=0)
    estimated_ctr: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_conversion_rate: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_profit: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_rpm: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_epc: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[ConfidenceLevel] = mapped_column(Enum(ConfidenceLevel), default=ConfidenceLevel.MEDIUM)
    assumptions: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    formula_version: Mapped[str] = mapped_column(String(50), default="v1")
    explanation: Mapped[Optional[str]] = mapped_column(Text)


class OfferFitScore(Base):
    __tablename__ = "offer_fit_scores"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    offer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("offers.id"), nullable=False, index=True)
    topic_candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topic_candidates.id"), nullable=False, index=True
    )
    fit_score: Mapped[float] = mapped_column(Float, nullable=False)
    audience_alignment: Mapped[float] = mapped_column(Float, default=0.0)
    intent_match: Mapped[float] = mapped_column(Float, default=0.0)
    friction_score: Mapped[float] = mapped_column(Float, default=0.0)
    repeatability_score: Mapped[float] = mapped_column(Float, default=0.0)
    revenue_potential: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[ConfidenceLevel] = mapped_column(Enum(ConfidenceLevel), default=ConfidenceLevel.MEDIUM)
    explanation: Mapped[Optional[str]] = mapped_column(Text)


class RecommendationQueue(Base):
    __tablename__ = "recommendation_queue"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    topic_candidate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topic_candidates.id"), index=True
    )
    offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("offers.id"), index=True)
    creator_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creator_accounts.id"), index=True
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    composite_score: Mapped[float] = mapped_column(Float, nullable=False)
    profit_forecast_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profit_forecasts.id")
    )
    recommended_action: Mapped[RecommendedAction] = mapped_column(
        Enum(RecommendedAction), default=RecommendedAction.SCALE
    )
    classification: Mapped[SignalClassification] = mapped_column(
        Enum(SignalClassification), default=SignalClassification.MONITOR
    )
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    is_actioned: Mapped[bool] = mapped_column(Boolean, default=False)
    actioned_at: Mapped[Optional[str]] = mapped_column(String(50))


class SaturationReport(Base):
    __tablename__ = "saturation_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    creator_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creator_accounts.id"), index=True
    )
    niche_cluster_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("niche_clusters.id"), index=True
    )
    saturation_score: Mapped[float] = mapped_column(Float, nullable=False)
    fatigue_score: Mapped[float] = mapped_column(Float, default=0.0)
    originality_score: Mapped[float] = mapped_column(Float, default=0.0)
    topic_overlap_pct: Mapped[float] = mapped_column(Float, default=0.0)
    audience_overlap_pct: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_action: Mapped[RecommendedAction] = mapped_column(
        Enum(RecommendedAction), default=RecommendedAction.MONITOR
    )
    details: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
