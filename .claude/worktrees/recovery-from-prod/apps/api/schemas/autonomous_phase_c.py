"""Schemas — Autonomous Execution Phase C."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class FunnelExecutionRunOut(BaseModel):
    id: str
    brand_id: str
    funnel_action: str
    target_funnel_path: str
    cta_path: Optional[str] = None
    capture_mode: str
    execution_mode: str
    expected_upside: float
    confidence: float
    explanation: Optional[str] = None
    run_status: str
    diagnostics_json: Optional[Any] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PaidOperatorRunOut(BaseModel):
    id: str
    brand_id: str
    paid_action: str
    budget_band: str
    expected_cac: float
    expected_roi: float
    execution_mode: str
    confidence: float
    explanation: Optional[str] = None
    winner_score: float
    content_item_id: Optional[str] = None
    autonomous_run_id: Optional[str] = None
    run_status: str
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


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
    explanation: Optional[str] = None
    execution_status: str = "proposed"
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PaidOperatorBundleOut(BaseModel):
    runs: list[PaidOperatorRunOut]
    decisions: list[PaidOperatorDecisionOut]


class SponsorAutonomousActionOut(BaseModel):
    id: str
    brand_id: str
    sponsor_action: str
    package_json: Optional[Any] = None
    target_category: str
    target_list_json: Optional[Any] = None
    pipeline_stage: str
    expected_deal_value: float
    confidence: float
    explanation: Optional[str] = None
    execution_status: str = "proposed"
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RetentionAutomationActionOut(BaseModel):
    id: str
    brand_id: str
    retention_action: str
    target_segment: str
    cohort_key: Optional[str] = None
    expected_incremental_value: float
    confidence: float
    explanation: Optional[str] = None
    execution_status: str = "proposed"
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RecoveryEscalationOut(BaseModel):
    id: str
    brand_id: str
    incident_type: str
    escalation_requirement: str
    severity: str
    explanation: Optional[str] = None
    related_autonomous_run_id: Optional[str] = None
    status: str
    resolved_at: Optional[datetime] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SelfHealingActionOut(BaseModel):
    id: str
    brand_id: str
    recovery_escalation_id: Optional[str] = None
    incident_type: str
    action_taken: str
    action_mode: str
    escalation_requirement: str
    expected_mitigation: Optional[str] = None
    confidence: float
    explanation: Optional[str] = None
    execution_status: str = "proposed"
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RecoveryAutonomyBundleOut(BaseModel):
    escalations: list[RecoveryEscalationOut]
    self_healing: list[SelfHealingActionOut]


class RecomputeSummaryOut(BaseModel):
    status: str
    detail: Optional[str] = None
    counts: Optional[dict] = None


class AdvanceStatusIn(BaseModel):
    target_status: str
    operator_notes: Optional[str] = None


class AdvanceStatusOut(BaseModel):
    id: str
    module: str
    previous_status: str
    new_status: str
    execution_notes: Optional[str] = None


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
    details: Optional[dict] = None


class OperatorNotifyOut(BaseModel):
    brand_id: str
    notifications_sent: int
    items: Optional[list] = None
    notification_payload: Optional[dict] = None
