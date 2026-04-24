"""Autonomous Execution Phase B: execution policies, runs, distribution, monetization, suppression, failures.

Revision ID: ae02phase_b_001
Revises: ae01phase_a_001
Create Date: 2026-03-30
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "ae02phase_b_001"
down_revision = "ae01phase_a_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("execution_mode", sa.String(50), server_default="guarded"),
        sa.Column("confidence_threshold", sa.Float, server_default="0.7"),
        sa.Column("risk_level", sa.String(50), server_default="medium"),
        sa.Column("cost_class", sa.String(50), server_default="low"),
        sa.Column("compliance_sensitivity", sa.String(50), server_default="standard"),
        sa.Column("platform_sensitivity", sa.String(50), server_default="standard"),
        sa.Column("budget_impact", sa.String(50), server_default="none"),
        sa.Column("account_health_impact", sa.String(50), server_default="neutral"),
        sa.Column("approval_requirement", sa.String(100), server_default="none"),
        sa.Column("rollback_rule", sa.Text, nullable=True),
        sa.Column("kill_switch_class", sa.String(50), server_default="soft"),
        sa.Column("policy_metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "distribution_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("source_concept", sa.String(500), nullable=False),
        sa.Column(
            "source_content_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content_items.id"), nullable=True
        ),
        sa.Column("target_platforms_json", postgresql.JSONB, nullable=True),
        sa.Column("derivative_types_json", postgresql.JSONB, nullable=True),
        sa.Column("platform_priority_json", postgresql.JSONB, nullable=True),
        sa.Column("cadence_json", postgresql.JSONB, nullable=True),
        sa.Column("publish_timing_json", postgresql.JSONB, nullable=True),
        sa.Column("duplication_guard_json", postgresql.JSONB, nullable=True),
        sa.Column("plan_status", sa.String(50), server_default="draft"),
        sa.Column("confidence", sa.Float, server_default="0.0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "monetization_routes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column(
            "content_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("content_items.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("queue_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auto_queue_items.id"), nullable=True),
        sa.Column("route_class", sa.String(100), nullable=False),
        sa.Column("selected_route", sa.String(200), nullable=False),
        sa.Column("funnel_path", sa.Text, nullable=True),
        sa.Column("follow_up_requirements_json", postgresql.JSONB, nullable=True),
        sa.Column("revenue_estimate", sa.Float, server_default="0.0"),
        sa.Column("confidence", sa.Float, server_default="0.0"),
        sa.Column("route_status", sa.String(50), server_default="proposed"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "autonomous_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column(
            "queue_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("auto_queue_items.id"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "target_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("creator_accounts.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("target_platform", sa.String(50), nullable=False),
        sa.Column("execution_mode", sa.String(50), server_default="guarded"),
        sa.Column("run_status", sa.String(50), server_default="pending"),
        sa.Column("current_step", sa.String(100), server_default="queued"),
        sa.Column("content_brief_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content_briefs.id"), nullable=True),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content_items.id"), nullable=True),
        sa.Column("publish_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("publish_jobs.id"), nullable=True),
        sa.Column(
            "distribution_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("distribution_plans.id"), nullable=True
        ),
        sa.Column(
            "monetization_route_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("monetization_routes.id"),
            nullable=True,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("run_metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "autonomous_run_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("autonomous_runs.id"), nullable=False, index=True
        ),
        sa.Column("step_name", sa.String(100), nullable=False),
        sa.Column("step_order", sa.Integer, nullable=False),
        sa.Column("step_status", sa.String(50), server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_json", postgresql.JSONB, nullable=True),
        sa.Column("output_json", postgresql.JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "suppression_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("suppression_type", sa.String(100), nullable=False),
        sa.Column("affected_scope", sa.String(200), nullable=False),
        sa.Column("affected_entity_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("trigger_reason", sa.Text, nullable=False),
        sa.Column("duration_hours", sa.Integer, nullable=True),
        sa.Column("lift_condition", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, server_default="0.0"),
        sa.Column("suppression_status", sa.String(50), server_default="active"),
        sa.Column("lifted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "execution_failures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column(
            "run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("autonomous_runs.id"), nullable=True, index=True
        ),
        sa.Column("failure_type", sa.String(100), nullable=False),
        sa.Column("failure_step", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text, nullable=False),
        sa.Column("error_context_json", postgresql.JSONB, nullable=True),
        sa.Column("recovery_action", sa.String(200), nullable=True),
        sa.Column("recovery_status", sa.String(50), server_default="pending"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("execution_failures")
    op.drop_table("suppression_executions")
    op.drop_table("autonomous_run_steps")
    op.drop_table("autonomous_runs")
    op.drop_table("monetization_routes")
    op.drop_table("distribution_plans")
    op.drop_table("execution_policies")
