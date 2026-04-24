"""Brain Architecture Phase A — shared memory, account/opportunity/execution/audience state engines.

Revision ID: brain_phase_a_001
Revises: ae04phase_d_001
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "brain_phase_a_001"
down_revision = "ae04phase_d_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "brain_memory_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("entry_type", sa.String(100), nullable=False, index=True),
        sa.Column("scope_type", sa.String(80), nullable=False, index=True),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("reuse_recommendation", sa.Text, nullable=True),
        sa.Column("suppression_caution", sa.Text, nullable=True),
        sa.Column("platform", sa.String(80), nullable=True, index=True),
        sa.Column("niche", sa.String(255), nullable=True),
        sa.Column("detail_json", postgresql.JSONB, nullable=True),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "brain_memory_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("source_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brain_memory_entries.id"), nullable=False, index=True),
        sa.Column("target_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brain_memory_entries.id"), nullable=False, index=True),
        sa.Column("link_type", sa.String(80), nullable=False, index=True),
        sa.Column("strength", sa.Float, server_default="0.5"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "account_state_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("creator_accounts.id"), nullable=False, index=True),
        sa.Column("current_state", sa.String(50), nullable=False, index=True),
        sa.Column("state_score", sa.Float, server_default="0"),
        sa.Column("previous_state", sa.String(50), nullable=True),
        sa.Column("transition_reason", sa.Text, nullable=True),
        sa.Column("next_expected_state", sa.String(50), nullable=True),
        sa.Column("days_in_state", sa.Integer, server_default="0"),
        sa.Column("platform", sa.String(80), nullable=True, index=True),
        sa.Column("inputs_json", postgresql.JSONB, nullable=True),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "opportunity_state_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("opportunity_scope", sa.String(100), nullable=False, index=True),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("current_state", sa.String(50), nullable=False, index=True),
        sa.Column("urgency", sa.Float, server_default="0"),
        sa.Column("readiness", sa.Float, server_default="0"),
        sa.Column("suppression_risk", sa.Float, server_default="0"),
        sa.Column("expected_upside", sa.Float, server_default="0"),
        sa.Column("expected_cost", sa.Float, server_default="0"),
        sa.Column("inputs_json", postgresql.JSONB, nullable=True),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "execution_state_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("execution_scope", sa.String(100), nullable=False, index=True),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("current_state", sa.String(50), nullable=False, index=True),
        sa.Column("transition_reason", sa.Text, nullable=True),
        sa.Column("rollback_eligible", sa.Boolean, server_default=sa.text("false")),
        sa.Column("escalation_required", sa.Boolean, server_default=sa.text("false")),
        sa.Column("failure_count", sa.Integer, server_default="0"),
        sa.Column("inputs_json", postgresql.JSONB, nullable=True),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "audience_state_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("segment_label", sa.String(100), nullable=False, index=True),
        sa.Column("current_state", sa.String(60), nullable=False, index=True),
        sa.Column("state_score", sa.Float, server_default="0"),
        sa.Column("transition_likelihoods_json", postgresql.JSONB, nullable=True),
        sa.Column("next_best_action", sa.Text, nullable=True),
        sa.Column("estimated_segment_size", sa.Integer, server_default="0"),
        sa.Column("estimated_ltv", sa.Float, server_default="0"),
        sa.Column("inputs_json", postgresql.JSONB, nullable=True),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "state_transition_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("engine_type", sa.String(50), nullable=False, index=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("from_state", sa.String(60), nullable=False),
        sa.Column("to_state", sa.String(60), nullable=False),
        sa.Column("trigger", sa.String(200), nullable=False),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("detail_json", postgresql.JSONB, nullable=True),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("state_transition_events")
    op.drop_table("audience_state_snapshots")
    op.drop_table("execution_state_snapshots")
    op.drop_table("opportunity_state_snapshots")
    op.drop_table("account_state_snapshots")
    op.drop_table("brain_memory_links")
    op.drop_table("brain_memory_entries")
