"""Portfolio allocations, scale recs, capital allocation, expansion, paid amp, roadmap."""
import uuid
from typing import Any, Optional

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.enums import ConfidenceLevel, JobStatus, RecommendedAction


class PortfolioAllocation(Base):
    __tablename__ = "portfolio_allocations"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("account_portfolios.id"), nullable=False, index=True
    )
    creator_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creator_accounts.id"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    allocation_pct: Mapped[float] = mapped_column(Float, default=0.0)
    budget_allocated: Mapped[float] = mapped_column(Float, default=0.0)
    posting_capacity_allocated: Mapped[int] = mapped_column(Integer, default=0)
    expected_roi: Mapped[float] = mapped_column(Float, default=0.0)
    actual_roi: Mapped[float] = mapped_column(Float, default=0.0)
    rationale: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[ConfidenceLevel] = mapped_column(
        Enum(ConfidenceLevel), default=ConfidenceLevel.MEDIUM
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ScaleRecommendation(Base):
    __tablename__ = "scale_recommendations"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    creator_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creator_accounts.id"), index=True
    )
    recommended_action: Mapped[RecommendedAction] = mapped_column(
        Enum(RecommendedAction), nullable=False
    )
    # Phase 5: canonical recommendation key (e.g. scale_current_winners_harder)
    recommendation_key: Mapped[str] = mapped_column(String(80), default="monitor", nullable=False, index=True)
    incremental_profit_new_account: Mapped[float] = mapped_column(Float, default=0.0)
    incremental_profit_existing_push: Mapped[float] = mapped_column(Float, default=0.0)
    comparison_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    scale_readiness_score: Mapped[float] = mapped_column(Float, default=0.0)
    cannibalization_risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    audience_segment_separation: Mapped[float] = mapped_column(Float, default=0.0)
    expansion_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_account_count: Mapped[int] = mapped_column(Integer, default=2)
    weekly_action_plan: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    best_next_account: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    score_components: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    penalties: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[ConfidenceLevel] = mapped_column(
        Enum(ConfidenceLevel), default=ConfidenceLevel.MEDIUM
    )
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    is_actioned: Mapped[bool] = mapped_column(Boolean, default=False)


class CapitalAllocationRecommendation(Base):
    __tablename__ = "capital_allocation_recommendations"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    allocation_target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    allocation_target_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    current_allocation_pct: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_allocation_pct: Mapped[float] = mapped_column(Float, default=0.0)
    expected_marginal_roi: Mapped[float] = mapped_column(Float, default=0.0)
    rationale: Mapped[Optional[str]] = mapped_column(Text)
    inputs_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[ConfidenceLevel] = mapped_column(
        Enum(ConfidenceLevel), default=ConfidenceLevel.MEDIUM
    )
    is_actioned: Mapped[bool] = mapped_column(Boolean, default=False)


class RevenuLeakReport(Base):
    __tablename__ = "revenue_leak_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    leak_type: Mapped[str] = mapped_column(String(100), nullable=False)
    affected_entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    affected_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    estimated_leaked_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_recoverable: Mapped[float] = mapped_column(Float, default=0.0)
    root_cause: Mapped[Optional[str]] = mapped_column(Text)
    recommended_fix: Mapped[Optional[str]] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(50), default="medium")
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)


class GeoLanguageExpansionRecommendation(Base):
    __tablename__ = "geo_language_expansion_recommendations"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    target_geography: Mapped[str] = mapped_column(String(100), nullable=False)
    target_language: Mapped[str] = mapped_column(String(50), nullable=False)
    target_platform: Mapped[Optional[str]] = mapped_column(String(50))
    estimated_audience_size: Mapped[int] = mapped_column(Integer, default=0)
    estimated_revenue_potential: Mapped[float] = mapped_column(Float, default=0.0)
    competition_level: Mapped[Optional[str]] = mapped_column(String(50))
    entry_cost_estimate: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[ConfidenceLevel] = mapped_column(
        Enum(ConfidenceLevel), default=ConfidenceLevel.MEDIUM
    )
    rationale: Mapped[Optional[str]] = mapped_column(Text)
    is_actioned: Mapped[bool] = mapped_column(Boolean, default=False)


class TrustSignalReport(Base):
    """Phase 6: persisted trust & authority scoring per account (or brand rollup)."""

    __tablename__ = "trust_signal_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    creator_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creator_accounts.id"), index=True
    )
    trust_score: Mapped[float] = mapped_column(Float, default=0.0)
    components: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    recommendations: Mapped[Any] = mapped_column(JSONB, default=list)
    evidence: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    confidence_label: Mapped[str] = mapped_column(String(20), default="medium")


class PaidAmplificationJob(Base):
    __tablename__ = "paid_amplification_jobs"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=False, index=True
    )
    creator_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creator_accounts.id"), index=True
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    budget: Mapped[float] = mapped_column(Float, default=0.0)
    spent: Mapped[float] = mapped_column(Float, default=0.0)
    target_audience_config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)
    results: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    roi: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    is_candidate: Mapped[bool] = mapped_column(Boolean, default=False)


class RoadmapRecommendation(Base):
    __tablename__ = "roadmap_recommendations"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_impact_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_effort: Mapped[str] = mapped_column(String(50), default="medium")
    confidence: Mapped[ConfidenceLevel] = mapped_column(
        Enum(ConfidenceLevel), default=ConfidenceLevel.MEDIUM
    )
    inputs_used: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_actioned: Mapped[bool] = mapped_column(Boolean, default=False)
    rationale: Mapped[Optional[str]] = mapped_column(Text)


class MonetizationRecommendation(Base):
    __tablename__ = "monetization_recommendations"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), index=True
    )
    recommendation_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    expected_revenue_uplift: Mapped[float] = mapped_column(Float, default=0.0)
    expected_cost: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_actioned: Mapped[bool] = mapped_column(Boolean, default=False)
