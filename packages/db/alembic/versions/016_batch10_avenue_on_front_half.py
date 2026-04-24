"""Batch 10: avenue_slug on front-half tables.

Revision ID: 016_batch10
Revises: 015_batch9
Create Date: 2026-04-21

Adds nullable avenue_slug VARCHAR(60) + composite index on the six
front-half tables that carry a lead from import → outreach → reply →
draft. Matching the Batch 9 pattern: additive only, idempotent, safe
on populated prod DB.

Tables affected:
  - sponsor_targets                (the lead)
  - sponsor_outreach_sequences     (per-target outreach cadence)
  - lead_opportunities             (inbound-opportunity row)
  - email_threads                  (conversation)
  - email_messages                 (each inbound/outbound message)
  - email_reply_drafts             (machine-drafted replies awaiting GM)
"""

import sqlalchemy as sa
from alembic import op

revision = "016_batch10"
down_revision = "015_batch9"
branch_labels = None
depends_on = None


# (table_name, scope_column_for_index) — some use brand_id, some org_id
FRONT_HALF_TABLES = [
    ("sponsor_targets", "brand_id"),
    ("sponsor_outreach_sequences", "sponsor_target_id"),
    ("lead_opportunities", "brand_id"),
    ("email_threads", "org_id"),
    ("email_messages", "org_id"),
    ("email_reply_drafts", "org_id"),
]


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_name = :t"),
        {"t": name},
    )
    return result.first() is not None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT 1 FROM information_schema.columns WHERE table_name = :t AND column_name = :c"),
        {"t": table, "c": column},
    )
    return result.first() is not None


def _index_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :n"),
        {"n": name},
    )
    return result.first() is not None


def upgrade():
    for tbl, scope_col in FRONT_HALF_TABLES:
        if not _table_exists(tbl):
            continue
        if not _column_exists(tbl, "avenue_slug"):
            op.add_column(tbl, sa.Column("avenue_slug", sa.String(60), nullable=True))
        idx_name = f"ix_{tbl}_scope_avenue"
        if not _index_exists(idx_name):
            op.create_index(idx_name, tbl, [scope_col, "avenue_slug"])

    # Batch 10: rewrite history for /gm/write/replies/drafts/{id}/rewrite.
    if _table_exists("email_reply_drafts") and not _column_exists("email_reply_drafts", "rewrite_history_json"):
        from sqlalchemy.dialects.postgresql import JSONB

        op.add_column(
            "email_reply_drafts",
            sa.Column("rewrite_history_json", JSONB(), nullable=True),
        )


def downgrade():
    for tbl, _scope_col in FRONT_HALF_TABLES:
        idx_name = f"ix_{tbl}_scope_avenue"
        if _index_exists(idx_name):
            op.drop_index(idx_name, table_name=tbl)
        if _table_exists(tbl) and _column_exists(tbl, "avenue_slug"):
            op.drop_column(tbl, "avenue_slug")

    if _table_exists("email_reply_drafts") and _column_exists("email_reply_drafts", "rewrite_history_json"):
        op.drop_column("email_reply_drafts", "rewrite_history_json")
