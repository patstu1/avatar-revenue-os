"""Autonomous Execution Phase D — agent orchestration, revenue pressure, overrides, blockers, escalations.

Revision ID: ae04phase_d_001
Revises: ae03phase_c_002
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "ae04phase_d_001"
down_revision = "ae03phase_c_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("agent_type", sa.String(120), nullable=False, index=True),
        sa.Column("run_status", sa.String(50), server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_context_json", postgresql.JSONB, nullable=True),
        sa.Column("output_json", postgresql.JSONB, nullable=True),
        sa.Column("commands_json", postgresql.JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "agent_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id"), nullable=False, index=True),
        sa.Column("sender_agent", sa.String(120), nullable=False),
        sa.Column("receiver_agent", sa.String(120), nullable=True),
        sa.Column("message_type", sa.String(80), nullable=False),
        sa.Column("payload_json", postgresql.JSONB, nullable=True),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "revenue_pressure_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("next_commands_json", postgresql.JSONB, nullable=True),
        sa.Column("next_launches_json", postgresql.JSONB, nullable=True),
        sa.Column("biggest_blocker", sa.Text, nullable=True),
        sa.Column("biggest_missed_opportunity", sa.Text, nullable=True),
        sa.Column("biggest_weak_lane_to_kill", sa.Text, nullable=True),
        sa.Column("underused_monetization_class", sa.String(200), nullable=True),
        sa.Column("underbuilt_platform", sa.String(120), nullable=True),
        sa.Column("missing_account_suggestion", sa.Text, nullable=True),
        sa.Column("unexploited_winner", sa.Text, nullable=True),
        sa.Column("leaking_funnel", sa.Text, nullable=True),
        sa.Column("inactive_asset_class", sa.String(200), nullable=True),
        sa.Column("pressure_score", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "override_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("action_ref", sa.String(200), nullable=False),
        sa.Column("override_mode", sa.String(50), server_default="guarded"),
        sa.Column("confidence_threshold", sa.Float, server_default="0.7"),
        sa.Column("approval_needed", sa.Boolean, server_default=sa.text("false")),
        sa.Column("rollback_available", sa.Boolean, server_default=sa.text("false")),
        sa.Column("rollback_plan", sa.Text, nullable=True),
        sa.Column("hard_stop_rule", sa.Text, nullable=True),
        sa.Column("audit_trail_json", postgresql.JSONB, nullable=True),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "escalation_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("command", sa.Text, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("supporting_data_json", postgresql.JSONB, nullable=True),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("urgency", sa.String(50), server_default="medium"),
        sa.Column("expected_upside", sa.Float, server_default="0"),
        sa.Column("expected_cost", sa.Float, server_default="0"),
        sa.Column("time_to_signal", sa.String(80), nullable=True),
        sa.Column("time_to_profit", sa.String(80), nullable=True),
        sa.Column("risk", sa.String(80), server_default="low"),
        sa.Column("required_resources", sa.Text, nullable=True),
        sa.Column("consequence_if_ignored", sa.Text, nullable=True),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "blocker_detection_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("blocker", sa.String(200), nullable=False),
        sa.Column("severity", sa.String(50), server_default="medium"),
        sa.Column("affected_scope", sa.String(300), nullable=False),
        sa.Column("operator_action_needed", sa.Text, nullable=False),
        sa.Column("deadline_or_urgency", sa.String(120), server_default="within_24h"),
        sa.Column("consequence_if_ignored", sa.Text, nullable=False),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("status", sa.String(50), server_default="open"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "operator_commands",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("escalation_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("escalation_events.id"), nullable=True, index=True),
        sa.Column("blocker_report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("blocker_detection_reports.id"), nullable=True, index=True),
        sa.Column("command_text", sa.Text, nullable=False),
        sa.Column("command_type", sa.String(120), nullable=False),
        sa.Column("urgency", sa.String(50), server_default="medium"),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("operator_commands")
    op.drop_table("blocker_detection_reports")
    op.drop_table("escalation_events")
    op.drop_table("override_policies")
    op.drop_table("revenue_pressure_reports")
    op.drop_table("agent_messages")
    op.drop_table("agent_runs")
