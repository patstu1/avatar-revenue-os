"""Expand media_jobs table for async job tracking and webhook pipeline.

Drops the old media_jobs table (simple schema) and recreates with the full
async-tracking schema: org_id, content_item_id, quality_tier, pipeline
continuation fields, JSONB payloads, and provider_job_id unique index.

Revision ID: 005_media_jobs_v2
Revises: 004_monetization
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "005_media_jobs_v2"
down_revision = "004_monetization"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the old simple media_jobs table
    op.drop_table("media_jobs")

    # Recreate with the full async-tracking schema
    op.create_table(
        "media_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_item_id", UUID(as_uuid=True), sa.ForeignKey("content_items.id"), nullable=True),
        sa.Column("script_id", UUID(as_uuid=True), sa.ForeignKey("scripts.id"), nullable=True),

        # Job classification
        sa.Column("job_type", sa.String(50), nullable=False, comment="voice | avatar | video | image | music"),
        sa.Column("provider", sa.String(100), nullable=False, comment="Provider key assigned by integration_manager"),
        sa.Column("quality_tier", sa.String(50), server_default="standard", nullable=False),

        # Provider tracking
        sa.Column("provider_job_id", sa.String(500), nullable=True, unique=True, comment="External job ID from the provider"),
        sa.Column("status", sa.String(50), server_default="dispatched", nullable=False, comment="dispatched | processing | completed | failed"),

        # Payloads
        sa.Column("input_payload", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("output_payload", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("output_url", sa.String(2048), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),

        # Timestamps
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),

        # Retry tracking (informational)
        sa.Column("retry_count", sa.Integer, server_default="0", nullable=False),

        # Pipeline continuation
        sa.Column("next_pipeline_task", sa.String(500), nullable=True),
        sa.Column("next_pipeline_args", JSONB, nullable=True),

        # Audit
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Indexes
    op.create_index("ix_media_jobs_org_id", "media_jobs", ["org_id"])
    op.create_index("ix_media_jobs_brand_id", "media_jobs", ["brand_id"])
    op.create_index("ix_media_jobs_content_item_id", "media_jobs", ["content_item_id"])
    op.create_index("ix_media_jobs_script_id", "media_jobs", ["script_id"])
    op.create_index("ix_media_jobs_job_type", "media_jobs", ["job_type"])
    op.create_index("ix_media_jobs_provider", "media_jobs", ["provider"])
    op.create_index("ix_media_jobs_provider_job_id", "media_jobs", ["provider_job_id"])
    op.create_index("ix_media_jobs_status", "media_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("media_jobs")

    # Recreate the original simple schema
    op.create_table(
        "media_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("script_id", UUID(as_uuid=True), sa.ForeignKey("scripts.id"), nullable=True),
        sa.Column("avatar_id", UUID(as_uuid=True), sa.ForeignKey("avatars.id"), nullable=True),
        sa.Column("job_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("provider_job_id", sa.String(255), nullable=True),
        sa.Column("input_config", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("output_config", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("output_asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("retries", sa.Integer, server_default="0", nullable=False),
        sa.Column("max_retries", sa.Integer, server_default="3", nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("error_details", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("cost", sa.Float, server_default="0.0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_media_jobs_brand_id", "media_jobs", ["brand_id"])
    op.create_index("ix_media_jobs_status", "media_jobs", ["status"])
