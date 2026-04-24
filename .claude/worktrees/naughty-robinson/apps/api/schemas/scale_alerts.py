"""Pydantic models for scale alerts APIs."""
from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field

class AlertResponse(BaseModel):
    id: str
    alert_type: str
    title: str
    summary: str
    explanation: Optional[str] = None
    recommended_action: Optional[str] = None
    confidence: float = 0.0
    urgency: float = 0.0
    expected_upside: float = 0.0
    expected_cost: float = 0.0
    expected_time_to_signal_days: int = 14
    supporting_metrics: Optional[dict[str, Any]] = None
    blocking_factors: Optional[list] = None
    severity: Optional[str] = None
    dashboard_section: Optional[str] = None
    linked_scale_recommendation_id: Optional[str] = None
    linked_launch_candidate_id: Optional[str] = None
    status: str = "unread"
    acknowledged_at: Optional[str] = None
    resolved_at: Optional[str] = None
    created_at: Optional[str] = None

class LaunchCandidateResponse(BaseModel):
    id: str
    linked_scale_recommendation_id: Optional[str] = None
    candidate_type: str
    primary_platform: str
    secondary_platform: Optional[str] = None
    niche: str
    sub_niche: Optional[str] = None
    language: str = "en"
    geography: str = "US"
    avatar_persona_strategy: Optional[str] = None
    monetization_path: Optional[str] = None
    content_style: Optional[str] = None
    posting_strategy: Optional[str] = None
    expected_monthly_revenue_min: float = 0.0
    expected_monthly_revenue_max: float = 0.0
    expected_launch_cost: float = 0.0
    expected_time_to_signal_days: int = 30
    expected_time_to_profit_days: int = 90
    cannibalization_risk: float = 0.0
    audience_separation_score: float = 0.0
    confidence: float = 0.0
    urgency: float = 0.0
    supporting_reasons: Optional[list] = None
    required_resources: Optional[list] = None
    launch_blockers: Optional[list] = None

class BlockerResponse(BaseModel):
    id: str
    blocker_type: str
    severity: str = "medium"
    title: str
    explanation: Optional[str] = None
    recommended_fix: Optional[str] = None
    current_value: float = 0.0
    threshold_value: float = 0.0

class ReadinessResponse(BaseModel):
    id: str
    launch_readiness_score: float = 0.0
    explanation: Optional[str] = None
    recommended_action: str = "monitor"
    gating_factors: Optional[list] = None
    components: Optional[dict[str, Any]] = None

class NotificationResponse(BaseModel):
    id: str
    alert_id: Optional[str] = None
    channel: str
    status: str = "pending"
    attempts: int = 0
    last_error: Optional[str] = None
    delivered_at: Optional[str] = None

class ResolveRequest(BaseModel):
    notes: Optional[str] = None
