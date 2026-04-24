"""Creator Revenue Avenues Pack — Phase B tables

Revision ID: cra_phase_b_001
Revises: cra_phase_a_001
Create Date: 2025-01-01 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "cra_phase_b_001"
down_revision = "cra_phase_a_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "licensing_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("opportunity_id", UUID(as_uuid=True), sa.ForeignKey("creator_revenue_opportunities.id"), nullable=True, index=True),
        sa.Column("asset_type", sa.String(80), nullable=False, index=True),
        sa.Column("licensing_tier", sa.String(40), server_default="standard", index=True),
        sa.Column("target_buyer_type", sa.String(120), nullable=False),
        sa.Column("usage_scope", sa.String(40), server_default="limited_use", index=True),
        sa.Column("price_band", sa.String(60), server_default="mid"),
        sa.Column("expected_deal_value", sa.Float, server_default="0"),
        sa.Column("execution_plan_json", JSONB, server_default="[]"),
        sa.Column("status", sa.String(30), server_default="planned", index=True),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("blockers_json", JSONB, server_default="[]"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "syndication_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("opportunity_id", UUID(as_uuid=True), sa.ForeignKey("creator_revenue_opportunities.id"), nullable=True, index=True),
        sa.Column("syndication_format", sa.String(80), nullable=False, index=True),
        sa.Column("target_partner", sa.String(120), nullable=False),
        sa.Column("revenue_model", sa.String(30), server_default="recurring", index=True),
        sa.Column("price_band", sa.String(60), server_default="mid"),
        sa.Column("expected_value", sa.Float, server_default="0"),
        sa.Column("execution_plan_json", JSONB, server_default="[]"),
        sa.Column("status", sa.String(30), server_default="planned", index=True),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("blockers_json", JSONB, server_default="[]"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "data_product_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("opportunity_id", UUID(as_uuid=True), sa.ForeignKey("creator_revenue_opportunities.id"), nullable=True, index=True),
        sa.Column("product_type", sa.String(80), nullable=False, index=True),
        sa.Column("target_segment", sa.String(120), nullable=False),
        sa.Column("revenue_model", sa.String(30), server_default="recurring", index=True),
        sa.Column("price_band", sa.String(60), server_default="mid"),
        sa.Column("expected_value", sa.Float, server_default="0"),
        sa.Column("execution_plan_json", JSONB, server_default="[]"),
        sa.Column("status", sa.String(30), server_default="planned", index=True),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("blockers_json", JSONB, server_default="[]"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("data_product_actions")
    op.drop_table("syndication_actions")
    op.drop_table("licensing_actions")
