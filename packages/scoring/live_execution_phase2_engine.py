"""Live Execution Phase 2 + Buffer Expansion — pure scoring/logic functions."""
from __future__ import annotations

from typing import Any

# ── Constants ──

WEBHOOK_SOURCES = [
    "stripe",
    "shopify",
    "buffer",
    "hubspot",
    "mailchimp",
    "sendgrid",
    "twilio",
    "convertkit",
]

SOURCE_CATEGORIES = {
    "stripe": "payment",
    "shopify": "payment",
    "buffer": "social",
    "buffer_analytics": "social",
    "hubspot": "crm",
    "salesforce": "crm",
    "mailchimp": "email",
    "sendgrid": "email",
    "convertkit": "email",
    "twilio": "sms",
    "meta_ads": "ads",
    "google_ads": "ads",
    "tiktok_ads": "ads",
    "youtube_analytics": "platform_analytics",
    "instagram_insights": "platform_analytics",
    "tiktok_analytics": "platform_analytics",
}

TRIGGER_ACTION_TYPES = [
    "start_nurture_sequence",
    "start_conversion_sequence",
    "start_reactivation_sequence",
    "send_followup_email",
    "send_followup_sms",
    "update_crm_stage",
    "create_upsell_offer",
    "flag_for_retention",
    "notify_operator",
]

BUFFER_TRUTH_STATES = [
    "queued_internally",
    "selected_for_buffer",
    "submitted_to_buffer",
    "accepted_by_buffer",
    "scheduled_in_buffer",
    "published_by_buffer",
    "failed_in_buffer",
    "degraded",
    "unknown",
    "blocked",
]

BUFFER_TRUTH_TRANSITIONS = {
    "queued_internally": ["selected_for_buffer", "blocked"],
    "selected_for_buffer": ["submitted_to_buffer", "blocked"],
    "submitted_to_buffer": ["accepted_by_buffer", "failed_in_buffer", "unknown"],
    "accepted_by_buffer": ["scheduled_in_buffer", "failed_in_buffer"],
    "scheduled_in_buffer": ["published_by_buffer", "failed_in_buffer", "degraded"],
    "published_by_buffer": [],
    "failed_in_buffer": ["submitted_to_buffer", "blocked"],
    "degraded": ["submitted_to_buffer", "blocked"],
    "unknown": ["submitted_to_buffer", "degraded", "blocked"],
    "blocked": ["queued_internally"],
}

AD_PLATFORMS = ["meta_ads", "google_ads", "tiktok_ads"]

PAYMENT_PROVIDERS = ["stripe", "shopify"]

MAX_BUFFER_RETRIES = 5
STALE_JOB_THRESHOLD_HOURS = 48
RETRY_BACKOFF_BASE_SECONDS = 60
RETRY_BACKOFF_MULTIPLIER = 2.0
ESCALATION_THRESHOLD = 3

# Job status strings (external) → BUFFER_TRUTH_STATES
_JOB_STATUS_TO_TRUTH: dict[str, str] = {
    "queued": "queued_internally",
    "queued_internally": "queued_internally",
    "selected": "selected_for_buffer",
    "selected_for_buffer": "selected_for_buffer",
    "submitted": "submitted_to_buffer",
    "submitted_to_buffer": "submitted_to_buffer",
    "accepted": "accepted_by_buffer",
    "accepted_by_buffer": "accepted_by_buffer",
    "scheduled": "scheduled_in_buffer",
    "scheduled_in_buffer": "scheduled_in_buffer",
    "published": "published_by_buffer",
    "published_by_buffer": "published_by_buffer",
    "failed": "failed_in_buffer",
    "failed_in_buffer": "failed_in_buffer",
    "degraded": "degraded",
    "unknown": "unknown",
    "blocked": "blocked",
}

_BUFFER_TERMINAL_FOR_STALE = frozenset({"published_by_buffer"})

