"""Live Execution Closure Phase 1 — engines for truth reconciliation, import classification, send logic."""

from __future__ import annotations

from typing import Any

TRUTH_LEVELS = ["live_import", "live_verified", "synthetic_proxy", "operator_override", "unknown"]
SOURCE_CATEGORIES = ["social", "checkout", "affiliate", "crm", "email", "sms", "ads", "manual"]
CONVERSION_TYPES = ["purchase", "signup", "lead", "affiliate_payout", "subscription", "upsell", "refund", "chargeback"]
OBSERVATION_TYPES = ["impression", "click", "conversion", "engagement", "view", "revenue", "ctr", "cpa"]
LIFECYCLE_STAGES = [
    "subscriber",
    "lead",
    "qualified_lead",
    "opportunity",
    "customer",
    "repeat_buyer",
    "churned",
    "advocate",
]
SEND_STATUSES = ["queued", "sending", "sent", "delivered", "opened", "clicked", "bounced", "failed", "unsubscribed"]
BLOCKER_TYPES = [
    "missing_smtp_config",
    "missing_sms_api_key",
    "missing_crm_credentials",
    "missing_esp_api_key",
    "rate_limited",
    "provider_down",
    "invalid_sender",
    "no_contacts",
    "compliance_hold",
]


def classify_analytics_source(source: str) -> str:
    source_lower = source.lower()
    if any(
        k in source_lower
        for k in ("buffer", "tiktok", "instagram", "youtube", "twitter", "facebook", "linkedin", "reddit")
    ):
        return "social"
    if any(k in source_lower for k in ("stripe", "shopify", "gumroad", "paypal", "checkout")):
        return "checkout"
    if any(k in source_lower for k in ("affiliate", "clickbank", "impact", "shareasale")):
        return "affiliate"
    if any(k in source_lower for k in ("mailchimp", "convertkit", "activecampaign", "sendgrid", "esp")):
        return "email"
    if any(k in source_lower for k in ("twilio", "sms", "messagebird")):
        return "sms"
    if any(k in source_lower for k in ("google_ads", "meta_ads", "tiktok_ads")):
        return "ads"
    if any(k in source_lower for k in ("hubspot", "salesforce", "pipedrive", "crm")):
        return "crm"
    return "manual"


def reconcile_truth(existing_level: str, new_level: str) -> str:
    """Determine which truth level takes priority. Live > proxy > unknown."""
    priority = {"live_verified": 5, "live_import": 4, "operator_override": 3, "synthetic_proxy": 2, "unknown": 1}
    if priority.get(new_level, 0) >= priority.get(existing_level, 0):
        return new_level
    return existing_level


def compute_import_summary(events: list[dict[str, Any]], existing_ids: set) -> dict[str, Any]:
    total = len(events)
    matched = sum(
        1 for e in events if e.get("external_id") in existing_ids or e.get("external_post_id") in existing_ids
    )
    return {"events_imported": total, "events_matched": matched, "events_new": total - matched}


def derive_experiment_truth(proxy_value: float, live_value: float | None, live_sample: int) -> dict[str, Any]:
    """Prefer live truth when sample is meaningful, fall back to proxy."""
    if live_value is not None and live_sample >= 30:
        confidence = min(1.0, live_sample / 100)
        return {"value": live_value, "truth_level": "live_import", "confidence": round(confidence, 3), "source": "live"}
    if live_value is not None and live_sample >= 10:
        blended = proxy_value * 0.3 + live_value * 0.7
        confidence = min(0.7, live_sample / 50)
        return {
            "value": round(blended, 4),
            "truth_level": "live_import",
            "confidence": round(confidence, 3),
            "source": "blended",
        }
    return {"value": proxy_value, "truth_level": "synthetic_proxy", "confidence": 0.3, "source": "proxy"}


def detect_messaging_blockers(brand_ctx: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []

    if not brand_ctx.get("has_smtp_config"):
        blockers.append(
            {
                "blocker_type": "missing_smtp_config",
                "channel": "email",
                "severity": "critical",
                "description": "SMTP configuration not set. Email cannot be sent.",
                "operator_action_needed": "Configure SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS in environment.",
            }
        )
    if not brand_ctx.get("has_sms_api_key"):
        blockers.append(
            {
                "blocker_type": "missing_sms_api_key",
                "channel": "sms",
                "severity": "critical",
                "description": "SMS API key not configured. SMS cannot be sent.",
                "operator_action_needed": "Set SMS_API_KEY in environment (e.g. Twilio auth).",
            }
        )
    if not brand_ctx.get("has_esp_api_key"):
        blockers.append(
            {
                "blocker_type": "missing_esp_api_key",
                "channel": "email",
                "severity": "high",
                "description": "ESP API key not configured. Templated/sequence emails cannot be sent.",
                "operator_action_needed": "Set ESP_API_KEY (ConvertKit, Mailchimp, etc.) in environment.",
            }
        )
    if not brand_ctx.get("has_crm_credentials"):
        blockers.append(
            {
                "blocker_type": "missing_crm_credentials",
                "channel": "crm",
                "severity": "high",
                "description": "CRM credentials not configured. Contact sync is not available.",
                "operator_action_needed": "Set CRM_API_KEY (HubSpot, Salesforce, etc.) in environment.",
            }
        )
    if brand_ctx.get("contacts_count", 0) == 0:
        blockers.append(
            {
                "blocker_type": "no_contacts",
                "channel": "email",
                "severity": "medium",
                "description": "No contacts in CRM. Email/SMS sequences have no audience.",
                "operator_action_needed": "Import contacts or enable lead capture integrations.",
            }
        )
    return blockers


def validate_email_send(request: dict[str, Any], brand_ctx: dict[str, Any]) -> dict[str, Any]:
    if not brand_ctx.get("has_smtp_config") and not brand_ctx.get("has_esp_api_key"):
        return {"valid": False, "error": "No email provider configured"}
    if not request.get("to_email"):
        return {"valid": False, "error": "Missing recipient email"}
    if not request.get("subject"):
        return {"valid": False, "error": "Missing subject line"}
    if not request.get("body_html") and not request.get("body_text") and not request.get("template_id"):
        return {"valid": False, "error": "Missing body or template"}
    return {"valid": True, "error": None}


def validate_sms_send(request: dict[str, Any], brand_ctx: dict[str, Any]) -> dict[str, Any]:
    if not brand_ctx.get("has_sms_api_key"):
        return {"valid": False, "error": "No SMS provider configured"}
    if not request.get("to_phone"):
        return {"valid": False, "error": "Missing recipient phone number"}
    if not request.get("message_body"):
        return {"valid": False, "error": "Missing message body"}
    if len(request.get("message_body", "")) > 1600:
        return {"valid": False, "error": "Message body exceeds 1600 characters"}
    return {"valid": True, "error": None}
