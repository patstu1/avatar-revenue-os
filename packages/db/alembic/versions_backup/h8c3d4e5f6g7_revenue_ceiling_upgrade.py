"""revenue ceiling upgrade: offer_stack, density score, monetization_recommendations

Revision ID: h8c3d4e5f6g7
Revises: g7b2c3d4e5f6
Create Date: 2026-03-29

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "h8c3d4e5f6g7"
down_revision: Union[str, None] = "g7b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("content_items", sa.Column("offer_stack", JSONB(), nullable=True))
    op.add_column(
        "content_items", sa.Column("monetization_density_score", sa.Float(), nullable=False, server_default="0")
    )
    op.alter_column("content_items", "monetization_density_score", server_default=None)

    op.create_table(
        "monetization_recommendations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("content_item_id", sa.UUID(), nullable=True),
        sa.Column("recommendation_type", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("expected_revenue_uplift", sa.Float(), nullable=False, server_default="0"),
        sa.Column("expected_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("evidence", JSONB(), nullable=True),
        sa.Column("is_actioned", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_monetization_recommendations_brand_id"), "monetization_recommendations", ["brand_id"])
    op.create_index(
        op.f("ix_monetization_recommendations_recommendation_type"),
        "monetization_recommendations",
        ["recommendation_type"],
    )
    op.create_index(
        op.f("ix_monetization_recommendations_content_item_id"), "monetization_recommendations", ["content_item_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_monetization_recommendations_content_item_id"), table_name="monetization_recommendations")
    op.drop_index(
        op.f("ix_monetization_recommendations_recommendation_type"), table_name="monetization_recommendations"
    )
    op.drop_index(op.f("ix_monetization_recommendations_brand_id"), table_name="monetization_recommendations")
    op.drop_table("monetization_recommendations")
    op.drop_column("content_items", "monetization_density_score")
    op.drop_column("content_items", "offer_stack")
