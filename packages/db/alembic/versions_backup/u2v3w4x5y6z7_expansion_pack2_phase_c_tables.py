"""Expansion Pack 2 Phase C: referral, competitive gap, sponsor sales, profit guardrail.

Revision ID: u2v3w4x5y6z7
Revises: t1u2v3w4x5y6
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "u2v3w4x5y6z7"
down_revision: Union[str, None] = "t1u2v3w4x5y6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # referral_program_recommendations
    # ------------------------------------------------------------------
    op.create_table(
        "referral_program_recommendations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("customer_segment", sa.String(255), nullable=False),
        sa.Column("recommendation_type", sa.String(80), nullable=False),
        sa.Column("referral_bonus", sa.Float(), server_default="0", nullable=False),
        sa.Column("referred_bonus", sa.Float(), server_default="0", nullable=False),
        sa.Column("estimated_conversion_rate", sa.Float(), server_default="0", nullable=False),
        sa.Column("estimated_revenue_impact", sa.Float(), server_default="0", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id", "customer_segment", name="uq_referral_brand_segment"),
    )
    op.create_index("ix_referral_program_recommendations_brand_id", "referral_program_recommendations", ["brand_id"])

    # ------------------------------------------------------------------
    # competitive_gap_reports
    # ------------------------------------------------------------------
    op.create_table(
        "competitive_gap_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("offer_id", sa.UUID(), nullable=True),
        sa.Column("competitor_name", sa.String(255), nullable=False),
        sa.Column("gap_type", sa.String(80), nullable=False),
        sa.Column("gap_description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(80), nullable=False),
        sa.Column("estimated_impact", sa.Float(), server_default="0", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["offer_id"], ["offers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id", "competitor_name", "offer_id", name="uq_gap_brand_competitor_offer"),
    )
    op.create_index("ix_competitive_gap_reports_brand_id", "competitive_gap_reports", ["brand_id"])
    op.create_index("ix_competitive_gap_reports_offer_id", "competitive_gap_reports", ["offer_id"])

    # ------------------------------------------------------------------
    # sponsor_targets
    # ------------------------------------------------------------------
    op.create_table(
        "sponsor_targets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("target_company_name", sa.String(255), nullable=False),
        sa.Column("industry", sa.String(255), nullable=True),
        sa.Column("contact_info", JSONB(), nullable=True),
        sa.Column("estimated_deal_value", sa.Float(), server_default="0", nullable=False),
        sa.Column("fit_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id", "target_company_name", name="uq_sponsor_brand_company"),
    )
    op.create_index("ix_sponsor_targets_brand_id", "sponsor_targets", ["brand_id"])

    # ------------------------------------------------------------------
    # sponsor_outreach_sequences
    # ------------------------------------------------------------------
    op.create_table(
        "sponsor_outreach_sequences",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sponsor_target_id", sa.UUID(), nullable=False),
        sa.Column("sequence_name", sa.String(255), nullable=False),
        sa.Column("steps", JSONB(), server_default="[]", nullable=False),
        sa.Column("estimated_response_rate", sa.Float(), server_default="0", nullable=False),
        sa.Column("expected_value", sa.Float(), server_default="0", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["sponsor_target_id"], ["sponsor_targets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sponsor_target_id", "sequence_name", name="uq_outreach_target_sequence"),
    )
    op.create_index("ix_sponsor_outreach_sequences_sponsor_target_id", "sponsor_outreach_sequences", ["sponsor_target_id"])

    # ------------------------------------------------------------------
    # profit_guardrail_reports
    # ------------------------------------------------------------------
    op.create_table(
        "profit_guardrail_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("metric_name", sa.String(255), nullable=False),
        sa.Column("current_value", sa.Float(), server_default="0", nullable=False),
        sa.Column("threshold_value", sa.Float(), server_default="0", nullable=False),
        sa.Column("status", sa.String(80), nullable=False),
        sa.Column("action_recommended", sa.Text(), nullable=True),
        sa.Column("estimated_impact", sa.Float(), server_default="0", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id", "metric_name", name="uq_guardrail_brand_metric"),
    )
    op.create_index("ix_profit_guardrail_reports_brand_id", "profit_guardrail_reports", ["brand_id"])


def downgrade() -> None:
    op.drop_index("ix_profit_guardrail_reports_brand_id", table_name="profit_guardrail_reports")
    op.drop_table("profit_guardrail_reports")
    op.drop_index("ix_sponsor_outreach_sequences_sponsor_target_id", table_name="sponsor_outreach_sequences")
    op.drop_table("sponsor_outreach_sequences")
    op.drop_index("ix_sponsor_targets_brand_id", table_name="sponsor_targets")
    op.drop_table("sponsor_targets")
    op.drop_index("ix_competitive_gap_reports_offer_id", table_name="competitive_gap_reports")
    op.drop_index("ix_competitive_gap_reports_brand_id", table_name="competitive_gap_reports")
    op.drop_table("competitive_gap_reports")
    op.drop_index("ix_referral_program_recommendations_brand_id", table_name="referral_program_recommendations")
    op.drop_table("referral_program_recommendations")
