"""Batch 13: sponsor_deals FULL_CIRCLE close — invoices + sponsor campaigns.

Revision ID: 019_batch13
Revises: 018_batch12
Create Date: 2026-04-21

Adds six new tables:

  Payment side (invoicing — net-new infrastructure; sponsor deals bill
  by invoice/milestones, not by Stripe Checkout):
    1. invoices                    — invoice header
    2. invoice_line_items          — billable lines
    3. invoice_milestones          — milestone-billing schedule

  Onboarding / Fulfillment / Follow-up side (sponsor-specific, 1:1
  or N:1 with Client):
    4. sponsor_campaigns           — sponsor campaign state machine
    5. sponsor_placements          — individual ad/mention placements
                                     (with self-referential FK for
                                     make-goods)
    6. sponsor_reports             — periodic performance reports

Schema decisions (per Batch 12/13 discipline): every daily-queryable
timestamp, status, money field, and URL is a first-class column with
an index. Rarely-accessed context goes in JSONB (brief_json,
metrics_json, exclusivity_clauses_json, attendees).

All tables additive and idempotent; safe on populated prod DB.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "019_batch13"
down_revision = "018_batch12"
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
    # ── 1. invoices ─────────────────────────────────────────────────────
    if not _table_exists("invoices"):
        op.create_table(
            "invoices",
            sa.Column("id", UUID(as_uuid=True), primary_key=True,
                      server_default=sa.text("gen_random_uuid()")),
            sa.Column("org_id", UUID(as_uuid=True),
                      sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("brand_id", UUID(as_uuid=True),
                      sa.ForeignKey("brands.id"), nullable=True),
            sa.Column("proposal_id", UUID(as_uuid=True),
                      sa.ForeignKey("proposals.id"), nullable=True),
            sa.Column("client_id", UUID(as_uuid=True),
                      sa.ForeignKey("clients.id"), nullable=True),
            sa.Column("avenue_slug", sa.String(60), nullable=True),
            sa.Column("invoice_number", sa.String(100), nullable=False),
            sa.Column("total_cents", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(10), nullable=False,
                      server_default="usd"),
            # status: draft / sent / paid / overdue / void
            sa.Column("status", sa.String(30), nullable=False,
                      server_default="draft"),
            sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
            # payment_method: wire / ach / check / stripe / other
            sa.Column("payment_method", sa.String(30), nullable=True),
            sa.Column("payment_reference", sa.String(255), nullable=True),
            sa.Column("recipient_email", sa.String(255), nullable=True),
            sa.Column("recipient_name", sa.String(255), nullable=True),
            sa.Column("recipient_company", sa.String(255), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.text("now()")),
            sa.Column("is_active", sa.Boolean(), nullable=False,
                      server_default=sa.true()),
            sa.UniqueConstraint("org_id", "invoice_number",
                                name="uq_invoices_org_number"),
        )
        op.create_index("ix_invoices_org_status", "invoices",
                        ["org_id", "status"])
        op.create_index("ix_invoices_due_date", "invoices", ["due_date"])
        op.create_index("ix_invoices_avenue_slug", "invoices",
                        ["avenue_slug"])
        op.create_index("ix_invoices_client_id", "invoices", ["client_id"])
        op.create_index("ix_invoices_proposal_id", "invoices", ["proposal_id"])

    # ── 2. invoice_line_items ───────────────────────────────────────────
    if not _table_exists("invoice_line_items"):
        op.create_table(
            "invoice_line_items",
            sa.Column("id", UUID(as_uuid=True), primary_key=True,
                      server_default=sa.text("gen_random_uuid()")),
            sa.Column("invoice_id", UUID(as_uuid=True),
                      sa.ForeignKey("invoices.id"), nullable=False),
            sa.Column("description", sa.String(500), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False,
                      server_default="1"),
            sa.Column("unit_amount_cents", sa.Integer(), nullable=False),
            sa.Column("total_amount_cents", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(10), nullable=False,
                      server_default="usd"),
            sa.Column("position", sa.Integer(), nullable=False,
                      server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.text("now()")),
            sa.Column("is_active", sa.Boolean(), nullable=False,
                      server_default=sa.true()),
        )
        op.create_index("ix_invoice_line_items_invoice_id",
                        "invoice_line_items", ["invoice_id"])

    # ── 3. invoice_milestones ───────────────────────────────────────────
    if not _table_exists("invoice_milestones"):
        op.create_table(
            "invoice_milestones",
            sa.Column("id", UUID(as_uuid=True), primary_key=True,
                      server_default=sa.text("gen_random_uuid()")),
            sa.Column("invoice_id", UUID(as_uuid=True),
                      sa.ForeignKey("invoices.id"), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("label", sa.String(255), nullable=False),
            sa.Column("amount_cents", sa.Integer(), nullable=False),
            sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
            # status: pending / paid / void
            sa.Column("status", sa.String(30), nullable=False,
                      server_default="pending"),
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("payment_reference", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.text("now()")),
            sa.Column("is_active", sa.Boolean(), nullable=False,
                      server_default=sa.true()),
        )
        op.create_index("ix_invoice_milestones_invoice_id",
                        "invoice_milestones", ["invoice_id"])
        op.create_index("ix_invoice_milestones_status",
                        "invoice_milestones", ["status"])

    # ── 4. sponsor_campaigns ────────────────────────────────────────────
    if not _table_exists("sponsor_campaigns"):
        op.create_table(
            "sponsor_campaigns",
            sa.Column("id", UUID(as_uuid=True), primary_key=True,
                      server_default=sa.text("gen_random_uuid()")),
            sa.Column("client_id", UUID(as_uuid=True),
                      sa.ForeignKey("clients.id"), nullable=False, unique=True),
            sa.Column("org_id", UUID(as_uuid=True),
                      sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("brand_id", UUID(as_uuid=True),
                      sa.ForeignKey("brands.id"), nullable=True),
            sa.Column("sponsor_opportunity_id", UUID(as_uuid=True),
                      nullable=True),
            sa.Column("avenue_slug", sa.String(60), nullable=False,
                      server_default="sponsor_deals"),
            # status: pre_contract / contract_signed / brief_received /
            #         campaign_live / campaign_complete / cancelled
            sa.Column("status", sa.String(30), nullable=False,
                      server_default="pre_contract"),
            sa.Column("contract_url", sa.String(2048), nullable=True),
            sa.Column("contract_signed_at",
                      sa.DateTime(timezone=True), nullable=True),
            sa.Column("counterparty_name", sa.String(255), nullable=True),
            sa.Column("brief_json", JSONB(), nullable=True),
            sa.Column("brief_received_at",
                      sa.DateTime(timezone=True), nullable=True),
            sa.Column("campaign_start_at",
                      sa.DateTime(timezone=True), nullable=True),
            sa.Column("campaign_end_at",
                      sa.DateTime(timezone=True), nullable=True),
            sa.Column("exclusivity_clauses_json", JSONB(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.text("now()")),
            sa.Column("is_active", sa.Boolean(), nullable=False,
                      server_default=sa.true()),
            sa.UniqueConstraint("client_id", name="uq_sponsor_campaigns_client"),
        )
        op.create_index("ix_sponsor_campaigns_org_status",
                        "sponsor_campaigns", ["org_id", "status"])
        op.create_index("ix_sponsor_campaigns_start_at",
                        "sponsor_campaigns", ["campaign_start_at"])

    # ── 5. sponsor_placements ────────────────────────────────────────────
    if not _table_exists("sponsor_placements"):
        op.create_table(
            "sponsor_placements",
            sa.Column("id", UUID(as_uuid=True), primary_key=True,
                      server_default=sa.text("gen_random_uuid()")),
            sa.Column("campaign_id", UUID(as_uuid=True),
                      sa.ForeignKey("sponsor_campaigns.id"), nullable=False),
            sa.Column("org_id", UUID(as_uuid=True),
                      sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False,
                      server_default="0"),
            # placement_type: ad_spot / host_read / video_integration /
            #                 social_mention / newsletter / other
            sa.Column("placement_type", sa.String(40), nullable=False),
            # status: scheduled / delivered / missed / make_good / cancelled
            sa.Column("status", sa.String(30), nullable=False,
                      server_default="scheduled"),
            sa.Column("scheduled_at",
                      sa.DateTime(timezone=True), nullable=True),
            sa.Column("delivered_at",
                      sa.DateTime(timezone=True), nullable=True),
            sa.Column("make_good_of_placement_id", UUID(as_uuid=True),
                      nullable=True),
            sa.Column("metrics_json", JSONB(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.text("now()")),
            sa.Column("is_active", sa.Boolean(), nullable=False,
                      server_default=sa.true()),
        )
        op.create_index("ix_sponsor_placements_campaign_id",
                        "sponsor_placements", ["campaign_id"])
        op.create_index("ix_sponsor_placements_status",
                        "sponsor_placements", ["status"])
        op.create_index("ix_sponsor_placements_scheduled_at",
                        "sponsor_placements", ["scheduled_at"])
        op.create_index("ix_sponsor_placements_makegood",
                        "sponsor_placements",
                        ["make_good_of_placement_id"])

    # ── 6. sponsor_reports ───────────────────────────────────────────────
    if not _table_exists("sponsor_reports"):
        op.create_table(
            "sponsor_reports",
            sa.Column("id", UUID(as_uuid=True), primary_key=True,
                      server_default=sa.text("gen_random_uuid()")),
            sa.Column("campaign_id", UUID(as_uuid=True),
                      sa.ForeignKey("sponsor_campaigns.id"), nullable=False),
            sa.Column("org_id", UUID(as_uuid=True),
                      sa.ForeignKey("organizations.id"), nullable=False),
            # report_type: weekly / monthly / final / ad_hoc
            sa.Column("report_type", sa.String(30), nullable=False,
                      server_default="monthly"),
            sa.Column("period_start",
                      sa.DateTime(timezone=True), nullable=False),
            sa.Column("period_end",
                      sa.DateTime(timezone=True), nullable=False),
            # status: draft / sent
            sa.Column("status", sa.String(30), nullable=False,
                      server_default="draft"),
            sa.Column("compiled_at",
                      sa.DateTime(timezone=True), nullable=True),
            sa.Column("sent_at",
                      sa.DateTime(timezone=True), nullable=True),
            sa.Column("recipient_email", sa.String(255), nullable=True),
            sa.Column("metrics_json", JSONB(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.text("now()")),
            sa.Column("is_active", sa.Boolean(), nullable=False,
                      server_default=sa.true()),
        )
        op.create_index("ix_sponsor_reports_campaign_id",
                        "sponsor_reports", ["campaign_id"])
        op.create_index("ix_sponsor_reports_period",
                        "sponsor_reports", ["period_start", "period_end"])


def downgrade():
    for tbl in (
        "sponsor_reports", "sponsor_placements", "sponsor_campaigns",
        "invoice_milestones", "invoice_line_items", "invoices",
    ):
        if _table_exists(tbl):
            op.drop_table(tbl)
