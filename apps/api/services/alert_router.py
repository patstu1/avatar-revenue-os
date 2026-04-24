"""Alert Router — self-healing error recovery and operator notification.

Routes alerts by severity to appropriate notification channels.
The system resolves what it can silently (token refresh, provider failover,
retry with backoff) and only alerts the operator when it cannot self-heal.

Severity routing (defaults, operator-configurable):
  critical  -> slack + email + in_app  (all providers down, revenue anomaly, expired OAuth, consecutive failures)
  warning   -> slack + in_app          (single provider down, high error rate, approaching quota)
  info      -> in_app only             (successful recoveries, token refreshes, new content published)

Usage:
    from apps.api.services.alert_router import AlertRouter

    router = AlertRouter()

    # Async (API context with db session)
    await router.route_alert(
        db=db,
        severity="critical",
        title="All YouTube providers down",
        message="YouTube publishing unavailable — 3/3 providers report auth failures.",
        org_id=org_id,
        brand_id=brand_id,
        source_event_id=event.id,
        metadata={"providers": ["yt-1", "yt-2", "yt-3"]},
    )

    # Sync (Celery worker context)
    router.route_alert_sync(
        session=session,
        severity="warning",
        title="TikTok error rate above 50%",
        message="Provider tiktok-main returning errors on 52% of requests in the last hour.",
        org_id=org_id,
        metadata={"error_rate": 0.52},
    )
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from packages.db.models.alert_routing import AlertDeliveryLog, OperatorNotificationPreference
from packages.notifications.adapters import (
    EmailAdapter,
    InAppAdapter,
    NotificationPayload,
    SlackWebhookAdapter,
)

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Default routing config (used when no DB preference exists for the org)
# ---------------------------------------------------------------------------

DEFAULT_CHANNEL_MAP: dict[str, list[str]] = {
    "critical": ["slack", "email", "in_app"],
    "warning": ["slack", "in_app"],
    "info": ["in_app"],
}

# Events that the system tries to self-heal silently.
# If they appear with requires_action=True, self-healing failed and we alert.
SELF_HEALING_EVENT_TYPES = frozenset(
    {
        "job.retrying",  # Transient errors being retried
        "token.refreshing",  # OAuth token refresh in progress
        "provider.failover",  # Automatic failover to backup provider
        "recovery.auto_retry",  # Recovery engine auto-retry
    }
)

# Event types that always warrant an alert when they appear
ALWAYS_ALERT_EVENT_TYPES = frozenset(
    {
        "job.failed.auth",  # Auth failure — provider needs re-auth
        "job.consecutive_failures",  # 3+ consecutive failures
        "job.failed.permanent",  # Permanent failure
        "provider.all_down",  # All providers for a category down
        "revenue.anomaly",  # Revenue anomaly detected
        "oauth.expired_no_refresh",  # OAuth expired with no refresh token
        "publishing.consecutive_failures",  # Multiple publish failures in a row
    }
)


def _severity_to_urgency(severity: str) -> float:
    """Map severity string to numeric urgency for NotificationPayload."""
    return {"critical": 0.95, "warning": 0.65, "info": 0.3}.get(severity, 0.5)


class AlertRouter:
    """Routes alerts to the appropriate notification channels based on severity
    and operator preferences. Handles both async (API) and sync (worker) contexts.
    """

    def __init__(self):
        self._in_app = InAppAdapter()
        self._email = EmailAdapter()
        self._slack = SlackWebhookAdapter(webhook_url=os.environ.get("SLACK_WEBHOOK_URL", ""))

    # ------------------------------------------------------------------
    # Async path (API / async workers)
    # ------------------------------------------------------------------

    async def route_alert(
        self,
        db: AsyncSession,
        *,
        severity: str,
        title: str,
        message: str,
        org_id: uuid.UUID | None = None,
        brand_id: uuid.UUID | None = None,
        source_event_id: uuid.UUID | None = None,
        metadata: dict | None = None,
    ) -> list[AlertDeliveryLog]:
        """Route an alert to the appropriate channels. Returns delivery log entries."""
        channels = await self._resolve_channels_async(db, severity, org_id)
        prefs = await self._get_prefs_async(db, org_id) if org_id else None

        if prefs and not prefs.alerts_enabled:
            logger.info("alert_router.alerts_disabled", org_id=str(org_id), title=title)
            return []

        # Quiet hours check (suppress non-critical during quiet window)
        if prefs and severity != "critical" and self._in_quiet_hours(prefs):
            logger.info("alert_router.quiet_hours", severity=severity, title=title)
            return []

        payload = NotificationPayload(
            title=title,
            summary=message,
            urgency=_severity_to_urgency(severity),
            alert_type=f"system.{severity}",
            brand_id=str(brand_id) if brand_id else "system",
        )

        logs: list[AlertDeliveryLog] = []
        for channel in channels:
            log_entry = AlertDeliveryLog(
                organization_id=org_id,
                brand_id=brand_id,
                source_event_id=source_event_id,
                severity=severity,
                title=title,
                message=message,
                metadata=metadata or {},
                channel=channel,
                recipient=self._resolve_recipient(channel, prefs),
            )

            success, error = await self._deliver(channel, payload, prefs)

            if success:
                log_entry.status = "delivered"
                log_entry.delivered_at = datetime.now(timezone.utc)
            else:
                log_entry.status = "failed"
                log_entry.error_message = error

            db.add(log_entry)
            logs.append(log_entry)

        await db.flush()

        logger.info(
            "alert_router.routed",
            severity=severity,
            title=title,
            channels=channels,
            delivered=sum(1 for l in logs if l.status == "delivered"),
            failed=sum(1 for l in logs if l.status == "failed"),
        )

        return logs

    async def _deliver(
        self,
        channel: str,
        payload: NotificationPayload,
        prefs: OperatorNotificationPreference | None,
    ) -> tuple[bool, str | None]:
        """Deliver to a single channel."""
        recipient = self._resolve_recipient(channel, prefs)
        try:
            if channel == "in_app":
                return await self._in_app.send(payload, recipient)
            elif channel == "slack":
                adapter = self._slack
                if prefs and prefs.slack_webhook_url:
                    adapter = SlackWebhookAdapter(webhook_url=prefs.slack_webhook_url)
                return await adapter.send(payload, recipient)
            elif channel == "email":
                return await self._email.send(payload, recipient)
            else:
                return False, f"Unknown channel: {channel}"
        except Exception as e:
            logger.error("alert_router.delivery_error", channel=channel, error=str(e))
            return False, str(e)

    async def _resolve_channels_async(self, db: AsyncSession, severity: str, org_id: uuid.UUID | None) -> list[str]:
        """Resolve channel list from DB prefs or defaults."""
        if not org_id:
            return DEFAULT_CHANNEL_MAP.get(severity, ["in_app"])
        prefs = await self._get_prefs_async(db, org_id)
        if not prefs:
            return DEFAULT_CHANNEL_MAP.get(severity, ["in_app"])
        return self._channels_from_prefs(prefs, severity)

    async def _get_prefs_async(self, db: AsyncSession, org_id: uuid.UUID) -> OperatorNotificationPreference | None:
        result = await db.execute(
            select(OperatorNotificationPreference).where(OperatorNotificationPreference.organization_id == org_id)
        )
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Sync path (Celery workers)
    # ------------------------------------------------------------------

    def route_alert_sync(
        self,
        session: Session,
        *,
        severity: str,
        title: str,
        message: str,
        org_id: uuid.UUID | None = None,
        brand_id: uuid.UUID | None = None,
        source_event_id: uuid.UUID | None = None,
        metadata: dict | None = None,
    ) -> list[AlertDeliveryLog]:
        """Synchronous version for Celery workers. Logs delivery attempts
        but actual async sends are deferred — the log entries with status='pending'
        will be picked up by the notification delivery worker.
        """
        channels = self._resolve_channels_sync(session, severity, org_id)
        prefs = self._get_prefs_sync(session, org_id) if org_id else None

        if prefs and not prefs.alerts_enabled:
            logger.info("alert_router.alerts_disabled_sync", org_id=str(org_id), title=title)
            return []

        if prefs and severity != "critical" and self._in_quiet_hours(prefs):
            logger.info("alert_router.quiet_hours_sync", severity=severity, title=title)
            return []

        logs: list[AlertDeliveryLog] = []
        for channel in channels:
            log_entry = AlertDeliveryLog(
                organization_id=org_id,
                brand_id=brand_id,
                source_event_id=source_event_id,
                severity=severity,
                title=title,
                message=message,
                metadata=metadata or {},
                channel=channel,
                recipient=self._resolve_recipient(channel, prefs),
                status="pending",
            )
            session.add(log_entry)
            logs.append(log_entry)

        session.flush()

        logger.info(
            "alert_router.queued_sync",
            severity=severity,
            title=title,
            channels=channels,
            pending=len(logs),
        )
        return logs

    def _resolve_channels_sync(self, session: Session, severity: str, org_id: uuid.UUID | None) -> list[str]:
        if not org_id:
            return DEFAULT_CHANNEL_MAP.get(severity, ["in_app"])
        prefs = self._get_prefs_sync(session, org_id)
        if not prefs:
            return DEFAULT_CHANNEL_MAP.get(severity, ["in_app"])
        return self._channels_from_prefs(prefs, severity)

    def _get_prefs_sync(self, session: Session, org_id: uuid.UUID) -> OperatorNotificationPreference | None:
        return session.execute(
            select(OperatorNotificationPreference).where(OperatorNotificationPreference.organization_id == org_id)
        ).scalar_one_or_none()

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _channels_from_prefs(prefs: OperatorNotificationPreference, severity: str) -> list[str]:
        """Extract channel list from prefs by severity."""
        mapping = {
            "critical": prefs.critical_channels,
            "warning": prefs.warning_channels,
            "info": prefs.info_channels,
        }
        channels = mapping.get(severity)
        if not channels or not isinstance(channels, list):
            return DEFAULT_CHANNEL_MAP.get(severity, ["in_app"])
        return channels

    @staticmethod
    def _resolve_recipient(channel: str, prefs: OperatorNotificationPreference | None) -> str:
        """Resolve recipient string for a channel."""
        if channel == "in_app":
            return "operator"
        if channel == "email":
            if prefs and prefs.email_recipients and isinstance(prefs.email_recipients, list):
                return ", ".join(prefs.email_recipients)
            return os.environ.get("OPERATOR_EMAIL", "operator@localhost")
        if channel == "slack":
            return "webhook"
        return "unknown"

    @staticmethod
    def _in_quiet_hours(prefs: OperatorNotificationPreference) -> bool:
        """Check if current UTC hour falls within quiet window."""
        if prefs.quiet_start_hour_utc is None or prefs.quiet_end_hour_utc is None:
            return False
        now_hour = datetime.now(timezone.utc).hour
        start = prefs.quiet_start_hour_utc
        end = prefs.quiet_end_hour_utc
        if start <= end:
            return start <= now_hour < end
        else:
            # Wraps midnight (e.g., 22 to 6)
            return now_hour >= start or now_hour < end


# ---------------------------------------------------------------------------
# Event filtering — decides which SystemEvents become operator alerts
# ---------------------------------------------------------------------------


def should_alert(event) -> bool:
    """Determine if a SystemEvent should trigger an operator alert.

    Rules:
    - Events with requires_action=True always alert
    - Events with severity critical or warning always alert
    - Self-healing events (retrying, failover) are silent unless requires_action=True
    - Info events only alert if they are in ALWAYS_ALERT_EVENT_TYPES
    """
    # Already actioned events are skipped
    if getattr(event, "action_taken", False):
        return False

    # Self-healing events are silent unless they've given up
    if event.event_type in SELF_HEALING_EVENT_TYPES and not event.requires_action:
        return False

    # Always-alert event types
    if event.event_type in ALWAYS_ALERT_EVENT_TYPES:
        return True

    # requires_action flag
    if event.requires_action:
        return True

    # Severity-based
    if event.event_severity in ("critical", "warning"):
        return True

    return False


def event_to_alert_severity(event) -> str:
    """Map a SystemEvent to an alert severity.

    Preserves the event's own severity in most cases, but upgrades
    certain event types that are always critical.
    """
    always_critical = {
        "job.failed.auth",
        "provider.all_down",
        "oauth.expired_no_refresh",
        "revenue.anomaly",
    }
    if event.event_type in always_critical:
        return "critical"
    if event.event_type == "job.consecutive_failures":
        return "critical"
    return event.event_severity or "warning"
