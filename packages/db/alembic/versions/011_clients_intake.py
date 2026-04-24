"""Clients, onboarding events, intake requests, intake submissions.

Revision ID: 011_clients_intake
Revises: 010_proposals_payments
Create Date: 2026-04-20

Batch 3B. Additive schema — no changes to existing tables. Each table
is guarded by ``IF NOT EXISTS`` so re-running on a partially migrated
DB is safe.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "011_clients_intake"
down_revision = "010_proposals_payments"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :t)"),
        {"t": name},
    )
    return bool(result.scalar())


def _base_cols():
    return (
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
    )


def upgrade() -> None:
    # 1. clients
    if not _table_exists("clients"):
        op.create_table(
            "clients",
            *_base_cols(),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=True),
            sa.Column("primary_email", sa.String(255), nullable=False),
            sa.Column("display_name", sa.String(255), nullable=False),
            sa.Column("company_name", sa.String(255), nullable=False, server_default=""),
            sa.Column("first_proposal_id", UUID(as_uuid=True), sa.ForeignKey("proposals.id"), nullable=True),
            sa.Column("first_payment_id", UUID(as_uuid=True), sa.ForeignKey("payments.id"), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="active"),
            sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_paid_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("total_paid_cents", sa.Integer, nullable=False, server_default="0"),
            sa.Column("metadata_json", JSONB, nullable=True),
            sa.Column("notes", sa.Text, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
            sa.UniqueConstraint("org_id", "primary_email", name="uq_clients_org_email"),
        )
        for col in ("org_id", "brand_id", "primary_email", "first_proposal_id", "first_payment_id", "status"):
            op.create_index(f"ix_clients_{col}", "clients", [col])

    # 2. intake_requests  (must come before client_onboarding_events because FK)
    if not _table_exists("intake_requests"):
        op.create_table(
            "intake_requests",
            *_base_cols(),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("client_id", UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("proposal_id", UUID(as_uuid=True), sa.ForeignKey("proposals.id"), nullable=True),
            sa.Column("payment_id", UUID(as_uuid=True), sa.ForeignKey("payments.id"), nullable=True),
            sa.Column("token", sa.String(100), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("instructions", sa.Text, nullable=False, server_default=""),
            sa.Column("schema_json", JSONB, nullable=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("first_viewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reminder_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("last_reminder_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
            sa.UniqueConstraint("token", name="uq_intake_requests_token"),
        )
        for col in ("org_id", "client_id", "proposal_id", "payment_id", "token", "status"):
            op.create_index(f"ix_intake_requests_{col}", "intake_requests", [col])

    # 3. intake_submissions
    if not _table_exists("intake_submissions"):
        op.create_table(
            "intake_submissions",
            *_base_cols(),
            sa.Column("intake_request_id", UUID(as_uuid=True), sa.ForeignKey("intake_requests.id"), nullable=False),
            sa.Column("client_id", UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("responses_json", JSONB, nullable=True),
            sa.Column("is_complete", sa.Boolean, nullable=False, server_default=sa.text("false")),
            sa.Column("missing_fields_json", JSONB, nullable=True),
            sa.Column("submitted_via", sa.String(30), nullable=False, server_default="form"),
            sa.Column("submitter_email", sa.String(255), nullable=False, server_default=""),
            sa.Column("submitter_ip", sa.String(60), nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        )
        for col in ("intake_request_id", "client_id", "org_id", "is_complete"):
            op.create_index(f"ix_intake_submissions_{col}", "intake_submissions", [col])

    # 4. client_onboarding_events
    if not _table_exists("client_onboarding_events"):
        op.create_table(
            "client_onboarding_events",
            *_base_cols(),
            sa.Column("client_id", UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("event_type", sa.String(50), nullable=False),
            sa.Column("proposal_id", UUID(as_uuid=True), sa.ForeignKey("proposals.id"), nullable=True),
            sa.Column("payment_id", UUID(as_uuid=True), sa.ForeignKey("payments.id"), nullable=True),
            sa.Column("intake_request_id", UUID(as_uuid=True), sa.ForeignKey("intake_requests.id"), nullable=True),
            sa.Column(
                "intake_submission_id", UUID(as_uuid=True), sa.ForeignKey("intake_submissions.id"), nullable=True
            ),
            sa.Column("details_json", JSONB, nullable=True),
            sa.Column("actor_type", sa.String(30), nullable=False, server_default="system"),
            sa.Column("actor_id", sa.String(255), nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        )
        for col in (
            "client_id",
            "org_id",
            "event_type",
            "proposal_id",
            "payment_id",
            "intake_request_id",
            "intake_submission_id",
        ):
            op.create_index(f"ix_client_onb_events_{col}", "client_onboarding_events", [col])


def downgrade() -> None:
    for name in (
        "client_onboarding_events",
        "intake_submissions",
        "intake_requests",
        "clients",
    ):
        if _table_exists(name):
            op.drop_table(name)
