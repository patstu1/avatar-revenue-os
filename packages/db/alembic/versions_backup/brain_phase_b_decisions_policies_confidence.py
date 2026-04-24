"""Brain Architecture Phase B — decisions, policies, confidence, cost/upside, arbitration.

Revision ID: brain_phase_b_001
Revises: brain_phase_a_001
Create Date: 2026-03-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "brain_phase_b_001"
down_revision = "brain_phase_a_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "brain_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("decision_class", sa.String(60), nullable=False, index=True),
        sa.Column("objective", sa.Text, nullable=False),
        sa.Column("target_scope", sa.String(120), nullable=False, index=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("selected_action", sa.Text, nullable=False),
        sa.Column("alternatives_json", postgresql.JSONB, nullable=True),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("policy_mode", sa.String(30), server_default="guarded", index=True),
        sa.Column("expected_upside", sa.Float, server_default="0"),
        sa.Column("expected_cost", sa.Float, server_default="0"),
        sa.Column("downstream_action", sa.Text, nullable=True),
        sa.Column("inputs_json", postgresql.JSONB, nullable=True),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "policy_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("decision_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brain_decisions.id"), nullable=True, index=True),
        sa.Column("action_ref", sa.String(200), nullable=False, index=True),
        sa.Column("policy_mode", sa.String(30), nullable=False, index=True),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("approval_needed", sa.Boolean, server_default=sa.text("false")),
        sa.Column("hard_stop_rule", sa.Text, nullable=True),
        sa.Column("rollback_rule", sa.Text, nullable=True),
        sa.Column("risk_score", sa.Float, server_default="0"),
        sa.Column("cost_impact", sa.Float, server_default="0"),
        sa.Column("inputs_json", postgresql.JSONB, nullable=True),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "confidence_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("decision_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brain_decisions.id"), nullable=True, index=True),
        sa.Column("scope_label", sa.String(200), nullable=False, index=True),
        sa.Column("confidence_score", sa.Float, server_default="0"),
        sa.Column("confidence_band", sa.String(30), server_default="medium"),
        sa.Column("signal_strength", sa.Float, server_default="0"),
        sa.Column("historical_precedent", sa.Float, server_default="0"),
        sa.Column("saturation_risk", sa.Float, server_default="0"),
        sa.Column("memory_support", sa.Float, server_default="0"),
        sa.Column("data_completeness", sa.Float, server_default="0"),
        sa.Column("execution_history", sa.Float, server_default="0"),
        sa.Column("blocker_severity", sa.Float, server_default="0"),
        sa.Column("uncertainty_factors_json", postgresql.JSONB, nullable=True),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "upside_cost_estimates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("decision_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brain_decisions.id"), nullable=True, index=True),
        sa.Column("scope_label", sa.String(200), nullable=False, index=True),
        sa.Column("expected_upside", sa.Float, server_default="0"),
        sa.Column("expected_cost", sa.Float, server_default="0"),
        sa.Column("expected_payback_days", sa.Integer, server_default="0"),
        sa.Column("operational_burden", sa.Float, server_default="0"),
        sa.Column("concentration_risk", sa.Float, server_default="0"),
        sa.Column("net_value", sa.Float, server_default="0"),
        sa.Column("inputs_json", postgresql.JSONB, nullable=True),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "arbitration_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("ranked_priorities_json", postgresql.JSONB, nullable=True),
        sa.Column("chosen_winner_class", sa.String(60), nullable=False, index=True),
        sa.Column("chosen_winner_label", sa.Text, nullable=False),
        sa.Column("rejected_actions_json", postgresql.JSONB, nullable=True),
        sa.Column("competing_count", sa.Integer, server_default="0"),
        sa.Column("net_value_chosen", sa.Float, server_default="0"),
        sa.Column("inputs_json", postgresql.JSONB, nullable=True),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("arbitration_reports")
    op.drop_table("upside_cost_estimates")
    op.drop_table("confidence_reports")
    op.drop_table("policy_evaluations")
    op.drop_table("brain_decisions")
