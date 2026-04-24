"""Creator Revenue Avenues Pack — Phase A tables

Revision ID: cra_phase_a_001
Revises: lec_phase1_001
Create Date: 2025-01-01 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "cra_phase_a_001"
down_revision = "lec_phase1_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "creator_revenue_opportunities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("avenue_type", sa.String(60), nullable=False, index=True),
        sa.Column("subtype", sa.String(80), nullable=False, index=True),
        sa.Column("target_segment", sa.String(120), nullable=False),
        sa.Column("recommended_package", sa.String(200), nullable=True),
        sa.Column("expected_value", sa.Float, server_default="0"),
        sa.Column("expected_margin", sa.Float, server_default="0"),
        sa.Column("priority_score", sa.Float, server_default="0"),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("status", sa.String(30), server_default="active", index=True),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("details_json", JSONB, server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "ugc_service_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("opportunity_id", UUID(as_uuid=True), sa.ForeignKey("creator_revenue_opportunities.id"), nullable=True, index=True),
        sa.Column("service_type", sa.String(80), nullable=False, index=True),
        sa.Column("target_segment", sa.String(120), nullable=False),
        sa.Column("recommended_package", sa.String(200), nullable=False),
        sa.Column("price_band", sa.String(60), server_default="mid"),
        sa.Column("expected_value", sa.Float, server_default="0"),
        sa.Column("expected_margin", sa.Float, server_default="0"),
        sa.Column("execution_steps_json", JSONB, server_default="[]"),
        sa.Column("status", sa.String(30), server_default="planned", index=True),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("blockers_json", JSONB, server_default="[]"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "service_consulting_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("opportunity_id", UUID(as_uuid=True), sa.ForeignKey("creator_revenue_opportunities.id"), nullable=True, index=True),
        sa.Column("service_type", sa.String(80), nullable=False, index=True),
        sa.Column("service_tier", sa.String(40), server_default="standard", index=True),
        sa.Column("target_buyer", sa.String(120), nullable=False),
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
        "premium_access_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("opportunity_id", UUID(as_uuid=True), sa.ForeignKey("creator_revenue_opportunities.id"), nullable=True, index=True),
        sa.Column("offer_type", sa.String(80), nullable=False, index=True),
        sa.Column("target_segment", sa.String(120), nullable=False),
        sa.Column("entry_criteria", sa.Text, nullable=True),
        sa.Column("revenue_model", sa.String(30), server_default="recurring", index=True),
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
        "creator_revenue_blockers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("avenue_type", sa.String(60), nullable=False, index=True),
        sa.Column("blocker_type", sa.String(80), nullable=False, index=True),
        sa.Column("severity", sa.String(30), server_default="high", index=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("operator_action_needed", sa.Text, nullable=False),
        sa.Column("resolved", sa.Boolean, server_default="false"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "creator_revenue_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("opportunity_id", UUID(as_uuid=True), sa.ForeignKey("creator_revenue_opportunities.id"), nullable=True, index=True),
        sa.Column("avenue_type", sa.String(60), nullable=False, index=True),
        sa.Column("event_type", sa.String(60), nullable=False, index=True),
        sa.Column("revenue", sa.Float, server_default="0"),
        sa.Column("cost", sa.Float, server_default="0"),
        sa.Column("profit", sa.Float, server_default="0"),
        sa.Column("client_name", sa.String(200), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("metadata_json", JSONB, server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("creator_revenue_events")
    op.drop_table("creator_revenue_blockers")
    op.drop_table("premium_access_actions")
    op.drop_table("service_consulting_actions")
    op.drop_table("ugc_service_actions")
    op.drop_table("creator_revenue_opportunities")
