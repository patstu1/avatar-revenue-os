"""AI Gatekeeper — hard internal control system for build/execution quality."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class GatekeeperCompletionReport(Base):
    __tablename__ = "gatekeeper_completion_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    module_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    has_model: Mapped[bool] = mapped_column(Boolean, default=False)
    has_migration: Mapped[bool] = mapped_column(Boolean, default=False)
    has_engine: Mapped[bool] = mapped_column(Boolean, default=False)
    has_service: Mapped[bool] = mapped_column(Boolean, default=False)
    has_api: Mapped[bool] = mapped_column(Boolean, default=False)
    has_frontend: Mapped[bool] = mapped_column(Boolean, default=False)
    has_tests: Mapped[bool] = mapped_column(Boolean, default=False)
    has_docs: Mapped[bool] = mapped_column(Boolean, default=False)
    has_worker: Mapped[bool] = mapped_column(Boolean, default=False)
    completion_score: Mapped[float] = mapped_column(Float, default=0.0)
    missing_layers: Mapped[list] = mapped_column(JSONB, default=list)
    gate_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    severity: Mapped[str] = mapped_column(String(30), default="high", index=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class GatekeeperTruthReport(Base):
    __tablename__ = "gatekeeper_truth_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    module_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    claimed_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    actual_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    truth_mismatch: Mapped[bool] = mapped_column(Boolean, default=False)
    mislabeled_as_live: Mapped[bool] = mapped_column(Boolean, default=False)
    synthetic_without_label: Mapped[bool] = mapped_column(Boolean, default=False)
    gate_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    severity: Mapped[str] = mapped_column(String(30), default="high", index=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class GatekeeperExecutionClosureReport(Base):
    __tablename__ = "gatekeeper_execution_closure_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    module_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    has_execution_path: Mapped[bool] = mapped_column(Boolean, default=False)
    has_downstream_action: Mapped[bool] = mapped_column(Boolean, default=False)
    has_blocker_handling: Mapped[bool] = mapped_column(Boolean, default=False)
    dead_end_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    orphaned_recommendation: Mapped[bool] = mapped_column(Boolean, default=False)
    stale_blocker_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    gate_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    severity: Mapped[str] = mapped_column(String(30), default="high", index=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class GatekeeperTestReport(Base):
    __tablename__ = "gatekeeper_test_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    module_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    unit_test_count: Mapped[int] = mapped_column(Integer, default=0)
    integration_test_count: Mapped[int] = mapped_column(Integer, default=0)
    critical_paths_covered: Mapped[bool] = mapped_column(Boolean, default=False)
    high_risk_flows_tested: Mapped[bool] = mapped_column(Boolean, default=False)
    gate_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    severity: Mapped[str] = mapped_column(String(30), default="medium", index=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class GatekeeperDependencyReport(Base):
    __tablename__ = "gatekeeper_dependency_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    module_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    provider_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    dependency_met: Mapped[bool] = mapped_column(Boolean, default=False)
    credential_present: Mapped[bool] = mapped_column(Boolean, default=False)
    integration_live: Mapped[bool] = mapped_column(Boolean, default=False)
    blocked_by_external: Mapped[bool] = mapped_column(Boolean, default=False)
    gate_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    severity: Mapped[str] = mapped_column(String(30), default="high", index=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class GatekeeperContradictionReport(Base):
    __tablename__ = "gatekeeper_contradiction_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    module_a: Mapped[str] = mapped_column(String(200), nullable=False)
    module_b: Mapped[str] = mapped_column(String(200), nullable=False)
    contradiction_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(30), default="high", index=True)
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gate_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class GatekeeperOperatorCommandReport(Base):
    __tablename__ = "gatekeeper_operator_command_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    command_source: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    command_summary: Mapped[str] = mapped_column(Text, nullable=False)
    is_actionable: Mapped[bool] = mapped_column(Boolean, default=False)
    is_specific: Mapped[bool] = mapped_column(Boolean, default=False)
    has_measurable_outcome: Mapped[bool] = mapped_column(Boolean, default=False)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    gate_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    severity: Mapped[str] = mapped_column(String(30), default="medium", index=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class GatekeeperExpansionPermission(Base):
    __tablename__ = "gatekeeper_expansion_permissions"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    expansion_target: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    prerequisites_met: Mapped[bool] = mapped_column(Boolean, default=False)
    blockers_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    test_coverage_sufficient: Mapped[bool] = mapped_column(Boolean, default=False)
    dependencies_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    permission_granted: Mapped[bool] = mapped_column(Boolean, default=False)
    blocking_reasons: Mapped[list] = mapped_column(JSONB, default=list)
    severity: Mapped[str] = mapped_column(String(30), default="high", index=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class GatekeeperAlert(Base):
    __tablename__ = "gatekeeper_alerts"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    gate_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(30), default="high", index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_module: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    operator_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class GatekeeperAuditLedger(Base):
    __tablename__ = "gatekeeper_audit_ledgers"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    gate_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    module_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    result: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
