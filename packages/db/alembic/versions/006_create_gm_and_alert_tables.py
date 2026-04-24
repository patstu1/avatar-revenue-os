"""Create GM conversation tables and alert delivery tables.

Revision ID: 006_gm_alerts
Revises: b6587e9c03b5
Create Date: 2026-04-06
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "006_gm_alerts"
down_revision = "b6587e9c03b5"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :t)"),
        {"t": name},
    )
    return result.scalar()


def upgrade() -> None:
    if not _table_exists("gm_sessions"):
        op.create_table(
            "gm_sessions",
            sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column(
                "organization_id",
                UUID(as_uuid=True),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("title", sa.String(255), default="GM Strategy Session"),
            sa.Column("status", sa.String(30), default="active"),
            sa.Column("machine_phase", sa.String(40), nullable=True),
            sa.Column("message_count", sa.Integer, default=0),
            sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("active_blueprint_id", UUID(as_uuid=True), nullable=True),
            sa.Column("is_active", sa.Boolean, default=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )

    if not _table_exists("gm_messages"):
        op.create_table(
            "gm_messages",
            sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column(
                "session_id",
                UUID(as_uuid=True),
                sa.ForeignKey("gm_sessions.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("content", sa.Text, nullable=False),
            sa.Column("message_type", sa.String(30), default="conversation"),
            sa.Column("blueprint_data", JSONB, nullable=True),
            sa.Column("machine_state_snapshot", JSONB, nullable=True),
            sa.Column("generation_model", sa.String(60), nullable=True),
            sa.Column("is_active", sa.Boolean, default=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )

    if not _table_exists("gm_blueprints"):
        op.create_table(
            "gm_blueprints",
            sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column(
                "organization_id",
                UUID(as_uuid=True),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "session_id",
                UUID(as_uuid=True),
                sa.ForeignKey("gm_sessions.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("version", sa.Integer, default=1),
            sa.Column("status", sa.String(30), default="proposed"),
            sa.Column("account_blueprint", JSONB, nullable=True),
            sa.Column("niche_blueprint", JSONB, nullable=True),
            sa.Column("identity_blueprint", JSONB, nullable=True),
            sa.Column("platform_blueprint", JSONB, nullable=True),
            sa.Column("monetization_blueprint", JSONB, nullable=True),
            sa.Column("scaling_blueprint", JSONB, nullable=True),
            sa.Column("operator_inputs_needed", JSONB, nullable=True),
            sa.Column("machine_assessment", JSONB, nullable=True),
            sa.Column("execution_progress", JSONB, nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_active", sa.Boolean, default=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )

    if not _table_exists("gm_conversations"):
        op.create_table(
            "gm_conversations",
            sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column(
                "organization_id",
                UUID(as_uuid=True),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "brand_id",
                UUID(as_uuid=True),
                sa.ForeignKey("brands.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("messages", JSONB, nullable=True),
            sa.Column("actions_log", JSONB, nullable=True),
            sa.Column("is_active", sa.Boolean, default=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )

    if not _table_exists("operator_notification_preferences"):
        op.create_table(
            "operator_notification_preferences",
            sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column(
                "organization_id",
                UUID(as_uuid=True),
                sa.ForeignKey("organizations.id"),
                nullable=False,
                unique=True,
                index=True,
            ),
            sa.Column("critical_channels", JSONB, nullable=True),
            sa.Column("warning_channels", JSONB, nullable=True),
            sa.Column("info_channels", JSONB, nullable=True),
            sa.Column("alerts_enabled", sa.Boolean, default=True),
            sa.Column("slack_webhook_url", sa.String(500), nullable=True),
            sa.Column("email_recipients", JSONB, nullable=True),
            sa.Column("quiet_start_hour_utc", sa.Integer, nullable=True),
            sa.Column("quiet_end_hour_utc", sa.Integer, nullable=True),
            sa.Column("updated_by", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )

    if not _table_exists("alert_delivery_log"):
        op.create_table(
            "alert_delivery_log",
            sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column(
                "organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True, index=True
            ),
            sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=True, index=True),
            sa.Column(
                "source_event_id", UUID(as_uuid=True), sa.ForeignKey("system_events.id"), nullable=True, index=True
            ),
            sa.Column("severity", sa.String(20), nullable=False, index=True),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("message", sa.Text, nullable=True),
            sa.Column("metadata", JSONB, nullable=True),
            sa.Column("channel", sa.String(50), nullable=False, index=True),
            sa.Column("recipient", sa.String(500), nullable=True),
            sa.Column("status", sa.String(30), default="pending", index=True),
            sa.Column("error_message", sa.Text, nullable=True),
            sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )


def downgrade() -> None:
    for t in (
        "alert_delivery_log",
        "operator_notification_preferences",
        "gm_conversations",
        "gm_blueprints",
        "gm_messages",
        "gm_sessions",
    ):
        op.drop_table(t)
