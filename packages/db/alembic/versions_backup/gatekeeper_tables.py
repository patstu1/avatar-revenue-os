"""AI Gatekeeper — 10 tables for completion, truth, execution closure, tests, dependencies, contradictions, operator commands, expansion permissions, alerts, audit ledger.

Revision ID: gatekeeper_001
Revises: copilot_claude_001
Create Date: 2026-03-31
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "gatekeeper_001"
down_revision: Union[str, None] = "copilot_claude_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gatekeeper_completion_reports",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("module_name", sa.String(200), nullable=False, index=True),
        sa.Column("has_model", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("has_migration", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("has_engine", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("has_service", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("has_api", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("has_frontend", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("has_tests", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("has_docs", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("has_worker", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("completion_score", sa.Float(), server_default="0.0"),
        sa.Column("missing_layers", JSONB(), server_default="[]"),
        sa.Column("gate_passed", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("severity", sa.String(30), server_default="high", index=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "gatekeeper_truth_reports",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("module_name", sa.String(200), nullable=False, index=True),
        sa.Column("claimed_status", sa.String(40), nullable=False, index=True),
        sa.Column("actual_status", sa.String(40), nullable=False, index=True),
        sa.Column("truth_mismatch", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("mislabeled_as_live", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("synthetic_without_label", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("gate_passed", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("severity", sa.String(30), server_default="high", index=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("details_json", JSONB(), server_default="{}"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "gatekeeper_execution_closure_reports",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("module_name", sa.String(200), nullable=False, index=True),
        sa.Column("has_execution_path", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("has_downstream_action", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("has_blocker_handling", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("dead_end_detected", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("orphaned_recommendation", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("stale_blocker_detected", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("gate_passed", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("severity", sa.String(30), server_default="high", index=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("details_json", JSONB(), server_default="{}"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "gatekeeper_test_reports",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("module_name", sa.String(200), nullable=False, index=True),
        sa.Column("unit_test_count", sa.Integer(), server_default="0"),
        sa.Column("integration_test_count", sa.Integer(), server_default="0"),
        sa.Column("critical_paths_covered", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("high_risk_flows_tested", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("gate_passed", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("severity", sa.String(30), server_default="medium", index=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("details_json", JSONB(), server_default="{}"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "gatekeeper_dependency_reports",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("module_name", sa.String(200), nullable=False, index=True),
        sa.Column("provider_key", sa.String(80), nullable=True, index=True),
        sa.Column("dependency_met", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("credential_present", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("integration_live", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("blocked_by_external", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("gate_passed", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("severity", sa.String(30), server_default="high", index=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "gatekeeper_contradiction_reports",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("module_a", sa.String(200), nullable=False),
        sa.Column("module_b", sa.String(200), nullable=False),
        sa.Column("contradiction_type", sa.String(80), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(30), server_default="high", index=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("gate_passed", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("details_json", JSONB(), server_default="{}"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "gatekeeper_operator_command_reports",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("command_source", sa.String(120), nullable=False, index=True),
        sa.Column("command_summary", sa.Text(), nullable=False),
        sa.Column("is_actionable", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("is_specific", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("has_measurable_outcome", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("quality_score", sa.Float(), server_default="0.0"),
        sa.Column("gate_passed", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("severity", sa.String(30), server_default="medium", index=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "gatekeeper_expansion_permissions",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("expansion_target", sa.String(200), nullable=False, index=True),
        sa.Column("prerequisites_met", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("blockers_resolved", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("test_coverage_sufficient", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("dependencies_ready", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("permission_granted", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("blocking_reasons", JSONB(), server_default="[]"),
        sa.Column("severity", sa.String(30), server_default="high", index=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "gatekeeper_alerts",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("gate_type", sa.String(80), nullable=False, index=True),
        sa.Column("severity", sa.String(30), server_default="high", index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_module", sa.String(200), nullable=True),
        sa.Column("operator_action", sa.Text(), nullable=True),
        sa.Column("resolved", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "gatekeeper_audit_ledgers",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("gate_type", sa.String(80), nullable=False, index=True),
        sa.Column("action", sa.String(80), nullable=False, index=True),
        sa.Column("module_name", sa.String(200), nullable=True),
        sa.Column("result", sa.String(30), nullable=False, index=True),
        sa.Column("details_json", JSONB(), server_default="{}"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("gatekeeper_audit_ledgers")
    op.drop_table("gatekeeper_alerts")
    op.drop_table("gatekeeper_expansion_permissions")
    op.drop_table("gatekeeper_operator_command_reports")
    op.drop_table("gatekeeper_contradiction_reports")
    op.drop_table("gatekeeper_dependency_reports")
    op.drop_table("gatekeeper_test_reports")
    op.drop_table("gatekeeper_execution_closure_reports")
    op.drop_table("gatekeeper_truth_reports")
    op.drop_table("gatekeeper_completion_reports")
