"""MXP Phase D: deal desk and kill ledger tables.

Revision ID: w1x2y3z4a5b6
Revises: v0w1x2y3z4a5
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "w1x2y3z4a5b6"
down_revision: Union[str, None] = "v0w1x2y3z4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "deal_desk_recommendations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("scope_type", sa.String(100), nullable=False),
        sa.Column("scope_id", sa.UUID(), nullable=True),
        sa.Column("deal_strategy", sa.String(100), nullable=False),
        sa.Column("pricing_stance", sa.String(100), nullable=False),
        sa.Column("packaging_recommendation_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("expected_margin", sa.Float(), server_default="0", nullable=False),
        sa.Column("expected_close_probability", sa.Float(), server_default="0", nullable=False),
        sa.Column("confidence_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deal_desk_recommendations_brand_id", "deal_desk_recommendations", ["brand_id"])

    op.create_table(
        "deal_desk_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("recommendation_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("result_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["recommendation_id"], ["deal_desk_recommendations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deal_desk_events_brand_id", "deal_desk_events", ["brand_id"])
    op.create_index("ix_deal_desk_events_recommendation_id", "deal_desk_events", ["recommendation_id"])

    op.create_table(
        "kill_ledger_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("scope_type", sa.String(100), nullable=False),
        sa.Column("scope_id", sa.UUID(), nullable=False),
        sa.Column("kill_reason", sa.Text(), nullable=False),
        sa.Column("performance_snapshot_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("replacement_recommendation_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("confidence_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("killed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kill_ledger_entries_brand_id", "kill_ledger_entries", ["brand_id"])

    op.create_table(
        "kill_hindsight_reviews",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("kill_ledger_entry_id", sa.UUID(), nullable=False),
        sa.Column("hindsight_outcome", sa.Text(), nullable=False),
        sa.Column("was_correct_kill", sa.Boolean(), nullable=True),
        sa.Column("explanation_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["kill_ledger_entry_id"], ["kill_ledger_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kill_hindsight_reviews_brand_id", "kill_hindsight_reviews", ["brand_id"])
    op.create_index(
        "ix_kill_hindsight_reviews_kill_ledger_entry_id", "kill_hindsight_reviews", ["kill_ledger_entry_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_kill_hindsight_reviews_kill_ledger_entry_id", table_name="kill_hindsight_reviews")
    op.drop_index("ix_kill_hindsight_reviews_brand_id", table_name="kill_hindsight_reviews")
    op.drop_table("kill_hindsight_reviews")
    op.drop_index("ix_kill_ledger_entries_brand_id", table_name="kill_ledger_entries")
    op.drop_table("kill_ledger_entries")
    op.drop_index("ix_deal_desk_events_recommendation_id", table_name="deal_desk_events")
    op.drop_index("ix_deal_desk_events_brand_id", table_name="deal_desk_events")
    op.drop_table("deal_desk_events")
    op.drop_index("ix_deal_desk_recommendations_brand_id", table_name="deal_desk_recommendations")
    op.drop_table("deal_desk_recommendations")
