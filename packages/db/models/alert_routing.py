"""Alert routing models: notification preferences and alert delivery log.

OperatorNotificationPreference stores per-org channel routing rules.
AlertDeliveryLog tracks every alert delivery attempt for audit.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class OperatorNotificationPreference(Base):
    """Per-organization notification routing preferences.

    Operators can configure which severities go to which channels,
    or disable alerts entirely. One row per org; upserted on change.
    """

    __tablename__ = "operator_notification_preferences"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, unique=True, index=True
    )

    # --- Channel routing by severity ---
    # Each is a list of channel names: ["slack", "email", "in_app"]
    critical_channels: Mapped[Optional[dict]] = mapped_column(
        JSONB, default=lambda: ["slack", "email", "in_app"], comment="Channels for critical alerts (default: all)"
    )
    warning_channels: Mapped[Optional[dict]] = mapped_column(
        JSONB, default=lambda: ["slack", "in_app"], comment="Channels for warning alerts (default: slack + in_app)"
    )
    info_channels: Mapped[Optional[dict]] = mapped_column(
        JSONB, default=lambda: ["in_app"], comment="Channels for info alerts (default: in_app only)"
    )

    # --- Global toggle ---
    alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="Master kill switch for all alerts")

    # --- Recipient overrides ---
    slack_webhook_url: Mapped[Optional[str]] = mapped_column(
        String(500), comment="Override org-level Slack webhook (falls back to env SLACK_WEBHOOK_URL)"
    )
    email_recipients: Mapped[Optional[dict]] = mapped_column(
        JSONB, default=list, comment="List of email addresses for alert delivery"
    )

    # --- Quiet hours (optional) ---
    quiet_start_hour_utc: Mapped[Optional[int]] = mapped_column(
        Integer, comment="Start of quiet window (UTC hour, 0-23). Info/warning suppressed during quiet hours."
    )
    quiet_end_hour_utc: Mapped[Optional[int]] = mapped_column(
        Integer, comment="End of quiet window (UTC hour, 0-23). Critical alerts always deliver."
    )

    # --- Metadata ---
    updated_by: Mapped[Optional[str]] = mapped_column(String(255))


class AlertDeliveryLog(Base):
    """Append-only log of every alert delivery attempt.

    Used for audit, dedup, and delivery status tracking.
    """

    __tablename__ = "alert_delivery_log"

    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), index=True
    )
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), index=True)

    # --- Source ---
    source_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("system_events.id"),
        index=True,
        comment="The SystemEvent that triggered this alert",
    )

    # --- Alert content ---
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text)
    alert_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, default=dict)

    # --- Delivery ---
    channel: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="slack, email, in_app")
    recipient: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(
        String(30), default="pending", index=True, comment="pending, delivered, failed, skipped"
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
