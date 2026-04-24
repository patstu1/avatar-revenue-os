"""Create autonomous farm tables (af_*).

Revision ID: af_001
Revises: tv_001
Create Date: 2026-04-02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "af_001"
down_revision = "tv_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "af_niche_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("niche", sa.String(120), nullable=False, index=True),
        sa.Column("platform", sa.String(60), nullable=False, index=True),
        sa.Column("composite_score", sa.Float, default=0.0),
        sa.Column("monetization_score", sa.Float, default=0.0),
        sa.Column("opportunity_score", sa.Float, default=0.0),
        sa.Column("trend_velocity", sa.Float, default=0.0),
        sa.Column("competition", sa.Float, default=0.0),
        sa.Column("avg_cpm", sa.Float, default=0.0),
        sa.Column("affiliate_density", sa.Float, default=0.0),
        sa.Column("evergreen", sa.Boolean, default=False),
        sa.Column("keywords", postgresql.JSONB, default=list),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    op.create_table(
        "af_warmup_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("creator_accounts.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("current_phase", sa.String(30), default="seed"),
        sa.Column("age_days", sa.Integer, default=0),
        sa.Column("max_posts_per_day", sa.Integer, default=0),
        sa.Column("monetization_allowed", sa.Boolean, default=False),
        sa.Column("shadow_ban_detected", sa.Boolean, default=False),
        sa.Column("shadow_ban_severity", sa.String(20), nullable=True),
        sa.Column("cooldown_until", sa.String(30), nullable=True),
        sa.Column("posts_today", sa.Integer, default=0),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    op.create_table(
        "af_fleet_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("total_accounts", sa.Integer, default=0),
        sa.Column("accounts_warming", sa.Integer, default=0),
        sa.Column("accounts_scaling", sa.Integer, default=0),
        sa.Column("accounts_plateaued", sa.Integer, default=0),
        sa.Column("accounts_suspended", sa.Integer, default=0),
        sa.Column("accounts_retired", sa.Integer, default=0),
        sa.Column("total_posts_today", sa.Integer, default=0),
        sa.Column("total_revenue_30d", sa.Float, default=0.0),
        sa.Column("expansion_recommended", sa.Boolean, default=False),
        sa.Column("expansion_details", postgresql.JSONB, default=dict),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    op.create_table(
        "af_voice_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("creator_accounts.id"),
            nullable=False,
            index=True,
            unique=True,
        ),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("style", sa.String(60), nullable=False),
        sa.Column("vocabulary_level", sa.String(30), nullable=False),
        sa.Column("emoji_usage", sa.String(20), default="minimal"),
        sa.Column("preferred_hook_style", sa.String(40), nullable=False),
        sa.Column("cta_style", sa.String(40), nullable=False),
        sa.Column("paragraph_style", sa.String(40), nullable=False),
        sa.Column("signature_phrases", postgresql.JSONB, default=list),
        sa.Column("tone_keywords", postgresql.JSONB, default=list),
        sa.Column("avoid_keywords", postgresql.JSONB, default=list),
        sa.Column("full_profile", postgresql.JSONB, default=dict),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    op.create_table(
        "af_repurpose_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "source_content_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("content_items.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "derived_brief_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("content_briefs.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("target_platform", sa.String(60), nullable=False),
        sa.Column("target_content_type", sa.String(60), nullable=False),
        sa.Column("status", sa.String(30), default="pending"),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    op.create_table(
        "af_competitor_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("platform", sa.String(60), nullable=False),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("niche", sa.String(120), nullable=False),
        sa.Column("follower_count", sa.Integer, default=0),
        sa.Column("avg_engagement_rate", sa.Float, default=0.0),
        sa.Column("posting_frequency", sa.Float, default=0.0),
        sa.Column("monetization_methods", postgresql.JSONB, default=list),
        sa.Column("content_gaps", postgresql.JSONB, default=list),
        sa.Column("last_scanned_at", sa.String(30), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    op.create_table(
        "af_daily_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("report_date", sa.String(10), nullable=False, index=True),
        sa.Column("content_created", sa.Integer, default=0),
        sa.Column("content_approved", sa.Integer, default=0),
        sa.Column("content_published", sa.Integer, default=0),
        sa.Column("content_quality_blocked", sa.Integer, default=0),
        sa.Column("total_impressions", sa.Integer, default=0),
        sa.Column("total_engagement", sa.Integer, default=0),
        sa.Column("total_revenue", sa.Float, default=0.0),
        sa.Column("top_performing_content", postgresql.JSONB, default=list),
        sa.Column("niche_performance", postgresql.JSONB, default=dict),
        sa.Column("fleet_status", postgresql.JSONB, default=dict),
        sa.Column("recommendations", postgresql.JSONB, default=list),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("af_daily_reports")
    op.drop_table("af_competitor_accounts")
    op.drop_table("af_repurpose_records")
    op.drop_table("af_voice_profiles")
    op.drop_table("af_fleet_reports")
    op.drop_table("af_warmup_plans")
    op.drop_table("af_niche_scores")
