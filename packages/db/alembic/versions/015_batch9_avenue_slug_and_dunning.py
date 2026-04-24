"""Batch 9: avenue_slug columns + proposal dunning fields.

Revision ID: 015_batch9
Revises: 014_gm_control
Create Date: 2026-04-21

Adds:
  - avenue_slug VARCHAR(60) NULL to: proposals, payments, clients,
    intake_requests, client_projects, production_jobs, deliveries.
  - Index on (org_id, avenue_slug) for each of the above.
  - Proposals gains dunning fields: dunning_reminders_sent (INT DEFAULT 0),
    dunning_last_sent_at TIMESTAMPTZ, dunning_status VARCHAR(30) DEFAULT 'none'.
  - Deliveries gains followup_sent_at TIMESTAMPTZ (already has
    followup_scheduled_at — sent_at is new).
  - ProductionJob gains worker_id VARCHAR(80), picked_up_at TIMESTAMPTZ,
    output_url VARCHAR(2000) (nullable; existing content kept).

All additions are additive and nullable — safe to run on populated DB.
"""
import sqlalchemy as sa
from alembic import op

revision = "015_batch9"
down_revision = "014_gm_control"
branch_labels = None
depends_on = None


AVENUE_TABLES = [
    "proposals", "payments", "clients", "intake_requests",
    "client_projects", "production_jobs", "deliveries",
]


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.first() is not None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = :t"
        ),
        {"t": name},
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
    # 1. avenue_slug on 7 tables + index on (org_id, avenue_slug)
    for tbl in AVENUE_TABLES:
        if not _table_exists(tbl):
            continue
        if not _column_exists(tbl, "avenue_slug"):
            op.add_column(tbl, sa.Column("avenue_slug", sa.String(60), nullable=True))
        idx_name = f"ix_{tbl}_org_avenue"
        if not _index_exists(idx_name):
            # Only some tables have org_id; the rest use organization_id.
            # Detect which column name the table uses.
            conn = op.get_bind()
            r = conn.execute(
                sa.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = :t "
                    "AND column_name IN ('org_id','organization_id') "
                    "ORDER BY column_name LIMIT 1"
                ),
                {"t": tbl},
            )
            row = r.first()
            if row is not None:
                org_col = row[0]
                op.create_index(idx_name, tbl, [org_col, "avenue_slug"])

    # 2. proposals dunning fields
    if _table_exists("proposals"):
        if not _column_exists("proposals", "dunning_reminders_sent"):
            op.add_column(
                "proposals",
                sa.Column(
                    "dunning_reminders_sent",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                ),
            )
        if not _column_exists("proposals", "dunning_last_sent_at"):
            op.add_column(
                "proposals",
                sa.Column("dunning_last_sent_at", sa.DateTime(timezone=True), nullable=True),
            )
        if not _column_exists("proposals", "dunning_status"):
            op.add_column(
                "proposals",
                sa.Column(
                    "dunning_status",
                    sa.String(30),
                    nullable=False,
                    server_default="none",
                ),
            )
        if not _index_exists("ix_proposals_dunning_status"):
            op.create_index(
                "ix_proposals_dunning_status", "proposals", ["dunning_status"]
            )

    # 3. deliveries.followup_sent_at
    if _table_exists("deliveries") and not _column_exists(
        "deliveries", "followup_sent_at"
    ):
        op.add_column(
            "deliveries",
            sa.Column("followup_sent_at", sa.DateTime(timezone=True), nullable=True),
        )
    if (
        _table_exists("deliveries")
        and not _index_exists("ix_deliveries_followup_due")
    ):
        op.create_index(
            "ix_deliveries_followup_due",
            "deliveries",
            ["followup_sent_at", "followup_scheduled_at"],
        )

    # 4. production_jobs worker fields
    if _table_exists("production_jobs"):
        if not _column_exists("production_jobs", "worker_id"):
            op.add_column(
                "production_jobs",
                sa.Column("worker_id", sa.String(80), nullable=True),
            )
        if not _column_exists("production_jobs", "picked_up_at"):
            op.add_column(
                "production_jobs",
                sa.Column("picked_up_at", sa.DateTime(timezone=True), nullable=True),
            )
        if not _column_exists("production_jobs", "output_url"):
            op.add_column(
                "production_jobs",
                sa.Column("output_url", sa.String(2000), nullable=True),
            )
        if not _index_exists("ix_production_jobs_status_picked_up"):
            op.create_index(
                "ix_production_jobs_status_picked_up",
                "production_jobs",
                ["status", "picked_up_at"],
            )


def downgrade():
    # Best-effort reverse — we drop only the specific columns/indexes we added.
    for tbl in AVENUE_TABLES:
        idx_name = f"ix_{tbl}_org_avenue"
        if _index_exists(idx_name):
            op.drop_index(idx_name, table_name=tbl)
        if _table_exists(tbl) and _column_exists(tbl, "avenue_slug"):
            op.drop_column(tbl, "avenue_slug")

    if _table_exists("proposals"):
        if _index_exists("ix_proposals_dunning_status"):
            op.drop_index("ix_proposals_dunning_status", table_name="proposals")
        for col in ("dunning_status", "dunning_last_sent_at", "dunning_reminders_sent"):
            if _column_exists("proposals", col):
                op.drop_column("proposals", col)

    if _table_exists("deliveries"):
        if _index_exists("ix_deliveries_followup_due"):
            op.drop_index("ix_deliveries_followup_due", table_name="deliveries")
        if _column_exists("deliveries", "followup_sent_at"):
            op.drop_column("deliveries", "followup_sent_at")

    if _table_exists("production_jobs"):
        if _index_exists("ix_production_jobs_status_picked_up"):
            op.drop_index(
                "ix_production_jobs_status_picked_up", table_name="production_jobs"
            )
        for col in ("output_url", "picked_up_at", "worker_id"):
            if _column_exists("production_jobs", col):
                op.drop_column("production_jobs", col)
