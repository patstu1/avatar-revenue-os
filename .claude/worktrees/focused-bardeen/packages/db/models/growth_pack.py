"""Revenue Growth Commander / Portfolio Launch pack — persisted plans and reports."""
import uuid
from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class PortfolioLaunchPlan(Base):
    __tablename__ = "portfolio_launch_plans"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    recommended_total_account_count: Mapped[int] = mapped_column(Integer, default=1)
    recommended_platform_mix_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    recommended_launch_order_json: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    recommended_role_mix_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    estimated_first_90_day_cost: Mapped[float] = mapped_column(Float, default=0.0)
    expected_first_90_day_revenue_min: Mapped[float] = mapped_column(Float, default=0.0)
    expected_first_90_day_revenue_max: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    explanation_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)


class AccountLaunchBlueprint(Base):
    __tablename__ = "account_launch_blueprints"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    account_type: Mapped[str] = mapped_column(String(100), nullable=False)
    niche: Mapped[str] = mapped_column(String(255), nullable=False)
    sub_niche: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("avatars.id"), nullable=True)
    persona_strategy_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    monetization_strategy_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    content_role: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    first_30_content_plan_json: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    first_offer_stack_json: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    first_cta_strategy_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    first_owned_audience_strategy_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    success_criteria_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    failure_criteria_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    expected_cost: Mapped[float] = mapped_column(Float, default=0.0)
    expected_time_to_signal_days: Mapped[int] = mapped_column(Integer, default=21)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    explanation_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)


class PlatformAllocationReport(Base):
    __tablename__ = "platform_allocation_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    recommended_account_count: Mapped[int] = mapped_column(Integer, default=0)
    current_account_count: Mapped[int] = mapped_column(Integer, default=0)
    expansion_priority: Mapped[int] = mapped_column(Integer, default=50, index=True)
    rationale_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    expected_upside: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)


class NicheDeploymentReport(Base):
    __tablename__ = "niche_deployment_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    niche: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sub_niche: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    recommended_account_role: Mapped[str] = mapped_column(String(120), default="growth")
    recommended_platform: Mapped[str] = mapped_column(String(80), default="youtube")
    expected_upside: Mapped[float] = mapped_column(Float, default=0.0)
    saturation_risk: Mapped[float] = mapped_column(Float, default=0.0)
    cannibalization_risk: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    explanation_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)


class GrowthPackBlockerReport(Base):
    """Pack-specific growth blocker rows (distinct from scale_blocker_reports)."""

    __tablename__ = "growth_blocker_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    blocker_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    affected_scope_type: Mapped[str] = mapped_column(String(80), default="brand")
    affected_scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_fix: Mapped[str] = mapped_column(Text, nullable=False)
    expected_impact_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    urgency_score: Mapped[float] = mapped_column(Float, default=0.0)


class CapitalDeploymentPlan(Base):
    __tablename__ = "capital_deployment_plans"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    total_budget: Mapped[float] = mapped_column(Float, default=0.0)
    platform_budget_mix_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    account_budget_mix_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    content_budget_mix_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    funnel_budget_mix_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    paid_budget_mix_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    holdback_budget: Mapped[float] = mapped_column(Float, default=0.0)
    explanation_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)


class CrossAccountCannibalizationReport(Base):
    __tablename__ = "cross_account_cannibalization_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    account_a_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("creator_accounts.id"), nullable=False)
    account_b_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("creator_accounts.id"), nullable=False)
    overlap_score: Mapped[float] = mapped_column(Float, default=0.0)
    audience_overlap_score: Mapped[float] = mapped_column(Float, default=0.0)
    topic_overlap_score: Mapped[float] = mapped_column(Float, default=0.0)
    monetization_overlap_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[str] = mapped_column(String(30), default="low", index=True)
    recommendation_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)


class PortfolioOutputReport(Base):
    __tablename__ = "portfolio_output_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    total_output_recommendation: Mapped[int] = mapped_column(Integer, default=0)
    per_platform_output_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    per_account_output_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    duplication_risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    saturation_risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    throttle_recommendation_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
