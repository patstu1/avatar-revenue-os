"""Expand media_jobs table for async job tracking and webhook pipeline.

ALTERs the existing media_jobs table in place to add async-tracking columns
(org_id, content_item_id, quality_tier, pipeline continuation fields, JSONB
payloads, provider_job_id unique index) while preserving existing rows and
FK relationships (e.g. studio_generations.media_job_id).

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
    # ---------------------------------------------------------------
    # Strategy: ALTER TABLE in place.
    #
    # Old columns kept as-is: id, brand_id, script_id, job_type,
    #   status, provider, provider_job_id, error_message,
    #   completed_at, created_at, updated_at
    #
    # Old columns renamed:
    #   input_config  -> input_payload   (JSONB, already correct type)
    #   output_config -> output_payload  (JSONB, already correct type)
    #   retries       -> retry_count     (Integer, already correct type)
    #
    # Old columns dropped (no longer in new schema):
    #   avatar_id, output_asset_id, max_retries, error_details,
    #   cost, started_at
    #
    # New columns added:
    #   org_id, content_item_id, quality_tier, output_url,
    #   dispatched_at, next_pipeline_task, next_pipeline_args
    #
    # Existing data and FK constraints (studio_generations) preserved.
    # ---------------------------------------------------------------

    # --- 1. Add new columns (skip if already present) ---
    conn = op.get_bind()
    _existing = {
        row[0] for row in conn.execute(sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'media_jobs'"
        ))
    }
    new_columns = [
        ("org_id", sa.Column("org_id", UUID(as_uuid=True), nullable=True)),
        ("content_item_id", sa.Column("content_item_id", UUID(as_uuid=True), nullable=True)),
        ("quality_tier", sa.Column("quality_tier", sa.String(50), server_default="standard", nullable=False)),
        ("output_url", sa.Column("output_url", sa.String(2048), nullable=True)),
        ("dispatched_at", sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True)),
        ("next_pipeline_task", sa.Column("next_pipeline_task", sa.String(500), nullable=True)),
        ("next_pipeline_args", sa.Column("next_pipeline_args", JSONB, nullable=True)),
    ]
    for col_name, col_def in new_columns:
        if col_name not in _existing:
            op.add_column("media_jobs", col_def)

    # --- 2. Rename columns (only if old name exists) ---
    conn = op.get_bind()
    existing_cols = {
        row[0] for row in conn.execute(sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'media_jobs'"
        ))
    }
    if "input_config" in existing_cols:
        op.alter_column("media_jobs", "input_config", new_column_name="input_payload")
    if "output_config" in existing_cols:
        op.alter_column("media_jobs", "output_config", new_column_name="output_payload")
    if "retries" in existing_cols:
        op.alter_column("media_jobs", "retries", new_column_name="retry_count")

    # --- 3. Widen provider and provider_job_id columns ---
    op.alter_column("media_jobs", "provider",
                    type_=sa.String(100), existing_type=sa.String(50),
                    nullable=False, existing_nullable=True)
    op.alter_column("media_jobs", "provider_job_id",
                    type_=sa.String(500), existing_type=sa.String(255))

    # --- 4. Change status default ---
    op.alter_column("media_jobs", "status",
                    server_default="dispatched",
                    existing_type=sa.String(20))

    # --- 5. Add FK constraints for new columns ---
    op.create_foreign_key(
        "fk_media_jobs_org_id", "media_jobs",
        "organizations", ["org_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_media_jobs_content_item_id", "media_jobs",
        "content_items", ["content_item_id"], ["id"]
    )

    # --- 6. Drop old columns no longer in the new schema ---
    # Drop FK constraints on columns being removed.
    # Use raw SQL to find and drop by column rather than by name,
    # since constraint names may vary across environments.
    op.execute("""
        DO $$
        DECLARE
            _con text;
        BEGIN
            -- Drop FK constraints referencing avatar_id
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

            -- Drop FK constraints referencing output_asset_id
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

    # Drop columns only if they exist (safe for varying DB states)
    conn = op.get_bind()
    existing_cols = {
        row[0] for row in conn.execute(sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'media_jobs'"
        ))
    }
    for col in ["avatar_id", "output_asset_id", "max_retries", "error_details", "cost", "started_at"]:
        if col in existing_cols:
            op.drop_column("media_jobs", col)

    # --- 7. Add unique constraint on provider_job_id ---
    op.create_unique_constraint(
        "uq_media_jobs_provider_job_id", "media_jobs", ["provider_job_id"]
    )

    # --- 8. Add new indexes ---
    op.create_index("ix_media_jobs_org_id", "media_jobs", ["org_id"])
    op.create_index("ix_media_jobs_content_item_id", "media_jobs", ["content_item_id"])
    op.create_index("ix_media_jobs_script_id", "media_jobs", ["script_id"])
    op.create_index("ix_media_jobs_job_type", "media_jobs", ["job_type"])
    op.create_index("ix_media_jobs_provider", "media_jobs", ["provider"])
    op.create_index("ix_media_jobs_provider_job_id", "media_jobs", ["provider_job_id"])


def downgrade() -> None:
    # --- Reverse: restore old columns, rename back, drop new columns ---

    # Drop new indexes
    op.drop_index("ix_media_jobs_provider_job_id", "media_jobs")
    op.drop_index("ix_media_jobs_provider", "media_jobs")
    op.drop_index("ix_media_jobs_job_type", "media_jobs")
    op.drop_index("ix_media_jobs_script_id", "media_jobs")
    op.drop_index("ix_media_jobs_content_item_id", "media_jobs")
    op.drop_index("ix_media_jobs_org_id", "media_jobs")

    # Drop unique constraint
    op.drop_constraint("uq_media_jobs_provider_job_id", "media_jobs", type_="unique")

    # Restore dropped columns
    op.add_column("media_jobs", sa.Column(
        "avatar_id", UUID(as_uuid=True), nullable=True
    ))
    op.add_column("media_jobs", sa.Column(
        "output_asset_id", UUID(as_uuid=True), nullable=True
    ))
    op.add_column("media_jobs", sa.Column(
        "max_retries", sa.Integer, server_default="3", nullable=False
    ))
    op.add_column("media_jobs", sa.Column(
        "error_details", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True
    ))
    op.add_column("media_jobs", sa.Column(
        "cost", sa.Float, server_default="0.0", nullable=False
    ))
    op.add_column("media_jobs", sa.Column(
        "started_at", sa.DateTime(timezone=True), nullable=True
    ))

    # Restore FK constraints
    op.create_foreign_key(
        "media_jobs_avatar_id_fkey", "media_jobs",
        "avatars", ["avatar_id"], ["id"]
    )
    op.create_foreign_key(
        "media_jobs_output_asset_id_fkey", "media_jobs",
        "assets", ["output_asset_id"], ["id"]
    )

    # Drop new FK constraints
    op.drop_constraint("fk_media_jobs_content_item_id", "media_jobs", type_="foreignkey")
    op.drop_constraint("fk_media_jobs_org_id", "media_jobs", type_="foreignkey")

    # Drop new columns
    op.drop_column("media_jobs", "next_pipeline_args")
    op.drop_column("media_jobs", "next_pipeline_task")
    op.drop_column("media_jobs", "dispatched_at")
    op.drop_column("media_jobs", "output_url")
    op.drop_column("media_jobs", "quality_tier")
    op.drop_column("media_jobs", "content_item_id")
    op.drop_column("media_jobs", "org_id")

    # Rename columns back
    op.alter_column("media_jobs", "retry_count", new_column_name="retries")
    op.alter_column("media_jobs", "output_payload", new_column_name="output_config")
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
