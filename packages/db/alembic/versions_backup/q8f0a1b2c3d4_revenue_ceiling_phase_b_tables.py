"""Revenue Ceiling Phase B: high-ticket, productization, revenue density, upsell

Revision ID: q8f0a1b2c3d4
Revises: p7d8e9f0a1b2
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "q8f0a1b2c3d4"
down_revision: Union[str, None] = "p7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "high_ticket_opportunities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("opportunity_key", sa.String(255), nullable=False),
        sa.Column("source_offer_id", sa.UUID(), nullable=True),
        sa.Column("source_content_item_id", sa.UUID(), nullable=True),
        sa.Column("eligibility_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("recommended_offer_path", JSONB(), nullable=True),
        sa.Column("recommended_cta", sa.Text(), nullable=True),
        sa.Column("expected_close_rate_proxy", sa.Float(), server_default="0", nullable=False),
        sa.Column("expected_deal_value", sa.Float(), server_default="0", nullable=False),
        sa.Column("expected_profit", sa.Float(), server_default="0", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["source_offer_id"], ["offers.id"]),
        sa.ForeignKeyConstraint(["source_content_item_id"], ["content_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id", "opportunity_key", name="uq_high_ticket_brand_key"),
    )
    op.create_index("ix_high_ticket_opportunities_brand_id", "high_ticket_opportunities", ["brand_id"])

    op.create_table(
        "product_opportunities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("opportunity_key", sa.String(255), nullable=False),
        sa.Column("product_recommendation", sa.String(500), server_default="", nullable=False),
        sa.Column("product_type", sa.String(120), server_default="", nullable=False),
        sa.Column("target_audience", sa.Text(), nullable=True),
        sa.Column("price_range_min", sa.Float(), server_default="0", nullable=False),
        sa.Column("price_range_max", sa.Float(), server_default="0", nullable=False),
        sa.Column("expected_launch_value", sa.Float(), server_default="0", nullable=False),
        sa.Column("expected_recurring_value", sa.Float(), nullable=True),
        sa.Column("build_complexity", sa.String(40), server_default="medium", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id", "opportunity_key", name="uq_product_opp_brand_key"),
    )
    op.create_index("ix_product_opportunities_brand_id", "product_opportunities", ["brand_id"])

    op.create_table(
        "revenue_density_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("content_item_id", sa.UUID(), nullable=False),
        sa.Column("revenue_per_content_item", sa.Float(), server_default="0", nullable=False),
        sa.Column("revenue_per_1k_impressions", sa.Float(), server_default="0", nullable=False),
        sa.Column("profit_per_1k_impressions", sa.Float(), server_default="0", nullable=False),
        sa.Column("profit_per_audience_member", sa.Float(), server_default="0", nullable=False),
        sa.Column("monetization_depth_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("repeat_monetization_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("ceiling_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id", "content_item_id", name="uq_revenue_density_brand_content"),
    )
    op.create_index("ix_revenue_density_reports_brand_id", "revenue_density_reports", ["brand_id"])
    op.create_index("ix_revenue_density_reports_content_item_id", "revenue_density_reports", ["content_item_id"])

    op.create_table(
        "upsell_recommendations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("opportunity_key", sa.String(255), nullable=False),
        sa.Column("anchor_offer_id", sa.UUID(), nullable=True),
        sa.Column("anchor_content_item_id", sa.UUID(), nullable=True),
        sa.Column("best_next_offer", JSONB(), nullable=True),
        sa.Column("best_timing", sa.String(120), server_default="", nullable=False),
        sa.Column("best_channel", sa.String(80), server_default="", nullable=False),
        sa.Column("expected_take_rate", sa.Float(), server_default="0", nullable=False),
        sa.Column("expected_incremental_value", sa.Float(), server_default="0", nullable=False),
        sa.Column("best_upsell_sequencing", JSONB(), nullable=True),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["anchor_offer_id"], ["offers.id"]),
        sa.ForeignKeyConstraint(["anchor_content_item_id"], ["content_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id", "opportunity_key", name="uq_upsell_brand_key"),
    )
    op.create_index("ix_upsell_recommendations_brand_id", "upsell_recommendations", ["brand_id"])


def downgrade() -> None:
    op.drop_index("ix_upsell_recommendations_brand_id", table_name="upsell_recommendations")
    op.drop_table("upsell_recommendations")
    op.drop_index("ix_revenue_density_reports_content_item_id", table_name="revenue_density_reports")
    op.drop_index("ix_revenue_density_reports_brand_id", table_name="revenue_density_reports")
    op.drop_table("revenue_density_reports")
    op.drop_index("ix_product_opportunities_brand_id", table_name="product_opportunities")
    op.drop_table("product_opportunities")
    op.drop_index("ix_high_ticket_opportunities_brand_id", table_name="high_ticket_opportunities")
    op.drop_table("high_ticket_opportunities")
