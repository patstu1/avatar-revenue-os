"""Pydantic response schemas for the Growth Pack / Portfolio Launch APIs."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class PortfolioLaunchPlanOut(BaseModel):
    id: str | None = None
    brand_id: str | None = None
    recommended_total_account_count: int = 0
    recommended_platform_mix_json: Any | None = None
    recommended_launch_order_json: Any | None = None
    recommended_role_mix_json: Any | None = None
    estimated_first_90_day_cost: float = 0.0
    expected_first_90_day_revenue_min: float = 0.0
    expected_first_90_day_revenue_max: float = 0.0
    confidence_score: float = 0.0
    explanation_json: Any | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AccountLaunchBlueprintOut(BaseModel):
    id: str | None = None
    brand_id: str | None = None
    platform: str = ""
    account_type: str = ""
    niche: str = ""
    sub_niche: str | None = None
    avatar_id: str | None = None
    persona_strategy_json: Any | None = None
    monetization_strategy_json: Any | None = None
    content_role: str | None = None
    first_30_content_plan_json: Any | None = None
    first_offer_stack_json: Any | None = None
    first_cta_strategy_json: Any | None = None
    first_owned_audience_strategy_json: Any | None = None
    success_criteria_json: Any | None = None
    failure_criteria_json: Any | None = None
    expected_cost: float = 0.0
    expected_time_to_signal_days: int = 21
    confidence_score: float = 0.0
    explanation_json: Any | None = None
    created_at: str | None = None
    updated_at: str | None = None


class PlatformAllocationReportOut(BaseModel):
    id: str | None = None
    brand_id: str | None = None
    platform: str = ""
    recommended_account_count: int = 0
    current_account_count: int = 0
    expansion_priority: int = 50
    rationale_json: Any | None = None
    expected_upside: float = 0.0
    confidence_score: float = 0.0
    created_at: str | None = None
    updated_at: str | None = None


class NicheDeploymentReportOut(BaseModel):
    id: str | None = None
    brand_id: str | None = None
    niche: str = ""
    sub_niche: str | None = None
    recommended_account_role: str = "growth"
    recommended_platform: str = "youtube"
    expected_upside: float = 0.0
    saturation_risk: float = 0.0
    cannibalization_risk: float = 0.0
    confidence_score: float = 0.0
    explanation_json: Any | None = None
    created_at: str | None = None
    updated_at: str | None = None


class GrowthPackBlockerReportOut(BaseModel):
    id: str | None = None
    brand_id: str | None = None
    blocker_type: str = ""
    severity: str = ""
    affected_scope_type: str = "brand"
    affected_scope_id: str | None = None
    reason: str = ""
    recommended_fix: str = ""
    expected_impact_json: Any | None = None
    confidence_score: float = 0.0
    urgency_score: float = 0.0
    created_at: str | None = None
    updated_at: str | None = None


class CapitalDeploymentPlanOut(BaseModel):
    id: str | None = None
    brand_id: str | None = None
    total_budget: float = 0.0
    platform_budget_mix_json: Any | None = None
    account_budget_mix_json: Any | None = None
    content_budget_mix_json: Any | None = None
    funnel_budget_mix_json: Any | None = None
    paid_budget_mix_json: Any | None = None
    holdback_budget: float = 0.0
    explanation_json: Any | None = None
    confidence_score: float = 0.0
    created_at: str | None = None
    updated_at: str | None = None


class CrossAccountCannibalizationReportOut(BaseModel):
    id: str | None = None
    brand_id: str | None = None
    account_a_id: str | None = None
    account_b_id: str | None = None
    overlap_score: float = 0.0
    audience_overlap_score: float = 0.0
    topic_overlap_score: float = 0.0
    monetization_overlap_score: float = 0.0
    risk_level: str = "low"
    recommendation_json: Any | None = None
    created_at: str | None = None
    updated_at: str | None = None


class PortfolioOutputReportOut(BaseModel):
    id: str | None = None
    brand_id: str | None = None
    total_output_recommendation: int = 0
    per_platform_output_json: Any | None = None
    per_account_output_json: Any | None = None
    duplication_risk_score: float = 0.0
    saturation_risk_score: float = 0.0
    throttle_recommendation_json: Any | None = None
    created_at: str | None = None
    updated_at: str | None = None


class RecomputeSummaryOut(BaseModel):
    status: str
    detail: str
    counts: dict[str, Any] | None = None
