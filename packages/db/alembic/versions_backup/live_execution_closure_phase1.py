"""Live Execution Closure Phase 1 — analytics, experiment truth, CRM/ESP/SMS

Revision ID: lec_phase1_001
Revises: buffer_dist_001
Create Date: 2025-01-01 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "lec_phase1_001"
down_revision = "buffer_dist_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Analytics ────────────────────────────────────────────
    op.create_table(
        "analytics_imports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("source", sa.String(80), nullable=False, index=True),
        sa.Column("source_category", sa.String(40), server_default="social", index=True),
        sa.Column("events_imported", sa.Integer, server_default="0"),
        sa.Column("events_matched", sa.Integer, server_default="0"),
        sa.Column("events_new", sa.Integer, server_default="0"),
        sa.Column("import_mode", sa.String(30), server_default="full", index=True),
        sa.Column("raw_payload_json", JSONB, server_default="{}"),
        sa.Column("status", sa.String(30), server_default="completed", index=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "analytics_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("import_id", UUID(as_uuid=True), sa.ForeignKey("analytics_imports.id"), nullable=True, index=True),
        sa.Column("content_item_id", UUID(as_uuid=True), sa.ForeignKey("content_items.id"), nullable=True, index=True),
        sa.Column(
            "creator_account_id", UUID(as_uuid=True), sa.ForeignKey("creator_accounts.id"), nullable=True, index=True
        ),
        sa.Column("source", sa.String(80), nullable=False, index=True),
        sa.Column("event_type", sa.String(60), nullable=False, index=True),
        sa.Column("platform", sa.String(50), nullable=True, index=True),
        sa.Column("external_post_id", sa.String(255), nullable=True, index=True),
        sa.Column("metric_value", sa.Float, server_default="0"),
        sa.Column("truth_level", sa.String(30), server_default="live_import", index=True),
        sa.Column("raw_json", JSONB, server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── Conversions ─────────────────────────────────────────
    op.create_table(
        "conversion_imports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("source", sa.String(80), nullable=False, index=True),
        sa.Column("source_category", sa.String(40), server_default="checkout", index=True),
        sa.Column("conversions_imported", sa.Integer, server_default="0"),
        sa.Column("revenue_imported", sa.Float, server_default="0"),
        sa.Column("status", sa.String(30), server_default="completed", index=True),
        sa.Column("raw_payload_json", JSONB, server_default="{}"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "conversion_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("import_id", UUID(as_uuid=True), sa.ForeignKey("conversion_imports.id"), nullable=True, index=True),
        sa.Column("content_item_id", UUID(as_uuid=True), sa.ForeignKey("content_items.id"), nullable=True, index=True),
        sa.Column("offer_id", UUID(as_uuid=True), sa.ForeignKey("offers.id"), nullable=True, index=True),
        sa.Column("source", sa.String(80), nullable=False, index=True),
        sa.Column("conversion_type", sa.String(60), nullable=False, index=True),
        sa.Column("revenue", sa.Float, server_default="0"),
        sa.Column("cost", sa.Float, server_default="0"),
        sa.Column("profit", sa.Float, server_default="0"),
        sa.Column("currency", sa.String(10), server_default="USD"),
        sa.Column("external_order_id", sa.String(255), nullable=True, index=True),
        sa.Column("truth_level", sa.String(30), server_default="live_import", index=True),
        sa.Column("raw_json", JSONB, server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── Experiment Truth ────────────────────────────────────
    op.create_table(
        "experiment_observation_imports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("source", sa.String(80), nullable=False, index=True),
        sa.Column("observations_imported", sa.Integer, server_default="0"),
        sa.Column("observations_matched", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(30), server_default="completed", index=True),
        sa.Column("raw_payload_json", JSONB, server_default="{}"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "experiment_live_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column(
            "import_id",
            UUID(as_uuid=True),
            sa.ForeignKey("experiment_observation_imports.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("experiment_id", UUID(as_uuid=True), sa.ForeignKey("experiments.id"), nullable=True, index=True),
        sa.Column("variant_id", UUID(as_uuid=True), sa.ForeignKey("experiment_variants.id"), nullable=True, index=True),
        sa.Column("source", sa.String(80), nullable=False, index=True),
        sa.Column("observation_type", sa.String(60), nullable=False, index=True),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("metric_value", sa.Float, server_default="0"),
        sa.Column("sample_size", sa.Integer, server_default="0"),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("truth_level", sa.String(30), server_default="live_import", index=True),
        sa.Column("previous_truth_level", sa.String(30), nullable=True),
        sa.Column("raw_json", JSONB, server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── CRM ─────────────────────────────────────────────────
    op.create_table(
        "crm_contacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("external_id", sa.String(255), nullable=True, index=True),
        sa.Column("email", sa.String(255), nullable=True, index=True),
        sa.Column("phone", sa.String(50), nullable=True, index=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("tags_json", JSONB, server_default="[]"),
        sa.Column("segment", sa.String(100), nullable=True, index=True),
        sa.Column("lifecycle_stage", sa.String(60), server_default="subscriber", index=True),
        sa.Column("source", sa.String(80), server_default="manual", index=True),
        sa.Column("sync_status", sa.String(30), server_default="pending", index=True),
        sa.Column("last_synced_at", sa.String(50), nullable=True),
        sa.Column("metadata_json", JSONB, server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "crm_syncs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("provider", sa.String(80), nullable=False, index=True),
        sa.Column("direction", sa.String(20), server_default="push", index=True),
        sa.Column("contacts_synced", sa.Integer, server_default="0"),
        sa.Column("contacts_created", sa.Integer, server_default="0"),
        sa.Column("contacts_updated", sa.Integer, server_default="0"),
        sa.Column("contacts_failed", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(30), server_default="completed", index=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── Email ───────────────────────────────────────────────
    op.create_table(
        "email_send_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("contact_id", UUID(as_uuid=True), sa.ForeignKey("crm_contacts.id"), nullable=True, index=True),
        sa.Column("to_email", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body_html", sa.Text, nullable=True),
        sa.Column("body_text", sa.Text, nullable=True),
        sa.Column("template_id", sa.String(100), nullable=True),
        sa.Column("sequence_step", sa.String(100), nullable=True),
        sa.Column("provider", sa.String(80), server_default="smtp", index=True),
        sa.Column("status", sa.String(30), server_default="queued", index=True),
        sa.Column("sent_at", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("metadata_json", JSONB, server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── SMS ─────────────────────────────────────────────────
    op.create_table(
        "sms_send_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("contact_id", UUID(as_uuid=True), sa.ForeignKey("crm_contacts.id"), nullable=True, index=True),
        sa.Column("to_phone", sa.String(50), nullable=False),
        sa.Column("message_body", sa.Text, nullable=False),
        sa.Column("sequence_step", sa.String(100), nullable=True),
        sa.Column("provider", sa.String(80), server_default="twilio", index=True),
        sa.Column("status", sa.String(30), server_default="queued", index=True),
        sa.Column("sent_at", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("external_message_id", sa.String(255), nullable=True),
        sa.Column("metadata_json", JSONB, server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── Messaging Blockers ──────────────────────────────────
    op.create_table(
        "messaging_blockers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("blocker_type", sa.String(80), nullable=False, index=True),
        sa.Column("channel", sa.String(30), nullable=False, index=True),
        sa.Column("severity", sa.String(30), server_default="high", index=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("operator_action_needed", sa.Text, nullable=False),
        sa.Column("resolved", sa.Boolean, server_default="false"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("messaging_blockers")
    op.drop_table("sms_send_requests")
    op.drop_table("email_send_requests")
    op.drop_table("crm_syncs")
    op.drop_table("crm_contacts")
    op.drop_table("experiment_live_results")
    op.drop_table("experiment_observation_imports")
    op.drop_table("conversion_events")
    op.drop_table("conversion_imports")
    op.drop_table("analytics_events")
    op.drop_table("analytics_imports")
