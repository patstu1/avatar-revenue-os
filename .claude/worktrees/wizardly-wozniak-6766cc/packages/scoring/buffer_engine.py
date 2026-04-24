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


def _is_video_url(url: str) -> bool:
    if not url:
        return False
    lower = url.lower()
    return lower.endswith((".mp4", ".mov", ".webm", ".m4v")) or ("video" in lower and "unsplash" not in lower)


def build_publish_payload(content_context: dict[str, Any], profile_context: dict[str, Any]) -> dict[str, Any]:
    """Build a platform-aware payload for Buffer's GraphQL createPost mutation.

    Produces the exact shape that BufferClient will forward as the `input` variable
    to Buffer's createPost GraphQL mutation, including platform-specific metadata
    and assets. The shape is:

        {
          "text": str,
          "channelId": str,          # added by caller at submit time
          "schedulingType": "automatic",
          "mode": "addToQueue" | "shareNow" | "shareNext",
          "metadata": {<platform>: {...}},   # platform-specific (Instagram, etc.)
          "assets": {"images": [{"url": ...}]} | {"videos": [{"url": ...}]},
        }

    Platform-specific behavior:
      - instagram: requires metadata.instagram.type in {post, story, reel}
        and metadata.instagram.shouldShareToFeed (bool). Requires at least one
        image or video asset.
      - twitter / x: text <= 280 chars. Media optional.
      - tiktok: requires video asset. metadata.tiktok minimal.
      - youtube: requires video asset.
      - linkedin / facebook: text + optional media.

    The caller (`submit_job_to_buffer`) will add `channelId` and `mode` before
    sending to BufferClient. This function returns the reusable core payload
    so it can be persisted in `buffer_publish_jobs.payload_json` and inspected.
    """
    platform = (profile_context.get("platform") or "unknown").lower()
    text = content_context.get("caption") or content_context.get("title") or ""
    media_url = content_context.get("media_url")
    link_url = content_context.get("link_url")

    # Platform character limits
    if platform in ("twitter", "x"):
        text_limit = 280
    elif platform == "linkedin":
        text_limit = 3000
    else:
        text_limit = 2200

    # Append link to text if present (Buffer does not have a dedicated link field
    # in createPost; link_url is rendered inline).
    if link_url:
        text = f"{text}\n\n{link_url}" if text else link_url

    payload: dict[str, Any] = {
        "text": text[:text_limit],
        "schedulingType": "automatic",
    }

    # Assets
    if media_url:
        if _is_video_url(media_url):
            payload["assets"] = {"videos": [{"url": media_url}]}
        else:
            payload["assets"] = {"images": [{"url": media_url}]}

    # Platform-specific metadata
    metadata: dict[str, Any] = {}

    if platform == "instagram":
        # Determine post type from content signals
        content_type = (content_context.get("content_type") or "").upper()
        explicit_ig_type = (content_context.get("instagram_type") or "").lower()

        if explicit_ig_type in ("post", "story", "reel"):
            ig_type = explicit_ig_type
        elif content_type == "STORY":
            ig_type = "story"
        elif content_type in ("SHORT_VIDEO", "LONG_VIDEO") or (media_url and _is_video_url(media_url)):
            # Short videos on Instagram are reels. Default for video content.
            ig_type = "reel"
        else:
            # Static image / carousel → feed post
            ig_type = "post"

        metadata["instagram"] = {
            "type": ig_type,
            "shouldShareToFeed": True,
        }

    elif platform == "tiktok":
        metadata["tiktok"] = {}

    elif platform == "youtube":
        # YouTube community posts or Shorts — minimal metadata
        metadata["youtube"] = {}

    if metadata:
        payload["metadata"] = metadata

    scheduled_at = content_context.get("scheduled_at")
    if scheduled_at:
        payload["dueAt"] = scheduled_at
        payload["schedulingType"] = "customScheduled"

    # Legacy fields preserved for backward compat with older job rows
    payload["_platform"] = platform
    payload["_profile_ids"] = [profile_context.get("buffer_profile_id", "")]

    return payload


def validate_publish_payload(payload: dict[str, Any], platform: str) -> dict[str, Any]:
    """Return {"ok": bool, "reason": str} — honest pre-submit validation.

    Fails closed: any missing required field blocks submission.
    """
    platform = (platform or "unknown").lower()
    text = payload.get("text") or ""
    assets = payload.get("assets") or {}
    has_image = bool(assets.get("images"))
    has_video = bool(assets.get("videos"))
    has_media = has_image or has_video

    if not text.strip() and not has_media:
        return {"ok": False, "reason": "empty_post_no_text_and_no_media"}

    if platform == "instagram":
        if not has_media:
            return {"ok": False, "reason": "instagram_requires_image_or_video"}
        meta = (payload.get("metadata") or {}).get("instagram") or {}
        if meta.get("type") not in ("post", "story", "reel"):
            return {"ok": False, "reason": "instagram_requires_type_metadata"}
        if "shouldShareToFeed" not in meta:
            return {"ok": False, "reason": "instagram_requires_shouldShareToFeed"}

    elif platform == "tiktok":
        if not has_video:
            return {"ok": False, "reason": "tiktok_requires_video"}

    elif platform == "youtube":
        if not has_video:
            return {"ok": False, "reason": "youtube_requires_video"}

    elif platform in ("twitter", "x"):
        if len(text) > 280:
            return {"ok": False, "reason": "x_text_exceeds_280_chars"}

    return {"ok": True, "reason": ""}


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
