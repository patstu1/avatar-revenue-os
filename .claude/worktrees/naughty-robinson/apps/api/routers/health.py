"""Health check endpoints — liveness, readiness, deep checks, and provider status."""
from __future__ import annotations

import time
from typing import Any

import httpx
from redis.asyncio import Redis as AsyncRedis
from fastapi import APIRouter
from sqlalchemy import text

from apps.api.config import Settings, get_settings
from apps.api.deps import DBSession

router = APIRouter()


# ── Basic liveness ──────────────────────────────────────────────────────────

@router.get("/health")
@router.get("/healthz")
async def healthz():
    """Liveness probe — confirms the process is running."""
    return {"status": "ok", "service": "avatar-revenue-os-api"}


# ── Readiness (legacy alias kept for backwards compat) ──────────────────────

@router.get("/readyz")
async def readyz(db: DBSession):
    """Readiness probe — checks Postgres and Redis connectivity."""
    checks: dict[str, bool] = {}

    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    try:
        settings = get_settings()
        r = AsyncRedis.from_url(settings.redis_url, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        checks["redis"] = True
    except Exception:
        checks["redis"] = False

    try:
        settings = get_settings()
        r_celery = AsyncRedis.from_url(settings.celery_broker_url, socket_connect_timeout=2)
        await r_celery.ping()
        await r_celery.aclose()
        checks["celery_broker"] = True
    except Exception:
        checks["celery_broker"] = False

    all_ok = all(checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
    }


# ── Deep health check ──────────────────────────────────────────────────────

@router.get("/health/deep")
async def health_deep(db: DBSession):
    """Deep health check — DB, Redis, Celery ping, S3 connectivity."""
    settings = get_settings()
    checks: dict[str, dict[str, Any]] = {}

    # Database
    t0 = time.monotonic()
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        checks["database"] = {"ok": True, "latency_ms": latency_ms}
    except Exception as exc:
        checks["database"] = {"ok": False, "error": str(exc)}

    # Redis
    t0 = time.monotonic()
    try:
        r = AsyncRedis.from_url(settings.redis_url, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        checks["redis"] = {"ok": True, "latency_ms": latency_ms}
    except Exception as exc:
        checks["redis"] = {"ok": False, "error": str(exc)}

    # Celery broker
    t0 = time.monotonic()
    try:
        r_celery = AsyncRedis.from_url(settings.celery_broker_url, socket_connect_timeout=2)
        await r_celery.ping()
        await r_celery.aclose()
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        checks["celery_broker"] = {"ok": True, "latency_ms": latency_ms}
    except Exception as exc:
        checks["celery_broker"] = {"ok": False, "error": str(exc)}

    # S3
    t0 = time.monotonic()
    try:
        if settings.s3_endpoint_url and settings.s3_access_key_id:
            async with httpx.AsyncClient(timeout=5) as client:
                # HEAD request to endpoint to verify connectivity
                resp = await client.head(settings.s3_endpoint_url)
                latency_ms = round((time.monotonic() - t0) * 1000, 1)
                checks["s3"] = {"ok": resp.status_code < 500, "latency_ms": latency_ms}
        else:
            checks["s3"] = {"ok": False, "error": "not_configured"}
    except Exception as exc:
        checks["s3"] = {"ok": False, "error": str(exc)}

    all_ok = all(c.get("ok", False) for c in checks.values() if c.get("error") != "not_configured")
    return {
        "status": "healthy" if all_ok else "degraded",
        "checks": checks,
    }


# ── Provider status ─────────────────────────────────────────────────────────

_PROVIDER_MAP: dict[str, tuple[str, str]] = {
    # (settings_attr, display_name)
    "anthropic": ("anthropic_api_key", "Anthropic (Claude)"),
    "openai": ("openai_api_key", "OpenAI"),
    "google_ai": ("google_ai_api_key", "Google AI (Gemini)"),
    "deepseek": ("deepseek_api_key", "DeepSeek"),
    "groq": ("groq_api_key", "Groq"),
    "xai": ("xai_api_key", "xAI (Grok)"),
    "fal": ("fal_api_key", "fal.ai"),
    "replicate": ("replicate_api_token", "Replicate"),
    "runway": ("runway_api_key", "Runway"),
    "kling": ("kling_api_key", "Kling AI"),
    "heygen": ("heygen_api_key", "HeyGen"),
    "did": ("did_api_key", "D-ID"),
    "tavus": ("tavus_api_key", "Tavus"),
    "elevenlabs": ("elevenlabs_api_key", "ElevenLabs"),
    "fish_audio": ("fish_audio_api_key", "Fish Audio"),
    "mistral": ("mistral_api_key", "Mistral (Voxtral)"),
    "suno": ("suno_api_key", "Suno"),
    "mubert": ("mubert_api_key", "Mubert"),
    "buffer": ("buffer_api_key", "Buffer"),
    "publer": ("publer_api_key", "Publer"),
    "ayrshare": ("ayrshare_api_key", "Ayrshare"),
    "serpapi": ("serpapi_key", "SerpAPI"),
    "stripe": ("stripe_api_key", "Stripe"),
    "youtube": ("youtube_api_key", "YouTube Data API"),
}


@router.get("/health/providers")
async def health_providers():
    """Report which external providers have API keys configured."""
    settings = get_settings()
    providers: dict[str, dict[str, Any]] = {}

    for key, (attr, display_name) in _PROVIDER_MAP.items():
        api_key = getattr(settings, attr, "")
        configured = bool(api_key and api_key.strip())
        providers[key] = {
            "name": display_name,
            "configured": configured,
        }

    configured_count = sum(1 for p in providers.values() if p["configured"])
    total = len(providers)

    return {
        "status": "ok",
        "configured": configured_count,
        "total": total,
        "providers": providers,
    }
