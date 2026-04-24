"""Pydantic models for Growth Commander APIs."""
from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field


class GrowthCommandResponse(BaseModel):
    id: str
    command_type: str
    priority: int = 50
    title: str
    exact_instruction: str
    rationale: Optional[str] = None
    comparison: Optional[dict[str, Any]] = None
    platform_fit: Optional[dict[str, Any]] = None
    niche_fit: Optional[dict[str, Any]] = None
    monetization_path: Optional[dict[str, Any]] = None
    cannibalization_analysis: Optional[dict[str, Any]] = None
    success_threshold: Optional[dict[str, Any]] = None
    failure_threshold: Optional[dict[str, Any]] = None
    expected_upside: float = 0.0
    expected_cost: float = 0.0
    expected_time_to_signal_days: int = 14
    expected_time_to_profit_days: int = 60
    confidence: float = 0.0
    confidence_score: Optional[float] = None
    urgency: float = 0.0
    urgency_score: Optional[float] = None
    blocking_factors: Optional[list] = None
    first_week_plan: Optional[list] = None
    linked_launch_candidate_id: Optional[str] = None
    linked_scale_recommendation_id: Optional[str] = None
    evidence: Optional[dict[str, Any]] = None
    execution_spec: Optional[dict[str, Any]] = None
    required_resources: Optional[dict[str, Any]] = None
    required_resources_json: Optional[dict[str, Any]] = None
    command_priority: Optional[int] = None
    action_deadline: Optional[str] = None
    platform: Optional[str] = None
    account_type: Optional[str] = None
    niche: Optional[str] = None
    sub_niche: Optional[str] = None
    persona_strategy_json: Optional[dict[str, Any]] = None
    monetization_strategy_json: Optional[dict[str, Any]] = None
    output_requirements_json: Optional[dict[str, Any]] = None
    success_threshold_json: Optional[dict[str, Any]] = None
    failure_threshold_json: Optional[dict[str, Any]] = None
    expected_revenue_min: Optional[float] = None
    expected_revenue_max: Optional[float] = None
    risk_score: Optional[float] = None
    blockers_json: Optional[list] = None
    explanation_json: Optional[dict[str, Any]] = None
    consequence_if_ignored_json: Optional[dict[str, Any]] = None
    status: Optional[str] = None
    created_at: Optional[str] = None


class PortfolioAssessmentResponse(BaseModel):
    balance: dict[str, Any] = Field(default_factory=dict)
    whitespace: list[dict[str, Any]] = Field(default_factory=list)
    latest_portfolio_directive: Optional[dict[str, Any]] = None


class GrowthCommandRunResponse(BaseModel):
    id: str
    created_at: str
    status: str = "completed"
    commands_generated: int = 0
    command_types: list[str] = Field(default_factory=list)
    portfolio_balance_snapshot: dict[str, Any] = Field(default_factory=dict)
    whitespace_count: int = 0
    error_message: Optional[str] = None
    triggered_by_user_id: Optional[str] = None
    portfolio_directive: Optional[dict[str, Any]] = None
