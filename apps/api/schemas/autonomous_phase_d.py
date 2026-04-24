"""Pydantic schemas for Autonomous Execution Phase D."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AgentRunOut(BaseModel):
    id: UUID
    brand_id: UUID
    agent_type: str
    run_status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    input_context_json: Any | None = None
    output_json: Any | None = None
    commands_json: Any | None = None
    error_message: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgentMessageOut(BaseModel):
    id: UUID
    agent_run_id: UUID
    sender_agent: str
    receiver_agent: str | None = None
    message_type: str
    payload_json: Any | None = None
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgentOrchestrationBundleOut(BaseModel):
    runs: list[AgentRunOut]
    messages: list[AgentMessageOut]


class RevenuePressureReportOut(BaseModel):
    id: UUID
    brand_id: UUID
    next_commands_json: Any | None = None
    next_launches_json: Any | None = None
    biggest_blocker: str | None = None
    biggest_missed_opportunity: str | None = None
    biggest_weak_lane_to_kill: str | None = None
    underused_monetization_class: str | None = None
    underbuilt_platform: str | None = None
    missing_account_suggestion: str | None = None
    unexploited_winner: str | None = None
    leaking_funnel: str | None = None
    inactive_asset_class: str | None = None
    pressure_score: float
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class OverridePolicyOut(BaseModel):
    id: UUID
    brand_id: UUID
    action_ref: str
    override_mode: str
    confidence_threshold: float
    approval_needed: bool
    rollback_available: bool
    rollback_plan: str | None = None
    hard_stop_rule: str | None = None
    audit_trail_json: Any | None = None
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

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
    explanation: str | None = None
    status: str
    resolved_at: datetime | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class EscalationEventOut(BaseModel):
    id: UUID
    brand_id: UUID
    command: str
    reason: str
    supporting_data_json: Any | None = None
    confidence: float
    urgency: str
    expected_upside: float
    expected_cost: float
    time_to_signal: str | None = None
    time_to_profit: str | None = None
    risk: str
    required_resources: str | None = None
    consequence_if_ignored: str | None = None
    status: str
    resolved_at: datetime | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class OperatorCommandOut(BaseModel):
    id: UUID
    brand_id: UUID
    escalation_event_id: UUID | None = None
    blocker_report_id: UUID | None = None
    command_text: str
    command_type: str
    urgency: str
    status: str
    resolved_at: datetime | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class EscalationBundleOut(BaseModel):
    escalations: list[EscalationEventOut]
    commands: list[OperatorCommandOut]


class RecomputeSummaryOut(BaseModel):
    status: str
    detail: str
    counts: dict[str, int] | None = None
