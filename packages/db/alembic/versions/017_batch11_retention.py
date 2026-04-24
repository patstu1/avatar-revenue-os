"""Batch 11: retention / renewal / reactivation layer.

Revision ID: 017_batch11
Revises: 016_batch10
Create Date: 2026-04-21

Adds:
  - 6 retention columns on ``clients``:
      retention_state, next_renewal_at, last_retention_check_at,
      churn_risk_score, is_recurring, recurring_period_days
  - New ``client_retention_events`` table — the audit trail for every
    retention action GM or the scanner takes on a client.
  - Composite index on (org_id, retention_state) so the scan beat task
    can drain candidates in bounded time.

Additive only; idempotent. Safe on populated prod DB.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "017_batch11"
down_revision = "016_batch10"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    return (
        conn.execute(
            sa.text("SELECT 1 FROM information_schema.tables WHERE table_name = :t"),
            {"t": name},
        ).first()
        is not None
    )


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    return (
        conn.execute(
            sa.text("SELECT 1 FROM information_schema.columns WHERE table_name = :t AND column_name = :c"),
            {"t": table, "c": column},
        ).first()
        is not None
    )


def _index_exists(name: str) -> bool:
    conn = op.get_bind()
    return (
        conn.execute(
            sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :n"),
            {"n": name},
        ).first()
        is not None
    )


def upgrade():
    # 1. 6 new columns on clients
    if _table_exists("clients"):
        if not _column_exists("clients", "retention_state"):
            op.add_column(
                "clients",
                sa.Column(
                    "retention_state",
                    sa.String(30),
                    nullable=False,
                    server_default="active",
                ),
            )
        if not _column_exists("clients", "next_renewal_at"):
            op.add_column(
                "clients",
                sa.Column("next_renewal_at", sa.DateTime(timezone=True), nullable=True),
            )
        if not _column_exists("clients", "last_retention_check_at"):
            op.add_column(
                "clients",
                sa.Column("last_retention_check_at", sa.DateTime(timezone=True), nullable=True),
            )
        if not _column_exists("clients", "churn_risk_score"):
            op.add_column(
                "clients",
                sa.Column(
                    "churn_risk_score",
                    sa.Float(),
                    nullable=False,
                    server_default="0",
                ),
            )
        if not _column_exists("clients", "is_recurring"):
            op.add_column(
                "clients",
                sa.Column(
                    "is_recurring",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                ),
            )
        if not _column_exists("clients", "recurring_period_days"):
            op.add_column(
                "clients",
                sa.Column("recurring_period_days", sa.Integer(), nullable=True),
            )
        if not _index_exists("ix_clients_org_retention_state"):
            op.create_index(
                "ix_clients_org_retention_state",
                "clients",
                ["org_id", "retention_state"],
            )

    # 2. client_retention_events table
    if not _table_exists("client_retention_events"):
        op.create_table(
            "client_retention_events",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("client_id", UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("avenue_slug", sa.String(60), nullable=True),
            # event_type: state_evaluated, renewal_triggered,
            # reactivation_sent, upsell_offered, subscription_cancelled
            sa.Column("event_type", sa.String(60), nullable=False),
            sa.Column("previous_state", sa.String(30), nullable=True),
            sa.Column("new_state", sa.String(30), nullable=True),
            sa.Column("triggered_by_actor_type", sa.String(30), nullable=False, server_default="system"),
            sa.Column("triggered_by_actor_id", sa.String(255), nullable=True),
            sa.Column("source_proposal_id", UUID(as_uuid=True), nullable=True),
            sa.Column("target_proposal_id", UUID(as_uuid=True), nullable=True),
            sa.Column("details_json", JSONB(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
        op.create_index(
            "ix_client_retention_events_client",
            "client_retention_events",
            ["client_id", "created_at"],
        )
        op.create_index(
            "ix_client_retention_events_event_type",
            "client_retention_events",
            ["event_type"],
        )
        op.create_index(
            "ix_client_retention_events_org_avenue",
            "client_retention_events",
            ["org_id", "avenue_slug"],
        )


def downgrade():
    if _table_exists("client_retention_events"):
        op.drop_index(
            "ix_client_retention_events_org_avenue",
            table_name="client_retention_events",
        )
        op.drop_index(
            "ix_client_retention_events_event_type",
            table_name="client_retention_events",
        )
        op.drop_index(
            "ix_client_retention_events_client",
            table_name="client_retention_events",
        )
        op.drop_table("client_retention_events")
    if _table_exists("clients"):
        if _index_exists("ix_clients_org_retention_state"):
            op.drop_index("ix_clients_org_retention_state", table_name="clients")
        for col in (
            "recurring_period_days",
            "is_recurring",
            "churn_risk_score",
            "last_retention_check_at",
            "next_renewal_at",
            "retention_state",
        ):
            if _column_exists("clients", col):
                op.drop_column("clients", col)
