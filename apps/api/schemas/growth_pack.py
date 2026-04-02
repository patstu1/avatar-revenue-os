"""Pydantic response schemas for the Growth Pack / Portfolio Launch APIs."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class PortfolioLaunchPlanOut(BaseModel):
    id: Optional[str] = None
    brand_id: Optional[str] = None
    recommended_total_account_count: int = 0
    recommended_platform_mix_json: Optional[Any] = None
    recommended_launch_order_json: Optional[Any] = None
    recommended_role_mix_json: Optional[Any] = None
    estimated_first_90_day_cost: float = 0.0
    expected_first_90_day_revenue_min: float = 0.0
    expected_first_90_day_revenue_max: float = 0.0
    confidence_score: float = 0.0
    explanation_json: Optional[Any] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class AccountLaunchBlueprintOut(BaseModel):
    id: Optional[str] = None
    brand_id: Optional[str] = None
    platform: str = ""
    account_type: str = ""
    niche: str = ""
    sub_niche: Optional[str] = None
    avatar_id: Optional[str] = None
    persona_strategy_json: Optional[Any] = None
    monetization_strategy_json: Optional[Any] = None
    content_role: Optional[str] = None
    first_30_content_plan_json: Optional[Any] = None
    first_offer_stack_json: Optional[Any] = None
    first_cta_strategy_json: Optional[Any] = None
    first_owned_audience_strategy_json: Optional[Any] = None
    success_criteria_json: Optional[Any] = None
    failure_criteria_json: Optional[Any] = None
    expected_cost: float = 0.0
    expected_time_to_signal_days: int = 21
    confidence_score: float = 0.0
    explanation_json: Optional[Any] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PlatformAllocationReportOut(BaseModel):
    id: Optional[str] = None
    brand_id: Optional[str] = None
    platform: str = ""
    recommended_account_count: int = 0
    current_account_count: int = 0
    expansion_priority: int = 50
    rationale_json: Optional[Any] = None
    expected_upside: float = 0.0
    confidence_score: float = 0.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class NicheDeploymentReportOut(BaseModel):
    id: Optional[str] = None
    brand_id: Optional[str] = None
    niche: str = ""
    sub_niche: Optional[str] = None
    recommended_account_role: str = "growth"
    recommended_platform: str = "youtube"
    expected_upside: float = 0.0
    saturation_risk: float = 0.0
    cannibalization_risk: float = 0.0
    confidence_score: float = 0.0
    explanation_json: Optional[Any] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class GrowthPackBlockerReportOut(BaseModel):
    id: Optional[str] = None
    brand_id: Optional[str] = None
    blocker_type: str = ""
    severity: str = ""
    affected_scope_type: str = "brand"
    affected_scope_id: Optional[str] = None
    reason: str = ""
    recommended_fix: str = ""
    expected_impact_json: Optional[Any] = None
    confidence_score: float = 0.0
    urgency_score: float = 0.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CapitalDeploymentPlanOut(BaseModel):
    id: Optional[str] = None
    brand_id: Optional[str] = None
    total_budget: float = 0.0
    platform_budget_mix_json: Optional[Any] = None
    account_budget_mix_json: Optional[Any] = None
    content_budget_mix_json: Optional[Any] = None
    funnel_budget_mix_json: Optional[Any] = None
    paid_budget_mix_json: Optional[Any] = None
    holdback_budget: float = 0.0
    explanation_json: Optional[Any] = None
    confidence_score: float = 0.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CrossAccountCannibalizationReportOut(BaseModel):
    id: Optional[str] = None
    brand_id: Optional[str] = None
    account_a_id: Optional[str] = None
    account_b_id: Optional[str] = None
    overlap_score: float = 0.0
    audience_overlap_score: float = 0.0
    topic_overlap_score: float = 0.0
    monetization_overlap_score: float = 0.0
    risk_level: str = "low"
    recommendation_json: Optional[Any] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PortfolioOutputReportOut(BaseModel):
    id: Optional[str] = None
    brand_id: Optional[str] = None
    total_output_recommendation: int = 0
    per_platform_output_json: Optional[Any] = None
    per_account_output_json: Optional[Any] = None
    duplication_risk_score: float = 0.0
    saturation_risk_score: float = 0.0
    throttle_recommendation_json: Optional[Any] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class RecomputeSummaryOut(BaseModel):
    status: str
    detail: str
    counts: Optional[dict[str, Any]] = None
