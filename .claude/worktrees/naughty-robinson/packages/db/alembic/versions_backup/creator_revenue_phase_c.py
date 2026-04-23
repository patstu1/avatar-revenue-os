"""Creator Revenue Avenues Pack — Phase C tables

Revision ID: cra_phase_c_001
Revises: cra_phase_b_001
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "cra_phase_c_001"
down_revision = "cra_phase_b_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "merch_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("opportunity_id", UUID(as_uuid=True), sa.ForeignKey("creator_revenue_opportunities.id"), nullable=True, index=True),
        sa.Column("product_class", sa.String(80), nullable=False, index=True),
        sa.Column("target_segment", sa.String(120), nullable=False),
        sa.Column("price_band", sa.String(60), server_default="mid"),
        sa.Column("expected_value", sa.Float, server_default="0"),
        sa.Column("execution_plan_json", JSONB, server_default="[]"),
        sa.Column("truth_label", sa.String(30), server_default="recommended", index=True),
        sa.Column("status", sa.String(30), server_default="planned", index=True),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("blockers_json", JSONB, server_default="[]"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "live_event_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("opportunity_id", UUID(as_uuid=True), sa.ForeignKey("creator_revenue_opportunities.id"), nullable=True, index=True),
        sa.Column("event_type", sa.String(80), nullable=False, index=True),
        sa.Column("audience_segment", sa.String(120), nullable=False),
        sa.Column("ticket_model", sa.String(40), server_default="paid", index=True),
        sa.Column("price_band", sa.String(60), server_default="mid"),
        sa.Column("expected_value", sa.Float, server_default="0"),
        sa.Column("execution_plan_json", JSONB, server_default="[]"),
        sa.Column("truth_label", sa.String(30), server_default="recommended", index=True),
        sa.Column("status", sa.String(30), server_default="planned", index=True),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("blockers_json", JSONB, server_default="[]"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "owned_affiliate_program_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("opportunity_id", UUID(as_uuid=True), sa.ForeignKey("creator_revenue_opportunities.id"), nullable=True, index=True),
        sa.Column("program_type", sa.String(80), nullable=False, index=True),
        sa.Column("target_partner_type", sa.String(120), nullable=False),
        sa.Column("incentive_model", sa.String(60), server_default="percentage", index=True),
        sa.Column("partner_tier", sa.String(40), server_default="standard", index=True),
        sa.Column("expected_value", sa.Float, server_default="0"),
        sa.Column("execution_plan_json", JSONB, server_default="[]"),
        sa.Column("truth_label", sa.String(30), server_default="recommended", index=True),
        sa.Column("status", sa.String(30), server_default="planned", index=True),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("blockers_json", JSONB, server_default="[]"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("owned_affiliate_program_actions")
    op.drop_table("live_event_actions")
    op.drop_table("merch_actions")