_ANALYTICS_SOURCES = frozenset(
    k for k, v in SOURCE_CATEGORIES.items() if v == "platform_analytics"
)

_BUFFER_SUPPORTED_PLATFORMS = frozenset(
    {
        "twitter",
        "x",
        "facebook",
        "instagram",
        "linkedin",
        "pinterest",
        "threads",
        "mastodon",
        "bluesky",
    }
)

_KNOWN_EVENT_TYPES = frozenset(
    {
        "purchase",
        "subscription_started",
        "subscription_renewed",
        "subscription_cancelled",
        "trial_started",
        "trial_ended",
        "lead_created",
        "deal_stage_changed",
        "contact_updated",
        "email_opened",
        "email_clicked",
        "sms_delivered",
        "page_view",
        "form_submit",
        "cart_abandoned",
        "payment_failed",
        "refund",
    }
)


def classify_webhook_source(source: str) -> dict[str, str]:
    """Classify a webhook source; known if listed in webhook sources or category map."""
    normalized = (source or "").strip().lower()
    if not normalized:
        return {"source": source, "source_category": "unknown", "known": False}
    category = SOURCE_CATEGORIES.get(normalized)
    known = normalized in WEBHOOK_SOURCES or normalized in SOURCE_CATEGORIES
    if category is None:
        category = "unknown" if not known else "uncategorized"
    return {"source": source, "source_category": category, "known": known}


def check_idempotency(external_event_id: str, existing_ids: set[str]) -> bool:
    """Return True if this event id was already seen (duplicate)."""
    return external_event_id in existing_ids


def determine_sequence_triggers(
    event_type: str,
    source_category: str,
    conversion_value: float = 0,
) -> list[dict[str, Any]]:
    """Return trigger action dicts for the event; at least one for known event types."""
    et = (event_type or "").strip().lower()
    triggers: list[dict[str, Any]] = []

    if et == "purchase":
        triggers.append(
            {"action_type": "start_conversion_sequence", "reason": "purchase"}
        )
        if conversion_value > 100:
            triggers.append(
                {
                    "action_type": "create_upsell_offer",
                    "reason": "high_value_purchase",
                    "conversion_value": conversion_value,
                }
            )
    elif et == "subscription_cancelled":
        triggers.append(
            {
                "action_type": "start_reactivation_sequence",
                "reason": "subscription_cancelled",
            }
        )
        triggers.append(
            {"action_type": "flag_for_retention", "reason": "subscription_cancelled"}
        )
    elif et in ("deal_stage_changed", "contact_updated", "lead_created") or (
        source_category == "crm"
        and et in ("page_view", "form_submit", "email_opened")
    ):
        triggers.append(
            {
                "action_type": "update_crm_stage",
                "reason": "crm_lifecycle" if source_category == "crm" else et,
            }
        )
    elif et == "payment_failed":
        triggers.append(
            {"action_type": "send_followup_email", "reason": "payment_failed"}
        )
        triggers.append({"action_type": "notify_operator", "reason": "payment_failed"})
    elif et == "cart_abandoned":
        triggers.append(
            {"action_type": "start_nurture_sequence", "reason": "cart_abandoned"}
        )
    elif et in ("email_opened", "email_clicked") or source_category == "email":
        triggers.append(
            {"action_type": "send_followup_email", "reason": et or "email_engagement"}
        )
    elif et in ("sms_delivered",) or source_category == "sms":
        triggers.append(
            {"action_type": "send_followup_sms", "reason": et or "sms_engagement"}
        )
    elif et in _KNOWN_EVENT_TYPES:
        triggers.append(
            {"action_type": "start_nurture_sequence", "reason": "lifecycle_event"}
        )

    if et in _KNOWN_EVENT_TYPES and not triggers:
        triggers.append(
            {"action_type": "notify_operator", "reason": "fallback_known_event"}
        )

    return triggers


