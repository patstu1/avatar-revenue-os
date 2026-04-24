"""Canonical decision objects — persisted records of every automated decision."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.enums import ActorType, ConfidenceLevel, DecisionMode, DecisionType, RecommendedAction


class _DecisionBase(Base):
    """Abstract base for all decision types. Not mapped to a table."""

    __abstract__ = True

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    decision_type: Mapped[DecisionType] = mapped_column(Enum(DecisionType), nullable=False, index=True)
    decision_mode: Mapped[DecisionMode] = mapped_column(Enum(DecisionMode), default=DecisionMode.GUARDED_AUTO)
    actor_type: Mapped[ActorType] = mapped_column(Enum(ActorType), default=ActorType.SYSTEM)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))

    input_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    formulas_used: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    score_components: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    penalties: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    thresholds_applied: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    composite_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[ConfidenceLevel] = mapped_column(Enum(ConfidenceLevel), default=ConfidenceLevel.MEDIUM)
    recommended_action: Mapped[RecommendedAction] = mapped_column(
        Enum(RecommendedAction), default=RecommendedAction.MONITOR
    )
    explanation: Mapped[Optional[str]] = mapped_column(Text)

    downstream_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    downstream_action_taken: Mapped[Optional[str]] = mapped_column(String(255))

    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class OpportunityDecision(_DecisionBase):
    __tablename__ = "opportunity_decisions"

    topic_candidate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topic_candidates.id"), index=True
    )
    opportunity_score_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunity_scores.id")
    )


class MonetizationDecision(_DecisionBase):
    __tablename__ = "monetization_decisions"

    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), index=True
    )
    offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("offers.id"), index=True)
    direct_revenue_estimate: Mapped[float] = mapped_column(Float, default=0.0)
    conversion_rate_estimate: Mapped[float] = mapped_column(Float, default=0.0)
    friction_score: Mapped[float] = mapped_column(Float, default=0.0)
    audience_fit_score: Mapped[float] = mapped_column(Float, default=0.0)
    repeatability_score: Mapped[float] = mapped_column(Float, default=0.0)
    ltv_estimate: Mapped[float] = mapped_column(Float, default=0.0)


class PublishDecision(_DecisionBase):
    __tablename__ = "publish_decisions"

    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), index=True
    )
    creator_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creator_accounts.id"), index=True
    )
    publish_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("publish_jobs.id"))


class SuppressionDecision(_DecisionBase):
    __tablename__ = "suppression_decisions"

    target_entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    suppression_reason: Mapped[str] = mapped_column(String(100), nullable=False)
    suppression_duration_hours: Mapped[Optional[int]] = mapped_column()
    is_permanent: Mapped[bool] = mapped_column(default=False)


class ScaleDecision(_DecisionBase):
    __tablename__ = "scale_decisions"

    creator_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creator_accounts.id"), index=True
    )
    incremental_profit_new: Mapped[float] = mapped_column(Float, default=0.0)
    incremental_profit_existing: Mapped[float] = mapped_column(Float, default=0.0)
    comparison_ratio: Mapped[float] = mapped_column(Float, default=0.0)


class AllocationDecision(_DecisionBase):
    __tablename__ = "allocation_decisions"

    portfolio_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("account_portfolios.id"), index=True
    )
    allocation_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    rebalance_actions: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)


class ExpansionDecision(_DecisionBase):
    __tablename__ = "expansion_decisions"

    expansion_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_geography: Mapped[Optional[str]] = mapped_column(String(100))
    target_language: Mapped[Optional[str]] = mapped_column(String(50))
    target_platform: Mapped[Optional[str]] = mapped_column(String(50))
    estimated_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
