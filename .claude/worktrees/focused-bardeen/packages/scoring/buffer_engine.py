"""Buffer Distribution Layer — engine logic for job creation, status mapping, blocker detection."""
from __future__ import annotations

from typing import Any

PUBLISH_MODES = ["queue", "schedule", "publish_now"]
JOB_STATUSES = ["pending", "submitted", "queued", "scheduled", "published", "failed", "cancelled"]
CREDENTIAL_STATUSES = ["connected", "not_connected", "expired", "revoked"]
SYNC_STATUSES = ["synced", "stale", "error", "never"]
BLOCKER_TYPES = [
    "missing_buffer_credentials", "expired_buffer_token", "profile_not_linked",
    "platform_not_supported", "content_not_ready", "rate_limited",
    "account_suspended", "missing_buffer_api_key",
]


def build_publish_payload(content_context: dict[str, Any], profile_context: dict[str, Any]) -> dict[str, Any]:
    """Build the payload that would be sent to Buffer's publish API."""
    platform = profile_context.get("platform", "unknown")
    text = content_context.get("caption", content_context.get("title", ""))
    media_url = content_context.get("media_url")
    link_url = content_context.get("link_url")

    payload: dict[str, Any] = {
        "profile_ids": [profile_context.get("buffer_profile_id", "")],
        "text": text[:280] if platform in ("twitter", "x") else text[:2200],
        "now": False,
    }

    if media_url:
        payload["media"] = {"photo": media_url} if not media_url.endswith((".mp4", ".mov", ".webm")) else {"video": media_url}
    if link_url:
        payload["text"] = f"{payload['text']}\n\n{link_url}" if payload["text"] else link_url

    scheduled_at = content_context.get("scheduled_at")
    if scheduled_at:
        payload["scheduled_at"] = scheduled_at

    return payload


def determine_publish_mode(content_context: dict[str, Any], profile_context: dict[str, Any]) -> str:
    if content_context.get("publish_now", False):
        return "publish_now"
    if content_context.get("scheduled_at"):
        return "schedule"
    return "queue"


def detect_buffer_blockers(
    profiles: list[dict[str, Any]],
    brand_context: dict[str, Any],
) -> list[dict[str, Any]]:
    """Detect blockers preventing Buffer distribution."""
    blockers: list[dict[str, Any]] = []
    has_api_key = brand_context.get("has_buffer_api_key", False)

    if not has_api_key:
        blockers.append({
            "blocker_type": "missing_buffer_api_key",
            "severity": "critical",
            "description": "Buffer API key is not configured. No content can be distributed.",
            "operator_action_needed": "Add BUFFER_API_KEY to environment configuration.",
        })

    if not profiles:
        blockers.append({
            "blocker_type": "profile_not_linked",
            "severity": "critical",
            "description": "No Buffer profiles linked for this brand. Content has no distribution target.",
            "operator_action_needed": "Create and link at least one Buffer profile to a creator account.",
        })

    for p in profiles:
        cred_status = p.get("credential_status", "not_connected")
        if cred_status == "not_connected":
            blockers.append({
                "blocker_type": "missing_buffer_credentials",
                "severity": "high",
                "description": f"Buffer profile '{p.get('display_name', 'unknown')}' ({p.get('platform', '?')}) is not connected.",
                "operator_action_needed": f"Connect Buffer profile for {p.get('display_name', 'unknown')} via Buffer dashboard.",
                "buffer_profile_id_fk": p.get("id"),
            })
        elif cred_status in ("expired", "revoked"):
            blockers.append({
                "blocker_type": "expired_buffer_token",
                "severity": "high",
                "description": f"Buffer credentials for '{p.get('display_name', 'unknown')}' are {cred_status}.",
                "operator_action_needed": f"Re-authenticate Buffer profile for {p.get('display_name', 'unknown')}.",
                "buffer_profile_id_fk": p.get("id"),
            })

    return blockers


def map_buffer_status(buffer_api_status: str | None) -> str:
    """Map Buffer API status strings to our normalized status."""
    mapping = {
        "buffer": "queued",
        "pending": "queued",
        "sent": "published",
        "service": "scheduled",
        "error": "failed",
        "needs_approval": "queued",
    }
    return mapping.get((buffer_api_status or "").lower(), "unknown")


def compute_publish_job_summary(jobs: list[dict[str, Any]]) -> dict[str, int]:
    """Summarize job statuses for dashboard display."""
    summary: dict[str, int] = {"total": len(jobs)}
    for status in JOB_STATUSES:
        summary[status] = sum(1 for j in jobs if j.get("status") == status)
    return summary


def evaluate_profile_readiness(profile: dict[str, Any]) -> dict[str, Any]:
    """Evaluate whether a Buffer profile is ready for publishing."""
    ready = True
    issues: list[str] = []

    if profile.get("credential_status") != "connected":
        ready = False
        issues.append(f"Credential status: {profile.get('credential_status', 'unknown')}")
    if not profile.get("buffer_profile_id"):
        ready = False
        issues.append("No external Buffer profile ID configured")
    if not profile.get("is_active", True):
        ready = False
        issues.append("Profile is inactive")

    return {
        "ready": ready,
        "issues": issues,
        "credential_status": profile.get("credential_status", "not_connected"),
        "platform": profile.get("platform", "unknown"),
    }
