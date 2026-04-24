"""Proposals, line items, payment links, payments — conversion backbone.

Revision ID: 010_proposals_payments
Revises: 009_email_pipeline
Create Date: 2026-04-20

Introduced in Batch 3A. Narrow, additive schema — every table is guarded
by a defensive ``IF NOT EXISTS`` (matching the pattern from
009_email_pipeline) so re-running on a partially-migrated DB is safe.

No columns are added to existing tables. No foreign keys from existing
tables into the new ones. Preserves the Batch 2B reply send-loop path
untouched.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "010_proposals_payments"
down_revision = "009_email_pipeline"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :t)"
        ),
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
    # 1. proposals
    if not _table_exists("proposals"):
        op.create_table(
            "proposals",
            *_base_cols(),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=True),
            sa.Column("thread_id", UUID(as_uuid=True), sa.ForeignKey("email_threads.id"), nullable=True),
            sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("email_messages.id"), nullable=True),
            sa.Column("draft_id", UUID(as_uuid=True), sa.ForeignKey("email_reply_drafts.id"), nullable=True),
            sa.Column("operator_action_id", UUID(as_uuid=True), nullable=True),
            sa.Column("recipient_email", sa.String(255), nullable=False),
            sa.Column("recipient_name", sa.String(255), nullable=False, server_default=""),
            sa.Column("recipient_company", sa.String(255), nullable=False, server_default=""),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("summary", sa.Text, nullable=False, server_default=""),
            sa.Column("package_slug", sa.String(100), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("total_amount_cents", sa.Integer, nullable=False, server_default="0"),
            sa.Column("currency", sa.String(10), nullable=False, server_default="usd"),
            sa.Column("created_by_actor_type", sa.String(30), nullable=False, server_default="system"),
            sa.Column("created_by_actor_id", sa.String(255), nullable=True),
            sa.Column("notes", sa.Text, nullable=True),
            sa.Column("extra_json", JSONB, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        )
        for col in (
            "org_id", "brand_id", "thread_id", "message_id", "draft_id",
            "operator_action_id", "recipient_email", "package_slug", "status",
        ):
            op.create_index(f"ix_proposals_{col}", "proposals", [col])

    # 2. proposal_line_items
    if not _table_exists("proposal_line_items"):
        op.create_table(
            "proposal_line_items",
            *_base_cols(),
            sa.Column("proposal_id", UUID(as_uuid=True), sa.ForeignKey("proposals.id"), nullable=False),
            sa.Column("offer_id", UUID(as_uuid=True), sa.ForeignKey("offers.id"), nullable=True),
            sa.Column("package_slug", sa.String(100), nullable=True),
            sa.Column("description", sa.String(500), nullable=False),
            sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
            sa.Column("unit_amount_cents", sa.Integer, nullable=False),
            sa.Column("total_amount_cents", sa.Integer, nullable=False),
            sa.Column("currency", sa.String(10), nullable=False, server_default="usd"),
            sa.Column("position", sa.Integer, nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        )
        for col in ("proposal_id", "offer_id", "position"):
            op.create_index(f"ix_proposal_line_items_{col}", "proposal_line_items", [col])

    # 3. payment_links
    if not _table_exists("payment_links"):
        op.create_table(
            "payment_links",
            *_base_cols(),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=True),
            sa.Column("proposal_id", UUID(as_uuid=True), sa.ForeignKey("proposals.id"), nullable=True),
            sa.Column("provider", sa.String(30), nullable=False, server_default="stripe"),
            sa.Column("provider_link_id", sa.String(255), nullable=True),
            sa.Column("provider_price_id", sa.String(255), nullable=True),
            sa.Column("provider_product_id", sa.String(255), nullable=True),
            sa.Column("url", sa.String(2000), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="active"),
            sa.Column("amount_cents", sa.Integer, nullable=False),
            sa.Column("currency", sa.String(10), nullable=False, server_default="usd"),
            sa.Column("source", sa.String(50), nullable=False, server_default="proposal"),
            sa.Column("metadata_json", JSONB, nullable=True),
            sa.Column("first_clicked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        )
        for col in ("org_id", "brand_id", "proposal_id", "provider", "provider_link_id", "status"):
            op.create_index(f"ix_payment_links_{col}", "payment_links", [col])

    # 4. payments
    if not _table_exists("payments"):
        op.create_table(
            "payments",
            *_base_cols(),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=True),
            sa.Column("proposal_id", UUID(as_uuid=True), sa.ForeignKey("proposals.id"), nullable=True),
            sa.Column("payment_link_id", UUID(as_uuid=True), sa.ForeignKey("payment_links.id"), nullable=True),
            sa.Column("offer_id", UUID(as_uuid=True), sa.ForeignKey("offers.id"), nullable=True),
            sa.Column("provider", sa.String(30), nullable=False, server_default="stripe"),
            sa.Column("provider_event_id", sa.String(255), nullable=True),
            sa.Column("provider_payment_intent_id", sa.String(255), nullable=True),
            sa.Column("provider_checkout_session_id", sa.String(255), nullable=True),
            sa.Column("provider_charge_id", sa.String(255), nullable=True),
            sa.Column("amount_cents", sa.Integer, nullable=False),
            sa.Column("currency", sa.String(10), nullable=False, server_default="usd"),
            sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("customer_email", sa.String(255), nullable=False, server_default=""),
            sa.Column("customer_name", sa.String(255), nullable=False, server_default=""),
            sa.Column("raw_event_json", JSONB, nullable=True),
            sa.Column("metadata_json", JSONB, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
            sa.UniqueConstraint(
                "provider", "provider_event_id", name="uq_payments_provider_event"
            ),
        )
        for col in (
            "org_id", "brand_id", "proposal_id", "payment_link_id", "offer_id",
            "provider", "provider_event_id", "provider_payment_intent_id",
            "provider_checkout_session_id", "customer_email", "status",
        ):
            op.create_index(f"ix_payments_{col}", "payments", [col])


def downgrade() -> None:
    for name in ("payments", "payment_links", "proposal_line_items", "proposals"):
        if _table_exists(name):
            op.drop_table(name)
