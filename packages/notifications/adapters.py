"""Notification delivery adapters: email, Slack/webhook, SMS, in-app.

Each adapter implements send() returning (success: bool, error: Optional[str]).
Credentials are checked at call time — adapters are always importable.
Missing credentials fail loudly in logs and status rows.
"""
from __future__ import annotations

import os
import threading
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional

import aiosmtplib
import structlog
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = structlog.get_logger()


class NotificationPayload:
    def __init__(self, title: str, summary: str, urgency: float, alert_type: str,
                 brand_id: str, alert_id: Optional[str] = None, detail_url: Optional[str] = None):
        self.title = title
        self.summary = summary
        self.urgency = urgency
        self.alert_type = alert_type
        self.brand_id = brand_id
        self.alert_id = alert_id
        self.detail_url = detail_url

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title, "summary": self.summary, "urgency": self.urgency,
            "alert_type": self.alert_type, "brand_id": self.brand_id,
            "alert_id": self.alert_id, "detail_url": self.detail_url,
        }


class BaseNotificationAdapter(ABC):
    channel: str = "base"

    @abstractmethod
    async def send(self, payload: NotificationPayload, recipient: str) -> tuple[bool, Optional[str]]:
        ...


class _InAppStore:
    """Thread-safe in-memory notification store for InAppAdapter."""

    def __init__(self, max_size: int = 10_000):
        self._lock = threading.Lock()
        self._notifications: list[dict[str, Any]] = []
        self._max_size = max_size

    def add(self, notification: dict[str, Any]) -> None:
        with self._lock:
            self._notifications.append(notification)
            if len(self._notifications) > self._max_size:
                self._notifications = self._notifications[-self._max_size:]

    def get_for_recipient(self, recipient: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [n for n in reversed(self._notifications) if n.get("recipient") == recipient][:limit]

    def get_for_brand(self, brand_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [n for n in reversed(self._notifications) if n.get("brand_id") == brand_id][:limit]

    def count(self) -> int:
        with self._lock:
            return len(self._notifications)


_in_app_store = _InAppStore()


class InAppAdapter(BaseNotificationAdapter):
    channel = "in_app"

    async def send(self, payload: NotificationPayload, recipient: str) -> tuple[bool, Optional[str]]:
        notification = {
            "id": str(uuid.uuid4()),
            "recipient": recipient,
            "brand_id": payload.brand_id,
            "alert_id": payload.alert_id,
            "title": payload.title,
            "summary": payload.summary,
            "urgency": payload.urgency,
            "alert_type": payload.alert_type,
            "detail_url": payload.detail_url,
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _in_app_store.add(notification)
        logger.info(
            "notification.in_app.persisted",
            notification_id=notification["id"],
            alert_type=payload.alert_type,
            brand_id=payload.brand_id,
            recipient=recipient,
        )
        return True, None

    @staticmethod
    def get_notifications(recipient: str, limit: int = 50) -> list[dict[str, Any]]:
        return _in_app_store.get_for_recipient(recipient, limit)

    @staticmethod
    def get_brand_notifications(brand_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return _in_app_store.get_for_brand(brand_id, limit)

    @staticmethod
    def notification_count() -> int:
        return _in_app_store.count()


class EmailAdapter(BaseNotificationAdapter):
    channel = "email"

    def __init__(self, smtp_host: str = "", smtp_port: int = 587, smtp_user: str = "", smtp_pass: str = "",
                 smtp_from_email: str = "", use_tls: Optional[bool] = None, source: str = "legacy"):
        """Explicit-params construction is the primary path. Use ``EmailAdapter.from_db``
        to pull config from ``integration_providers`` (system-managed). No-arg init
        falls back to SMTP_* env vars with a clearly-marked transitional warning.
        """
        if smtp_host or smtp_user or smtp_pass or smtp_from_email:
            # Explicit construction — DB-resolved or test-harness path.
            self.smtp_host = smtp_host
            self.smtp_port = smtp_port
            self.smtp_user = smtp_user
            self.smtp_pass = smtp_pass
            self.from_email = smtp_from_email or smtp_user
            self.use_tls = True if use_tls is None else bool(use_tls)
            self.source = source
        else:
            # Legacy env-backed construction. Not the primary runtime path;
            # to be removed once all callers migrate to from_db.
            self.smtp_host = os.environ.get("SMTP_HOST", "")
            self.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
            self.smtp_user = os.environ.get("SMTP_USER", "") or os.environ.get("SMTP_USERNAME", "")
            self.smtp_pass = os.environ.get("SMTP_PASS", "") or os.environ.get("SMTP_PASSWORD", "")
            self.from_email = os.environ.get("SMTP_FROM_EMAIL", "") or self.smtp_user
            self.use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
            self.source = "env_legacy"
            logger.warning(
                "notification.email.env_legacy_fallback",
                hint="EmailAdapter constructed from env vars. Configure SMTP in Settings > Integrations and construct via EmailAdapter.from_db.",
            )
        self.configured = bool(self.smtp_host and (self.smtp_user or self.from_email))

    @classmethod
    async def from_db(cls, db, org_id) -> "EmailAdapter":
        """Construct from DB-managed SMTP config for the org. Returns an
        unconfigured adapter if none is present (no env fallback)."""
        from packages.clients.credential_loader import load_smtp_config_async
        cfg = await load_smtp_config_async(db, org_id)
        if not cfg:
            inst = object.__new__(cls)
            inst.smtp_host = ""
            inst.smtp_port = 587
            inst.smtp_user = ""
            inst.smtp_pass = ""
            inst.from_email = ""
            inst.use_tls = True
            inst.source = "db_missing"
            inst.configured = False
            return inst
        return cls(
            smtp_host=cfg["host"], smtp_port=cfg["port"],
            smtp_user=cfg["username"], smtp_pass=cfg["password"],
            smtp_from_email=cfg["from_email"], use_tls=cfg["use_tls"],
            source=cfg["source"],
        )

    async def send(self, payload: NotificationPayload, recipient: str) -> tuple[bool, Optional[str]]:
        if not self.configured:
            msg = "SMTP credentials missing (SMTP_HOST/SMTP_USER not set) — email delivery unavailable"
            logger.warning("notification.email.not_configured", recipient=recipient, alert_type=payload.alert_type)
            return False, msg
        try:
            mime_msg = MIMEMultipart("alternative")
            mime_msg["Subject"] = f"[Revenue OS] {payload.title}"
            mime_msg["From"] = self.from_email
            mime_msg["To"] = recipient

            body_text = f"{payload.summary}\n\nUrgency: {payload.urgency}\nType: {payload.alert_type}\nBrand: {payload.brand_id}"
            body_html = (
                f"<h2>{payload.title}</h2>"
                f"<p>{payload.summary}</p>"
                f"<p><strong>Urgency:</strong> {payload.urgency} | <strong>Type:</strong> {payload.alert_type}</p>"
            )
            if payload.detail_url:
                body_html += f'<p><a href="{payload.detail_url}">View Details</a></p>'

            mime_msg.attach(MIMEText(body_text, "plain", "utf-8"))
            mime_msg.attach(MIMEText(body_html, "html", "utf-8"))

            await aiosmtplib.send(
                mime_msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user or None,
                password=self.smtp_pass or None,
                use_tls=self.use_tls,
            )
            logger.info("notification.email.sent", recipient=recipient, title=payload.title)
            return True, None
        except aiosmtplib.SMTPException as e:
            logger.error("notification.email.smtp_error", recipient=recipient, error=str(e))
            return False, f"Email SMTP error: {e}"
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error("notification.email.connection_error", recipient=recipient, error=str(e))
            return False, f"Email connection error: {e}"
        except Exception as e:
            logger.error("notification.email.failed", recipient=recipient, error=str(e))
            return False, f"Email send failed: {e}"


class SlackWebhookAdapter(BaseNotificationAdapter):
    channel = "slack"

    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url
        self.configured = bool(webhook_url)

    async def send(self, payload: NotificationPayload, recipient: str) -> tuple[bool, Optional[str]]:
        if not self.configured:
            msg = "Slack webhook URL not set (SLACK_WEBHOOK_URL) — Slack delivery unavailable"
            logger.warning("notification.slack.not_configured", alert_type=payload.alert_type)
            return False, msg
        import httpx
        try:
            urgency_emoji = "\U0001f534" if payload.urgency > 0.8 else "\U0001f7e1" if payload.urgency > 0.5 else "\U0001f7e2"
            text = f"{urgency_emoji} *{payload.title}*\n{payload.summary}\nType: `{payload.alert_type}` | Brand: `{payload.brand_id}`"
            if payload.detail_url:
                text += f"\n<{payload.detail_url}|View Details>"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.webhook_url, json={"text": text})
            if resp.status_code == 200:
                logger.info("notification.slack.sent", title=payload.title)
                return True, None
            logger.warning("notification.slack.http_error", status=resp.status_code)
            return False, f"Slack returned {resp.status_code}"
        except Exception as e:
            logger.error("notification.slack.failed", error=str(e))
            return False, f"Slack send failed: {e}"


class SMSAdapter(BaseNotificationAdapter):
    channel = "sms"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.configured = bool(api_key)

    async def send(self, payload: NotificationPayload, recipient: str) -> tuple[bool, Optional[str]]:
        if not self.configured:
            msg = "SMS API key not set (SMS_API_KEY) — SMS delivery unavailable"
            logger.warning("notification.sms.not_configured", recipient=recipient, alert_type=payload.alert_type)
            return False, msg
        import httpx
        try:
            sms_url = os.environ.get("SMS_API_URL", "https://api.twilio.com/2010-04-01")
            account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
            from_number = os.environ.get("SMS_FROM_NUMBER", "")
            body = f"[Revenue OS] {payload.title}: {payload.summary[:140]}"
            if not account_sid or not from_number:
                missing = []
                if not account_sid:
                    missing.append("TWILIO_ACCOUNT_SID")
                if not from_number:
                    missing.append("SMS_FROM_NUMBER")
                msg = f"Twilio not configured — missing: {', '.join(missing)}"
                logger.warning("notification.sms.not_configured", recipient=recipient, missing=missing)
                return False, msg
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{sms_url}/Accounts/{account_sid}/Messages.json",
                    data={"To": recipient, "From": from_number, "Body": body},
                    auth=(account_sid, self.api_key),
                )
            if resp.status_code in (200, 201):
                logger.info("notification.sms.sent", recipient=recipient)
                return True, None
            logger.warning("notification.sms.http_error", status=resp.status_code)
            return False, f"SMS API returned {resp.status_code}"
        except Exception as e:
            logger.error("notification.sms.failed", error=str(e))
            return False, f"SMS send failed: {e}"


def get_adapters() -> list[BaseNotificationAdapter]:
    return [
        InAppAdapter(),
        EmailAdapter(),
        SlackWebhookAdapter(webhook_url=os.environ.get("SLACK_WEBHOOK_URL", "")),
        SMSAdapter(api_key=os.environ.get("SMS_API_KEY", "") or os.environ.get("TWILIO_AUTH_TOKEN", "")),
    ]
