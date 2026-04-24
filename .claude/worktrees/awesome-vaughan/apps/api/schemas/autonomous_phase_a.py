"""Schemas — Autonomous Execution Phase A: signal scanning, auto-queue, warmup & output."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class SignalScanRunOut(BaseModel):
    id: str
    brand_id: str
    scan_type: str
    status: str
    signals_detected: int
    signals_actionable: int
    scan_duration_ms: Optional[int] = None
    scan_metadata_json: Optional[Any] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class NormalizedSignalEventOut(BaseModel):
    id: str
    brand_id: str
    scan_run_id: Optional[str] = None
    signal_type: str
    signal_source: str
    normalized_title: str
    normalized_description: Optional[str] = None
    freshness_score: float
    monetization_relevance: float
    urgency_score: float
    confidence: float
    explanation: Optional[str] = None
    is_actionable: bool
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AutoQueueItemOut(BaseModel):
    id: str
    brand_id: str
    signal_event_id: Optional[str] = None
    queue_item_type: str
    target_account_id: Optional[str] = None
    target_account_role: Optional[str] = None
    platform: str
    niche: str
    sub_niche: Optional[str] = None
    content_family: Optional[str] = None
    monetization_path: Optional[str] = None
    priority_score: float
    urgency_score: float
    queue_status: str
    suppression_flags_json: Optional[Any] = None
    hold_reason: Optional[str] = None
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AccountWarmupPlanOut(BaseModel):
    id: str
    brand_id: str
    account_id: str
    platform: str
    warmup_phase: str
    initial_posts_per_week: int
    current_posts_per_week: int
    target_posts_per_week: Optional[int] = None
    warmup_start_date: Optional[datetime] = None
    warmup_end_date: Optional[datetime] = None
    engagement_target: float
    trust_target: float
    content_mix_json: Optional[Any] = None
    failure_signals_json: Optional[Any] = None
    ramp_conditions_json: Optional[Any] = None
    confidence: float
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AccountOutputReportOut(BaseModel):
    id: str
    brand_id: str
    account_id: str
    platform: str
    current_output_per_week: float
    recommended_output_per_week: float
    max_safe_output_per_week: float
    max_profitable_output_per_week: float
    throttle_reason: Optional[str] = None
    next_increase_date: Optional[datetime] = None
    quality_score: float
    monetization_response_score: float
    account_health_score: float
    saturation_score: float
    confidence: float
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AccountMaturityReportOut(BaseModel):
    id: str
    brand_id: str
    account_id: str
    platform: str
    maturity_state: str
    previous_state: Optional[str] = None
    days_in_current_state: int
    posts_published: int
    avg_engagement_rate: float
    follower_velocity: float
    health_score: float
    transition_reason: Optional[str] = None
    next_expected_transition: Optional[str] = None
    confidence: float
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PlatformWarmupPolicyOut(BaseModel):
    id: str
    platform: str
    initial_posts_per_week_min: int
    initial_posts_per_week_max: int
    warmup_duration_weeks_min: int
    warmup_duration_weeks_max: int
    steady_state_posts_per_week_min: int
    steady_state_posts_per_week_max: int
    max_safe_posts_per_day: int
    ramp_conditions_json: Optional[Any] = None
    account_health_signals_json: Optional[Any] = None
    spam_risk_signals_json: Optional[Any] = None
    trust_risk_signals_json: Optional[Any] = None
    scale_ready_conditions_json: Optional[Any] = None
    ramp_behavior: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OutputRampEventOut(BaseModel):
    id: str
    brand_id: str
    account_id: str
    platform: str
    event_type: str
    from_output_per_week: float
    to_output_per_week: float
    trigger_reason: Optional[str] = None
    confidence: float
    explanation: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RecomputeSummaryOut(BaseModel):
    status: str
    detail: Optional[str] = None
    counts: Optional[Any] = None
