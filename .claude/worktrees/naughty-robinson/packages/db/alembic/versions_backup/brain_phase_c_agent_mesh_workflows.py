"""Brain Architecture Phase C — agent mesh, workflows, context bus, memory binding.

Revision ID: brain_phase_c_001
Revises: brain_phase_b_001
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "brain_phase_c_001"
down_revision = "brain_phase_b_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("agent_slug", sa.String(80), nullable=False, index=True),
        sa.Column("agent_label", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("input_schema_json", postgresql.JSONB, nullable=True),
        sa.Column("output_schema_json", postgresql.JSONB, nullable=True),
        sa.Column("memory_scopes_json", postgresql.JSONB, nullable=True),
        sa.Column("upstream_agents_json", postgresql.JSONB, nullable=True),
        sa.Column("downstream_agents_json", postgresql.JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "agent_runs_v2",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("agent_slug", sa.String(80), nullable=False, index=True),
        sa.Column("run_status", sa.String(40), server_default="running", index=True),
        sa.Column("trigger", sa.String(120), nullable=False),
        sa.Column("inputs_json", postgresql.JSONB, nullable=True),
        sa.Column("outputs_json", postgresql.JSONB, nullable=True),
        sa.Column("memory_refs_json", postgresql.JSONB, nullable=True),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("duration_ms", sa.Integer, server_default="0"),
        sa.Column("error_detail", sa.Text, nullable=True),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "agent_messages_v2",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs_v2.id"), nullable=False, index=True),
        sa.Column("agent_slug", sa.String(80), nullable=False, index=True),
        sa.Column("direction", sa.String(20), nullable=False, index=True),
        sa.Column("message_type", sa.String(60), nullable=False, index=True),
        sa.Column("payload_json", postgresql.JSONB, nullable=True),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "workflow_coordination_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("workflow_type", sa.String(100), nullable=False, index=True),
        sa.Column("sequence_json", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.String(40), server_default="running", index=True),
        sa.Column("handoff_events_json", postgresql.JSONB, nullable=True),
        sa.Column("failure_points_json", postgresql.JSONB, nullable=True),
        sa.Column("inputs_json", postgresql.JSONB, nullable=True),
        sa.Column("outputs_json", postgresql.JSONB, nullable=True),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "coordination_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_coordination_runs.id"), nullable=False, index=True),
        sa.Column("step_index", sa.Integer, nullable=False),
        sa.Column("from_agent", sa.String(80), nullable=False, index=True),
        sa.Column("to_agent", sa.String(80), nullable=False, index=True),
        sa.Column("decision", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("payload_json", postgresql.JSONB, nullable=True),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "shared_context_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("event_type", sa.String(100), nullable=False, index=True),
        sa.Column("source_module", sa.String(120), nullable=False, index=True),
        sa.Column("target_modules_json", postgresql.JSONB, nullable=True),
        sa.Column("payload_json", postgresql.JSONB, nullable=True),
        sa.Column("priority", sa.Integer, server_default="5"),
        sa.Column("consumed", sa.Boolean, server_default=sa.text("false")),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("shared_context_events")
    op.drop_table("coordination_decisions")
    op.drop_table("workflow_coordination_runs")
    op.drop_table("agent_messages_v2")
    op.drop_table("agent_runs_v2")
    op.drop_table("agent_registry")
