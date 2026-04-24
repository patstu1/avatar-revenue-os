"""Hyper-Scale Execution OS tables.

Revision ID: hs_001
Revises: wf_001
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "hs_001"
down_revision: Union[str, None] = "wf_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _b():
    return [sa.Column("id", sa.UUID(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)]

def upgrade() -> None:
    op.create_table("hs_capacity_reports", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("total_queued", sa.Integer(), server_default="0"), sa.Column("total_running", sa.Integer(), server_default="0"), sa.Column("total_completed_24h", sa.Integer(), server_default="0"), sa.Column("throughput_per_hour", sa.Float(), server_default="0"), sa.Column("avg_latency_seconds", sa.Float(), server_default="0"), sa.Column("burst_active", sa.Boolean(), server_default=sa.text("false")), sa.Column("degraded", sa.Boolean(), server_default=sa.text("false")), sa.Column("health_status", sa.String(20), server_default="healthy"), sa.Column("summary_json", JSONB(), server_default="{}"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("hs_queue_segments", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("segment_key", sa.String(120), nullable=False), sa.Column("segment_type", sa.String(40), nullable=False), sa.Column("brand_id", sa.UUID()), sa.Column("queue_depth", sa.Integer(), server_default="0"), sa.Column("running_count", sa.Integer(), server_default="0"), sa.Column("max_concurrency", sa.Integer(), server_default="10"), sa.Column("priority", sa.Integer(), server_default="50"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("hs_workload_allocations", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("brand_id", sa.UUID()), sa.Column("allocation_type", sa.String(40), nullable=False), sa.Column("allocated_capacity", sa.Integer(), server_default="0"), sa.Column("used_capacity", sa.Integer(), server_default="0"), sa.Column("market", sa.String(40)), sa.Column("language", sa.String(10)), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("hs_throughput_events", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("period", sa.String(30), nullable=False), sa.Column("tasks_completed", sa.Integer(), server_default="0"), sa.Column("tasks_failed", sa.Integer(), server_default="0"), sa.Column("avg_latency_ms", sa.Float(), server_default="0"), sa.Column("cost_incurred", sa.Float(), server_default="0"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("hs_burst_events", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("burst_type", sa.String(40), nullable=False), sa.Column("peak_qps", sa.Float(), server_default="0"), sa.Column("duration_seconds", sa.Integer(), server_default="0"), sa.Column("tasks_queued", sa.Integer(), server_default="0"), sa.Column("degradation_triggered", sa.Boolean(), server_default=sa.text("false")), sa.Column("resolution", sa.Text()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("hs_usage_ceilings", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("brand_id", sa.UUID()), sa.Column("ceiling_type", sa.String(40), nullable=False), sa.Column("max_value", sa.Float(), server_default="0"), sa.Column("current_value", sa.Float(), server_default="0"), sa.Column("period", sa.String(20), server_default="monthly"), sa.Column("enforced", sa.Boolean(), server_default=sa.text("true")), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("hs_degradation_events", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("degradation_type", sa.String(40), nullable=False), sa.Column("trigger_reason", sa.Text(), nullable=False), sa.Column("action_taken", sa.Text(), nullable=False), sa.Column("recovered", sa.Boolean(), server_default=sa.text("false")), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("hs_scale_health", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("health_status", sa.String(20), server_default="healthy"), sa.Column("queue_depth_total", sa.Integer(), server_default="0"), sa.Column("ceiling_utilization_pct", sa.Float(), server_default="0"), sa.Column("burst_count_24h", sa.Integer(), server_default="0"), sa.Column("degradation_count_24h", sa.Integer(), server_default="0"), sa.Column("recommendation", sa.Text()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.PrimaryKeyConstraint("id"))


def downgrade() -> None:
    for t in ("hs_scale_health", "hs_degradation_events", "hs_usage_ceilings", "hs_burst_events", "hs_throughput_events", "hs_workload_allocations", "hs_queue_segments", "hs_capacity_reports"):
        op.drop_table(t)
