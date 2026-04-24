"""Autonomous Execution Phase A: signal scanning, queue, warm-up, output & maturity tables.

Revision ID: ae01phase_a_001
Revises: a2b3c4d5e6f7
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "ae01phase_a_001"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. signal_scan_runs
    op.create_table(
        "signal_scan_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("scan_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), server_default="running", nullable=True),
        sa.Column("signals_detected", sa.Integer(), server_default="0", nullable=True),
        sa.Column("signals_actionable", sa.Integer(), server_default="0", nullable=True),
        sa.Column("scan_duration_ms", sa.Integer(), nullable=True),
        sa.Column("scan_metadata_json", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signal_scan_runs_brand_id", "signal_scan_runs", ["brand_id"])

    # 2. normalized_signal_events
    op.create_table(
        "normalized_signal_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("scan_run_id", sa.UUID(), nullable=True),
        sa.Column("signal_type", sa.String(100), nullable=False),
        sa.Column("signal_source", sa.String(100), nullable=False),
        sa.Column("raw_payload_json", JSONB, nullable=True),
        sa.Column("normalized_title", sa.String(500), nullable=False),
        sa.Column("normalized_description", sa.Text(), nullable=True),
        sa.Column("freshness_score", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("monetization_relevance", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("urgency_score", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("confidence", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_actionable", sa.Boolean(), server_default="false", nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["scan_run_id"], ["signal_scan_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_normalized_signal_events_brand_id", "normalized_signal_events", ["brand_id"])
    op.create_index("ix_normalized_signal_events_scan_run_id", "normalized_signal_events", ["scan_run_id"])

    # 3. auto_queue_items
    op.create_table(
        "auto_queue_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("signal_event_id", sa.UUID(), nullable=True),
        sa.Column("queue_item_type", sa.String(100), nullable=False),
        sa.Column("target_account_id", sa.UUID(), nullable=True),
        sa.Column("target_account_role", sa.String(100), nullable=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("niche", sa.String(255), nullable=False),
        sa.Column("sub_niche", sa.String(255), nullable=True),
        sa.Column("content_family", sa.String(100), nullable=True),
        sa.Column("monetization_path", sa.String(100), nullable=True),
        sa.Column("priority_score", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("urgency_score", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("queue_status", sa.String(50), server_default="pending", nullable=True),
        sa.Column("suppression_flags_json", JSONB, nullable=True),
        sa.Column("hold_reason", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["signal_event_id"], ["normalized_signal_events.id"]),
        sa.ForeignKeyConstraint(["target_account_id"], ["creator_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auto_queue_items_brand_id", "auto_queue_items", ["brand_id"])
    op.create_index("ix_auto_queue_items_signal_event_id", "auto_queue_items", ["signal_event_id"])
    op.create_index("ix_auto_queue_items_target_account_id", "auto_queue_items", ["target_account_id"])

    # 4. platform_warmup_policies
    op.create_table(
        "platform_warmup_policies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("initial_posts_per_week_min", sa.Integer(), server_default="1", nullable=True),
        sa.Column("initial_posts_per_week_max", sa.Integer(), server_default="3", nullable=True),
        sa.Column("warmup_duration_weeks_min", sa.Integer(), server_default="2", nullable=True),
        sa.Column("warmup_duration_weeks_max", sa.Integer(), server_default="4", nullable=True),
        sa.Column("steady_state_posts_per_week_min", sa.Integer(), server_default="3", nullable=True),
        sa.Column("steady_state_posts_per_week_max", sa.Integer(), server_default="14", nullable=True),
        sa.Column("max_safe_posts_per_day", sa.Integer(), server_default="3", nullable=True),
        sa.Column("ramp_conditions_json", JSONB, nullable=True),
        sa.Column("account_health_signals_json", JSONB, nullable=True),
        sa.Column("spam_risk_signals_json", JSONB, nullable=True),
        sa.Column("trust_risk_signals_json", JSONB, nullable=True),
        sa.Column("scale_ready_conditions_json", JSONB, nullable=True),
        sa.Column("ramp_behavior", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform"),
    )

    # 5. account_warmup_plans
    op.create_table(
        "account_warmup_plans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("warmup_phase", sa.String(50), server_default="phase_1_warmup", nullable=True),
        sa.Column("initial_posts_per_week", sa.Integer(), server_default="1", nullable=True),
        sa.Column("current_posts_per_week", sa.Integer(), server_default="1", nullable=True),
        sa.Column("target_posts_per_week", sa.Integer(), nullable=True),
        sa.Column("warmup_start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("warmup_end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("engagement_target", sa.Float(), server_default="0.02", nullable=True),
        sa.Column("trust_target", sa.Float(), server_default="0.5", nullable=True),
        sa.Column("content_mix_json", JSONB, nullable=True),
        sa.Column("failure_signals_json", JSONB, nullable=True),
        sa.Column("ramp_conditions_json", JSONB, nullable=True),
        sa.Column("confidence", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["creator_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_warmup_plans_brand_id", "account_warmup_plans", ["brand_id"])
    op.create_index("ix_account_warmup_plans_account_id", "account_warmup_plans", ["account_id"])

    # 6. account_output_reports
    op.create_table(
        "account_output_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("current_output_per_week", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("recommended_output_per_week", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("max_safe_output_per_week", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("max_profitable_output_per_week", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("throttle_reason", sa.Text(), nullable=True),
        sa.Column("next_increase_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quality_score", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("monetization_response_score", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("account_health_score", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("saturation_score", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("confidence", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["creator_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_output_reports_brand_id", "account_output_reports", ["brand_id"])
    op.create_index("ix_account_output_reports_account_id", "account_output_reports", ["account_id"])

    # 7. account_maturity_reports
    op.create_table(
        "account_maturity_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("maturity_state", sa.String(50), nullable=False),
        sa.Column("previous_state", sa.String(50), nullable=True),
        sa.Column("days_in_current_state", sa.Integer(), server_default="0", nullable=True),
        sa.Column("posts_published", sa.Integer(), server_default="0", nullable=True),
        sa.Column("avg_engagement_rate", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("follower_velocity", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("health_score", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("transition_reason", sa.Text(), nullable=True),
        sa.Column("next_expected_transition", sa.String(50), nullable=True),
        sa.Column("confidence", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["creator_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_maturity_reports_brand_id", "account_maturity_reports", ["brand_id"])
    op.create_index("ix_account_maturity_reports_account_id", "account_maturity_reports", ["account_id"])

    # 8. output_ramp_events
    op.create_table(
        "output_ramp_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("from_output_per_week", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("to_output_per_week", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("trigger_reason", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["creator_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_output_ramp_events_brand_id", "output_ramp_events", ["brand_id"])
    op.create_index("ix_output_ramp_events_account_id", "output_ramp_events", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_output_ramp_events_account_id", table_name="output_ramp_events")
    op.drop_index("ix_output_ramp_events_brand_id", table_name="output_ramp_events")
    op.drop_table("output_ramp_events")

    op.drop_index("ix_account_maturity_reports_account_id", table_name="account_maturity_reports")
    op.drop_index("ix_account_maturity_reports_brand_id", table_name="account_maturity_reports")
    op.drop_table("account_maturity_reports")

    op.drop_index("ix_account_output_reports_account_id", table_name="account_output_reports")
    op.drop_index("ix_account_output_reports_brand_id", table_name="account_output_reports")
    op.drop_table("account_output_reports")

    op.drop_index("ix_account_warmup_plans_account_id", table_name="account_warmup_plans")
    op.drop_index("ix_account_warmup_plans_brand_id", table_name="account_warmup_plans")
    op.drop_table("account_warmup_plans")

    op.drop_table("platform_warmup_policies")

    op.drop_index("ix_auto_queue_items_target_account_id", table_name="auto_queue_items")
    op.drop_index("ix_auto_queue_items_signal_event_id", table_name="auto_queue_items")
    op.drop_index("ix_auto_queue_items_brand_id", table_name="auto_queue_items")
    op.drop_table("auto_queue_items")

    op.drop_index("ix_normalized_signal_events_scan_run_id", table_name="normalized_signal_events")
    op.drop_index("ix_normalized_signal_events_brand_id", table_name="normalized_signal_events")
    op.drop_table("normalized_signal_events")

    op.drop_index("ix_signal_scan_runs_brand_id", table_name="signal_scan_runs")
    op.drop_table("signal_scan_runs")
