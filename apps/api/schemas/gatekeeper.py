"""Pydantic schemas for AI Gatekeeper APIs."""
from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict


class _GKBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CompletionReportOut(_GKBase):
    id: uuid.UUID
    module_name: str
    completion_score: float
    missing_layers: list
    gate_passed: bool
    severity: str
    explanation: str | None = None
    has_model: bool
    has_migration: bool
    has_engine: bool
    has_service: bool
    has_api: bool
    has_frontend: bool
    has_tests: bool
    has_docs: bool
    has_worker: bool


class TruthReportOut(_GKBase):
    id: uuid.UUID
    module_name: str
    claimed_status: str
    actual_status: str
    truth_mismatch: bool
    mislabeled_as_live: bool
    gate_passed: bool
    severity: str
    explanation: str | None = None


class ExecutionClosureReportOut(_GKBase):
    id: uuid.UUID
    module_name: str
    has_execution_path: bool
    has_downstream_action: bool
    dead_end_detected: bool
    stale_blocker_detected: bool
    orphaned_recommendation: bool
    gate_passed: bool
    severity: str
    explanation: str | None = None


class TestReportOut(_GKBase):
    id: uuid.UUID
    module_name: str
    unit_test_count: int
    integration_test_count: int
    critical_paths_covered: bool
    high_risk_flows_tested: bool
    gate_passed: bool
    severity: str
    explanation: str | None = None


class DependencyReportOut(_GKBase):
    id: uuid.UUID
    module_name: str
    provider_key: str | None = None
    dependency_met: bool
    credential_present: bool
    integration_live: bool
    blocked_by_external: bool
    gate_passed: bool
    severity: str
    explanation: str | None = None


class ContradictionReportOut(_GKBase):
    id: uuid.UUID
    module_a: str
    module_b: str
    contradiction_type: str
    description: str
    severity: str
    gate_passed: bool


class OperatorCommandReportOut(_GKBase):
    id: uuid.UUID
    command_source: str
    command_summary: str
    is_actionable: bool
    is_specific: bool
    has_measurable_outcome: bool
    quality_score: float
    gate_passed: bool
    severity: str
    explanation: str | None = None


class ExpansionPermissionOut(_GKBase):
    id: uuid.UUID
    expansion_target: str
    prerequisites_met: bool
    blockers_resolved: bool
    test_coverage_sufficient: bool
    dependencies_ready: bool
    permission_granted: bool
    blocking_reasons: list
    severity: str
    explanation: str | None = None


class AlertOut(_GKBase):
    id: uuid.UUID
    gate_type: str
    severity: str
    title: str
    description: str
    source_module: str | None = None
    operator_action: str | None = None
    resolved: bool


class AuditLedgerOut(_GKBase):
    id: uuid.UUID
    gate_type: str
    action: str
    module_name: str | None = None
    result: str
    details_json: dict | None = None
    created_at: Any | None = None


class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0
    alerts_generated: int = 0
    status: str = "completed"
