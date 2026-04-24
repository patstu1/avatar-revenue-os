"""Autonomous Execution + Blocker Escalation — Phase A control plane tables.

Revision ID: a2b3c4d5e6f7
Revises: z1a2b3c4d5e6
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "z1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "automation_execution_policies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("operating_mode", sa.String(40), server_default="guarded_autonomous", nullable=False),
        sa.Column("min_confidence_auto_execute", sa.Float(), server_default="0.72", nullable=False),
        sa.Column("min_confidence_publish", sa.Float(), server_default="0.78", nullable=False),
        sa.Column("kill_switch_engaged", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("max_auto_cost_usd_per_action", sa.Float(), nullable=True),
        sa.Column("require_approval_above_cost_usd", sa.Float(), nullable=True),
        sa.Column("approval_gates_json", JSONB, nullable=True),
        sa.Column("extra_policy_json", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id"),
    )
    op.create_index("ix_automation_execution_policies_brand_id", "automation_execution_policies", ["brand_id"])

    op.create_table(
        "automation_execution_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("loop_step", sa.String(80), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("confidence_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("policy_snapshot_json", JSONB, nullable=True),
        sa.Column("input_payload_json", JSONB, nullable=True),
        sa.Column("output_payload_json", JSONB, nullable=True),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("approval_status", sa.String(30), nullable=True),
        sa.Column("parent_run_id", sa.UUID(), nullable=True),
        sa.Column("rollback_of_run_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["parent_run_id"], ["automation_execution_runs.id"]),
        sa.ForeignKeyConstraint(["rollback_of_run_id"], ["automation_execution_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_automation_execution_runs_brand_id", "automation_execution_runs", ["brand_id"])
    op.create_index("ix_automation_execution_runs_loop_step", "automation_execution_runs", ["loop_step"])
    op.create_index("ix_automation_execution_runs_status", "automation_execution_runs", ["status"])

    op.create_table(
        "execution_blocker_escalations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("blocker_category", sa.String(80), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("exact_operator_steps_json", JSONB, nullable=False),
        sa.Column("linked_run_id", sa.UUID(), nullable=True),
        sa.Column("risk_flags_json", JSONB, nullable=True),
        sa.Column("cost_exposure_json", JSONB, nullable=True),
        sa.Column("resolution_status", sa.String(30), server_default="open", nullable=False),
        sa.Column("resolved_at", sa.String(50), nullable=True),
        sa.Column("resolved_by_user_id", sa.UUID(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("notification_enqueued_at", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["linked_run_id"], ["automation_execution_runs.id"]),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exec_blocker_esc_brand_id", "execution_blocker_escalations", ["brand_id"])
    op.create_index("ix_exec_blocker_esc_category", "execution_blocker_escalations", ["blocker_category"])
    op.create_index("ix_exec_blocker_esc_resolution", "execution_blocker_escalations", ["resolution_status"])


def downgrade() -> None:
    op.drop_index("ix_exec_blocker_esc_resolution", table_name="execution_blocker_escalations")
    op.drop_index("ix_exec_blocker_esc_category", table_name="execution_blocker_escalations")
    op.drop_index("ix_exec_blocker_esc_brand_id", table_name="execution_blocker_escalations")
    op.drop_table("execution_blocker_escalations")
    op.drop_index("ix_automation_execution_runs_status", table_name="automation_execution_runs")
    op.drop_index("ix_automation_execution_runs_loop_step", table_name="automation_execution_runs")
    op.drop_index("ix_automation_execution_runs_brand_id", table_name="automation_execution_runs")
    op.drop_table("automation_execution_runs")
    op.drop_index("ix_automation_execution_policies_brand_id", table_name="automation_execution_policies")
    op.drop_table("automation_execution_policies")
