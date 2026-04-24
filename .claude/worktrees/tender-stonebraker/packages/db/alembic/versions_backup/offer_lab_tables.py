"""Offer Lab tables.

Revision ID: ol_001
Revises: afe_001
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "ol_001"
down_revision: Union[str, None] = "afe_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _b():
    return [sa.Column("id", sa.UUID(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)]

def upgrade() -> None:
    op.create_table("ol_offers", *_b(), sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("source_offer_id", sa.UUID()), sa.Column("offer_name", sa.String(500), nullable=False), sa.Column("offer_type", sa.String(60), nullable=False), sa.Column("audience_segment", sa.String(120)), sa.Column("problem_solved", sa.Text()), sa.Column("value_promise", sa.Text()), sa.Column("primary_angle", sa.String(60)), sa.Column("secondary_angle", sa.String(60)), sa.Column("trust_requirement", sa.String(20), server_default="medium"), sa.Column("risk_level", sa.String(20), server_default="low"), sa.Column("price_point", sa.Float(), server_default="0"), sa.Column("margin_estimate", sa.Float(), server_default="0"), sa.Column("monetization_method", sa.String(60)), sa.Column("platform_fit", sa.Float(), server_default="0.5"), sa.Column("funnel_stage_fit", sa.String(40)), sa.Column("content_form_fit", sa.String(60)), sa.Column("expected_upside", sa.Float(), server_default="0"), sa.Column("expected_cost", sa.Float(), server_default="0"), sa.Column("confidence", sa.Float(), server_default="0"), sa.Column("rank_score", sa.Float(), server_default="0"), sa.Column("status", sa.String(30), server_default="draft"), sa.Column("truth_label", sa.String(40), server_default="recommendation_only"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.ForeignKeyConstraint(["source_offer_id"], ["offers.id"]), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_olo_brand", "ol_offers", ["brand_id"])

    op.create_table("ol_variants", *_b(), sa.Column("offer_id", sa.UUID(), nullable=False), sa.Column("variant_type", sa.String(40), nullable=False), sa.Column("variant_name", sa.String(255), nullable=False), sa.Column("angle", sa.String(60)), sa.Column("price_point", sa.Float(), server_default="0"), sa.Column("value_promise", sa.Text()), sa.Column("is_control", sa.Boolean(), server_default=sa.text("false")), sa.Column("performance_score", sa.Float(), server_default="0"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["offer_id"], ["ol_offers.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("ol_pricing_tests", *_b(), sa.Column("offer_id", sa.UUID(), nullable=False), sa.Column("test_price", sa.Float(), nullable=False), sa.Column("control_price", sa.Float(), nullable=False), sa.Column("conversion_at_test", sa.Float(), server_default="0"), sa.Column("conversion_at_control", sa.Float(), server_default="0"), sa.Column("revenue_at_test", sa.Float(), server_default="0"), sa.Column("revenue_at_control", sa.Float(), server_default="0"), sa.Column("winner", sa.String(20)), sa.Column("confidence", sa.Float(), server_default="0"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["offer_id"], ["ol_offers.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("ol_positioning_tests", *_b(), sa.Column("offer_id", sa.UUID(), nullable=False), sa.Column("test_angle", sa.String(60), nullable=False), sa.Column("control_angle", sa.String(60), nullable=False), sa.Column("test_conversion", sa.Float(), server_default="0"), sa.Column("control_conversion", sa.Float(), server_default="0"), sa.Column("winner", sa.String(20)), sa.Column("confidence", sa.Float(), server_default="0"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["offer_id"], ["ol_offers.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("ol_bundles", *_b(), sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("bundle_name", sa.String(255), nullable=False), sa.Column("offer_ids", JSONB(), server_default="[]"), sa.Column("combined_price", sa.Float(), server_default="0"), sa.Column("savings_pct", sa.Float(), server_default="0"), sa.Column("expected_uplift", sa.Float(), server_default="0"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("ol_upsells", *_b(), sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("primary_offer_id", sa.UUID(), nullable=False), sa.Column("upsell_offer_id", sa.UUID(), nullable=False), sa.Column("upsell_type", sa.String(20), server_default="upsell"), sa.Column("expected_take_rate", sa.Float(), server_default="0"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.ForeignKeyConstraint(["primary_offer_id"], ["ol_offers.id"]), sa.ForeignKeyConstraint(["upsell_offer_id"], ["ol_offers.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("ol_downsells", *_b(), sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("primary_offer_id", sa.UUID(), nullable=False), sa.Column("downsell_offer_id", sa.UUID(), nullable=False), sa.Column("expected_save_rate", sa.Float(), server_default="0"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.ForeignKeyConstraint(["primary_offer_id"], ["ol_offers.id"]), sa.ForeignKeyConstraint(["downsell_offer_id"], ["ol_offers.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("ol_cross_sells", *_b(), sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("source_offer_id", sa.UUID(), nullable=False), sa.Column("cross_offer_id", sa.UUID(), nullable=False), sa.Column("relevance_score", sa.Float(), server_default="0"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.ForeignKeyConstraint(["source_offer_id"], ["ol_offers.id"]), sa.ForeignKeyConstraint(["cross_offer_id"], ["ol_offers.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("ol_blockers", *_b(), sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("offer_id", sa.UUID()), sa.Column("blocker_type", sa.String(60), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("recommendation", sa.Text()), sa.Column("severity", sa.String(20), server_default="medium"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.ForeignKeyConstraint(["offer_id"], ["ol_offers.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("ol_learning", *_b(), sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("offer_id", sa.UUID(), nullable=False), sa.Column("learning_type", sa.String(40), nullable=False), sa.Column("measured_metric", sa.String(60), nullable=False), sa.Column("measured_value", sa.Float(), server_default="0"), sa.Column("previous_value", sa.Float(), server_default="0"), sa.Column("insight", sa.Text()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.ForeignKeyConstraint(["offer_id"], ["ol_offers.id"]), sa.PrimaryKeyConstraint("id"))


def downgrade() -> None:
    for t in ("ol_learning", "ol_blockers", "ol_cross_sells", "ol_downsells", "ol_upsells", "ol_bundles", "ol_positioning_tests", "ol_pricing_tests", "ol_variants", "ol_offers"):
        op.drop_table(t)
