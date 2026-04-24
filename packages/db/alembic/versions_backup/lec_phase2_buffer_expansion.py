"""Live Execution Phase 2 + Buffer Execution Expansion — 10 tables.

Revision ID: lec_phase2_001
Revises: b3c4d5e6f7g8, cra_phase_d_001 (merge)
Create Date: 2026-03-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "lec_phase2_001"
down_revision = ("b3c4d5e6f7g8", "cra_phase_d_001")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=True, index=True),
        sa.Column("source", sa.String(80), nullable=False, index=True),
        sa.Column("source_category", sa.String(40), nullable=False, index=True),
        sa.Column("event_type", sa.String(120), nullable=False, index=True),
        sa.Column("external_event_id", sa.String(255), nullable=True, index=True),
        sa.Column("raw_payload", JSONB, nullable=True),
        sa.Column("processed", sa.Boolean, server_default=sa.text("false"), nullable=False, index=True),
        sa.Column("processing_result", sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=True, unique=True, index=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
    )

    op.create_table(
        "external_event_ingestions",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("source", sa.String(80), nullable=False, index=True),
        sa.Column("source_category", sa.String(40), nullable=False, index=True),
        sa.Column("ingestion_mode", sa.String(30), server_default=sa.text("'webhook'"), nullable=False, index=True),
        sa.Column("events_received", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("events_processed", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("events_skipped", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("events_failed", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("status", sa.String(30), server_default=sa.text("'completed'"), nullable=False, index=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("details_json", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
    )

    op.create_table(
        "sequence_trigger_actions",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("trigger_source", sa.String(80), nullable=False, index=True),
        sa.Column("trigger_event_type", sa.String(120), nullable=False, index=True),
        sa.Column("trigger_event_id", sa.UUID(), nullable=True, index=True),
        sa.Column("action_type", sa.String(80), nullable=False, index=True),
        sa.Column("action_target", sa.String(255), nullable=True),
        sa.Column("action_payload", JSONB, nullable=True),
        sa.Column("status", sa.String(30), server_default=sa.text("'pending'"), nullable=False, index=True),
        sa.Column("executed_at", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
    )

    op.create_table(
        "payment_connector_syncs",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("provider", sa.String(80), nullable=False, index=True),
        sa.Column("sync_mode", sa.String(30), server_default=sa.text("'incremental'"), nullable=False, index=True),
        sa.Column("orders_imported", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("revenue_imported", sa.Float, server_default=sa.text("0"), nullable=False),
        sa.Column("refunds_imported", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("status", sa.String(30), server_default=sa.text("'completed'"), nullable=False, index=True),
        sa.Column("credential_status", sa.String(30), server_default=sa.text("'not_configured'"), nullable=False, index=True),
        sa.Column("last_cursor", sa.String(255), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("details_json", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
    )

    op.create_table(
        "platform_analytics_syncs",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("source", sa.String(80), nullable=False, index=True),
        sa.Column("source_category", sa.String(40), nullable=False, index=True),
        sa.Column("sync_mode", sa.String(30), server_default=sa.text("'scheduled'"), nullable=False, index=True),
        sa.Column("metrics_imported", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("content_items_matched", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("attribution_refreshed", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("reconciliation_status", sa.String(30), server_default=sa.text("'clean'"), nullable=False, index=True),
        sa.Column("credential_status", sa.String(30), server_default=sa.text("'not_configured'"), nullable=False, index=True),
        sa.Column("blocker_state", sa.String(60), nullable=True),
        sa.Column("operator_action", sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("details_json", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
    )

    op.create_table(
        "ad_reporting_imports",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("ad_platform", sa.String(80), nullable=False, index=True),
        sa.Column("report_type", sa.String(80), server_default=sa.text("'campaign_summary'"), nullable=False, index=True),
        sa.Column("campaigns_imported", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("spend_imported", sa.Float, server_default=sa.text("0"), nullable=False),
        sa.Column("impressions_imported", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("clicks_imported", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("conversions_imported", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("revenue_attributed", sa.Float, server_default=sa.text("0"), nullable=False),
        sa.Column("source_classification", sa.String(40), server_default=sa.text("'ads'"), nullable=False, index=True),
        sa.Column("reconciliation_status", sa.String(30), server_default=sa.text("'clean'"), nullable=False, index=True),
        sa.Column("credential_status", sa.String(30), server_default=sa.text("'not_configured'"), nullable=False, index=True),
        sa.Column("blocker_state", sa.String(60), nullable=True),
        sa.Column("operator_action", sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("details_json", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
    )

    op.create_table(
        "buffer_execution_truth",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column(
            "buffer_publish_job_id",
            sa.UUID(),
            sa.ForeignKey("buffer_publish_jobs.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("content_item_id", sa.UUID(), sa.ForeignKey("content_items.id"), nullable=True, index=True),
        sa.Column("truth_state", sa.String(40), server_default=sa.text("'queued_internally'"), nullable=False, index=True),
        sa.Column("previous_truth_state", sa.String(40), nullable=True),
        sa.Column("is_duplicate", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("is_stale", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("stale_since", sa.String(50), nullable=True),
        sa.Column("conflict_detected", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("conflict_description", sa.Text, nullable=True),
        sa.Column("operator_action", sa.Text, nullable=True),
        sa.Column("details_json", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
    )

    op.create_table(
        "buffer_execution_events",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column(
            "buffer_publish_job_id",
            sa.UUID(),
            sa.ForeignKey("buffer_publish_jobs.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("event_type", sa.String(80), nullable=False, index=True),
        sa.Column("from_state", sa.String(40), nullable=True),
        sa.Column("to_state", sa.String(40), nullable=True),
        sa.Column("details_json", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
    )

    op.create_table(
        "buffer_retry_records",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column(
            "buffer_publish_job_id",
            sa.UUID(),
            sa.ForeignKey("buffer_publish_jobs.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("attempt_number", sa.Integer, server_default=sa.text("1"), nullable=False),
        sa.Column("retry_reason", sa.String(120), nullable=False),
        sa.Column("backoff_seconds", sa.Integer, server_default=sa.text("60"), nullable=False),
        sa.Column("next_retry_at", sa.String(50), nullable=True),
        sa.Column("outcome", sa.String(30), server_default=sa.text("'pending'"), nullable=False, index=True),
        sa.Column("escalated", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
    )

    op.create_table(
        "buffer_capability_checks",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column(
            "buffer_profile_id_fk",
            sa.UUID(),
            sa.ForeignKey("buffer_profiles.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("profile_ready", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("credential_valid", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("missing_profile_mapping", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("inactive_profile", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("platform_supported", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("unsupported_modes", JSONB, nullable=True),
        sa.Column("capabilities_json", JSONB, nullable=True),
        sa.Column("blocker_summary", sa.Text, nullable=True),
        sa.Column("operator_action", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("buffer_capability_checks")
    op.drop_table("buffer_retry_records")
    op.drop_table("buffer_execution_events")
    op.drop_table("buffer_execution_truth")
    op.drop_table("ad_reporting_imports")
    op.drop_table("platform_analytics_syncs")
    op.drop_table("payment_connector_syncs")
    op.drop_table("sequence_trigger_actions")
    op.drop_table("external_event_ingestions")
    op.drop_table("webhook_events")