def evaluate_payment_sync_readiness(
    provider: str, api_key_present: bool
) -> dict[str, Any]:
    """Payment provider sync: credentials and readiness."""
    p = (provider or "").strip().lower()
    supported = p in PAYMENT_PROVIDERS
    if not supported:
        return {
            "credential_status": "unsupported_provider",
            "blocker_state": "invalid_configuration",
            "operator_action": "configure_supported_payment_provider",
            "sync_ready": False,
        }
    if not api_key_present:
        return {
            "credential_status": "missing",
            "blocker_state": "missing_api_credentials",
            "operator_action": "add_payment_api_key",
            "sync_ready": False,
        }
    return {
        "credential_status": "valid",
        "blocker_state": None,
        "operator_action": None,
        "sync_ready": True,
    }


def evaluate_ad_platform_readiness(
    platform: str, api_key_present: bool, account_id_present: bool
) -> dict[str, Any]:
    """Ad platform import readiness."""
    plat = (platform or "").strip().lower()
    supported = plat in AD_PLATFORMS
    if not supported:
        return {
            "credential_status": "unsupported_platform",
            "blocker_state": "invalid_configuration",
            "operator_action": "connect_supported_ad_platform",
            "import_ready": False,
        }
    if not api_key_present:
        return {
            "credential_status": "missing",
            "blocker_state": "missing_api_credentials",
            "operator_action": "add_ad_platform_api_key",
            "import_ready": False,
        }
    if not account_id_present:
        return {
            "credential_status": "partial",
            "blocker_state": "missing_account_id",
            "operator_action": "link_ad_account_id",
            "import_ready": False,
        }
    return {
        "credential_status": "valid",
        "blocker_state": None,
        "operator_action": None,
        "import_ready": True,
    }


def evaluate_analytics_sync_readiness(
    source: str, api_key_present: bool
) -> dict[str, Any]:
    """Platform analytics / insights sync readiness."""
    src = (source or "").strip().lower()
    if src not in _ANALYTICS_SOURCES:
        return {
            "credential_status": "unsupported_source",
            "blocker_state": "invalid_configuration",
            "operator_action": "configure_supported_analytics_source",
            "sync_ready": False,
        }
    if not api_key_present:
        return {
            "credential_status": "missing",
            "blocker_state": "missing_api_credentials",
            "operator_action": "add_analytics_api_key",
            "sync_ready": False,
        }
    return {
        "credential_status": "valid",
        "blocker_state": None,
        "operator_action": None,
        "sync_ready": True,
    }


def classify_buffer_truth_state(
    job_status: str,
    buffer_post_id: str | None,
    retry_count: int,
    hours_since_submit: float,
) -> dict[str, Any]:
    """Map job status and signals to Buffer truth state; detect stale non-terminal jobs."""
    raw = (job_status or "").strip().lower()
    truth_state = _JOB_STATUS_TO_TRUTH.get(raw, "unknown")

    if buffer_post_id and truth_state in ("submitted_to_buffer", "unknown"):
        truth_state = "accepted_by_buffer"
    if retry_count >= MAX_BUFFER_RETRIES and truth_state not in (
        "published_by_buffer",
        "blocked",
    ):
        truth_state = "blocked"
        operator_action = "max_retries_exceeded_review"
    else:
        operator_action = None

    is_terminal = truth_state in _BUFFER_TERMINAL_FOR_STALE
    is_stale = (
        hours_since_submit > STALE_JOB_THRESHOLD_HOURS
        and not is_terminal
        and truth_state != "blocked"
    )
    if is_stale and operator_action is None:
        operator_action = "investigate_stale_buffer_job"

    return {
        "truth_state": truth_state,
        "is_stale": is_stale,
        "is_duplicate": False,
        "operator_action": operator_action,
    }


def check_duplicate_submit(content_item_id: str, platform: str, existing_keys: set[str]) -> bool:
    """Return True if this content+platform was already submitted."""
    key = f"{content_item_id}:{platform}"
    return key in existing_keys


