"""Pydantic schemas for MXP Experiment Decisions."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class DataSource(str, Enum):
    """Transparency label: where this data came from."""
    SYNTHETIC_PROXY = "synthetic_proxy"
    LIVE_IMPORT = "live_import"
    OPERATOR_QUEUED = "operator_queued"
    AUTO_EXECUTED = "auto_executed"


class ExperimentDecisionOut(BaseModel):
    id: str
    brand_id: str
    experiment_type: str
    target_scope_type: str
    target_scope_id: Optional[str] = None
    hypothesis: Optional[str] = None
    expected_upside: float
    confidence_gap: float
    priority_score: float
    recommended_allocation: float
    promotion_rule_json: Optional[dict] = None
    suppression_rule_json: Optional[dict] = None
    explanation_json: Optional[dict] = None
    status: str
    is_active: bool
    data_source: str = DataSource.SYNTHETIC_PROXY
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ExperimentOutcomeOut(BaseModel):
    id: str
    brand_id: str
    experiment_decision_id: str
    observation_source: str
    outcome_type: str
    winner_variant_id: Optional[str] = None
    loser_variant_ids_json: Optional[dict] = None
    confidence_score: float
    observed_uplift: float
    recommended_next_action: Optional[str] = None
    explanation_json: Optional[dict] = None
    data_source: str = DataSource.SYNTHETIC_PROXY
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ExperimentOutcomeActionOut(BaseModel):
    id: str
    brand_id: str
    experiment_outcome_id: str
    action_kind: str
    execution_status: str
    structured_payload_json: Optional[dict] = None
    operator_note: Optional[str] = None
    data_source: str = DataSource.OPERATOR_QUEUED
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OutcomeActionStatusUpdate(BaseModel):
    execution_status: str
    operator_note: Optional[str] = None
