"""Authority Score reports — AI Buyer Trust Test storage.

Adds the ``authority_score_reports`` table that holds per-prospect AI Buyer
Trust Test results: company/website/email, total + per-dimension scores,
evidence (detected/missing/why/fix), raw signals, scanned-page transcript,
recommended package slug, and the public-result envelope returned to the
form.

Lead handoff lives on the existing ``lead_opportunities`` table — this
migration does NOT add a parallel CRM. ``recommended_package_slug`` mirrors
the universal slugs in ``apps/web/src/lib/proofhook-packages.ts`` so the
operator-side proposal flow continues to use the existing Stripe DB-only
metadata chain (``package_slug`` flows through Stripe → webhook → Payment →
Client → IntakeRequest unchanged).

Revision ID: 020_authority_score_reports
Revises: 019_batch13, b6587e9c03b5  (merge migration — combines the two
         pre-existing heads into a single head before adding the new table)
Create Date: 2026-04-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from packages.db.alembic.migration_safety import table_exists

# revision identifiers, used by Alembic.
revision: str = "020_authority_score_reports"
down_revision: Union[str, Sequence[str], None] = ("019_batch13", "b6587e9c03b5")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if table_exists("authority_score_reports"):
        return

    op.create_table(
        "authority_score_reports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lead_opportunity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("website_url", sa.String(length=500), nullable=False),
        sa.Column("website_domain", sa.String(length=255), nullable=False),
        sa.Column("contact_email", sa.String(length=255), nullable=False),
        sa.Column("industry", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("competitor_url", sa.String(length=500), nullable=True),
        sa.Column("city_or_market", sa.String(length=100), nullable=True),
        sa.Column("total_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("authority_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score_label", sa.String(length=40), nullable=False, server_default="not_assessed"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("dimension_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("technical_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("scanned_pages", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("top_gaps", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("quick_wins", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("recommended_package_slug", sa.String(length=100), nullable=True),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("public_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        # Platform-ready fields (Decision Layer surfaces consume these later).
        sa.Column("authority_graph", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("buyer_questions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("recommended_pages", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("recommended_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("recommended_proof_assets", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("recommended_comparison_surfaces", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("monitoring_recommendation", sa.Text(), nullable=True),
        sa.Column("report_status", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("scan_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scan_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetch_error", sa.Text(), nullable=True),
        sa.Column("formula_version", sa.String(length=20), nullable=False, server_default="v1"),
        sa.Column("report_version", sa.String(length=20), nullable=False, server_default="v1"),
        sa.Column("scan_version", sa.String(length=20), nullable=False, server_default="v1"),
        sa.Column("request_ip", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["lead_opportunity_id"], ["lead_opportunities.id"]),
    )
    op.create_index(
        "ix_authority_score_reports_id",
        "authority_score_reports",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_authority_score_reports_organization_id",
        "authority_score_reports",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_authority_score_reports_brand_id",
        "authority_score_reports",
        ["brand_id"],
        unique=False,
    )
    op.create_index(
        "ix_authority_score_reports_lead_opportunity_id",
        "authority_score_reports",
        ["lead_opportunity_id"],
        unique=False,
    )
    op.create_index(
        "ix_authority_score_reports_website_domain",
        "authority_score_reports",
        ["website_domain"],
        unique=False,
    )
    op.create_index(
        "ix_authority_score_reports_contact_email",
        "authority_score_reports",
        ["contact_email"],
        unique=False,
    )
    op.create_index(
        "ix_authority_score_reports_report_status",
        "authority_score_reports",
        ["report_status"],
        unique=False,
    )
    op.create_index(
        "ix_authority_reports_org_created",
        "authority_score_reports",
        ["organization_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_authority_reports_domain_email",
        "authority_score_reports",
        ["website_domain", "contact_email"],
        unique=False,
    )
    op.create_index(
        "ix_authority_reports_status_created",
        "authority_score_reports",
        ["report_status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    if not table_exists("authority_score_reports"):
        return
    op.drop_index("ix_authority_reports_status_created", table_name="authority_score_reports")
    op.drop_index("ix_authority_reports_domain_email", table_name="authority_score_reports")
    op.drop_index("ix_authority_reports_org_created", table_name="authority_score_reports")
    op.drop_index("ix_authority_score_reports_report_status", table_name="authority_score_reports")
    op.drop_index("ix_authority_score_reports_contact_email", table_name="authority_score_reports")
    op.drop_index("ix_authority_score_reports_website_domain", table_name="authority_score_reports")
    op.drop_index("ix_authority_score_reports_lead_opportunity_id", table_name="authority_score_reports")
    op.drop_index("ix_authority_score_reports_brand_id", table_name="authority_score_reports")
    op.drop_index("ix_authority_score_reports_organization_id", table_name="authority_score_reports")
    op.drop_index("ix_authority_score_reports_id", table_name="authority_score_reports")
    op.drop_table("authority_score_reports")
