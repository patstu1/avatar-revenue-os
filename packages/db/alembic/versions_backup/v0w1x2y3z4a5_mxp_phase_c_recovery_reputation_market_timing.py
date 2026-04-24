"""MXP Phase C: recovery, reputation, market timing tables.

Revision ID: v0w1x2y3z4a5
Revises: u2v3w4x5y6z7
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "v0w1x2y3z4a5"
down_revision: Union[str, None] = "u2v3w4x5y6z7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recovery_incidents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("incident_type", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("scope_type", sa.String(100), nullable=False),
        sa.Column("scope_id", sa.UUID(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(50), server_default="open", nullable=False),
        sa.Column("explanation_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("escalation_state", sa.String(50), server_default="open", nullable=False),
        sa.Column("recommended_recovery_action", sa.String(100), nullable=True),
        sa.Column("automatic_action_taken", sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recovery_incidents_brand_id", "recovery_incidents", ["brand_id"])

    op.create_table(
        "recovery_actions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("incident_id", sa.UUID(), nullable=False),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("action_mode", sa.String(50), nullable=False),
        sa.Column("executed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("expected_effect_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("result_json", JSONB, nullable=True),
        sa.Column("confidence_score", sa.Float(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["incident_id"], ["recovery_incidents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recovery_actions_brand_id", "recovery_actions", ["brand_id"])
    op.create_index("ix_recovery_actions_incident_id", "recovery_actions", ["incident_id"])

    op.create_table(
        "reputation_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("scope_type", sa.String(100), nullable=False),
        sa.Column("scope_id", sa.UUID(), nullable=True),
        sa.Column("reputation_risk_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("primary_risks_json", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column("recommended_mitigation_json", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column("expected_impact_if_unresolved", sa.Float(), server_default="0", nullable=False),
        sa.Column("confidence_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reputation_reports_brand_id", "reputation_reports", ["brand_id"])

    op.create_table(
        "reputation_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("scope_type", sa.String(100), nullable=True),
        sa.Column("scope_id", sa.UUID(), nullable=True),
        sa.Column("details_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reputation_events_brand_id", "reputation_events", ["brand_id"])

    op.create_table(
        "market_timing_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("market_category", sa.String(100), nullable=False),
        sa.Column("timing_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("active_window", sa.String(200), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("expected_uplift", sa.Float(), server_default="0", nullable=False),
        sa.Column("confidence_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_timing_reports_brand_id", "market_timing_reports", ["brand_id"])

    op.create_table(
        "macro_signal_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=True),
        sa.Column("signal_type", sa.String(100), nullable=False),
        sa.Column("source_name", sa.String(200), nullable=False),
        sa.Column("signal_metadata_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_macro_signal_events_brand_id", "macro_signal_events", ["brand_id"])


def downgrade() -> None:
    op.drop_index("ix_macro_signal_events_brand_id", table_name="macro_signal_events")
    op.drop_table("macro_signal_events")
    op.drop_index("ix_market_timing_reports_brand_id", table_name="market_timing_reports")
    op.drop_table("market_timing_reports")
    op.drop_index("ix_reputation_events_brand_id", table_name="reputation_events")
    op.drop_table("reputation_events")
    op.drop_index("ix_reputation_reports_brand_id", table_name="reputation_reports")
    op.drop_table("reputation_reports")
    op.drop_index("ix_recovery_actions_incident_id", table_name="recovery_actions")
    op.drop_index("ix_recovery_actions_brand_id", table_name="recovery_actions")
    op.drop_table("recovery_actions")
    op.drop_index("ix_recovery_incidents_brand_id", table_name="recovery_incidents")
    op.drop_table("recovery_incidents")
