"""Dependency checker — surfaces missing credentials, unhealthy workers, and
blocked runtime dependencies so the system never fakes success.

Used by:
- Blueprint approval (hard gate — blocks if critical deps missing)
- Hourly beat task (proactive alerting)
- Brain ops status endpoint (operator visibility)
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Critical vs optional providers
# ---------------------------------------------------------------------------
_CRITICAL_ENV = [
    "DATABASE_URL",
    "REDIS_URL",
    "API_SECRET_KEY",
]

_CRITICAL_PROVIDERS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "smtp": "SMTP_HOST",
}

_OPTIONAL_PROVIDERS = {
    "openai": "OPENAI_API_KEY",
    "google_ai": "GOOGLE_AI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "elevenlabs": "ELEVENLABS_API_KEY",
    "heygen": "HEYGEN_API_KEY",
    "runway": "RUNWAY_API_KEY",
    "fal": "FAL_API_KEY",
    "buffer": "BUFFER_API_KEY",
    "stripe": "STRIPE_API_KEY",
    "ayrshare": "AYRSHARE_API_KEY",
}


async def check_runtime_dependencies(db: AsyncSession) -> dict[str, Any]:
    """Full system dependency check.

    Returns structured dict with overall status, per-provider checks,
    env var checks, worker health, and a list of blockers.
    """
    result: dict[str, Any] = {
        "status": "healthy",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "env_vars": {},
        "critical_providers": {},
        "optional_providers": {},
        "workers": {},
        "beat": {},
        "blockers": [],
    }

    # ── Env vars ──
    for var in _CRITICAL_ENV:
        val = os.environ.get(var, "")
        present = bool(val and val not in ("", "changeme"))
        result["env_vars"][var] = "configured" if present else "missing"
        if not present:
            result["blockers"].append(f"env:{var}")

    # ── Critical providers ──
    for name, env_key in _CRITICAL_PROVIDERS.items():
        val = os.environ.get(env_key, "")
        present = bool(val and val.strip())
        result["critical_providers"][name] = "configured" if present else "missing"
        if not present:
            result["blockers"].append(f"provider:{name}")

    # ── Optional providers ──
    for name, env_key in _OPTIONAL_PROVIDERS.items():
        val = os.environ.get(env_key, "")
        present = bool(val and val.strip())
        result["optional_providers"][name] = "configured" if present else "missing"

    # ── Worker health (check recent job activity per queue) ──
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        rows = (await db.execute(
            text(
                "SELECT queue, COUNT(*) AS cnt "
                "FROM system_jobs "
                "WHERE created_at > :cutoff "
                "GROUP BY queue"
            ),
            {"cutoff": cutoff},
        )).all()
        active_queues = {r[0]: r[1] for r in rows}
        for q in ["default", "generation", "publishing", "analytics", "outreach"]:
            count = active_queues.get(q, 0)
            result["workers"][q] = "active" if count > 0 else "idle"
    except Exception:
        result["workers"]["_error"] = "could_not_query_system_jobs"

    # ── Beat scheduler health ──
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
        recent_events = (await db.execute(
            text(
                "SELECT COUNT(*) FROM system_events "
                "WHERE created_at > :cutoff AND event_type LIKE 'job.%%'"
            ),
            {"cutoff": cutoff},
        )).scalar() or 0
        result["beat"]["status"] = "active" if recent_events > 0 else "possibly_down"
        result["beat"]["recent_job_events"] = recent_events
        if recent_events == 0:
            result["blockers"].append("beat:scheduler_possibly_down")
    except Exception:
        result["beat"]["status"] = "unknown"

    # ── Overall status ──
    if result["blockers"]:
        critical_blockers = [b for b in result["blockers"] if not b.startswith("beat:")]
        if critical_blockers:
            result["status"] = "critical"
        else:
            result["status"] = "degraded"

    return result


async def check_blueprint_readiness(db: AsyncSession) -> dict[str, Any]:
    """Subset check for blueprint execution prerequisites.

    Returns {"ready": bool, "blockers": [...]} — used as a hard gate
    before blueprint approval dispatches execution.
    """
    blockers: list[str] = []

    # Must have at least one AI text provider
    has_ai = any(
        bool(os.environ.get(key, "").strip())
        for key in ["ANTHROPIC_API_KEY", "GOOGLE_AI_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY"]
    )
    if not has_ai:
        blockers.append("No AI text provider configured (need at least one of: ANTHROPIC, GOOGLE_AI, DEEPSEEK, OPENAI)")

    # Must have DB connectivity (if we got here, it works, but check anyway)
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        blockers.append("Database not reachable")

    # Must have SMTP for onboarding emails (warn, don't block)
    smtp_host = os.environ.get("SMTP_HOST", "").strip()
    if not smtp_host:
        blockers.append("SMTP not configured — onboarding emails will not send")

    return {
        "ready": len(blockers) == 0,
        "blockers": blockers,
    }
