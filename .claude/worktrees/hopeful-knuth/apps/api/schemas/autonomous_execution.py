"""Schemas — Autonomous Execution control plane."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AutomationExecutionPolicyOut(BaseModel):
    id: str
    brand_id: str
    organization_id: Optional[str] = None
    operating_mode: str
    min_confidence_auto_execute: float
    min_confidence_publish: float
    kill_switch_engaged: bool
    max_auto_cost_usd_per_action: Optional[float] = None
    require_approval_above_cost_usd: Optional[float] = None
    approval_gates_json: Optional[dict] = None
    extra_policy_json: Optional[dict] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AutomationExecutionPolicyUpdate(BaseModel):
    operating_mode: Optional[str] = Field(
        default=None, description="fully_autonomous | guarded_autonomous | escalation_only"
    )
    min_confidence_auto_execute: Optional[float] = None
    min_confidence_publish: Optional[float] = None
    kill_switch_engaged: Optional[bool] = None
    max_auto_cost_usd_per_action: Optional[float] = None
    require_approval_above_cost_usd: Optional[float] = None
    approval_gates_json: Optional[dict] = None
    extra_policy_json: Optional[dict] = None


class AutomationExecutionRunOut(BaseModel):
    id: str
    brand_id: str
    loop_step: str
    status: str
    confidence_score: float
    policy_snapshot_json: Optional[dict] = None
    input_payload_json: Optional[dict] = None
    output_payload_json: Optional[dict] = None
    blocked_reason: Optional[str] = None
    error_message: Optional[str] = None
    approval_status: Optional[str] = None
    parent_run_id: Optional[str] = None
    rollback_of_run_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AutomationExecutionRunCreate(BaseModel):
    loop_step: str
    status: str = "running"
    confidence_score: float = 0.0
    input_payload_json: Optional[dict] = None
    policy_snapshot_json: Optional[dict] = None


class ExecutionBlockerEscalationOut(BaseModel):
    id: str
    brand_id: str
    blocker_category: str
    severity: str
    title: str
    summary: str
    exact_operator_steps_json: list[dict[str, Any]]
    linked_run_id: Optional[str] = None
    risk_flags_json: Optional[dict] = None
    cost_exposure_json: Optional[dict] = None
    resolution_status: str
    resolved_at: Optional[str] = None
    resolved_by_user_id: Optional[str] = None
    resolution_notes: Optional[str] = None
    notification_enqueued_at: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AutomationGatePreviewOut(BaseModel):
    decision: str
    reasons: list[str]
    guardrail: Optional[dict] = None


class BlockerResolveBody(BaseModel):
    resolution_notes: Optional[str] = None


class ExecutionBlockerCreate(BaseModel):
    blocker_category: str
    severity: str = Field(..., description="critical | high | medium | low")
    title: str
    summary: str
    exact_operator_steps_json: list[dict[str, Any]]
    linked_run_id: Optional[str] = None
    risk_flags_json: Optional[dict] = None
    cost_exposure_json: Optional[dict] = None
    enqueue_notification: bool = True


class AutomationExecutionRunPatch(BaseModel):
    status: Optional[str] = None
    output_payload_json: Optional[dict] = None
    blocked_reason: Optional[str] = None
    error_message: Optional[str] = None
    approval_status: Optional[str] = None