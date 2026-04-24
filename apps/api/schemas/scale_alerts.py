"""Pydantic models for scale alerts APIs."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class AlertResponse(BaseModel):
    id: str
    alert_type: str
    title: str
    summary: str
    explanation: str | None = None
    recommended_action: str | None = None
    confidence: float = 0.0
    urgency: float = 0.0
    expected_upside: float = 0.0
    expected_cost: float = 0.0
    expected_time_to_signal_days: int = 14
    supporting_metrics: dict[str, Any] | None = None
    blocking_factors: list | None = None
    severity: str | None = None
    dashboard_section: str | None = None
    linked_scale_recommendation_id: str | None = None
    linked_launch_candidate_id: str | None = None
    status: str = "unread"
    acknowledged_at: str | None = None
    resolved_at: str | None = None
    created_at: str | None = None

class LaunchCandidateResponse(BaseModel):
    id: str
    linked_scale_recommendation_id: str | None = None
    candidate_type: str
    primary_platform: str
    secondary_platform: str | None = None
    niche: str
    sub_niche: str | None = None
    language: str = "en"
    geography: str = "US"
    avatar_persona_strategy: str | None = None
    monetization_path: str | None = None
    content_style: str | None = None
    posting_strategy: str | None = None
    expected_monthly_revenue_min: float = 0.0
    expected_monthly_revenue_max: float = 0.0
    expected_launch_cost: float = 0.0
    expected_time_to_signal_days: int = 30
    expected_time_to_profit_days: int = 90
    cannibalization_risk: float = 0.0
    audience_separation_score: float = 0.0
    confidence: float = 0.0
    urgency: float = 0.0
    supporting_reasons: list | None = None
    required_resources: list | None = None
    launch_blockers: list | None = None

class BlockerResponse(BaseModel):
    id: str
    blocker_type: str
    severity: str = "medium"
    title: str
    explanation: str | None = None
    recommended_fix: str | None = None
    current_value: float = 0.0
    threshold_value: float = 0.0

class ReadinessResponse(BaseModel):
    id: str
    launch_readiness_score: float = 0.0
    explanation: str | None = None
    recommended_action: str = "monitor"
    gating_factors: list | None = None
    components: dict[str, Any] | None = None

class NotificationResponse(BaseModel):
    id: str
    alert_id: str | None = None
    channel: str
    status: str = "pending"
    attempts: int = 0
    last_error: str | None = None
    delivered_at: str | None = None

class ResolveRequest(BaseModel):
    notes: str | None = None
