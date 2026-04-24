"""Schemas — Autonomous Execution Phase B: policies, runner, distribution, monetization, suppression."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

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
    rollback_rule: Optional[str] = None
    kill_switch_class: str
    policy_metadata_json: Optional[Any] = None
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AutonomousRunOut(BaseModel):
    id: str
    brand_id: str
    queue_item_id: Optional[str] = None
    target_account_id: Optional[str] = None
    target_platform: str
    execution_mode: str
    run_status: str
    current_step: str
    content_brief_id: Optional[str] = None
    content_item_id: Optional[str] = None
    publish_job_id: Optional[str] = None
    distribution_plan_id: Optional[str] = None
    monetization_route_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    run_metadata_json: Optional[Any] = None
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DistributionPlanOut(BaseModel):
    id: str
    brand_id: str
    source_concept: str
    source_content_item_id: Optional[str] = None
    target_platforms_json: Optional[Any] = None
    derivative_types_json: Optional[Any] = None
    platform_priority_json: Optional[Any] = None
    cadence_json: Optional[Any] = None
    publish_timing_json: Optional[Any] = None
    duplication_guard_json: Optional[Any] = None
    plan_status: str
    confidence: float
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MonetizationRouteOut(BaseModel):
    id: str
    brand_id: str
    content_item_id: Optional[str] = None
    queue_item_id: Optional[str] = None
    route_class: str
    selected_route: str
    funnel_path: Optional[str] = None
    follow_up_requirements_json: Optional[Any] = None
    revenue_estimate: float
    confidence: float
    route_status: str
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SuppressionExecutionOut(BaseModel):
    id: str
    brand_id: str
    suppression_type: str
    affected_scope: str
    affected_entity_id: Optional[str] = None
    trigger_reason: str
    duration_hours: Optional[int] = None
    lift_condition: Optional[str] = None
    confidence: float
    suppression_status: str
    lifted_at: Optional[datetime] = None
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RecomputeSummaryOut(BaseModel):
    status: str
    detail: Optional[str] = None
    counts: Optional[Any] = None
