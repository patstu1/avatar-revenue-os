"""Autonomous Execution Phase C: funnel, paid operator, sponsor, retention, recovery, self-healing.

Revision ID: ae03phase_c_001
Revises: ae02phase_b_001
Create Date: 2026-03-30
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "ae03phase_c_001"
down_revision = "ae02phase_b_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "funnel_execution_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("funnel_action", sa.String(120), nullable=False),
        sa.Column("target_funnel_path", sa.String(500), nullable=False),
        sa.Column("cta_path", sa.String(255), nullable=True),
        sa.Column("capture_mode", sa.String(80), server_default="owned_audience"),
        sa.Column("execution_mode", sa.String(50), server_default="guarded"),
        sa.Column("expected_upside", sa.Float, server_default="0"),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("run_status", sa.String(50), server_default="proposed"),
        sa.Column("diagnostics_json", postgresql.JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "paid_operator_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("paid_action", sa.String(120), nullable=False),
        sa.Column("budget_band", sa.String(80), nullable=False),
        sa.Column("expected_cac", sa.Float, server_default="0"),
        sa.Column("expected_roi", sa.Float, server_default="0"),
        sa.Column("execution_mode", sa.String(50), server_default="guarded"),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("winner_score", sa.Float, server_default="0"),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content_items.id"), nullable=True, index=True),
        sa.Column("autonomous_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("autonomous_runs.id"), nullable=True, index=True),
        sa.Column("run_status", sa.String(50), server_default="proposed"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "paid_operator_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("paid_operator_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("paid_operator_runs.id"), nullable=False, index=True),
        sa.Column("decision_type", sa.String(80), nullable=False),
        sa.Column("budget_band", sa.String(80), nullable=False),
        sa.Column("expected_cac", sa.Float, server_default="0"),
        sa.Column("expected_roi", sa.Float, server_default="0"),
        sa.Column("execution_mode", sa.String(50), server_default="guarded"),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "sponsor_autonomous_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("sponsor_action", sa.String(120), nullable=False),
        sa.Column("package_json", postgresql.JSONB, nullable=True),
        sa.Column("target_category", sa.String(200), nullable=False),
        sa.Column("target_list_json", postgresql.JSONB, nullable=True),
        sa.Column("pipeline_stage", sa.String(80), server_default="prospect"),
        sa.Column("expected_deal_value", sa.Float, server_default="0"),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "retention_automation_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("retention_action", sa.String(120), nullable=False),
        sa.Column("target_segment", sa.String(200), nullable=False),
        sa.Column("cohort_key", sa.String(120), nullable=True),
        sa.Column("expected_incremental_value", sa.Float, server_default="0"),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "recovery_escalations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("incident_type", sa.String(120), nullable=False),
        sa.Column("escalation_requirement", sa.String(80), nullable=False),
        sa.Column("severity", sa.String(50), server_default="medium"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("related_autonomous_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("autonomous_runs.id"), nullable=True, index=True),
        sa.Column("status", sa.String(50), server_default="open"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "self_healing_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("recovery_escalation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recovery_escalations.id"), nullable=True, index=True),
        sa.Column("incident_type", sa.String(120), nullable=False),
        sa.Column("action_taken", sa.String(200), nullable=False),
        sa.Column("action_mode", sa.String(50), server_default="guarded"),
        sa.Column("escalation_requirement", sa.String(80), server_default="none"),
        sa.Column("expected_mitigation", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("self_healing_actions")
    op.drop_table("recovery_escalations")
    op.drop_table("retention_automation_actions")
    op.drop_table("sponsor_autonomous_actions")
    op.drop_table("paid_operator_decisions")
    op.drop_table("paid_operator_runs")
    op.drop_table("funnel_execution_runs")
