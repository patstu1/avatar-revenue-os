"""Pydantic schemas for Brain Architecture Phase D."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class MetaMonitoringReportOut(BaseModel):
    id: UUID
    brand_id: UUID
    health_score: float
    health_band: str
    decision_quality_score: float
    confidence_drift_score: float
    policy_drift_score: float
    execution_failure_rate: float
    memory_quality_score: float
    escalation_rate: float
    queue_congestion: float
    dead_agent_count: int
    low_signal_count: int
    wasted_action_count: int
    weak_areas_json: Any | None = None
    recommended_corrections_json: Any | None = None
    inputs_json: Any | None = None
    confidence: float
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class SelfCorrectionActionOut(BaseModel):
    id: UUID
    brand_id: UUID
    correction_type: str
    reason: str
    effect_target: str
    severity: str
    applied: bool
    payload_json: Any | None = None
    confidence: float
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ReadinessBrainReportOut(BaseModel):
    id: UUID
    brand_id: UUID
    readiness_score: float
    readiness_band: str
    blockers_json: Any | None = None
    allowed_actions_json: Any | None = None
    forbidden_actions_json: Any | None = None
    inputs_json: Any | None = None
    confidence: float
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class BrainEscalationOut(BaseModel):
    id: UUID
    brand_id: UUID
    escalation_type: str
    command: str
    urgency: str
    expected_upside_unlocked: float
    expected_cost_of_delay: float
    affected_scope: str
    supporting_data_json: Any | None = None
    confidence: float
    resolved: bool
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class RecomputeSummaryOut(BaseModel):
    status: str
    detail: str
    counts: Any | None = None
