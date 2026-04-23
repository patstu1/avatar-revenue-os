"""Pydantic schemas for Brain Architecture Phase D."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
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
    weak_areas_json: Optional[Any] = None
    recommended_corrections_json: Optional[Any] = None
    inputs_json: Optional[Any] = None
    confidence: float
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SelfCorrectionActionOut(BaseModel):
    id: UUID
    brand_id: UUID
    correction_type: str
    reason: str
    effect_target: str
    severity: str
    applied: bool
    payload_json: Optional[Any] = None
    confidence: float
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ReadinessBrainReportOut(BaseModel):
    id: UUID
    brand_id: UUID
    readiness_score: float
    readiness_band: str
    blockers_json: Optional[Any] = None
    allowed_actions_json: Optional[Any] = None
    forbidden_actions_json: Optional[Any] = None
    inputs_json: Optional[Any] = None
    confidence: float
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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
    supporting_data_json: Optional[Any] = None
    confidence: float
    resolved: bool
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RecomputeSummaryOut(BaseModel):
    status: str
    detail: str
    counts: Optional[Any] = None
