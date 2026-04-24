"""Pydantic schemas for Brain Architecture Phase B."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class BrainDecisionOut(BaseModel):
    id: UUID
    brand_id: UUID
    decision_class: str
    objective: str
    target_scope: str
    target_id: UUID | None = None
    selected_action: str
    alternatives_json: Any | None = None
    confidence: float
    policy_mode: str
    expected_upside: float
    expected_cost: float
    downstream_action: str | None = None
    inputs_json: Any | None = None
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PolicyEvaluationOut(BaseModel):
    id: UUID
    brand_id: UUID
    decision_id: UUID | None = None
    action_ref: str
    policy_mode: str
    reason: str
    approval_needed: bool
    hard_stop_rule: str | None = None
    rollback_rule: str | None = None
    risk_score: float
    cost_impact: float
    inputs_json: Any | None = None
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ConfidenceReportOut(BaseModel):
    id: UUID
    brand_id: UUID
    decision_id: UUID | None = None
    scope_label: str
    confidence_score: float
    confidence_band: str
    signal_strength: float
    historical_precedent: float
    saturation_risk: float
    memory_support: float
    data_completeness: float
    execution_history: float
    blocker_severity: float
    uncertainty_factors_json: Any | None = None
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class UpsideCostEstimateOut(BaseModel):
    id: UUID
    brand_id: UUID
    decision_id: UUID | None = None
    scope_label: str
    expected_upside: float
    expected_cost: float
    expected_payback_days: int
    operational_burden: float
    concentration_risk: float
    net_value: float
    inputs_json: Any | None = None
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ArbitrationReportOut(BaseModel):
    id: UUID
    brand_id: UUID
    ranked_priorities_json: Any | None = None
    chosen_winner_class: str
    chosen_winner_label: str
    rejected_actions_json: Any | None = None
    competing_count: int
    net_value_chosen: float
    inputs_json: Any | None = None
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class RecomputeSummaryOut(BaseModel):
    status: str
    detail: str
    counts: Any | None = None
