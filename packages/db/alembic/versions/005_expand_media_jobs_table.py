"""Expand media_jobs table for async job tracking and webhook pipeline.

ALTERs the existing media_jobs table in place to add async-tracking columns
(org_id, content_item_id, quality_tier, pipeline continuation fields, JSONB
payloads, provider_job_id unique index) while preserving existing rows and
FK relationships (e.g. studio_generations.media_job_id).

Revision ID: 005_media_jobs_v2
Revises: 004_monetization
Create Date: 2026-04-05
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

from packages.db.alembic.migration_safety import (
    constraint_exists,
    fk_exists,
    get_columns,
    safe_add_column,
    safe_create_fk,
    safe_create_index,
    safe_create_unique_constraint,
    safe_drop_column,
)

revision = "005_media_jobs_v2"
down_revision = "004_monetization"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------------
    # Strategy: ALTER TABLE in place — fully idempotent.
    # Every operation checks existence before acting.
    # ---------------------------------------------------------------

    # --- 1. Add new columns (skip if already present) ---
    safe_add_column("media_jobs", "org_id",
                    sa.Column("org_id", UUID(as_uuid=True), nullable=True))
    safe_add_column("media_jobs", "content_item_id",
                    sa.Column("content_item_id", UUID(as_uuid=True), nullable=True))
    safe_add_column("media_jobs", "quality_tier",
                    sa.Column("quality_tier", sa.String(50), server_default="standard", nullable=False))
    safe_add_column("media_jobs", "output_url",
                    sa.Column("output_url", sa.String(2048), nullable=True))
    safe_add_column("media_jobs", "dispatched_at",
                    sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True))
    safe_add_column("media_jobs", "next_pipeline_task",
                    sa.Column("next_pipeline_task", sa.String(500), nullable=True))
    safe_add_column("media_jobs", "next_pipeline_args",
                    sa.Column("next_pipeline_args", JSONB, nullable=True))

    # --- 2. Rename columns (only if old name exists and new name doesn't) ---
    existing_cols = get_columns("media_jobs")

    if "input_config" in existing_cols and "input_payload" not in existing_cols:
        op.alter_column("media_jobs", "input_config", new_column_name="input_payload")
    if "output_config" in existing_cols and "output_payload" not in existing_cols:
        op.alter_column("media_jobs", "output_config", new_column_name="output_payload")
    if "retries" in existing_cols and "retry_count" not in existing_cols:
        op.alter_column("media_jobs", "retries", new_column_name="retry_count")

    # --- 3. Widen provider and provider_job_id columns ---
    # These are safe to run multiple times (widening is a no-op if already wide)
    op.alter_column("media_jobs", "provider",
                    type_=sa.String(100), existing_type=sa.String(50),
                    nullable=False, existing_nullable=True)
    op.alter_column("media_jobs", "provider_job_id",
                    type_=sa.String(500), existing_type=sa.String(255))

    # --- 4. Change status default ---
    op.alter_column("media_jobs", "status",
                    server_default="dispatched",
                    existing_type=sa.String(20))

    # --- 5. Add FK constraints for new columns (idempotent) ---
    safe_create_fk(
        "fk_media_jobs_org_id", "media_jobs",
        "organizations", ["org_id"], ["id"], ondelete="CASCADE",
    )
    safe_create_fk(
        "fk_media_jobs_content_item_id", "media_jobs",
        "content_items", ["content_item_id"], ["id"],
    )

    # --- 6. Drop old columns no longer in the new schema ---
    # Drop FK constraints on columns being removed (idempotent via DO $$ block).
    op.execute("""
        DO $$
        DECLARE
            _con text;
        BEGIN
            FOR _con IN
                SELECT constraint_name FROM information_schema.key_column_usage
                WHERE table_name = 'media_jobs' AND column_name = 'avatar_id'
                  AND constraint_name IN (
                      SELECT constraint_name FROM information_schema.table_constraints
                      WHERE table_name = 'media_jobs' AND constraint_type = 'FOREIGN KEY'
                  )
            LOOP
                EXECUTE format('ALTER TABLE media_jobs DROP CONSTRAINT IF EXISTS %I', _con);
            END LOOP;

            FOR _con IN
                SELECT constraint_name FROM information_schema.key_column_usage
                WHERE table_name = 'media_jobs' AND column_name = 'output_asset_id'
                  AND constraint_name IN (
                      SELECT constraint_name FROM information_schema.table_constraints
                      WHERE table_name = 'media_jobs' AND constraint_type = 'FOREIGN KEY'
                  )
            LOOP
                EXECUTE format('ALTER TABLE media_jobs DROP CONSTRAINT IF EXISTS %I', _con);
            END LOOP;
        END $$;
    """)

    for col in ["avatar_id", "output_asset_id", "max_retries", "error_details", "cost", "started_at"]:
        safe_drop_column("media_jobs", col)

    # --- 7. Add unique constraint on provider_job_id (idempotent) ---
    safe_create_unique_constraint(
        "uq_media_jobs_provider_job_id", "media_jobs", ["provider_job_id"],
    )

    # --- 8. Add new indexes (idempotent) ---
    safe_create_index("ix_media_jobs_org_id", "media_jobs", ["org_id"])
    safe_create_index("ix_media_jobs_content_item_id", "media_jobs", ["content_item_id"])
    safe_create_index("ix_media_jobs_script_id", "media_jobs", ["script_id"])
    safe_create_index("ix_media_jobs_job_type", "media_jobs", ["job_type"])
    safe_create_index("ix_media_jobs_provider", "media_jobs", ["provider"])
    safe_create_index("ix_media_jobs_provider_job_id", "media_jobs", ["provider_job_id"])


def downgrade() -> None:
    # --- Reverse: restore old columns, rename back, drop new columns ---
    from packages.db.alembic.migration_safety import index_exists

    # Drop new indexes (safe)
    for idx in ["ix_media_jobs_provider_job_id", "ix_media_jobs_provider",
                "ix_media_jobs_job_type", "ix_media_jobs_script_id",
                "ix_media_jobs_content_item_id", "ix_media_jobs_org_id"]:
        if index_exists(idx):
            op.drop_index(idx, "media_jobs")

    # Drop unique constraint (safe)
    if constraint_exists("media_jobs", "uq_media_jobs_provider_job_id"):
        op.drop_constraint("uq_media_jobs_provider_job_id", "media_jobs", type_="unique")

    # Restore dropped columns
    safe_add_column("media_jobs", "avatar_id",
                    sa.Column("avatar_id", UUID(as_uuid=True), nullable=True))
    safe_add_column("media_jobs", "output_asset_id",
                    sa.Column("output_asset_id", UUID(as_uuid=True), nullable=True))
    safe_add_column("media_jobs", "max_retries",
                    sa.Column("max_retries", sa.Integer, server_default="3", nullable=False))
    safe_add_column("media_jobs", "error_details",
                    sa.Column("error_details", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True))
    safe_add_column("media_jobs", "cost",
                    sa.Column("cost", sa.Float, server_default="0.0", nullable=False))
    safe_add_column("media_jobs", "started_at",
                    sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))

    # Restore FK constraints
    safe_create_fk("media_jobs_avatar_id_fkey", "media_jobs", "avatars", ["avatar_id"], ["id"])
    safe_create_fk("media_jobs_output_asset_id_fkey", "media_jobs", "assets", ["output_asset_id"], ["id"])

    # Drop new FK constraints
    if fk_exists("fk_media_jobs_content_item_id"):
        op.drop_constraint("fk_media_jobs_content_item_id", "media_jobs", type_="foreignkey")
    if fk_exists("fk_media_jobs_org_id"):
        op.drop_constraint("fk_media_jobs_org_id", "media_jobs", type_="foreignkey")

    # Drop new columns
    for col in ["next_pipeline_args", "next_pipeline_task", "dispatched_at",
                "output_url", "quality_tier", "content_item_id", "org_id"]:
        safe_drop_column("media_jobs", col)

    # Rename columns back
    existing_cols = get_columns("media_jobs")
    if "retry_count" in existing_cols and "retries" not in existing_cols:
        op.alter_column("media_jobs", "retry_count", new_column_name="retries")
    if "output_payload" in existing_cols and "output_config" not in existing_cols:
        op.alter_column("media_jobs", "output_payload", new_column_name="output_config")
    if "input_payload" in existing_cols and "input_config" not in existing_cols:
        op.alter_column("media_jobs", "input_payload", new_column_name="input_config")

    # Restore provider column width
    op.alter_column("media_jobs", "provider",
                    type_=sa.String(50), existing_type=sa.String(100),
                    nullable=True)
    op.alter_column("media_jobs", "provider_job_id",
                    type_=sa.String(255), existing_type=sa.String(500))

    # Restore status default
    op.alter_column("media_jobs", "status",
                    server_default="pending",
                    existing_type=sa.String(20))
