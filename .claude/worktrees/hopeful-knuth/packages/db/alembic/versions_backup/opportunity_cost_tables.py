"""Opportunity-Cost Ranking tables.

Revision ID: oc_001
Revises: om_001
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "oc_001"
down_revision: Union[str, None] = "om_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("oc_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("total_actions", sa.Integer(), server_default="0"),
        sa.Column("top_action_type", sa.String(60), nullable=True),
        sa.Column("total_opportunity_cost", sa.Float(), server_default="0"),
        sa.Column("safe_to_wait_count", sa.Integer(), server_default="0"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ocr_brand", "oc_reports", ["brand_id"])

    op.create_table("oc_ranked_actions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("action_type", sa.String(60), nullable=False),
        sa.Column("action_key", sa.String(255), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=True),
        sa.Column("expected_upside", sa.Float(), server_default="0"),
        sa.Column("cost_of_delay", sa.Float(), server_default="0"),
        sa.Column("urgency", sa.Float(), server_default="0"),
        sa.Column("confidence", sa.Float(), server_default="0"),
        sa.Column("composite_rank", sa.Float(), server_default="0"),
        sa.Column("rank_position", sa.Integer(), server_default="0"),
        sa.Column("safe_to_wait", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["report_id"], ["oc_reports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table("oc_cost_of_delay",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("action_type", sa.String(60), nullable=False),
        sa.Column("action_key", sa.String(255), nullable=False),
        sa.Column("daily_cost", sa.Float(), server_default="0"),
        sa.Column("weekly_cost", sa.Float(), server_default="0"),
        sa.Column("decay_rate", sa.Float(), server_default="0"),
        sa.Column("time_sensitivity", sa.String(20), server_default="normal"),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    for t in ("oc_cost_of_delay", "oc_ranked_actions", "oc_reports"):
        op.drop_table(t)
