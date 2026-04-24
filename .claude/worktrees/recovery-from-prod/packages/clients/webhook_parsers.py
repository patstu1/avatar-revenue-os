"""Provider-specific webhook payload parsers for async media jobs.

Each parser extracts a standardized tuple from the provider's unique
callback format. New providers are added by registering a function —
no changes to the webhook route itself.

Usage:
    from packages.clients.webhook_parsers import parse_webhook_payload

    result = parse_webhook_payload("heygen", raw_payload)
    # result.job_id, result.status, result.output_url, result.error
"""
from __future__ import annotations

import structlog
from dataclasses import dataclass
from typing import Callable, Optional

logger = structlog.get_logger()


@dataclass(frozen=True)
class WebhookParseResult:
    """Standardized output from any provider webhook parser."""
    job_id: Optional[str]
    status: str          # "completed" | "failed" | "processing"
    output_url: Optional[str]
    error: Optional[str]


# Type alias for parser functions
ParserFn = Callable[[dict], WebhookParseResult]

# ── Registry ─────────────────────────────────────────────────────────
_PARSERS: dict[str, ParserFn] = {}


def register_parser(provider_key: str):
    """Decorator to register a webhook payload parser for a provider."""
    def decorator(fn: ParserFn) -> ParserFn:
        _PARSERS[provider_key] = fn
        return fn
    return decorator


def parse_webhook_payload(provider_key: str, payload: dict) -> WebhookParseResult:
    """Look up the parser for *provider_key* and extract standardized fields.

    Raises ValueError if no parser is registered for the provider.
    """
    parser = _PARSERS.get(provider_key)
    if parser is None:
        raise ValueError(f"No webhook parser registered for provider '{provider_key}'")
    return parser(payload)


def registered_providers() -> list[str]:
    """Return list of provider keys with registered parsers."""
    return list(_PARSERS.keys())


# =====================================================================
# Provider-specific parsers
# =====================================================================

def _normalize_status(raw: str) -> str:
    """Map provider-specific status strings to our canonical set."""
    raw_lower = raw.lower().strip()
    completed_synonyms = {"completed", "complete", "done", "success", "succeeded", "ready", "finished"}
    failed_synonyms = {"failed", "failure", "error", "errored", "cancelled", "canceled", "rejected"}
    processing_synonyms = {"processing", "pending", "in_progress", "running", "queued", "generating", "rendering"}

    if raw_lower in completed_synonyms:
        return "completed"
    if raw_lower in failed_synonyms:
        return "failed"
    if raw_lower in processing_synonyms:
        return "processing"
    # Default: pass through as-is but warn
    logger.warning("webhook_parser.unknown_status", raw_status=raw)
    return raw_lower


# ── HeyGen ───────────────────────────────────────────────────────────
@register_parser("heygen")
def _parse_heygen(payload: dict) -> WebhookParseResult:
    """HeyGen video avatar webhook.

    Typical payload:
    {
        "event_type": "avatar_video.success",
        "data": {
            "video_id": "...",
            "url": "https://...",
            "status": "completed"
        }
    }
    """
    data = payload.get("data", payload)
    event_type = payload.get("event_type", "")

    # Determine status from event_type or data.status
    if "success" in event_type or "complete" in event_type:
        status = "completed"
    elif "fail" in event_type or "error" in event_type:
        status = "failed"
    else:
        status = _normalize_status(data.get("status", "processing"))

    return WebhookParseResult(
        job_id=data.get("video_id") or data.get("id") or data.get("job_id"),
        status=status,
        output_url=data.get("url") or data.get("video_url"),
        error=data.get("error") or data.get("error_message") or data.get("msg"),
    )


# ── D-ID ─────────────────────────────────────────────────────────────
@register_parser("did")
def _parse_did(payload: dict) -> WebhookParseResult:
    """D-ID talking avatar webhook.

    Typical payload:
    {
        "id": "tlk_...",
        "status": "done",
        "result_url": "https://...",
        "error": { "description": "..." }
    }
    """
    error_obj = payload.get("error")
    error_msg = None
    if isinstance(error_obj, dict):
        error_msg = error_obj.get("description") or error_obj.get("message")
    elif isinstance(error_obj, str):
        error_msg = error_obj

    return WebhookParseResult(
        job_id=payload.get("id") or payload.get("job_id"),
        status=_normalize_status(payload.get("status", "processing")),
        output_url=payload.get("result_url") or payload.get("url"),
        error=error_msg,
    )


