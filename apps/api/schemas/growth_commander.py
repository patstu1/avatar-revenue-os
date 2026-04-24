"""Pydantic models for Growth Commander APIs."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GrowthCommandResponse(BaseModel):
    id: str
    command_type: str
    priority: int = 50
    title: str
    exact_instruction: str
    rationale: str | None = None
    comparison: dict[str, Any] | None = None
    platform_fit: dict[str, Any] | None = None
    niche_fit: dict[str, Any] | None = None
    monetization_path: dict[str, Any] | None = None
    cannibalization_analysis: dict[str, Any] | None = None
    success_threshold: dict[str, Any] | None = None
    failure_threshold: dict[str, Any] | None = None
    expected_upside: float = 0.0
    expected_cost: float = 0.0
    expected_time_to_signal_days: int = 14
    expected_time_to_profit_days: int = 60
    confidence: float = 0.0
    confidence_score: float | None = None
    urgency: float = 0.0
    urgency_score: float | None = None
    blocking_factors: list | None = None
    first_week_plan: list | None = None
    linked_launch_candidate_id: str | None = None
    linked_scale_recommendation_id: str | None = None
    evidence: dict[str, Any] | None = None
    execution_spec: dict[str, Any] | None = None
    required_resources: dict[str, Any] | None = None
    required_resources_json: dict[str, Any] | None = None
    command_priority: int | None = None
    action_deadline: str | None = None
    platform: str | None = None
    account_type: str | None = None
    niche: str | None = None
    sub_niche: str | None = None
    persona_strategy_json: dict[str, Any] | None = None
    monetization_strategy_json: dict[str, Any] | None = None
    output_requirements_json: dict[str, Any] | None = None
    success_threshold_json: dict[str, Any] | None = None
    failure_threshold_json: dict[str, Any] | None = None
    expected_revenue_min: float | None = None
    expected_revenue_max: float | None = None
    risk_score: float | None = None
    blockers_json: list | None = None
    explanation_json: dict[str, Any] | None = None
    consequence_if_ignored_json: dict[str, Any] | None = None
    status: str | None = None
    created_at: str | None = None


class PortfolioAssessmentResponse(BaseModel):
    balance: dict[str, Any] = Field(default_factory=dict)
    whitespace: list[dict[str, Any]] = Field(default_factory=list)
    latest_portfolio_directive: dict[str, Any] | None = None


class GrowthCommandRunResponse(BaseModel):
    id: str
    created_at: str
    status: str = "completed"
    commands_generated: int = 0
    command_types: list[str] = Field(default_factory=list)
    portfolio_balance_snapshot: dict[str, Any] = Field(default_factory=dict)
    whitespace_count: int = 0
    error_message: str | None = None
    triggered_by_user_id: str | None = None
    portfolio_directive: dict[str, Any] | None = None
