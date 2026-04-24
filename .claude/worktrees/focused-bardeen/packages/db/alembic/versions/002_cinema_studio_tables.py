"""Add Cinema Studio tables: studio_projects, studio_scenes, character_bibles,
style_presets, studio_generations, studio_activity.

Revision ID: 002_cinema_studio
Revises: 001_consolidated
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002_cinema_studio"
down_revision = "001_consolidated"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = set(inspector.get_table_names())

    if "style_presets" in existing:
        return

    op.create_table(
        "style_presets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("category", sa.String(100), server_default="cinematic"),
        sa.Column("preview_url", sa.String(1024)),
        sa.Column("tags", postgresql.JSONB, server_default="[]"),
        sa.Column("is_popular", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "studio_projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("genre", sa.String(100), server_default="drama"),
        sa.Column("status", sa.String(50), server_default="draft"),
        sa.Column("thumbnail_url", sa.String(1024)),
        sa.Column("offer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("offers.id"), index=True),
        sa.Column("target_platform", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "character_bibles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("gender", sa.String(50), server_default="other"),
        sa.Column("age", sa.Integer),
        sa.Column("ethnicity", sa.String(100)),
        sa.Column("hair_color", sa.String(50)),
        sa.Column("hair_style", sa.String(100)),
        sa.Column("eye_color", sa.String(50)),
        sa.Column("build", sa.String(100)),
        sa.Column("personality", sa.Text),
        sa.Column("role", sa.String(100), server_default="supporting"),
        sa.Column("image_url", sa.String(1024)),
        sa.Column("tags", postgresql.JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "studio_scenes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("studio_projects.id", ondelete="SET NULL"), index=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("negative_prompt", sa.Text),
        sa.Column("camera_shot", sa.String(50), server_default="medium"),
        sa.Column("camera_movement", sa.String(50), server_default="static"),
        sa.Column("lighting", sa.String(50), server_default="natural"),
        sa.Column("mood", sa.String(50), server_default="cinematic"),
        sa.Column("style_preset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("style_presets.id"), index=True),
        sa.Column("duration_seconds", sa.Float, server_default="5.0"),
        sa.Column("aspect_ratio", sa.String(20), server_default="16:9"),
        sa.Column("character_ids", postgresql.JSONB, server_default="[]"),
        sa.Column("order_index", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(50), server_default="draft"),
        sa.Column("thumbnail_url", sa.String(1024)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "studio_generations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scene_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("studio_scenes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("media_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("media_jobs.id"), index=True),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("progress", sa.Integer, server_default="0"),
        sa.Column("video_url", sa.String(1024)),
        sa.Column("thumbnail_url", sa.String(1024)),
        sa.Column("error_message", sa.Text),
        sa.Column("model", sa.String(100), server_default="runway"),
        sa.Column("seed", sa.Integer),
        sa.Column("steps", sa.Integer, server_default="50"),
        sa.Column("guidance", sa.Float, server_default="7.5"),
        sa.Column("duration_seconds", sa.Float, server_default="5.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "studio_activity",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("activity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_name", sa.String(500), nullable=False),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("studio_activity")
    op.drop_table("studio_generations")
    op.drop_table("studio_scenes")
    op.drop_table("character_bibles")
    op.drop_table("studio_projects")
    op.drop_table("style_presets")
