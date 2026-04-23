"""Expansion Pack 2 Phase A: lead qualification, closer actions, owned offer recommendations.

Revision ID: s0h1i2j3k4l5
Revises: r9g1h2i3j4k5
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "s0h1i2j3k4l5"
down_revision: Union[str, None] = "r9g1h2i3j4k5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # lead_opportunities
    # ------------------------------------------------------------------
    op.create_table(
        "lead_opportunities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("lead_source", sa.String(80), server_default="", nullable=False),
        sa.Column("message_text", sa.Text(), nullable=True),
        sa.Column("urgency_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("budget_proxy_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("sophistication_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("offer_fit_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("trust_readiness_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("composite_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("qualification_tier", sa.String(20), server_default="cold", nullable=False),
        sa.Column("recommended_action", sa.String(80), server_default="", nullable=False),
        sa.Column("expected_value", sa.Float(), server_default="0", nullable=False),
        sa.Column("likelihood_to_close", sa.Float(), server_default="0", nullable=False),
        sa.Column("channel_preference", sa.String(50), server_default="", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_opportunities_brand_id", "lead_opportunities", ["brand_id"])

    # ------------------------------------------------------------------
    # closer_actions
    # ------------------------------------------------------------------
    op.create_table(
        "closer_actions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("lead_opportunity_id", sa.UUID(), nullable=True),
        sa.Column("action_type", sa.String(80), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="1", nullable=False),
        sa.Column("channel", sa.String(30), server_default="", nullable=False),
        sa.Column("subject_or_opener", sa.String(500), server_default="", nullable=False),
        sa.Column("timing", sa.String(30), server_default="24h", nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("expected_outcome", sa.Text(), nullable=True),
        sa.Column("is_completed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["lead_opportunity_id"], ["lead_opportunities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_closer_actions_brand_id", "closer_actions", ["brand_id"])
    op.create_index("ix_closer_actions_lead_opportunity_id", "closer_actions", ["lead_opportunity_id"])

    # ------------------------------------------------------------------
    # lead_qualification_reports
    # ------------------------------------------------------------------
    op.create_table(
        "lead_qualification_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("total_leads_scored", sa.Integer(), server_default="0", nullable=False),
        sa.Column("hot_leads", sa.Integer(), server_default="0", nullable=False),
        sa.Column("warm_leads", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cold_leads", sa.Integer(), server_default="0", nullable=False),
        sa.Column("avg_composite_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("avg_expected_value", sa.Float(), server_default="0", nullable=False),
        sa.Column("top_channel", sa.String(50), server_default="", nullable=False),
        sa.Column("top_recommended_action", sa.String(80), server_default="", nullable=False),
        sa.Column("signal_summary", JSONB(), nullable=True),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id", name="uq_lead_qual_brand"),
    )
    op.create_index("ix_lead_qualification_reports_brand_id", "lead_qualification_reports", ["brand_id"])

    # ------------------------------------------------------------------
    # owned_offer_recommendations
    # ------------------------------------------------------------------
    op.create_table(
        "owned_offer_recommendations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("opportunity_key", sa.String(255), nullable=False),
        sa.Column("signal_type", sa.String(80), nullable=False),
        sa.Column("detected_signal", sa.Text(), nullable=True),
        sa.Column("recommended_offer_type", sa.String(80), server_default="", nullable=False),
        sa.Column("offer_name_suggestion", sa.String(500), server_default="", nullable=False),
        sa.Column("price_point_min", sa.Float(), server_default="0", nullable=False),
        sa.Column("price_point_max", sa.Float(), server_default="0", nullable=False),
        sa.Column("estimated_demand_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("estimated_first_month_revenue", sa.Float(), server_default="0", nullable=False),
        sa.Column("audience_fit", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("build_priority", sa.String(20), server_default="medium", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id", "opportunity_key", name="uq_owned_offer_brand_key"),
    )
    op.create_index("ix_owned_offer_recommendations_brand_id", "owned_offer_recommendations", ["brand_id"])
    op.create_index("ix_owned_offer_recommendations_opportunity_key", "owned_offer_recommendations", ["opportunity_key"])


def downgrade() -> None:
    op.drop_index("ix_owned_offer_recommendations_opportunity_key", table_name="owned_offer_recommendations")
    op.drop_index("ix_owned_offer_recommendations_brand_id", table_name="owned_offer_recommendations")
    op.drop_table("owned_offer_recommendations")
    op.drop_index("ix_lead_qualification_reports_brand_id", table_name="lead_qualification_reports")
    op.drop_table("lead_qualification_reports")
    op.drop_index("ix_closer_actions_lead_opportunity_id", table_name="closer_actions")
    op.drop_index("ix_closer_actions_brand_id", table_name="closer_actions")
    op.drop_table("closer_actions")
    op.drop_index("ix_lead_opportunities_brand_id", table_name="lead_opportunities")
    op.drop_table("lead_opportunities")
