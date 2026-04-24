"""Executive Intelligence tables.

Revision ID: ei_001
Revises: il_001
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "ei_001"
down_revision: Union[str, None] = "il_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _b():
    return [sa.Column("id", sa.UUID(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)]

def upgrade() -> None:
    op.create_table("ei_kpi_reports", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("brand_id", sa.UUID()), sa.Column("period", sa.String(30), nullable=False), sa.Column("total_revenue", sa.Float(), server_default="0"), sa.Column("total_profit", sa.Float(), server_default="0"), sa.Column("total_spend", sa.Float(), server_default="0"), sa.Column("content_produced", sa.Integer(), server_default="0"), sa.Column("content_published", sa.Integer(), server_default="0"), sa.Column("total_impressions", sa.Float(), server_default="0"), sa.Column("avg_engagement_rate", sa.Float(), server_default="0"), sa.Column("avg_conversion_rate", sa.Float(), server_default="0"), sa.Column("active_accounts", sa.Integer(), server_default="0"), sa.Column("active_campaigns", sa.Integer(), server_default="0"), sa.Column("kpi_json", JSONB(), server_default="{}"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("ei_forecasts", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("brand_id", sa.UUID()), sa.Column("forecast_type", sa.String(40), nullable=False), sa.Column("forecast_period", sa.String(30), nullable=False), sa.Column("predicted_value", sa.Float(), server_default="0"), sa.Column("confidence", sa.Float(), server_default="0"), sa.Column("risk_factors", JSONB(), server_default="[]"), sa.Column("opportunity_factors", JSONB(), server_default="[]"), sa.Column("explanation", sa.Text()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("ei_usage_cost", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("brand_id", sa.UUID()), sa.Column("period", sa.String(30), nullable=False), sa.Column("provider_key", sa.String(80)), sa.Column("tasks_executed", sa.Integer(), server_default="0"), sa.Column("cost_incurred", sa.Float(), server_default="0"), sa.Column("cost_by_tier", JSONB(), server_default="{}"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("ei_provider_uptime", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("provider_key", sa.String(80), nullable=False), sa.Column("period", sa.String(30), nullable=False), sa.Column("uptime_pct", sa.Float(), server_default="100"), sa.Column("total_requests", sa.Integer(), server_default="0"), sa.Column("failed_requests", sa.Integer(), server_default="0"), sa.Column("avg_latency_ms", sa.Float(), server_default="0"), sa.Column("reliability_grade", sa.String(5), server_default="A"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("ei_oversight_mode", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("mode", sa.String(30), server_default="hybrid"), sa.Column("auto_approved_count", sa.Integer(), server_default="0"), sa.Column("human_reviewed_count", sa.Integer(), server_default="0"), sa.Column("override_count", sa.Integer(), server_default="0"), sa.Column("ai_accuracy_estimate", sa.Float(), server_default="0"), sa.Column("recommendation", sa.Text()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("ei_service_health", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("service_name", sa.String(80), nullable=False), sa.Column("health_status", sa.String(20), server_default="healthy"), sa.Column("active_issues", sa.Integer(), server_default="0"), sa.Column("last_incident", sa.Text()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("ei_alerts", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("alert_type", sa.String(60), nullable=False), sa.Column("severity", sa.String(20), server_default="medium"), sa.Column("title", sa.String(500), nullable=False), sa.Column("detail", sa.Text(), nullable=False), sa.Column("recommended_action", sa.Text()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.PrimaryKeyConstraint("id"))


def downgrade() -> None:
    for t in ("ei_alerts", "ei_service_health", "ei_oversight_mode", "ei_provider_uptime", "ei_usage_cost", "ei_forecasts", "ei_kpi_reports"):
        op.drop_table(t)