# ── Runway ───────────────────────────────────────────────────────────
@register_parser("runway")
def _parse_runway(payload: dict) -> WebhookParseResult:
    """Runway Gen-3/Gen-4 video generation webhook.

    Typical payload:
    {
        "id": "...",
        "status": "SUCCEEDED",
        "output": ["https://..."],
        "failure": "..."
    }
    """
    output = payload.get("output", [])
    output_url = output[0] if isinstance(output, list) and output else payload.get("output_url")

    raw_status = payload.get("status", "processing")
    # Runway uses SUCCEEDED/FAILED
    if raw_status.upper() == "SUCCEEDED":
        status = "completed"
    elif raw_status.upper() == "FAILED":
        status = "failed"
    else:
        status = _normalize_status(raw_status)

    return WebhookParseResult(
        job_id=payload.get("id") or payload.get("task_id"),
        status=status,
        output_url=output_url,
        error=payload.get("failure") or payload.get("error"),
    )


# ── ElevenLabs ───────────────────────────────────────────────────────
@register_parser("elevenlabs")
def _parse_elevenlabs(payload: dict) -> WebhookParseResult:
    """ElevenLabs voice/music generation webhook.

    Typical payload:
    {
        "status": "completed",
        "request_id": "...",
        "output_url": "https://...",
        "error_message": "..."
    }
    """
    return WebhookParseResult(
        job_id=payload.get("request_id") or payload.get("id") or payload.get("job_id"),
        status=_normalize_status(payload.get("status", "processing")),
        output_url=payload.get("output_url") or payload.get("url") or payload.get("audio_url"),
        error=payload.get("error_message") or payload.get("error"),
    )


# ── Kling ────────────────────────────────────────────────────────────
@register_parser("kling")
def _parse_kling(payload: dict) -> WebhookParseResult:
    """Kling AI video generation webhook.

    Typical payload:
    {
        "task_id": "...",
        "task_status": "succeed",
        "task_result": {
            "videos": [{"url": "https://..."}]
        },
        "task_status_msg": "..."
    }
    """
    raw_status = payload.get("task_status", payload.get("status", "processing"))
    if raw_status.lower() in ("succeed", "succeeded"):
        status = "completed"
    elif raw_status.lower() in ("failed", "fail"):
        status = "failed"
    else:
        status = _normalize_status(raw_status)

    # Extract URL from nested task_result
    output_url = None
    task_result = payload.get("task_result", {})
    if isinstance(task_result, dict):
        videos = task_result.get("videos", [])
        if videos and isinstance(videos, list) and isinstance(videos[0], dict):
            output_url = videos[0].get("url")
        if not output_url:
            images = task_result.get("images", [])
            if images and isinstance(images, list) and isinstance(images[0], dict):
                output_url = images[0].get("url")
    if not output_url:
        output_url = payload.get("output_url") or payload.get("url")

    return WebhookParseResult(
        job_id=payload.get("task_id") or payload.get("id"),
        status=status,
        output_url=output_url,
        error=payload.get("task_status_msg") if status == "failed" else None,
    )


# ── Flux (Black Forest Labs) ────────────────────────────────────────
@register_parser("flux")
def _parse_flux(payload: dict) -> WebhookParseResult:
    """Flux image generation webhook.

    Typical payload:
    {
        "id": "...",
        "status": "Ready",
        "result": {
            "sample": "https://..."
        },
        "error": "..."
    }
    """
    raw_status = payload.get("status", "processing")
    if raw_status.lower() in ("ready", "succeeded", "completed"):
        status = "completed"
    elif raw_status.lower() in ("failed", "error"):
        status = "failed"
    else:
        status = _normalize_status(raw_status)

    result = payload.get("result", {})
    output_url = None
    if isinstance(result, dict):
        output_url = result.get("sample") or result.get("url") or result.get("image_url")
    if not output_url:
        output_url = payload.get("output_url") or payload.get("url")

    return WebhookParseResult(
        job_id=payload.get("id") or payload.get("request_id"),
        status=status,
        output_url=output_url,
        error=payload.get("error"),
    )
