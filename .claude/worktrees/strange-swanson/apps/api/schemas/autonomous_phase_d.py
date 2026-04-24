"""Pydantic schemas for Autonomous Execution Phase D."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class AgentRunOut(BaseModel):
    id: UUID
    brand_id: UUID
    agent_type: str
    run_status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    input_context_json: Optional[Any] = None
    output_json: Optional[Any] = None
    commands_json: Optional[Any] = None
    error_message: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AgentMessageOut(BaseModel):
    id: UUID
    agent_run_id: UUID
    sender_agent: str
    receiver_agent: Optional[str] = None
    message_type: str
    payload_json: Optional[Any] = None
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AgentOrchestrationBundleOut(BaseModel):
    runs: list[AgentRunOut]
    messages: list[AgentMessageOut]


class RevenuePressureReportOut(BaseModel):
    id: UUID
    brand_id: UUID
    next_commands_json: Optional[Any] = None
    next_launches_json: Optional[Any] = None
    biggest_blocker: Optional[str] = None
    biggest_missed_opportunity: Optional[str] = None
    biggest_weak_lane_to_kill: Optional[str] = None
    underused_monetization_class: Optional[str] = None
    underbuilt_platform: Optional[str] = None
    missing_account_suggestion: Optional[str] = None
    unexploited_winner: Optional[str] = None
    leaking_funnel: Optional[str] = None
    inactive_asset_class: Optional[str] = None
    pressure_score: float
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OverridePolicyOut(BaseModel):
    id: UUID
    brand_id: UUID
    action_ref: str
    override_mode: str
    confidence_threshold: float
    approval_needed: bool
    rollback_available: bool
    rollback_plan: Optional[str] = None
    hard_stop_rule: Optional[str] = None
    audit_trail_json: Optional[Any] = None
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BlockerDetectionReportOut(BaseModel):
    id: UUID
    brand_id: UUID
    blocker: str
    severity: str
    affected_scope: str
    operator_action_needed: str
    deadline_or_urgency: str
    consequence_if_ignored: str
    explanation: Optional[str] = None
    status: str
    resolved_at: Optional[datetime] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EscalationEventOut(BaseModel):
    id: UUID
    brand_id: UUID
    command: str
    reason: str
    supporting_data_json: Optional[Any] = None
    confidence: float
    urgency: str
    expected_upside: float
    expected_cost: float
    time_to_signal: Optional[str] = None
    time_to_profit: Optional[str] = None
    risk: str
    required_resources: Optional[str] = None
    consequence_if_ignored: Optional[str] = None
    status: str
    resolved_at: Optional[datetime] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OperatorCommandOut(BaseModel):
    id: UUID
    brand_id: UUID
    escalation_event_id: Optional[UUID] = None
    blocker_report_id: Optional[UUID] = None
    command_text: str
    command_type: str
    urgency: str
    status: str
    resolved_at: Optional[datetime] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EscalationBundleOut(BaseModel):
    escalations: list[EscalationEventOut]
    commands: list[OperatorCommandOut]


class RecomputeSummaryOut(BaseModel):
    status: str
    detail: str
    counts: Optional[dict[str, int]] = None
