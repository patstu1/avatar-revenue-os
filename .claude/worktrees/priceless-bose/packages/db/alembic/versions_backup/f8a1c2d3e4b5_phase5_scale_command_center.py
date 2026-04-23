"""phase5 scale command center columns

Revision ID: f8a1c2d3e4b5
Revises: e95d8f95a89e
Create Date: 2026-03-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "f8a1c2d3e4b5"
down_revision: Union[str, None] = "e95d8f95a89e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "creator_accounts",
        sa.Column("scale_role", sa.String(length=32), nullable=True),
    )
    op.create_index(op.f("ix_creator_accounts_scale_role"), "creator_accounts", ["scale_role"], unique=False)

    op.add_column(
        "scale_recommendations",
        sa.Column("recommendation_key", sa.String(length=80), nullable=False, server_default="monitor"),
    )
    op.add_column(
        "scale_recommendations",
        sa.Column("scale_readiness_score", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "scale_recommendations",
        sa.Column("cannibalization_risk_score", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "scale_recommendations",
        sa.Column("audience_segment_separation", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "scale_recommendations",
        sa.Column("expansion_confidence", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "scale_recommendations",
        sa.Column("recommended_account_count", sa.Integer(), nullable=False, server_default="2"),
    )
    op.add_column(
        "scale_recommendations",
        sa.Column("weekly_action_plan", JSONB(), nullable=True),
    )
    op.add_column(
        "scale_recommendations",
        sa.Column("best_next_account", JSONB(), nullable=True),
    )
    op.create_index(
        op.f("ix_scale_recommendations_recommendation_key"),
        "scale_recommendations",
        ["recommendation_key"],
        unique=False,
    )
    op.alter_column("scale_recommendations", "recommendation_key", server_default=None)
    op.alter_column("scale_recommendations", "scale_readiness_score", server_default=None)
    op.alter_column("scale_recommendations", "cannibalization_risk_score", server_default=None)
    op.alter_column("scale_recommendations", "audience_segment_separation", server_default=None)
    op.alter_column("scale_recommendations", "expansion_confidence", server_default=None)
    op.alter_column("scale_recommendations", "recommended_account_count", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_scale_recommendations_recommendation_key"), table_name="scale_recommendations")
    op.drop_column("scale_recommendations", "best_next_account")
    op.drop_column("scale_recommendations", "weekly_action_plan")
    op.drop_column("scale_recommendations", "recommended_account_count")
    op.drop_column("scale_recommendations", "expansion_confidence")
    op.drop_column("scale_recommendations", "audience_segment_separation")
    op.drop_column("scale_recommendations", "cannibalization_risk_score")
    op.drop_column("scale_recommendations", "scale_readiness_score")
    op.drop_column("scale_recommendations", "recommendation_key")

    op.drop_index(op.f("ix_creator_accounts_scale_role"), table_name="creator_accounts")
    op.drop_column("creator_accounts", "scale_role")
