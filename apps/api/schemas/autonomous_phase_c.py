"""Schemas — Autonomous Execution Phase C."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class FunnelExecutionRunOut(BaseModel):
    id: str
    brand_id: str
    funnel_action: str
    target_funnel_path: str
    cta_path: str | None = None
    capture_mode: str
    execution_mode: str
    expected_upside: float
    confidence: float
    explanation: str | None = None
    run_status: str
    diagnostics_json: Any | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PaidOperatorRunOut(BaseModel):
    id: str
    brand_id: str
    paid_action: str
    budget_band: str
    expected_cac: float
    expected_roi: float
    execution_mode: str
    confidence: float
    explanation: str | None = None
    winner_score: float
    content_item_id: str | None = None
    autonomous_run_id: str | None = None
    run_status: str
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PaidOperatorDecisionOut(BaseModel):
    id: str
    brand_id: str
    paid_operator_run_id: str
    decision_type: str
    budget_band: str
    expected_cac: float
    expected_roi: float
    execution_mode: str
    confidence: float
    explanation: str | None = None
    execution_status: str = "proposed"
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PaidOperatorBundleOut(BaseModel):
    runs: list[PaidOperatorRunOut]
    decisions: list[PaidOperatorDecisionOut]


class SponsorAutonomousActionOut(BaseModel):
    id: str
    brand_id: str
    sponsor_action: str
    package_json: Any | None = None
    target_category: str
    target_list_json: Any | None = None
    pipeline_stage: str
    expected_deal_value: float
    confidence: float
    explanation: str | None = None
    execution_status: str = "proposed"
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RetentionAutomationActionOut(BaseModel):
    id: str
    brand_id: str
    retention_action: str
    target_segment: str
    cohort_key: str | None = None
    expected_incremental_value: float
    confidence: float
    explanation: str | None = None
    execution_status: str = "proposed"
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RecoveryEscalationOut(BaseModel):
    id: str
    brand_id: str
    incident_type: str
    escalation_requirement: str
    severity: str
    explanation: str | None = None
    related_autonomous_run_id: str | None = None
    status: str
    resolved_at: datetime | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SelfHealingActionOut(BaseModel):
    id: str
    brand_id: str
    recovery_escalation_id: str | None = None
    incident_type: str
    action_taken: str
    action_mode: str
    escalation_requirement: str
    expected_mitigation: str | None = None
    confidence: float
    explanation: str | None = None
    execution_status: str = "proposed"
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RecoveryAutonomyBundleOut(BaseModel):
    escalations: list[RecoveryEscalationOut]
    self_healing: list[SelfHealingActionOut]


class RecomputeSummaryOut(BaseModel):
    status: str
    detail: str | None = None
    counts: dict | None = None


class AdvanceStatusIn(BaseModel):
    target_status: str
    operator_notes: str | None = None


class AdvanceStatusOut(BaseModel):
    id: str
    module: str
    previous_status: str
    new_status: str
    execution_notes: str | None = None


class PaidPerformanceIn(BaseModel):
    cpa_actual: float
    cpa_target: float = 55.0
    spend_7d: float
    conversions_7d: int
    roi_actual: float


class PaidPerformanceOut(BaseModel):
    paid_operator_run_id: str
    decision_id: str
    decision_type: str
    data_source: str
    confidence: float


class BatchExecuteOut(BaseModel):
    brand_id: str
    actions_executed: int
    details: dict | None = None


class OperatorNotifyOut(BaseModel):
    brand_id: str
    notifications_sent: int
    items: list | None = None
    notification_payload: dict | None = None
