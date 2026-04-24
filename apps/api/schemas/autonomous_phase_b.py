"""Schemas — Autonomous Execution Phase B: policies, runner, distribution, monetization, suppression."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ExecutionPolicyOut(BaseModel):
    id: str
    brand_id: str
    action_type: str
    execution_mode: str
    confidence_threshold: float
    risk_level: str
    cost_class: str
    compliance_sensitivity: str
    platform_sensitivity: str
    budget_impact: str
    account_health_impact: str
    approval_requirement: str
    rollback_rule: str | None = None
    kill_switch_class: str
    policy_metadata_json: Any | None = None
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AutonomousRunOut(BaseModel):
    id: str
    brand_id: str
    queue_item_id: str | None = None
    target_account_id: str | None = None
    target_platform: str
    execution_mode: str
    run_status: str
    current_step: str
    content_brief_id: str | None = None
    content_item_id: str | None = None
    publish_job_id: str | None = None
    distribution_plan_id: str | None = None
    monetization_route_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    run_metadata_json: Any | None = None
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DistributionPlanOut(BaseModel):
    id: str
    brand_id: str
    source_concept: str
    source_content_item_id: str | None = None
    target_platforms_json: Any | None = None
    derivative_types_json: Any | None = None
    platform_priority_json: Any | None = None
    cadence_json: Any | None = None
    publish_timing_json: Any | None = None
    duplication_guard_json: Any | None = None
    plan_status: str
    confidence: float
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MonetizationRouteOut(BaseModel):
    id: str
    brand_id: str
    content_item_id: str | None = None
    queue_item_id: str | None = None
    route_class: str
    selected_route: str
    funnel_path: str | None = None
    follow_up_requirements_json: Any | None = None
    revenue_estimate: float
    confidence: float
    route_status: str
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SuppressionExecutionOut(BaseModel):
    id: str
    brand_id: str
    suppression_type: str
    affected_scope: str
    affected_entity_id: str | None = None
    trigger_reason: str
    duration_hours: int | None = None
    lift_condition: str | None = None
    confidence: float
    suppression_status: str
    lifted_at: datetime | None = None
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RecomputeSummaryOut(BaseModel):
    status: str
    detail: str | None = None
    counts: Any | None = None
