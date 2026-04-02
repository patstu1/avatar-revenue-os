"""Notification delivery adapters: email, Slack/webhook, SMS.

Each adapter implements send() returning (success: bool, error: Optional[str]).
Credentials are checked at call time — adapters are always importable.
Missing credentials fail loudly in logs and status rows.
"""
from __future__ import annotations

import structlog
from typing import Any, Optional

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


class BaseNotificationAdapter:
    channel: str = "base"

    def send(self, payload: NotificationPayload, recipient: str) -> tuple[bool, Optional[str]]:
        raise NotImplementedError


class InAppAdapter(BaseNotificationAdapter):
    channel = "in_app"

    def send(self, payload: NotificationPayload, recipient: str) -> tuple[bool, Optional[str]]:
        logger.info("notification.in_app.delivered", alert_type=payload.alert_type, brand_id=payload.brand_id)
        return True, None


class EmailAdapter(BaseNotificationAdapter):
    channel = "email"

    def __init__(self, smtp_host: str = "", smtp_port: int = 587, smtp_user: str = "", smtp_pass: str = ""):
        self.smtp_host = smtp_host
        self.smtp_user = smtp_user
        self.configured = bool(smtp_host and smtp_user)

    def send(self, payload: NotificationPayload, recipient: str) -> tuple[bool, Optional[str]]:
        if not self.configured:
            msg = "SMTP credentials missing (SMTP_HOST/SMTP_USER not set) — email delivery unavailable"
            logger.warning("notification.email.not_configured", recipient=recipient, alert_type=payload.alert_type)
            return False, msg
        logger.info("notification.email.attempt", recipient=recipient, title=payload.title)
        return False, "Email SMTP send not yet wired — adapter ready, connect SMTP transport to enable."


class SlackWebhookAdapter(BaseNotificationAdapter):
    channel = "slack"

    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url
        self.configured = bool(webhook_url)

    def send(self, payload: NotificationPayload, recipient: str) -> tuple[bool, Optional[str]]:
        if not self.configured:
            msg = "Slack webhook URL not set (SLACK_WEBHOOK_URL) — Slack delivery unavailable"
            logger.warning("notification.slack.not_configured", alert_type=payload.alert_type)
            return False, msg
        logger.info("notification.slack.attempt", webhook=self.webhook_url[:30], title=payload.title)
        return False, "Slack webhook POST not yet wired — adapter ready, connect HTTP transport to enable."


class SMSAdapter(BaseNotificationAdapter):
    channel = "sms"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.configured = bool(api_key)

    def send(self, payload: NotificationPayload, recipient: str) -> tuple[bool, Optional[str]]:
        if not self.configured:
            msg = "SMS API key not set (SMS_API_KEY) — SMS delivery unavailable"
            logger.warning("notification.sms.not_configured", recipient=recipient, alert_type=payload.alert_type)
            return False, msg
        logger.info("notification.sms.attempt", recipient=recipient, title=payload.title)
        return False, "SMS API call not yet wired — adapter ready, connect SMS provider to enable."


def get_adapters() -> list[BaseNotificationAdapter]:
    return [InAppAdapter(), EmailAdapter(), SlackWebhookAdapter(), SMSAdapter()]
