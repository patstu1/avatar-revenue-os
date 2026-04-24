"""Brain Architecture Phase D — meta-monitoring, self-correction, readiness, escalation.

Revision ID: brain_phase_d_001
Revises: brain_phase_c_001
Create Date: 2026-03-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "brain_phase_d_001"
down_revision = "brain_phase_c_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meta_monitoring_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("health_score", sa.Float, server_default="0"),
        sa.Column("health_band", sa.String(30), server_default="medium", index=True),
        sa.Column("decision_quality_score", sa.Float, server_default="0"),
        sa.Column("confidence_drift_score", sa.Float, server_default="0"),
        sa.Column("policy_drift_score", sa.Float, server_default="0"),
        sa.Column("execution_failure_rate", sa.Float, server_default="0"),
        sa.Column("memory_quality_score", sa.Float, server_default="0"),
        sa.Column("escalation_rate", sa.Float, server_default="0"),
        sa.Column("queue_congestion", sa.Float, server_default="0"),
        sa.Column("dead_agent_count", sa.Integer, server_default="0"),
        sa.Column("low_signal_count", sa.Integer, server_default="0"),
        sa.Column("wasted_action_count", sa.Integer, server_default="0"),
        sa.Column("weak_areas_json", postgresql.JSONB, nullable=True),
        sa.Column("recommended_corrections_json", postgresql.JSONB, nullable=True),
        sa.Column("inputs_json", postgresql.JSONB, nullable=True),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "self_correction_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("correction_type", sa.String(80), nullable=False, index=True),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("effect_target", sa.String(200), nullable=False, index=True),
        sa.Column("severity", sa.String(30), server_default="medium", index=True),
        sa.Column("applied", sa.Boolean, server_default=sa.text("false")),
        sa.Column("payload_json", postgresql.JSONB, nullable=True),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "readiness_brain_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("readiness_score", sa.Float, server_default="0"),
        sa.Column("readiness_band", sa.String(30), server_default="not_ready", index=True),
        sa.Column("blockers_json", postgresql.JSONB, nullable=True),
        sa.Column("allowed_actions_json", postgresql.JSONB, nullable=True),
        sa.Column("forbidden_actions_json", postgresql.JSONB, nullable=True),
        sa.Column("inputs_json", postgresql.JSONB, nullable=True),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "brain_escalations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("escalation_type", sa.String(100), nullable=False, index=True),
        sa.Column("command", sa.Text, nullable=False),
        sa.Column("urgency", sa.String(30), server_default="medium", index=True),
        sa.Column("expected_upside_unlocked", sa.Float, server_default="0"),
        sa.Column("expected_cost_of_delay", sa.Float, server_default="0"),
        sa.Column("affected_scope", sa.String(200), nullable=False),
        sa.Column("supporting_data_json", postgresql.JSONB, nullable=True),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("resolved", sa.Boolean, server_default=sa.text("false")),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("brain_escalations")
    op.drop_table("readiness_brain_reports")
    op.drop_table("self_correction_actions")
    op.drop_table("meta_monitoring_reports")
