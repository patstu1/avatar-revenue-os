"""ai_search_authority_reports — public AI Buyer Trust Test diagnostic reports.

Revision ID: c1_ai_search_authority_reports
Revises: 019_batch13
Create Date: 2026-04-29

Additive schema. Idempotent: every create is guarded by IF NOT EXISTS so
re-running the migration on a partially migrated DB is safe.

Chains off ``019_batch13`` (the actual production head as of 2026-04-29).
The orphan auto-generated ``b6587e9c03b5_create_all_missing_tables_and_columns``
migration declared down_revision=003_provider_secrets and was never applied
to production; this migration deliberately skips it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "c1_ai_search_authority_reports"
down_revision = "019_batch13"
branch_labels = None
depends_on = None


TABLE_NAME = "ai_search_authority_reports"


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    return bool(
        conn.execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :t)"
            ),
            {"t": name},
        ).scalar()
    )


def _index_exists(name: str) -> bool:
    conn = op.get_bind()
    return bool(
        conn.execute(
            sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :n"), {"n": name}
        ).fetchone()
    )


def _create_index_if_missing(name: str, table: str, columns: list[str]) -> None:
    if not _index_exists(name):
        op.create_index(name, table, columns)


def upgrade() -> None:
    if not _table_exists(TABLE_NAME):
        op.create_table(
            TABLE_NAME,
            sa.Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "organization_id",
                UUID(as_uuid=True),
                sa.ForeignKey("organizations.id"),
                nullable=True,
            ),
            sa.Column(
                "brand_id",
                UUID(as_uuid=True),
                sa.ForeignKey("brands.id"),
                nullable=True,
            ),
            sa.Column("submitter_email", sa.String(255), nullable=False),
            sa.Column("submitter_name", sa.String(255), nullable=False, server_default=""),
            sa.Column("submitter_company", sa.String(255), nullable=False, server_default=""),
            sa.Column("submitter_url", sa.String(1024), nullable=False, server_default=""),
            sa.Column("submitter_role", sa.String(100), nullable=False, server_default=""),
            sa.Column("submitter_revenue_band", sa.String(60), nullable=False, server_default=""),
            sa.Column("vertical", sa.String(60), nullable=False, server_default=""),
            sa.Column("buyer_type", sa.String(60), nullable=False, server_default=""),
            sa.Column("industry_context", sa.String(255), nullable=False, server_default=""),
            sa.Column("answers_json", JSONB, nullable=True),
            sa.Column("score", sa.Float, nullable=False, server_default="0"),
            sa.Column("tier", sa.String(20), nullable=False, server_default="cold"),
            sa.Column("gaps_json", JSONB, nullable=True),
            sa.Column("quick_win", sa.Text, nullable=False, server_default=""),
            sa.Column(
                "recommended_package_slug", sa.String(100), nullable=False, server_default=""
            ),
            sa.Column("status", sa.String(40), nullable=False, server_default="submitted"),
            sa.Column("snapshot_requested_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("proposal_created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "lead_opportunity_id",
                UUID(as_uuid=True),
                sa.ForeignKey("lead_opportunities.id"),
                nullable=True,
            ),
            sa.Column(
                "proposal_id",
                UUID(as_uuid=True),
                sa.ForeignKey("proposals.id"),
                nullable=True,
            ),
            sa.Column("source", sa.String(60), nullable=False, server_default="public"),
            sa.Column("submission_ip", sa.String(64), nullable=True),
            sa.Column("user_agent", sa.String(500), nullable=True),
            sa.Column("notes", sa.Text, nullable=True),
        )

    _create_index_if_missing("ix_aisa_reports_organization_id", TABLE_NAME, ["organization_id"])
    _create_index_if_missing("ix_aisa_reports_brand_id", TABLE_NAME, ["brand_id"])
    _create_index_if_missing("ix_aisa_reports_submitter_email", TABLE_NAME, ["submitter_email"])
    _create_index_if_missing("ix_aisa_reports_vertical", TABLE_NAME, ["vertical"])
    _create_index_if_missing("ix_aisa_reports_score", TABLE_NAME, ["score"])
    _create_index_if_missing("ix_aisa_reports_tier", TABLE_NAME, ["tier"])
    _create_index_if_missing(
        "ix_aisa_reports_recommended_package_slug",
        TABLE_NAME,
        ["recommended_package_slug"],
    )
    _create_index_if_missing("ix_aisa_reports_status", TABLE_NAME, ["status"])
    _create_index_if_missing("ix_aisa_reports_lead_opportunity_id", TABLE_NAME, ["lead_opportunity_id"])
    _create_index_if_missing("ix_aisa_reports_proposal_id", TABLE_NAME, ["proposal_id"])
    _create_index_if_missing("ix_aisa_reports_status_created", TABLE_NAME, ["status", "created_at"])
    _create_index_if_missing(
        "ix_aisa_reports_email_created", TABLE_NAME, ["submitter_email", "created_at"]
    )


def downgrade() -> None:
    op.drop_table(TABLE_NAME)
