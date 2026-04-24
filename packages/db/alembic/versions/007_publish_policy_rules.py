"""Create publish_policy_rules table and add policy columns to approvals.

Revision ID: 007_publish_policy
Revises: 006_gm_alerts
Create Date: 2026-04-07
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "007_publish_policy"
down_revision = ("006_gm_alerts", "005_media_jobs_v2")
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :t)"),
        {"t": name},
    )
    return result.scalar()


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c)"
        ),
        {"t": table, "c": column},
    )
    return result.scalar()


def upgrade() -> None:
    # ── Create publish_policy_rules table ────────────────────────────────
    if not _table_exists("publish_policy_rules"):
        op.create_table(
            "publish_policy_rules",
            sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=True, index=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("priority", sa.Integer, nullable=False, default=100, index=True),
            sa.Column("tier", sa.String(30), nullable=False),
            sa.Column("sample_rate", sa.Float, default=0.0),
            sa.Column("description", sa.Text, nullable=True),
            # Match fields
            sa.Column("match_content_type", sa.String(50), nullable=True),
            sa.Column("match_platform", sa.String(50), nullable=True),
            sa.Column("match_monetization_method", sa.String(50), nullable=True),
            sa.Column("match_hook_type", sa.String(60), nullable=True),
            sa.Column("match_creative_structure", sa.String(60), nullable=True),
            sa.Column("match_has_offer", sa.Boolean, nullable=True),
            sa.Column("match_tags_contain", JSONB, nullable=True),
            sa.Column("match_account_health", sa.String(20), nullable=True),
            sa.Column("match_governance_level", sa.String(20), nullable=True),
            sa.Column("max_account_age_days", sa.Integer, nullable=True),
            sa.Column("min_qa_score", sa.Float, nullable=True),
            sa.Column("max_qa_score", sa.Float, nullable=True),
            sa.Column("min_confidence", sa.String(20), nullable=True),
            sa.Column("is_active", sa.Boolean, default=True, index=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )

    # ── Add columns to approvals ─────────────────────────────────────────
    if not _column_exists("approvals", "publish_policy_tier"):
        op.add_column("approvals", sa.Column("publish_policy_tier", sa.String(30), nullable=True, index=True))
    if not _column_exists("approvals", "sample_flagged"):
        op.add_column("approvals", sa.Column("sample_flagged", sa.Boolean, default=False, server_default=sa.text("false")))

    # ── Seed default rules ───────────────────────────────────────────────
    conn = op.get_bind()
    count = conn.execute(sa.text("SELECT count(*) FROM publish_policy_rules")).scalar()
    if count == 0:
        _seed_default_rules()


def _seed_default_rules():
    rules_table = sa.table(
        "publish_policy_rules",
        sa.column("name", sa.String),
        sa.column("priority", sa.Integer),
        sa.column("tier", sa.String),
        sa.column("sample_rate", sa.Float),
        sa.column("description", sa.Text),
        sa.column("match_content_type", sa.String),
        sa.column("match_platform", sa.String),
        sa.column("match_monetization_method", sa.String),
        sa.column("match_has_offer", sa.Boolean),
        sa.column("match_tags_contain", JSONB),
        sa.column("match_account_health", sa.String),
        sa.column("match_governance_level", sa.String),
        sa.column("max_account_age_days", sa.Integer),
        sa.column("min_qa_score", sa.Float),
        sa.column("max_qa_score", sa.Float),
        sa.column("min_confidence", sa.String),
        sa.column("is_active", sa.Boolean),
    )

    op.bulk_insert(rules_table, [
        # ── BLOCK tier (highest priority — catch dangerous content first) ──
        {
            "name": "block_low_qa", "priority": 10, "tier": "block",
            "sample_rate": 0.0, "max_qa_score": 0.3, "is_active": True,
            "description": "Block content with QA score below 0.3 — too low quality to publish.",
            "match_content_type": None, "match_platform": None, "match_monetization_method": None,
            "match_has_offer": None, "match_tags_contain": None, "match_account_health": None,
            "match_governance_level": None, "max_account_age_days": None, "min_qa_score": None,
            "min_confidence": None,
        },
        {
            "name": "block_insufficient_confidence", "priority": 20, "tier": "block",
            "sample_rate": 0.0, "min_confidence": "low", "max_qa_score": None, "is_active": True,
            "description": "Block content with insufficient confidence — system cannot assess quality.",
            "match_content_type": None, "match_platform": None, "match_monetization_method": None,
            "match_has_offer": None, "match_tags_contain": None, "match_account_health": None,
            "match_governance_level": None, "max_account_age_days": None, "min_qa_score": None,
        },
        {
            "name": "block_medical_claims", "priority": 30, "tier": "block",
            "sample_rate": 0.0, "is_active": True,
            "description": "Block content containing medical or health claims — requires human review.",
            "match_tags_contain": ["medical_claim", "health_claim"],
            "match_content_type": None, "match_platform": None, "match_monetization_method": None,
            "match_has_offer": None, "match_account_health": None,
            "match_governance_level": None, "max_account_age_days": None,
            "min_qa_score": None, "max_qa_score": None, "min_confidence": None,
        },
        {
            "name": "block_financial_claims", "priority": 40, "tier": "block",
            "sample_rate": 0.0, "is_active": True,
            "description": "Block content containing financial advice or investment claims.",
            "match_tags_contain": ["financial_advice", "investment"],
            "match_content_type": None, "match_platform": None, "match_monetization_method": None,
            "match_has_offer": None, "match_account_health": None,
            "match_governance_level": None, "max_account_age_days": None,
            "min_qa_score": None, "max_qa_score": None, "min_confidence": None,
        },
        {
            "name": "block_legal_claims", "priority": 50, "tier": "block",
            "sample_rate": 0.0, "is_active": True,
            "description": "Block content containing legal advice claims.",
            "match_tags_contain": ["legal_advice"],
            "match_content_type": None, "match_platform": None, "match_monetization_method": None,
            "match_has_offer": None, "match_account_health": None,
            "match_governance_level": None, "max_account_age_days": None,
            "min_qa_score": None, "max_qa_score": None, "min_confidence": None,
        },

        # ── MANUAL_APPROVAL tier (medium priority — catch risky content) ──
        {
            "name": "manual_sponsored", "priority": 60, "tier": "manual_approval",
            "sample_rate": 0.0, "match_monetization_method": "sponsor", "is_active": True,
            "description": "All sponsored posts require manual review before publishing.",
            "match_content_type": None, "match_platform": None, "match_has_offer": None,
            "match_tags_contain": None, "match_account_health": None,
            "match_governance_level": None, "max_account_age_days": None,
            "min_qa_score": None, "max_qa_score": None, "min_confidence": None,
        },
        {
            "name": "manual_new_accounts", "priority": 70, "tier": "manual_approval",
            "sample_rate": 0.0, "max_account_age_days": 14, "is_active": True,
            "description": "New accounts (< 14 days old) need manual review until trust is established.",
            "match_content_type": None, "match_platform": None, "match_monetization_method": None,
            "match_has_offer": None, "match_tags_contain": None, "match_account_health": None,
            "match_governance_level": None,
            "min_qa_score": None, "max_qa_score": None, "min_confidence": None,
        },
        {
            "name": "manual_degraded_accounts", "priority": 80, "tier": "manual_approval",
            "sample_rate": 0.0, "match_account_health": "degraded", "is_active": True,
            "description": "Degraded accounts need human check before publishing more content.",
            "match_content_type": None, "match_platform": None, "match_monetization_method": None,
            "match_has_offer": None, "match_tags_contain": None,
            "match_governance_level": None, "max_account_age_days": None,
            "min_qa_score": None, "max_qa_score": None, "min_confidence": None,
        },

        # ── SAMPLE_REVIEW tier (lower priority — spot-check certain categories) ──
        {
            "name": "sample_affiliate", "priority": 90, "tier": "sample_review",
            "sample_rate": 0.15, "match_has_offer": True, "match_monetization_method": "affiliate",
            "is_active": True,
            "description": "Sample 15% of affiliate content for async post-publish review.",
            "match_content_type": None, "match_platform": None,
            "match_tags_contain": None, "match_account_health": None,
            "match_governance_level": None, "max_account_age_days": None,
            "min_qa_score": None, "max_qa_score": None, "min_confidence": None,
        },
        {
            "name": "sample_live_stream", "priority": 100, "tier": "sample_review",
            "sample_rate": 0.25, "match_content_type": "live_stream", "is_active": True,
            "description": "Sample 25% of live streams for async review.",
            "match_platform": None, "match_monetization_method": None,
            "match_has_offer": None, "match_tags_contain": None, "match_account_health": None,
            "match_governance_level": None, "max_account_age_days": None,
            "min_qa_score": None, "max_qa_score": None, "min_confidence": None,
        },
        {
            "name": "sample_carousel", "priority": 110, "tier": "sample_review",
            "sample_rate": 0.10, "match_content_type": "carousel", "is_active": True,
            "description": "Sample 10% of carousels for async review.",
            "match_platform": None, "match_monetization_method": None,
            "match_has_offer": None, "match_tags_contain": None, "match_account_health": None,
            "match_governance_level": None, "max_account_age_days": None,
            "min_qa_score": None, "max_qa_score": None, "min_confidence": None,
        },
        {
            "name": "sample_strict_governance", "priority": 120, "tier": "sample_review",
            "sample_rate": 0.20, "match_governance_level": "strict", "is_active": True,
            "description": "Sample 20% of content under strict governance brands.",
            "match_content_type": None, "match_platform": None, "match_monetization_method": None,
            "match_has_offer": None, "match_tags_contain": None, "match_account_health": None,
            "max_account_age_days": None,
            "min_qa_score": None, "max_qa_score": None, "min_confidence": None,
        },

        # ── AUTO_PUBLISH tier (lowest priority — safe content flows automatically) ──
        {
            "name": "auto_high_qa", "priority": 130, "tier": "auto_publish",
            "sample_rate": 0.0, "min_qa_score": 0.7, "min_confidence": "medium",
            "is_active": True,
            "description": "Auto-publish high-quality content with medium+ confidence.",
            "match_content_type": None, "match_platform": None, "match_monetization_method": None,
            "match_has_offer": None, "match_tags_contain": None, "match_account_health": None,
            "match_governance_level": None, "max_account_age_days": None, "max_qa_score": None,
        },
        {
            "name": "auto_standard", "priority": 140, "tier": "auto_publish",
            "sample_rate": 0.0, "min_qa_score": 0.5, "is_active": True,
            "description": "Auto-publish content scoring 0.5+.",
            "match_content_type": None, "match_platform": None, "match_monetization_method": None,
            "match_has_offer": None, "match_tags_contain": None, "match_account_health": None,
            "match_governance_level": None, "max_account_age_days": None, "max_qa_score": None,
            "min_confidence": None,
        },

        # ── CATCH-ALL (highest priority number — last resort) ──
        {
            "name": "fallback_manual", "priority": 999, "tier": "manual_approval",
            "sample_rate": 0.0, "is_active": True,
            "description": "Catch-all: anything unmatched goes to manual review.",
            "match_content_type": None, "match_platform": None, "match_monetization_method": None,
            "match_has_offer": None, "match_tags_contain": None, "match_account_health": None,
            "match_governance_level": None, "max_account_age_days": None,
            "min_qa_score": None, "max_qa_score": None, "min_confidence": None,
        },
    ])


def downgrade() -> None:
    op.drop_table("publish_policy_rules")
    if _column_exists("approvals", "publish_policy_tier"):
        op.drop_column("approvals", "publish_policy_tier")
    if _column_exists("approvals", "sample_flagged"):
        op.drop_column("approvals", "sample_flagged")
