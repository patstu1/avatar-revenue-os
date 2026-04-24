"""Winning-Pattern Memory tables.

Revision ID: pattern_mem_001
Revises: content_routing_001
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "pattern_mem_001"
down_revision: Union[str, None] = "content_routing_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "winning_pattern_memory",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("pattern_type", sa.String(60), nullable=False),
        sa.Column("pattern_name", sa.String(255), nullable=False),
        sa.Column("pattern_signature", sa.String(500), nullable=False),
        sa.Column("platform", sa.String(50), nullable=True),
        sa.Column("niche", sa.String(255), nullable=True),
        sa.Column("sub_niche", sa.String(255), nullable=True),
        sa.Column("content_form", sa.String(80), nullable=True),
        sa.Column("offer_id", sa.UUID(), nullable=True),
        sa.Column("monetization_method", sa.String(60), nullable=True),
        sa.Column("performance_band", sa.String(20), server_default="standard", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("win_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("decay_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("usage_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_seen_at", sa.String(50), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("evidence_json", JSONB(), server_default="{}", nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["offer_id"], ["offers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wpm_brand", "winning_pattern_memory", ["brand_id"])
    op.create_index("ix_wpm_type", "winning_pattern_memory", ["pattern_type"])
    op.create_index("ix_wpm_platform", "winning_pattern_memory", ["platform"])

    op.create_table(
        "winning_pattern_evidence",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("pattern_id", sa.UUID(), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("content_item_id", sa.UUID(), nullable=True),
        sa.Column("impressions", sa.Integer(), server_default="0"),
        sa.Column("clicks", sa.Integer(), server_default="0"),
        sa.Column("saves", sa.Integer(), server_default="0"),
        sa.Column("comments", sa.Integer(), server_default="0"),
        sa.Column("watch_time_seconds", sa.Integer(), server_default="0"),
        sa.Column("conversion_rate", sa.Float(), server_default="0"),
        sa.Column("epc", sa.Float(), server_default="0"),
        sa.Column("aov", sa.Float(), server_default="0"),
        sa.Column("profit", sa.Float(), server_default="0"),
        sa.Column("revenue_density", sa.Float(), server_default="0"),
        sa.Column("engagement_rate", sa.Float(), server_default="0"),
        sa.Column("details_json", JSONB(), server_default="{}", nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["pattern_id"], ["winning_pattern_memory.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wpe_pattern", "winning_pattern_evidence", ["pattern_id"])

    op.create_table(
        "winning_pattern_clusters",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("cluster_name", sa.String(255), nullable=False),
        sa.Column("cluster_type", sa.String(60), nullable=False),
        sa.Column("pattern_ids", JSONB(), server_default="[]", nullable=True),
        sa.Column("avg_win_score", sa.Float(), server_default="0"),
        sa.Column("pattern_count", sa.Integer(), server_default="0"),
        sa.Column("platform", sa.String(50), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wpc_brand", "winning_pattern_clusters", ["brand_id"])

    op.create_table(
        "losing_pattern_memory",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("pattern_type", sa.String(60), nullable=False),
        sa.Column("pattern_name", sa.String(255), nullable=False),
        sa.Column("pattern_signature", sa.String(500), nullable=False),
        sa.Column("platform", sa.String(50), nullable=True),
        sa.Column("fail_score", sa.Float(), server_default="0"),
        sa.Column("usage_count", sa.Integer(), server_default="0"),
        sa.Column("suppress_reason", sa.Text(), nullable=True),
        sa.Column("evidence_json", JSONB(), server_default="{}", nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lpm_brand", "losing_pattern_memory", ["brand_id"])

    op.create_table(
        "pattern_reuse_recommendations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("pattern_id", sa.UUID(), nullable=False),
        sa.Column("target_platform", sa.String(50), nullable=False),
        sa.Column("target_content_form", sa.String(80), nullable=True),
        sa.Column("expected_uplift", sa.Float(), server_default="0"),
        sa.Column("confidence", sa.Float(), server_default="0"),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["pattern_id"], ["winning_pattern_memory.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prr_brand", "pattern_reuse_recommendations", ["brand_id"])

    op.create_table(
        "pattern_decay_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("pattern_id", sa.UUID(), nullable=False),
        sa.Column("decay_rate", sa.Float(), server_default="0"),
        sa.Column("decay_reason", sa.String(120), nullable=False),
        sa.Column("previous_win_score", sa.Float(), server_default="0"),
        sa.Column("current_win_score", sa.Float(), server_default="0"),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["pattern_id"], ["winning_pattern_memory.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pdr_brand", "pattern_decay_reports", ["brand_id"])


def downgrade() -> None:
    for t in (
        "pattern_decay_reports",
        "pattern_reuse_recommendations",
        "losing_pattern_memory",
        "winning_pattern_clusters",
        "winning_pattern_evidence",
        "winning_pattern_memory",
    ):
        op.drop_table(t)
