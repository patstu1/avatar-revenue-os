"""Email Pipeline tables — inboxes, threads, messages, classifications, drafts, transitions.

Revision ID: 009_email_pipeline
Revises: 008_autonomy_grants
Create Date: 2026-04-20

Defensive: each table is created only if absent (matching the existing
pattern from 008_autonomy_grants) so re-runs on partially-migrated DBs
do not fail. The pre-existing multi-head situation in the alembic chain
(005_media_jobs_v2 still a side tip) is deliberately NOT touched here.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "009_email_pipeline"
down_revision = "008_autonomy_grants"
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
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def upgrade() -> None:
    # 1. inbox_connections
    if not _table_exists("inbox_connections"):
        op.create_table(
            "inbox_connections",
            *_base_cols(),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("email_address", sa.String(255), nullable=False),
            sa.Column("display_name", sa.String(255), nullable=False, server_default=""),
            sa.Column("provider", sa.String(50), nullable=False, server_default="imap"),
            sa.Column("host", sa.String(255), nullable=False, server_default=""),
            sa.Column("port", sa.Integer, nullable=False, server_default="993"),
            sa.Column("auth_method", sa.String(30), nullable=False, server_default="password"),
            sa.Column("credential_provider_key", sa.String(100), nullable=False, server_default="imap"),
            sa.Column("oauth_access_token_encrypted", sa.Text, nullable=True),
            sa.Column("oauth_refresh_token_encrypted", sa.Text, nullable=True),
            sa.Column("oauth_token_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="active"),
            sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_sync_uid", sa.String(100), nullable=True),
            sa.Column("last_error", sa.Text, nullable=True),
            sa.Column("consecutive_failures", sa.Integer, nullable=False, server_default="0"),
            sa.Column("messages_synced_total", sa.Integer, nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
            sa.UniqueConstraint("org_id", "email_address", name="uq_inbox_org_email"),
        )
        op.create_index("ix_inbox_connections_org_id", "inbox_connections", ["org_id"])
        op.create_index("ix_inbox_connections_email_address", "inbox_connections", ["email_address"])
        op.create_index("ix_inbox_connections_provider", "inbox_connections", ["provider"])
        op.create_index("ix_inbox_connections_status", "inbox_connections", ["status"])

    # 2. email_threads
    if not _table_exists("email_threads"):
        op.create_table(
            "email_threads",
            *_base_cols(),
            sa.Column("inbox_connection_id", UUID(as_uuid=True), sa.ForeignKey("inbox_connections.id"), nullable=False),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("provider_thread_id", sa.String(500), nullable=False),
            sa.Column("subject", sa.String(1000), nullable=False, server_default=""),
            sa.Column("contact_id", UUID(as_uuid=True), sa.ForeignKey("crm_contacts.id"), nullable=True),
            sa.Column("lead_opportunity_id", UUID(as_uuid=True), sa.ForeignKey("lead_opportunities.id"), nullable=True),
            sa.Column("direction", sa.String(20), nullable=False, server_default="inbound"),
            sa.Column("sales_stage", sa.String(30), nullable=False, server_default="new_lead"),
            sa.Column("latest_classification", sa.String(50), nullable=True),
            sa.Column("reply_status", sa.String(30), nullable=False, server_default="pending"),
            sa.Column("message_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("from_email", sa.String(255), nullable=False, server_default=""),
            sa.Column("from_name", sa.String(255), nullable=False, server_default=""),
            sa.Column("to_emails", JSONB, nullable=True, server_default=sa.text("'[]'::jsonb")),
            sa.Column("first_message_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_inbound_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
            sa.UniqueConstraint("inbox_connection_id", "provider_thread_id", name="uq_thread_inbox_provider"),
        )
        for col in (
            "inbox_connection_id",
            "org_id",
            "provider_thread_id",
            "contact_id",
            "lead_opportunity_id",
            "direction",
            "sales_stage",
            "latest_classification",
            "reply_status",
            "from_email",
        ):
            op.create_index(f"ix_email_threads_{col}", "email_threads", [col])

    # 3. email_messages
    if not _table_exists("email_messages"):
        op.create_table(
            "email_messages",
            *_base_cols(),
            sa.Column("thread_id", UUID(as_uuid=True), sa.ForeignKey("email_threads.id"), nullable=False),
            sa.Column("inbox_connection_id", UUID(as_uuid=True), sa.ForeignKey("inbox_connections.id"), nullable=False),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("provider_message_id", sa.String(500), nullable=False),
            sa.Column("in_reply_to", sa.String(500), nullable=True),
            sa.Column("references", sa.Text, nullable=True),
            sa.Column("direction", sa.String(20), nullable=False),
            sa.Column("from_email", sa.String(255), nullable=False),
            sa.Column("from_name", sa.String(255), nullable=False, server_default=""),
            sa.Column("to_emails", JSONB, nullable=True, server_default=sa.text("'[]'::jsonb")),
            sa.Column("cc_emails", JSONB, nullable=True, server_default=sa.text("'[]'::jsonb")),
            sa.Column("subject", sa.String(1000), nullable=False, server_default=""),
            sa.Column("body_text", sa.Text, nullable=True),
            sa.Column("body_html", sa.Text, nullable=True),
            sa.Column("snippet", sa.String(500), nullable=False, server_default=""),
            sa.Column("message_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("has_attachments", sa.Boolean, nullable=False, server_default=sa.text("false")),
            sa.Column("raw_headers_json", JSONB, nullable=True),
            sa.Column("size_bytes", sa.Integer, nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
            sa.UniqueConstraint("provider_message_id", name="uq_email_message_provider_id"),
        )
        for col in ("thread_id", "inbox_connection_id", "org_id", "provider_message_id", "direction", "from_email"):
            op.create_index(f"ix_email_messages_{col}", "email_messages", [col])

    # 4. email_classifications
    if not _table_exists("email_classifications"):
        op.create_table(
            "email_classifications",
            *_base_cols(),
            sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("email_messages.id"), nullable=False),
            sa.Column("thread_id", UUID(as_uuid=True), sa.ForeignKey("email_threads.id"), nullable=False),
            sa.Column("intent", sa.String(50), nullable=False),
            sa.Column("confidence", sa.Float, nullable=False),
            sa.Column("rationale", sa.Text, nullable=False, server_default=""),
            sa.Column("secondary_intent", sa.String(50), nullable=True),
            sa.Column("secondary_confidence", sa.Float, nullable=True),
            sa.Column("classifier_version", sa.String(50), nullable=False, server_default="keyword_v1"),
            sa.Column("model_used", sa.String(100), nullable=True),
            sa.Column("reply_mode", sa.String(30), nullable=True),
            sa.Column("action_id", UUID(as_uuid=True), nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        )
        for col in ("message_id", "thread_id", "intent"):
            op.create_index(f"ix_email_classifications_{col}", "email_classifications", [col])

    # 5. email_reply_drafts
    if not _table_exists("email_reply_drafts"):
        op.create_table(
            "email_reply_drafts",
            *_base_cols(),
            sa.Column("thread_id", UUID(as_uuid=True), sa.ForeignKey("email_threads.id"), nullable=False),
            sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("email_messages.id"), nullable=False),
            sa.Column(
                "classification_id", UUID(as_uuid=True), sa.ForeignKey("email_classifications.id"), nullable=True
            ),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("to_email", sa.String(255), nullable=False),
            sa.Column("subject", sa.String(1000), nullable=False, server_default=""),
            sa.Column("body_text", sa.Text, nullable=False, server_default=""),
            sa.Column("body_html", sa.Text, nullable=True),
            sa.Column("reply_mode", sa.String(30), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
            sa.Column("approved_by", sa.String(255), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("prompt_used", sa.Text, nullable=True),
            sa.Column("model_used", sa.String(100), nullable=True),
            sa.Column("confidence", sa.Float, nullable=False, server_default="0.0"),
            sa.Column("reasoning", sa.Text, nullable=True),
            sa.Column("thread_context_json", JSONB, nullable=True),
            sa.Column("package_offered", sa.String(100), nullable=True),
            sa.Column("proof_links_json", JSONB, nullable=True),
            sa.Column("decision_trace", JSONB, nullable=True),
            sa.Column("error_message", sa.Text, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        )
        for col in ("thread_id", "message_id", "org_id", "reply_mode", "status"):
            op.create_index(f"ix_email_reply_drafts_{col}", "email_reply_drafts", [col])

    # 6. sales_stage_transitions
    if not _table_exists("sales_stage_transitions"):
        op.create_table(
            "sales_stage_transitions",
            *_base_cols(),
            sa.Column("thread_id", UUID(as_uuid=True), sa.ForeignKey("email_threads.id"), nullable=True),
            sa.Column("lead_opportunity_id", UUID(as_uuid=True), sa.ForeignKey("lead_opportunities.id"), nullable=True),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("from_stage", sa.String(30), nullable=False),
            sa.Column("to_stage", sa.String(30), nullable=False),
            sa.Column("trigger_type", sa.String(50), nullable=False),
            sa.Column("trigger_id", sa.String(255), nullable=True),
            sa.Column("rationale", sa.Text, nullable=False, server_default=""),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        )
        for col in ("thread_id", "lead_opportunity_id", "org_id", "trigger_type"):
            op.create_index(f"ix_sales_stage_transitions_{col}", "sales_stage_transitions", [col])


def downgrade() -> None:
    # Drop in reverse dependency order.
    for tbl in (
        "sales_stage_transitions",
        "email_reply_drafts",
        "email_classifications",
        "email_messages",
        "email_threads",
        "inbox_connections",
    ):
        if _table_exists(tbl):
            op.drop_table(tbl)
