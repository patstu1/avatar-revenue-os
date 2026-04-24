"""growth commander: growth_commands table

Revision ID: j0e5f6g7h8i9
Revises: i9d4e5f6g7h8
Create Date: 2026-03-29
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "j0e5f6g7h8i9"
down_revision: Union[str, None] = "i9d4e5f6g7h8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("growth_commands",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("command_type", sa.String(100), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="50"),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("exact_instruction", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text()),
        sa.Column("comparison", JSONB()),
        sa.Column("platform_fit", JSONB()),
        sa.Column("niche_fit", JSONB()),
        sa.Column("monetization_path", JSONB()),
        sa.Column("cannibalization_analysis", JSONB()),
        sa.Column("success_threshold", JSONB()),
        sa.Column("failure_threshold", JSONB()),
        sa.Column("expected_upside", sa.Float(), server_default="0"),
        sa.Column("expected_cost", sa.Float(), server_default="0"),
        sa.Column("expected_time_to_signal_days", sa.Integer(), server_default="14"),
        sa.Column("expected_time_to_profit_days", sa.Integer(), server_default="60"),
        sa.Column("confidence", sa.Float(), server_default="0"),
        sa.Column("urgency", sa.Float(), server_default="0"),
        sa.Column("blocking_factors", JSONB()),
        sa.Column("first_week_plan", JSONB()),
        sa.Column("linked_launch_candidate_id", sa.UUID()),
        sa.Column("linked_scale_recommendation_id", sa.UUID()),
        sa.Column("evidence", JSONB()),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_growth_commands_brand_id", "growth_commands", ["brand_id"])
    op.create_index("ix_growth_commands_command_type", "growth_commands", ["command_type"])


def downgrade() -> None:
    op.drop_table("growth_commands")
