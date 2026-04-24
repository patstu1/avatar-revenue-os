"""Trend / Viral Opportunity Engine tables.

Revision ID: tv_001
Revises: ca_001
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "tv_001"
down_revision: Union[str, None] = "ca_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _b():
    return [sa.Column("id", sa.UUID(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)]

def upgrade() -> None:
    op.create_table("tv_signals", *_b(), sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("source", sa.String(60), nullable=False), sa.Column("topic", sa.String(500), nullable=False), sa.Column("signal_strength", sa.Float(), server_default="0"), sa.Column("velocity", sa.Float(), server_default="0"), sa.Column("first_seen_at", sa.DateTime(timezone=True)), sa.Column("last_seen_at", sa.DateTime(timezone=True)), sa.Column("truth_label", sa.String(40), server_default="internal_proxy"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_tvs_brand", "tv_signals", ["brand_id"])

    op.create_table("tv_velocity", *_b(), sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("topic", sa.String(500), nullable=False), sa.Column("current_velocity", sa.Float(), server_default="0"), sa.Column("previous_velocity", sa.Float(), server_default="0"), sa.Column("acceleration", sa.Float(), server_default="0"), sa.Column("breakout", sa.Boolean(), server_default=sa.text("false")), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("tv_opportunities", *_b(), sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("topic", sa.String(500), nullable=False), sa.Column("source", sa.String(60), nullable=False), sa.Column("first_seen_at", sa.DateTime(timezone=True)), sa.Column("last_seen_at", sa.DateTime(timezone=True)), sa.Column("velocity_score", sa.Float(), server_default="0"), sa.Column("novelty_score", sa.Float(), server_default="0"), sa.Column("relevance_score", sa.Float(), server_default="0"), sa.Column("revenue_potential_score", sa.Float(), server_default="0"), sa.Column("platform_fit_score", sa.Float(), server_default="0"), sa.Column("account_fit_score", sa.Float(), server_default="0"), sa.Column("content_form_fit_score", sa.Float(), server_default="0"), sa.Column("saturation_risk", sa.Float(), server_default="0"), sa.Column("compliance_risk", sa.Float(), server_default="0"), sa.Column("opportunity_type", sa.String(40), server_default="growth"), sa.Column("recommended_platform", sa.String(50)), sa.Column("recommended_account_role", sa.String(40)), sa.Column("recommended_content_form", sa.String(60)), sa.Column("recommended_monetization", sa.String(60)), sa.Column("urgency", sa.Float(), server_default="0.5"), sa.Column("confidence", sa.Float(), server_default="0"), sa.Column("composite_score", sa.Float(), server_default="0"), sa.Column("explanation", sa.Text()), sa.Column("blocker_state", sa.String(60)), sa.Column("truth_label", sa.String(40), server_default="internal_proxy"), sa.Column("status", sa.String(20), server_default="active"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_tvo_brand", "tv_opportunities", ["brand_id"])

    op.create_table("tv_opp_scores", *_b(), sa.Column("opportunity_id", sa.UUID(), nullable=False), sa.Column("dimension", sa.String(40), nullable=False), sa.Column("score", sa.Float(), server_default="0"), sa.Column("explanation", sa.Text()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["opportunity_id"], ["tv_opportunities.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("tv_duplicates", *_b(), sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("original_topic", sa.String(500), nullable=False), sa.Column("duplicate_topic", sa.String(500), nullable=False), sa.Column("similarity", sa.Float(), server_default="0"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("tv_suppressions", *_b(), sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("suppression_type", sa.String(40), nullable=False), sa.Column("pattern", sa.String(255), nullable=False), sa.Column("reason", sa.Text(), nullable=False), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("tv_blockers", *_b(), sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("opportunity_id", sa.UUID()), sa.Column("blocker_type", sa.String(60), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("severity", sa.String(20), server_default="medium"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.ForeignKeyConstraint(["opportunity_id"], ["tv_opportunities.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("tv_source_health", *_b(), sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("source_name", sa.String(60), nullable=False), sa.Column("status", sa.String(20), server_default="healthy"), sa.Column("last_signal_count", sa.Integer(), server_default="0"), sa.Column("truth_label", sa.String(40), server_default="internal_proxy"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.PrimaryKeyConstraint("id"))


def downgrade() -> None:
    for t in ("tv_source_health", "tv_blockers", "tv_suppressions", "tv_duplicates", "tv_opp_scores", "tv_opportunities", "tv_velocity", "tv_signals"):
        op.drop_table(t)
