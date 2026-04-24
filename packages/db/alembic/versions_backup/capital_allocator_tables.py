"""Portfolio Capital Allocator tables.

Revision ID: cap_alloc_001
Revises: promote_win_001
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "cap_alloc_001"
down_revision: Union[str, None] = "promote_win_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ca_allocation_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("total_budget", sa.Float(), server_default="0"),
        sa.Column("allocated_budget", sa.Float(), server_default="0"),
        sa.Column("experiment_reserve", sa.Float(), server_default="0"),
        sa.Column("hero_spend", sa.Float(), server_default="0"),
        sa.Column("bulk_spend", sa.Float(), server_default="0"),
        sa.Column("target_count", sa.Integer(), server_default="0"),
        sa.Column("starved_count", sa.Integer(), server_default="0"),
        sa.Column("summary_json", JSONB(), server_default="{}", nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_car_brand", "ca_allocation_reports", ["brand_id"])

    op.create_table(
        "ca_allocation_targets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("target_type", sa.String(60), nullable=False),
        sa.Column("target_key", sa.String(255), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=True),
        sa.Column("expected_return", sa.Float(), server_default="0"),
        sa.Column("expected_cost", sa.Float(), server_default="0"),
        sa.Column("confidence", sa.Float(), server_default="0"),
        sa.Column("account_health", sa.Float(), server_default="1"),
        sa.Column("fatigue_score", sa.Float(), server_default="0"),
        sa.Column("pattern_win_score", sa.Float(), server_default="0"),
        sa.Column("provider_tier", sa.String(20), server_default="bulk"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["report_id"], ["ca_allocation_reports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_at_brand", "ca_allocation_targets", ["brand_id"])

    op.create_table(
        "ca_allocation_decisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("allocated_budget", sa.Float(), server_default="0"),
        sa.Column("allocated_volume", sa.Integer(), server_default="0"),
        sa.Column("provider_tier", sa.String(20), server_default="bulk"),
        sa.Column("allocation_pct", sa.Float(), server_default="0"),
        sa.Column("starved", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["report_id"], ["ca_allocation_reports.id"]),
        sa.ForeignKeyConstraint(["target_id"], ["ca_allocation_targets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "ca_allocation_constraints",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("constraint_type", sa.String(60), nullable=False),
        sa.Column("constraint_key", sa.String(255), nullable=False),
        sa.Column("min_value", sa.Float(), server_default="0"),
        sa.Column("max_value", sa.Float(), server_default="1"),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "ca_allocation_rebalances",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("rebalance_reason", sa.String(120), nullable=False),
        sa.Column("changes_json", JSONB(), server_default="{}", nullable=True),
        sa.Column("targets_starved", sa.Integer(), server_default="0"),
        sa.Column("targets_boosted", sa.Integer(), server_default="0"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["report_id"], ["ca_allocation_reports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    for t in (
        "ca_allocation_rebalances",
        "ca_allocation_constraints",
        "ca_allocation_decisions",
        "ca_allocation_targets",
        "ca_allocation_reports",
    ):
        op.drop_table(t)
