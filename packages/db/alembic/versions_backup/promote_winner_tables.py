"""Experiment / Promote-Winner tables (pw_ prefix).

Revision ID: promote_win_001
Revises: pattern_meta_001
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "promote_win_001"
down_revision: Union[str, None] = "pattern_meta_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pw_active_experiments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("experiment_name", sa.String(255), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("tested_variable", sa.String(80), nullable=False),
        sa.Column("target_platform", sa.String(50), nullable=True),
        sa.Column("target_account_id", sa.UUID(), nullable=True),
        sa.Column("target_offer_id", sa.UUID(), nullable=True),
        sa.Column("target_niche", sa.String(255), nullable=True),
        sa.Column("primary_metric", sa.String(60), nullable=False),
        sa.Column("secondary_metrics", JSONB(), server_default="[]", nullable=True),
        sa.Column("min_sample_size", sa.Integer(), server_default="30"),
        sa.Column("confidence_threshold", sa.Float(), server_default="0.9"),
        sa.Column("status", sa.String(30), server_default="active"),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("config_json", JSONB(), server_default="{}", nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["target_offer_id"], ["offers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pwae_brand", "pw_active_experiments", ["brand_id"])
    op.create_index("ix_pwae_status", "pw_active_experiments", ["status"])

    op.create_table(
        "pw_experiment_variants",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("experiment_id", sa.UUID(), nullable=False),
        sa.Column("variant_name", sa.String(255), nullable=False),
        sa.Column("variant_config", JSONB(), server_default="{}", nullable=True),
        sa.Column("is_control", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("sample_count", sa.Integer(), server_default="0"),
        sa.Column("primary_metric_value", sa.Float(), server_default="0"),
        sa.Column("secondary_metric_values", JSONB(), server_default="{}", nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["experiment_id"], ["pw_active_experiments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pwev_experiment", "pw_experiment_variants", ["experiment_id"])

    op.create_table(
        "pw_experiment_assignments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("experiment_id", sa.UUID(), nullable=False),
        sa.Column("variant_id", sa.UUID(), nullable=False),
        sa.Column("content_item_id", sa.UUID(), nullable=True),
        sa.Column("assignment_key", sa.String(255), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["experiment_id"], ["pw_active_experiments.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["pw_experiment_variants.id"]),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "pw_experiment_observations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("experiment_id", sa.UUID(), nullable=False),
        sa.Column("variant_id", sa.UUID(), nullable=False),
        sa.Column("content_item_id", sa.UUID(), nullable=True),
        sa.Column("metric_name", sa.String(60), nullable=False),
        sa.Column("metric_value", sa.Float(), server_default="0"),
        sa.Column("details_json", JSONB(), server_default="{}", nullable=True),
        sa.ForeignKeyConstraint(["experiment_id"], ["pw_active_experiments.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["pw_experiment_variants.id"]),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "pw_experiment_winners",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("experiment_id", sa.UUID(), nullable=False),
        sa.Column("variant_id", sa.UUID(), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("win_margin", sa.Float(), server_default="0"),
        sa.Column("confidence", sa.Float(), server_default="0"),
        sa.Column("sample_size", sa.Integer(), server_default="0"),
        sa.Column("promoted", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["experiment_id"], ["pw_active_experiments.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["pw_experiment_variants.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "pw_experiment_losers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("experiment_id", sa.UUID(), nullable=False),
        sa.Column("variant_id", sa.UUID(), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("loss_margin", sa.Float(), server_default="0"),
        sa.Column("suppressed", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["experiment_id"], ["pw_active_experiments.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["pw_experiment_variants.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "promoted_winner_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("experiment_id", sa.UUID(), nullable=False),
        sa.Column("winner_id", sa.UUID(), nullable=False),
        sa.Column("rule_type", sa.String(60), nullable=False),
        sa.Column("rule_key", sa.String(255), nullable=False),
        sa.Column("rule_value", JSONB(), server_default="{}", nullable=True),
        sa.Column("target_platform", sa.String(50), nullable=True),
        sa.Column("weight_boost", sa.Float(), server_default="0"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["experiment_id"], ["pw_active_experiments.id"]),
        sa.ForeignKeyConstraint(["winner_id"], ["pw_experiment_winners.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pwr_brand", "promoted_winner_rules", ["brand_id"])


def downgrade() -> None:
    for t in (
        "promoted_winner_rules",
        "pw_experiment_losers",
        "pw_experiment_winners",
        "pw_experiment_observations",
        "pw_experiment_assignments",
        "pw_experiment_variants",
        "pw_active_experiments",
    ):
        op.drop_table(t)
