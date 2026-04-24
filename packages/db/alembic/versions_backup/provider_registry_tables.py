"""Provider Registry — 6 tables for provider inventory, capabilities, dependencies, readiness, usage, blockers.

Revision ID: provider_reg_001
Revises: lec_phase2_001
Create Date: 2026-03-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "provider_reg_001"
down_revision = "lec_phase2_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_registry",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("provider_key", sa.String(80), nullable=False, unique=True, index=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(60), nullable=False, index=True),
        sa.Column("provider_type", sa.String(40), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("env_keys", JSONB(), server_default="[]"),
        sa.Column("credential_status", sa.String(30), server_default="not_configured", index=True),
        sa.Column("integration_status", sa.String(30), server_default="stubbed", index=True),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("is_fallback", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("is_optional", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("capabilities_json", JSONB(), server_default="{}"),
        sa.Column("config_json", JSONB(), server_default="{}"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "provider_capabilities",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("provider_key", sa.String(80), nullable=False, index=True),
        sa.Column("capability", sa.String(120), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "provider_dependencies",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("provider_key", sa.String(80), nullable=False, index=True),
        sa.Column("module_path", sa.String(200), nullable=False, index=True),
        sa.Column("dependency_type", sa.String(40), server_default="required", index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "provider_readiness_reports",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("provider_key", sa.String(80), nullable=False, index=True),
        sa.Column("credential_status", sa.String(30), server_default="not_configured", index=True),
        sa.Column("integration_status", sa.String(30), server_default="stubbed", index=True),
        sa.Column("is_ready", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("missing_env_keys", JSONB(), server_default="[]"),
        sa.Column("operator_action", sa.Text(), nullable=True),
        sa.Column("details_json", JSONB(), server_default="{}"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "provider_usage_events",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=True, index=True),
        sa.Column("provider_key", sa.String(80), nullable=False, index=True),
        sa.Column("event_type", sa.String(80), nullable=False, index=True),
        sa.Column("success", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("cost", sa.Float(), server_default="0.0"),
        sa.Column("details_json", JSONB(), server_default="{}"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "provider_blockers",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("provider_key", sa.String(80), nullable=False, index=True),
        sa.Column("blocker_type", sa.String(80), nullable=False, index=True),
        sa.Column("severity", sa.String(30), server_default="high", index=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("operator_action_needed", sa.Text(), nullable=False),
        sa.Column("resolved", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("provider_blockers")
    op.drop_table("provider_usage_events")
    op.drop_table("provider_readiness_reports")
    op.drop_table("provider_dependencies")
    op.drop_table("provider_capabilities")
    op.drop_table("provider_registry")
