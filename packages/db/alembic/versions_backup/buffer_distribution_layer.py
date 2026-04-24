"""Buffer Distribution Layer — 5 tables.

Revision ID: buffer_dist_001
Revises: brain_phase_d_001
Create Date: 2026-03-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "buffer_dist_001"
down_revision = "brain_phase_d_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "buffer_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("creator_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("creator_accounts.id"), nullable=True, index=True),
        sa.Column("platform", sa.String(50), nullable=False, index=True),
        sa.Column("buffer_profile_id", sa.String(255), nullable=True, unique=True, index=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("credential_status", sa.String(30), server_default="not_connected", index=True),
        sa.Column("last_sync_status", sa.String(30), server_default="never", index=True),
        sa.Column("last_sync_at", sa.String(50), nullable=True),
        sa.Column("config_json", postgresql.JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "buffer_publish_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("buffer_profile_id_fk", postgresql.UUID(as_uuid=True), sa.ForeignKey("buffer_profiles.id"), nullable=False, index=True),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content_items.id"), nullable=True, index=True),
        sa.Column("distribution_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("distribution_plans.id"), nullable=True, index=True),
        sa.Column("platform", sa.String(50), nullable=False, index=True),
        sa.Column("publish_mode", sa.String(30), server_default="queue", index=True),
        sa.Column("status", sa.String(30), server_default="pending", index=True),
        sa.Column("payload_json", postgresql.JSONB, nullable=True),
        sa.Column("buffer_post_id", sa.String(255), nullable=True, index=True),
        sa.Column("scheduled_at", sa.String(50), nullable=True),
        sa.Column("published_at", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "buffer_publish_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("buffer_publish_jobs.id"), nullable=False, index=True),
        sa.Column("attempt_number", sa.Integer, server_default="1"),
        sa.Column("request_payload_json", postgresql.JSONB, nullable=True),
        sa.Column("response_status_code", sa.Integer, nullable=True),
        sa.Column("response_body_json", postgresql.JSONB, nullable=True),
        sa.Column("success", sa.Boolean, server_default=sa.text("false")),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "buffer_status_syncs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("jobs_checked", sa.Integer, server_default="0"),
        sa.Column("jobs_updated", sa.Integer, server_default="0"),
        sa.Column("jobs_failed", sa.Integer, server_default="0"),
        sa.Column("jobs_published", sa.Integer, server_default="0"),
        sa.Column("sync_mode", sa.String(30), server_default="pull"),
        sa.Column("details_json", postgresql.JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "buffer_blockers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("buffer_profile_id_fk", postgresql.UUID(as_uuid=True), sa.ForeignKey("buffer_profiles.id"), nullable=True, index=True),
        sa.Column("blocker_type", sa.String(80), nullable=False, index=True),
        sa.Column("severity", sa.String(30), server_default="high", index=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("operator_action_needed", sa.Text, nullable=False),
        sa.Column("resolved", sa.Boolean, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("buffer_blockers")
    op.drop_table("buffer_status_syncs")
    op.drop_table("buffer_publish_attempts")
    op.drop_table("buffer_publish_jobs")
    op.drop_table("buffer_profiles")
