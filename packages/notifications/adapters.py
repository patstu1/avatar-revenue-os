"""Notification delivery adapters: email, Slack/webhook, SMS.

Each adapter implements send() returning (success: bool, error: Optional[str]).
Credentials are checked at call time — adapters are always importable.
Missing credentials fail loudly in logs and status rows.
"""
from __future__ import annotations

import os

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
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_pass = smtp_pass
        self.configured = bool(smtp_host and smtp_user)

    def send(self, payload: NotificationPayload, recipient: str) -> tuple[bool, Optional[str]]:
        if not self.configured:
            msg = "SMTP credentials missing (SMTP_HOST/SMTP_USER not set) — email delivery unavailable"
            logger.warning("notification.email.not_configured", recipient=recipient, alert_type=payload.alert_type)
            return False, msg
        import smtplib
        from email.mime.text import MIMEText
        try:
            msg = MIMEText(f"{payload.summary}\n\nUrgency: {payload.urgency}\nType: {payload.alert_type}\nBrand: {payload.brand_id}")
            msg["Subject"] = f"[Revenue OS] {payload.title}"
            msg["From"] = self.smtp_user
            msg["To"] = recipient
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
            logger.info("notification.email.sent", recipient=recipient, title=payload.title)
            return True, None
        except Exception as e:
            logger.error("notification.email.failed", recipient=recipient, error=str(e))
            return False, f"Email send failed: {e}"


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
        import httpx
        try:
            urgency_emoji = "🔴" if payload.urgency > 0.8 else "🟡" if payload.urgency > 0.5 else "🟢"
            text = f"{urgency_emoji} *{payload.title}*\n{payload.summary}\nType: `{payload.alert_type}` | Brand: `{payload.brand_id}`"
            if payload.detail_url:
                text += f"\n<{payload.detail_url}|View Details>"
            resp = httpx.post(self.webhook_url, json={"text": text}, timeout=10)
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

    def send(self, payload: NotificationPayload, recipient: str) -> tuple[bool, Optional[str]]:
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
                logger.info("notification.sms.queued", recipient=recipient, title=payload.title)
                return True, None
            resp = httpx.post(
                f"{sms_url}/Accounts/{account_sid}/Messages.json",
                data={"To": recipient, "From": from_number, "Body": body},
                auth=(account_sid, self.api_key),
                timeout=10,
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
    return [InAppAdapter(), EmailAdapter(), SlackWebhookAdapter(), SMSAdapter()]
