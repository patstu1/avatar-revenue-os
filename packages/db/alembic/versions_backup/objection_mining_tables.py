"""Objection Mining tables.

Revision ID: om_001
Revises: qg_001
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "om_001"
down_revision: Union[str, None] = "qg_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("om_objection_signals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=True),
        sa.Column("content_item_id", sa.UUID(), nullable=True),
        sa.Column("offer_id", sa.UUID(), nullable=True),
        sa.Column("objection_type", sa.String(40), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("extracted_objection", sa.Text(), nullable=False),
        sa.Column("severity", sa.Float(), server_default="0.5"),
        sa.Column("monetization_impact", sa.Float(), server_default="0"),
        sa.Column("platform", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"]),
        sa.ForeignKeyConstraint(["offer_id"], ["offers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_oms_brand", "om_objection_signals", ["brand_id"])
    op.create_index("ix_oms_type", "om_objection_signals", ["objection_type"])

    op.create_table("om_objection_clusters",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("objection_type", sa.String(40), nullable=False),
        sa.Column("cluster_label", sa.String(255), nullable=False),
        sa.Column("signal_count", sa.Integer(), server_default="0"),
        sa.Column("avg_severity", sa.Float(), server_default="0"),
        sa.Column("avg_monetization_impact", sa.Float(), server_default="0"),
        sa.Column("representative_texts", JSONB(), server_default="[]", nullable=True),
        sa.Column("recommended_response_angle", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_omc_brand", "om_objection_clusters", ["brand_id"])

    op.create_table("om_objection_responses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("cluster_id", sa.UUID(), nullable=False),
        sa.Column("response_type", sa.String(60), nullable=False),
        sa.Column("response_angle", sa.Text(), nullable=False),
        sa.Column("target_channel", sa.String(60), nullable=False),
        sa.Column("priority", sa.String(20), server_default="medium"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["cluster_id"], ["om_objection_clusters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table("om_priority_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("top_objections", JSONB(), server_default="[]", nullable=True),
        sa.Column("total_signals", sa.Integer(), server_default="0"),
        sa.Column("total_clusters", sa.Integer(), server_default="0"),
        sa.Column("highest_impact_type", sa.String(40), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    for t in ("om_priority_reports", "om_objection_responses", "om_objection_clusters", "om_objection_signals"):
        op.drop_table(t)
