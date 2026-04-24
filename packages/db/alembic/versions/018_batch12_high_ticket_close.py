"""Batch 12: high_ticket onboarding + issue handling close.

Revision ID: 018_batch12
Revises: 017_batch11
Create Date: 2026-04-21

Additive, idempotent. Two changes:

  1. New table ``client_high_ticket_profiles`` — 1:1 with ``clients``
     for Clients whose avenue_slug is ``high_ticket``. Operational-
     daily fields (discovery_call_at, sow_url, sow_sent_at,
     sow_countersigned_at, counterparty_name, kickoff_at, status) are
     first-class columns so the operator can filter / order by them
     without JSONB extraction. Rarely-accessed contextual fields
     (attendees, team members) stay in JSONB.

  2. ``client_retention_events.amount_cents`` nullable INTEGER — added
     so high-ticket credit issuance can be rolled up by SUM() without
     details_json extraction. Applies to any retention event that
     carries a dollar value; NULL for non-financial events
     (state_evaluated, reactivation_sent).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "018_batch12"
down_revision = "017_batch11"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = :t"
        ),
        {"t": name},
    ).first() is not None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).first() is not None


def _index_exists(name: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :n"),
        {"n": name},
    ).first() is not None


def upgrade():
    # 1. client_high_ticket_profiles
    if not _table_exists("client_high_ticket_profiles"):
        op.create_table(
            "client_high_ticket_profiles",
            sa.Column("id", UUID(as_uuid=True), primary_key=True,
                      server_default=sa.text("gen_random_uuid()")),
            sa.Column("client_id", UUID(as_uuid=True),
                      sa.ForeignKey("clients.id"), nullable=False, unique=True),
            sa.Column("org_id", UUID(as_uuid=True),
                      sa.ForeignKey("organizations.id"), nullable=False),
            # status values: discovery_pending / sow_drafted / sow_sent /
            #                sow_signed / kickoff_scheduled / kickoff_complete
            sa.Column("status", sa.String(30), nullable=False,
                      server_default="discovery_pending"),
            # Operational-daily timestamps (all nullable, all indexed where
            # a daily "due now" query would read them)
            sa.Column("discovery_call_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("discovery_attendees_json", JSONB(), nullable=True),
            sa.Column("sow_url", sa.String(2048), nullable=True),
            sa.Column("sow_sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sow_signer_email", sa.String(255), nullable=True),
            sa.Column("sow_countersigned_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("counterparty_name", sa.String(255), nullable=True),
            sa.Column("kickoff_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("kickoff_team_json", JSONB(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.text("now()")),
            sa.Column("is_active", sa.Boolean(), nullable=False,
                      server_default=sa.true()),
        )
        # Daily-query indexes
        op.create_index(
            "ix_htp_org_status", "client_high_ticket_profiles",
            ["org_id", "status"],
        )
        op.create_index(
            "ix_htp_kickoff_at", "client_high_ticket_profiles",
            ["kickoff_at"],
        )
        op.create_index(
            "ix_htp_discovery_call_at", "client_high_ticket_profiles",
            ["discovery_call_at"],
        )
        op.create_index(
            "ix_htp_sow_sent_at", "client_high_ticket_profiles",
            ["sow_sent_at"],
        )

    # 2. amount_cents on client_retention_events
    if _table_exists("client_retention_events") and not _column_exists(
        "client_retention_events", "amount_cents"
    ):
        op.add_column(
            "client_retention_events",
            sa.Column("amount_cents", sa.Integer(), nullable=True),
        )


def downgrade():
    if _table_exists("client_retention_events") and _column_exists(
        "client_retention_events", "amount_cents"
    ):
        op.drop_column("client_retention_events", "amount_cents")
    if _table_exists("client_high_ticket_profiles"):
        for ix in (
            "ix_htp_sow_sent_at", "ix_htp_discovery_call_at",
            "ix_htp_kickoff_at", "ix_htp_org_status",
        ):
            if _index_exists(ix):
                op.drop_index(ix, table_name="client_high_ticket_profiles")
        op.drop_table("client_high_ticket_profiles")
