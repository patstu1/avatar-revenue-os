"""Pydantic schemas for MXP Experiment Decisions."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

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
    target_scope_id: str | None = None
    hypothesis: str | None = None
    expected_upside: float
    confidence_gap: float
    priority_score: float
    recommended_allocation: float
    promotion_rule_json: dict | None = None
    suppression_rule_json: dict | None = None
    explanation_json: dict | None = None
    status: str
    is_active: bool
    data_source: str = DataSource.SYNTHETIC_PROXY
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ExperimentOutcomeOut(BaseModel):
    id: str
    brand_id: str
    experiment_decision_id: str
    observation_source: str
    outcome_type: str
    winner_variant_id: str | None = None
    loser_variant_ids_json: dict | None = None
    confidence_score: float
    observed_uplift: float
    recommended_next_action: str | None = None
    explanation_json: dict | None = None
    data_source: str = DataSource.SYNTHETIC_PROXY
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ExperimentOutcomeActionOut(BaseModel):
    id: str
    brand_id: str
    experiment_outcome_id: str
    action_kind: str
    execution_status: str
    structured_payload_json: dict | None = None
    operator_note: str | None = None
    data_source: str = DataSource.OPERATOR_QUEUED
    created_at: datetime | None = None
    updated_at: datetime | None = None


class OutcomeActionStatusUpdate(BaseModel):
    execution_status: str
    operator_note: str | None = None