def compute_retry_backoff(attempt_number: int) -> dict[str, Any]:
    """Exponential backoff; escalate after ESCALATION_THRESHOLD attempts."""
    n = max(1, int(attempt_number))
    backoff_seconds = int(
        RETRY_BACKOFF_BASE_SECONDS * (RETRY_BACKOFF_MULTIPLIER ** (n - 1))
    )
    should_escalate = n >= ESCALATION_THRESHOLD
    next_action = "escalate" if should_escalate else "retry"
    return {
        "backoff_seconds": backoff_seconds,
        "should_escalate": should_escalate,
        "next_action": next_action,
    }


def detect_stale_jobs(hours_since_submit: float, current_state: str) -> dict[str, Any]:
    """Mark jobs stale when over threshold and not in a terminal success state."""
    state = (current_state or "").strip().lower()
    is_terminal = state == "published_by_buffer"
    is_stale = hours_since_submit > STALE_JOB_THRESHOLD_HOURS and not is_terminal
    if not is_stale:
        return {
            "is_stale": False,
            "stale_reason": None,
            "operator_action": None,
        }
    return {
        "is_stale": True,
        "stale_reason": f"no_terminal_resolution_within_{STALE_JOB_THRESHOLD_HOURS}h",
        "operator_action": "review_stale_buffer_execution",
    }


def evaluate_buffer_profile_readiness(
    credential_status: str,
    buffer_profile_id: str | None,
    platform: str,
    is_active: bool,
) -> dict[str, Any]:
    """Buffer profile + platform support for publishing."""
    plat = (platform or "").strip().lower()
    platform_supported = plat in _BUFFER_SUPPORTED_PLATFORMS
    unsupported_modes: list[str] = []
    if not platform_supported:
        unsupported_modes.append(plat or "unknown_platform")

    credential_valid = (credential_status or "").lower() == "valid"
    missing_profile_mapping = not (buffer_profile_id and str(buffer_profile_id).strip())
    inactive_profile = not is_active

    profile_ready = (
        credential_valid
        and not missing_profile_mapping
        and not inactive_profile
        and platform_supported
    )

    blockers: list[str] = []
    if not credential_valid:
        blockers.append("invalid_credentials")
    if missing_profile_mapping:
        blockers.append("missing_buffer_profile_mapping")
    if inactive_profile:
        blockers.append("inactive_buffer_profile")
    if not platform_supported:
        blockers.append("unsupported_platform")

    if not blockers:
        blocker_summary = "none"
        operator_action = None
    else:
        blocker_summary = ";".join(blockers)
        operator_action = "fix_buffer_profile_blockers"

    return {
        "profile_ready": profile_ready,
        "credential_valid": credential_valid,
        "missing_profile_mapping": missing_profile_mapping,
        "inactive_profile": inactive_profile,
        "platform_supported": platform_supported,
        "unsupported_modes": unsupported_modes,
        "blocker_summary": blocker_summary,
        "operator_action": operator_action,
    }


def build_ingestion_summary(
    events_received: int,
    events_processed: int,
    events_skipped: int,
    events_failed: int,
) -> dict[str, Any]:
    """Aggregate ingestion counts into status and attention flags."""
    received = max(0, events_received)
    processed = max(0, events_processed)
    skipped = max(0, events_skipped)
    failed = max(0, events_failed)

    if received == 0:
        success_rate = 0.0
    else:
        success_rate = round(processed / received, 4)

    if failed == 0 and (processed + skipped) >= received and received > 0:
        status = "completed"
    elif failed > 0 and processed == 0 and skipped == 0:
        status = "failed"
    else:
        status = "partial"

    needs_attention = failed > 0 or (received > 0 and success_rate < 0.5)

    return {
        "status": status,
        "success_rate": success_rate,
        "needs_attention": needs_attention,
    }
