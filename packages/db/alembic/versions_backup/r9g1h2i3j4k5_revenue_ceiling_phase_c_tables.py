"""Revenue Ceiling Phase C: recurring revenue, sponsor inventory, trust conversion,
monetization mix, paid promotion gate.

Revision ID: r9g1h2i3j4k5
Revises: q8f0a1b2c3d4
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "r9g1h2i3j4k5"
down_revision: Union[str, None] = "q8f0a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # recurring_revenue_models
    # ------------------------------------------------------------------
    op.create_table(
        "recurring_revenue_models",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("recurring_potential_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("best_recurring_offer_type", sa.String(120), server_default="", nullable=False),
        sa.Column("audience_fit", sa.Float(), server_default="0", nullable=False),
        sa.Column("churn_risk_proxy", sa.Float(), server_default="0", nullable=False),
        sa.Column("expected_monthly_value", sa.Float(), server_default="0", nullable=False),
        sa.Column("expected_annual_value", sa.Float(), server_default="0", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id", name="uq_recurring_revenue_brand"),
    )
    op.create_index("ix_recurring_revenue_models_brand_id", "recurring_revenue_models", ["brand_id"])

    # ------------------------------------------------------------------
    # sponsor_inventory
    # ------------------------------------------------------------------
    op.create_table(
        "sponsor_inventory",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("content_item_id", sa.UUID(), nullable=True),
        sa.Column("sponsor_fit_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("recommended_package_name", sa.String(200), nullable=True),
        sa.Column("estimated_package_price", sa.Float(), server_default="0", nullable=False),
        sa.Column("sponsor_category", sa.String(120), server_default="general", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sponsor_inventory_brand_id", "sponsor_inventory", ["brand_id"])

    # ------------------------------------------------------------------
    # sponsor_package_recommendations
    # ------------------------------------------------------------------
    op.create_table(
        "sponsor_package_recommendations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("recommended_package", JSONB(), nullable=True),
        sa.Column("sponsor_fit_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("estimated_package_price", sa.Float(), server_default="0", nullable=False),
        sa.Column("sponsor_category", sa.String(120), server_default="general", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id", name="uq_sponsor_pkg_brand"),
    )
    op.create_index("ix_sponsor_package_recommendations_brand_id", "sponsor_package_recommendations", ["brand_id"])

    # ------------------------------------------------------------------
    # trust_conversion_reports
    # ------------------------------------------------------------------
    op.create_table(
        "trust_conversion_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("trust_deficit_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("recommended_proof_blocks", JSONB(), nullable=True),
        sa.Column("missing_trust_elements", JSONB(), nullable=True),
        sa.Column("expected_uplift", sa.Float(), server_default="0", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id", name="uq_trust_conversion_brand"),
    )
    op.create_index("ix_trust_conversion_reports_brand_id", "trust_conversion_reports", ["brand_id"])

    # ------------------------------------------------------------------
    # monetization_mix_reports
    # ------------------------------------------------------------------
    op.create_table(
        "monetization_mix_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("current_revenue_mix", JSONB(), nullable=True),
        sa.Column("dependency_risk", sa.Float(), server_default="0", nullable=False),
        sa.Column("underused_monetization_paths", JSONB(), nullable=True),
        sa.Column("next_best_mix", JSONB(), nullable=True),
        sa.Column("expected_margin_uplift", sa.Float(), server_default="0", nullable=False),
        sa.Column("expected_ltv_uplift", sa.Float(), server_default="0", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id", name="uq_monetization_mix_brand"),
    )
    op.create_index("ix_monetization_mix_reports_brand_id", "monetization_mix_reports", ["brand_id"])

    # ------------------------------------------------------------------
    # paid_promotion_candidates
    # ------------------------------------------------------------------
    op.create_table(
        "paid_promotion_candidates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("content_item_id", sa.UUID(), nullable=False),
        sa.Column("organic_winner_evidence", JSONB(), nullable=True),
        sa.Column("is_eligible", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("gate_reason", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id", "content_item_id", name="uq_paid_promo_brand_content"),
    )
    op.create_index("ix_paid_promotion_candidates_brand_id", "paid_promotion_candidates", ["brand_id"])


def downgrade() -> None:
    op.drop_index("ix_paid_promotion_candidates_brand_id", table_name="paid_promotion_candidates")
    op.drop_table("paid_promotion_candidates")
    op.drop_index("ix_monetization_mix_reports_brand_id", table_name="monetization_mix_reports")
    op.drop_table("monetization_mix_reports")
    op.drop_index("ix_trust_conversion_reports_brand_id", table_name="trust_conversion_reports")
    op.drop_table("trust_conversion_reports")
    op.drop_index("ix_sponsor_package_recommendations_brand_id", table_name="sponsor_package_recommendations")
    op.drop_table("sponsor_package_recommendations")
    op.drop_index("ix_sponsor_inventory_brand_id", table_name="sponsor_inventory")
    op.drop_table("sponsor_inventory")
    op.drop_index("ix_recurring_revenue_models_brand_id", table_name="recurring_revenue_models")
    op.drop_table("recurring_revenue_models")
