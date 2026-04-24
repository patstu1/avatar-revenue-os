"""Expansion Pack 2 Phase B: pricing, bundling, retention, reactivation.

Revision ID: t1u2v3w4x5y6
Revises: s0h1i2j3k4l5
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "t1u2v3w4x5y6"
down_revision: Union[str, None] = "s0h1i2j3k4l5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- pricing_recommendations ---
    op.create_table(
        "pricing_recommendations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("offer_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("offers.id"), nullable=False),
        sa.Column("recommendation_type", sa.String(80), nullable=False),
        sa.Column("current_price", sa.Float, server_default="0"),
        sa.Column("recommended_price", sa.Float, server_default="0"),
        sa.Column("price_elasticity", sa.Float, server_default="0"),
        sa.Column("estimated_revenue_impact", sa.Float, server_default="0"),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("brand_id", "offer_id", name="uq_pricing_brand_offer"),
    )
    op.create_index("ix_pricing_recommendations_brand_id", "pricing_recommendations", ["brand_id"])
    op.create_index("ix_pricing_recommendations_offer_id", "pricing_recommendations", ["offer_id"])

    # --- bundle_recommendations ---
    op.create_table(
        "bundle_recommendations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("bundle_name", sa.String(255), nullable=False),
        sa.Column("offer_ids", JSONB, server_default="[]"),
        sa.Column("recommended_bundle_price", sa.Float, server_default="0"),
        sa.Column("estimated_upsell_rate", sa.Float, server_default="0"),
        sa.Column("estimated_revenue_impact", sa.Float, server_default="0"),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("brand_id", "bundle_name", name="uq_bundle_brand_name"),
    )
    op.create_index("ix_bundle_recommendations_brand_id", "bundle_recommendations", ["brand_id"])

    # --- retention_recommendations ---
    op.create_table(
        "retention_recommendations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("customer_segment", sa.String(255), nullable=False),
        sa.Column("recommendation_type", sa.String(80), nullable=False),
        sa.Column("action_details", JSONB, nullable=True),
        sa.Column("estimated_retention_lift", sa.Float, server_default="0"),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("brand_id", "customer_segment", name="uq_retention_brand_segment"),
    )
    op.create_index("ix_retention_recommendations_brand_id", "retention_recommendations", ["brand_id"])

    # --- reactivation_campaigns ---
    op.create_table(
        "reactivation_campaigns",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("campaign_name", sa.String(255), nullable=False),
        sa.Column("target_segment", sa.String(255), nullable=False),
        sa.Column("campaign_type", sa.String(80), nullable=False),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated_reactivation_rate", sa.Float, server_default="0"),
        sa.Column("estimated_revenue_impact", sa.Float, server_default="0"),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("brand_id", "campaign_name", name="uq_reactivation_brand_campaign"),
    )
    op.create_index("ix_reactivation_campaigns_brand_id", "reactivation_campaigns", ["brand_id"])


def downgrade() -> None:
    op.drop_table("reactivation_campaigns")
    op.drop_table("retention_recommendations")
    op.drop_table("bundle_recommendations")
    op.drop_table("pricing_recommendations")
