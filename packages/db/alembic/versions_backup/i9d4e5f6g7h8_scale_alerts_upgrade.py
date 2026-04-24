"""scale alerts, launch candidates, blockers, notifications, readiness

Revision ID: i9d4e5f6g7h8
Revises: h8c3d4e5f6g7
Create Date: 2026-03-29
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "i9d4e5f6g7h8"
down_revision: Union[str, None] = "h8c3d4e5f6g7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("operator_alerts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("alert_type", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text()),
        sa.Column("recommended_action", sa.Text()),
        sa.Column("confidence", sa.Float(), server_default="0"),
        sa.Column("urgency", sa.Float(), server_default="0"),
        sa.Column("expected_upside", sa.Float(), server_default="0"),
        sa.Column("expected_cost", sa.Float(), server_default="0"),
        sa.Column("expected_time_to_signal_days", sa.Integer(), server_default="14"),
        sa.Column("supporting_metrics", JSONB()),
        sa.Column("blocking_factors", JSONB()),
        sa.Column("linked_scale_recommendation_id", sa.UUID()),
        sa.Column("linked_launch_candidate_id", sa.UUID()),
        sa.Column("status", sa.String(30), server_default="unread"),
        sa.Column("acknowledged_at", sa.String(50)),
        sa.Column("resolved_at", sa.String(50)),
        sa.Column("resolution_notes", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["linked_scale_recommendation_id"], ["scale_recommendations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_operator_alerts_brand_id", "operator_alerts", ["brand_id"])
    op.create_index("ix_operator_alerts_alert_type", "operator_alerts", ["alert_type"])
    op.create_index("ix_operator_alerts_status", "operator_alerts", ["status"])

    op.create_table("launch_candidates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("candidate_type", sa.String(100), nullable=False),
        sa.Column("primary_platform", sa.String(50), nullable=False),
        sa.Column("secondary_platform", sa.String(50)),
        sa.Column("niche", sa.String(255), nullable=False),
        sa.Column("sub_niche", sa.String(255)),
        sa.Column("language", sa.String(20), server_default="en"),
        sa.Column("geography", sa.String(100), server_default="US"),
        sa.Column("avatar_persona_strategy", sa.Text()),
        sa.Column("monetization_path", sa.Text()),
        sa.Column("content_style", sa.Text()),
        sa.Column("posting_strategy", sa.Text()),
        sa.Column("expected_monthly_revenue_min", sa.Float(), server_default="0"),
        sa.Column("expected_monthly_revenue_max", sa.Float(), server_default="0"),
        sa.Column("expected_launch_cost", sa.Float(), server_default="0"),
        sa.Column("expected_time_to_signal_days", sa.Integer(), server_default="30"),
        sa.Column("expected_time_to_profit_days", sa.Integer(), server_default="90"),
        sa.Column("cannibalization_risk", sa.Float(), server_default="0"),
        sa.Column("audience_separation_score", sa.Float(), server_default="0"),
        sa.Column("confidence", sa.Float(), server_default="0"),
        sa.Column("urgency", sa.Float(), server_default="0"),
        sa.Column("supporting_reasons", JSONB()),
        sa.Column("required_resources", JSONB()),
        sa.Column("launch_blockers", JSONB()),
        sa.Column("linked_scale_recommendation_id", sa.UUID()),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["linked_scale_recommendation_id"], ["scale_recommendations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_launch_candidates_brand_id", "launch_candidates", ["brand_id"])
    op.create_index("ix_launch_candidates_candidate_type", "launch_candidates", ["candidate_type"])

    op.create_table("scale_blocker_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("blocker_type", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20), server_default="medium"),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("explanation", sa.Text()),
        sa.Column("recommended_fix", sa.Text()),
        sa.Column("current_value", sa.Float(), server_default="0"),
        sa.Column("threshold_value", sa.Float(), server_default="0"),
        sa.Column("evidence", JSONB()),
        sa.Column("is_resolved", sa.Boolean(), server_default="false"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scale_blocker_reports_brand_id", "scale_blocker_reports", ["brand_id"])

    op.create_table("notification_deliveries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("alert_id", sa.UUID()),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("recipient", sa.String(255)),
        sa.Column("payload", JSONB()),
        sa.Column("status", sa.String(30), server_default="pending"),
        sa.Column("attempts", sa.Integer(), server_default="0"),
        sa.Column("last_error", sa.Text()),
        sa.Column("delivered_at", sa.String(50)),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["alert_id"], ["operator_alerts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_deliveries_brand_id", "notification_deliveries", ["brand_id"])
    op.create_index("ix_notification_deliveries_status", "notification_deliveries", ["status"])

    op.create_table("launch_readiness_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("launch_readiness_score", sa.Float(), server_default="0"),
        sa.Column("explanation", sa.Text()),
        sa.Column("recommended_action", sa.String(50), server_default="monitor"),
        sa.Column("gating_factors", JSONB()),
        sa.Column("components", JSONB()),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_launch_readiness_reports_brand_id", "launch_readiness_reports", ["brand_id"])


def downgrade() -> None:
    op.drop_table("launch_readiness_reports")
    op.drop_table("notification_deliveries")
    op.drop_table("scale_blocker_reports")
    op.drop_table("launch_candidates")
    op.drop_table("operator_alerts")
