"""growth commander: audit trail for recompute runs

Revision ID: k1f6g7h8i9j0
Revises: j0e5f6g7h8i9
Create Date: 2026-03-29
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "k1f6g7h8i9j0"
down_revision: Union[str, None] = "j0e5f6g7h8i9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "growth_command_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("triggered_by_user_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="completed"),
        sa.Column("commands_generated", sa.Integer(), server_default="0", nullable=False),
        sa.Column("command_types", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("portfolio_balance_snapshot", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("whitespace_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_growth_command_runs_brand_id", "growth_command_runs", ["brand_id"])
    op.create_index("ix_growth_command_runs_created_at", "growth_command_runs", ["created_at"])


def downgrade() -> None:
    op.drop_table("growth_command_runs")
