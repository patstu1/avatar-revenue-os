"""Pydantic schemas for Brain Architecture Phase B."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class BrainDecisionOut(BaseModel):
    id: UUID
    brand_id: UUID
    decision_class: str
    objective: str
    target_scope: str
    target_id: Optional[UUID] = None
    selected_action: str
    alternatives_json: Optional[Any] = None
    confidence: float
    policy_mode: str
    expected_upside: float
    expected_cost: float
    downstream_action: Optional[str] = None
    inputs_json: Optional[Any] = None
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PolicyEvaluationOut(BaseModel):
    id: UUID
    brand_id: UUID
    decision_id: Optional[UUID] = None
    action_ref: str
    policy_mode: str
    reason: str
    approval_needed: bool
    hard_stop_rule: Optional[str] = None
    rollback_rule: Optional[str] = None
    risk_score: float
    cost_impact: float
    inputs_json: Optional[Any] = None
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ConfidenceReportOut(BaseModel):
    id: UUID
    brand_id: UUID
    decision_id: Optional[UUID] = None
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
    uncertainty_factors_json: Optional[Any] = None
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UpsideCostEstimateOut(BaseModel):
    id: UUID
    brand_id: UUID
    decision_id: Optional[UUID] = None
    scope_label: str
    expected_upside: float
    expected_cost: float
    expected_payback_days: int
    operational_burden: float
    concentration_risk: float
    net_value: float
    inputs_json: Optional[Any] = None
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ArbitrationReportOut(BaseModel):
    id: UUID
    brand_id: UUID
    ranked_priorities_json: Optional[Any] = None
    chosen_winner_class: str
    chosen_winner_label: str
    rejected_actions_json: Optional[Any] = None
    competing_count: int
    net_value_chosen: float
    inputs_json: Optional[Any] = None
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RecomputeSummaryOut(BaseModel):
    status: str
    detail: str
    counts: Optional[Any] = None
