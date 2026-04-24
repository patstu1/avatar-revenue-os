"""Schemas — Autonomous Execution Phase A: signal scanning, auto-queue, warmup & output."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SignalScanRunOut(BaseModel):
    id: str
    brand_id: str
    scan_type: str
    status: str
    signals_detected: int
    signals_actionable: int
    scan_duration_ms: int | None = None
    scan_metadata_json: Any | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class NormalizedSignalEventOut(BaseModel):
    id: str
    brand_id: str
    scan_run_id: str | None = None
    signal_type: str
    signal_source: str
    normalized_title: str
    normalized_description: str | None = None
    freshness_score: float
    monetization_relevance: float
    urgency_score: float
    confidence: float
    explanation: str | None = None
    is_actionable: bool
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AutoQueueItemOut(BaseModel):
    id: str
    brand_id: str
    signal_event_id: str | None = None
    queue_item_type: str
    target_account_id: str | None = None
    target_account_role: str | None = None
    platform: str
    niche: str
    sub_niche: str | None = None
    content_family: str | None = None
    monetization_path: str | None = None
    priority_score: float
    urgency_score: float
    queue_status: str
    suppression_flags_json: Any | None = None
    hold_reason: str | None = None
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AccountWarmupPlanOut(BaseModel):
    id: str
    brand_id: str
    account_id: str
    platform: str
    warmup_phase: str
    initial_posts_per_week: int
    current_posts_per_week: int
    target_posts_per_week: int | None = None
    warmup_start_date: datetime | None = None
    warmup_end_date: datetime | None = None
    engagement_target: float
    trust_target: float
    content_mix_json: Any | None = None
    failure_signals_json: Any | None = None
    ramp_conditions_json: Any | None = None
    confidence: float
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AccountOutputReportOut(BaseModel):
    id: str
    brand_id: str
    account_id: str
    platform: str
    current_output_per_week: float
    recommended_output_per_week: float
    max_safe_output_per_week: float
    max_profitable_output_per_week: float
    throttle_reason: str | None = None
    next_increase_date: datetime | None = None
    quality_score: float
    monetization_response_score: float
    account_health_score: float
    saturation_score: float
    confidence: float
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AccountMaturityReportOut(BaseModel):
    id: str
    brand_id: str
    account_id: str
    platform: str
    maturity_state: str
    previous_state: str | None = None
    days_in_current_state: int
    posts_published: int
    avg_engagement_rate: float
    follower_velocity: float
    health_score: float
    transition_reason: str | None = None
    next_expected_transition: str | None = None
    confidence: float
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


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
    ramp_conditions_json: Any | None = None
    account_health_signals_json: Any | None = None
    spam_risk_signals_json: Any | None = None
    trust_risk_signals_json: Any | None = None
    scale_ready_conditions_json: Any | None = None
    ramp_behavior: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class OutputRampEventOut(BaseModel):
    id: str
    brand_id: str
    account_id: str
    platform: str
    event_type: str
    from_output_per_week: float
    to_output_per_week: float
    trigger_reason: str | None = None
    confidence: float
    explanation: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RecomputeSummaryOut(BaseModel):
    status: str
    detail: str | None = None
    counts: Any | None = None
