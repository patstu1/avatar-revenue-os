"""Schemas — Autonomous Execution control plane."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AutomationExecutionPolicyOut(BaseModel):
    id: str
    brand_id: str
    organization_id: str | None = None
    operating_mode: str
    min_confidence_auto_execute: float
    min_confidence_publish: float
    kill_switch_engaged: bool
    max_auto_cost_usd_per_action: float | None = None
    require_approval_above_cost_usd: float | None = None
    approval_gates_json: dict | None = None
    extra_policy_json: dict | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AutomationExecutionPolicyUpdate(BaseModel):
    operating_mode: str | None = Field(
        default=None, description="fully_autonomous | guarded_autonomous | escalation_only"
    )
    min_confidence_auto_execute: float | None = None
    min_confidence_publish: float | None = None
    kill_switch_engaged: bool | None = None
    max_auto_cost_usd_per_action: float | None = None
    require_approval_above_cost_usd: float | None = None
    approval_gates_json: dict | None = None
    extra_policy_json: dict | None = None


class AutomationExecutionRunOut(BaseModel):
    id: str
    brand_id: str
    loop_step: str
    status: str
    confidence_score: float
    policy_snapshot_json: dict | None = None
    input_payload_json: dict | None = None
    output_payload_json: dict | None = None
    blocked_reason: str | None = None
    error_message: str | None = None
    approval_status: str | None = None
    parent_run_id: str | None = None
    rollback_of_run_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AutomationExecutionRunCreate(BaseModel):
    loop_step: str
    status: str = "running"
    confidence_score: float = 0.0
    input_payload_json: dict | None = None
    policy_snapshot_json: dict | None = None


class ExecutionBlockerEscalationOut(BaseModel):
    id: str
    brand_id: str
    blocker_category: str
    severity: str
    title: str
    summary: str
    exact_operator_steps_json: list[dict[str, Any]]
    linked_run_id: str | None = None
    risk_flags_json: dict | None = None
    cost_exposure_json: dict | None = None
    resolution_status: str
    resolved_at: str | None = None
    resolved_by_user_id: str | None = None
    resolution_notes: str | None = None
    notification_enqueued_at: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AutomationGatePreviewOut(BaseModel):
    decision: str
    reasons: list[str]
    guardrail: dict | None = None


class BlockerResolveBody(BaseModel):
    resolution_notes: str | None = None


class ExecutionBlockerCreate(BaseModel):
    blocker_category: str
    severity: str = Field(..., description="critical | high | medium | low")
    title: str
    summary: str
    exact_operator_steps_json: list[dict[str, Any]]
    linked_run_id: str | None = None
    risk_flags_json: dict | None = None
    cost_exposure_json: dict | None = None
    enqueue_notification: bool = True


class AutomationExecutionRunPatch(BaseModel):
    status: str | None = None
    output_payload_json: dict | None = None
    blocked_reason: str | None = None
    error_message: str | None = None
    approval_status: str | None = None
