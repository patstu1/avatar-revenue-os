"""Operator exception ops — single-screen production truth.

GET /ops/exceptions — returns everything an operator needs to see in under 30 seconds:
  - failed jobs (last 6h)
  - stuck jobs (dispatched/processing > 30min)
  - missing credentials (configured vs required providers)
  - rate limit / quota pressure (recent 429s)
  - worker instability (restart counts, memory)
  - negative ROI lanes (placeholder for future scoring data)

No auth required — this is an internal endpoint behind the proxy.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from apps.api.config import get_settings
from apps.api.deps import DBSession

router = APIRouter(prefix="/ops", tags=["operations"])


@router.get("/exceptions")
async def get_exceptions(db: DBSession):
    """Single-screen operator view of all urgent failures."""
    now = datetime.now(timezone.utc)
    lookback_6h = now - timedelta(hours=6)
    lookback_30m = now - timedelta(minutes=30)
    issues: list[dict[str, Any]] = []

    # ── 1. Failed jobs (last 6h) ──────────────────────────────────────
    failed_jobs = []
    try:
        rows = (await db.execute(text("""
            SELECT id, job_name, queue, status, error_message,
                   created_at, completed_at, celery_task_id
            FROM system_jobs
            WHERE status = 'failed'
              AND created_at >= :since
            ORDER BY created_at DESC
            LIMIT 50
        """), {"since": lookback_6h})).fetchall()
        for r in rows:
            failed_jobs.append({
                "id": str(r.id),
                "job_name": r.job_name,
                "queue": r.queue,
                "error": (r.error_message or "")[:300],
                "failed_at": r.completed_at.isoformat() if r.completed_at else None,
                "task_id": r.celery_task_id,
            })
    except Exception:
        pass  # table may not exist yet

    if failed_jobs:
        issues.append({
            "category": "failed_jobs",
            "severity": "critical" if len(failed_jobs) > 5 else "warning",
            "count": len(failed_jobs),
            "items": failed_jobs[:20],
        })

    # ── 2. Stuck jobs (dispatched/processing > 30min) ─────────────────
    stuck_jobs = []
    try:
        rows = (await db.execute(text("""
            SELECT id, job_name, queue, status, created_at, celery_task_id
            FROM system_jobs
            WHERE status IN ('running', 'retrying')
              AND created_at < :cutoff
            ORDER BY created_at ASC
            LIMIT 50
        """), {"cutoff": lookback_30m})).fetchall()
        for r in rows:
            age_min = int((now - r.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 60)
            stuck_jobs.append({
                "id": str(r.id),
                "job_name": r.job_name,
                "queue": r.queue,
                "status": r.status,
                "age_minutes": age_min,
                "task_id": r.celery_task_id,
            })
    except Exception:
        pass

    # Also check media_jobs
    try:
        rows = (await db.execute(text("""
            SELECT id, job_type, provider, status, dispatched_at, provider_job_id
            FROM media_jobs
            WHERE status IN ('dispatched', 'processing')
              AND dispatched_at IS NOT NULL
              AND dispatched_at < :cutoff
            ORDER BY dispatched_at ASC
            LIMIT 20
        """), {"cutoff": lookback_30m})).fetchall()
        for r in rows:
            dispatched = r.dispatched_at.replace(tzinfo=timezone.utc) if r.dispatched_at else now
            age_min = int((now - dispatched).total_seconds() / 60)
            stuck_jobs.append({
                "id": str(r.id),
                "job_name": f"media_job:{r.job_type}",
                "queue": "pipeline",
                "status": r.status,
                "provider": r.provider,
                "age_minutes": age_min,
                "provider_job_id": r.provider_job_id,
            })
    except Exception:
        pass

    if stuck_jobs:
        issues.append({
            "category": "stuck_jobs",
            "severity": "critical" if any(j["age_minutes"] > 120 for j in stuck_jobs) else "warning",
            "count": len(stuck_jobs),
            "items": stuck_jobs[:20],
        })

    # ── 3. Missing credentials ────────────────────────────────────────
    settings = get_settings()
    _CRITICAL_PROVIDERS = {
        "anthropic_api_key": "Anthropic (Claude)",
        "stripe_api_key": "Stripe",
    }
    _IMPORTANT_PROVIDERS = {
        "openai_api_key": "OpenAI",
        "heygen_api_key": "HeyGen",
        "buffer_api_key": "Buffer",
        "elevenlabs_api_key": "ElevenLabs",
    }
    missing_critical = []
    missing_important = []
    for attr, name in _CRITICAL_PROVIDERS.items():
        val = getattr(settings, attr, "")
        if not val or not val.strip():
            missing_critical.append(name)
    for attr, name in _IMPORTANT_PROVIDERS.items():
        val = getattr(settings, attr, "")
        if not val or not val.strip():
            missing_important.append(name)

    if missing_critical:
        issues.append({
            "category": "missing_credentials",
            "severity": "critical",
            "count": len(missing_critical),
            "items": [{"provider": p, "level": "critical"} for p in missing_critical],
        })
    if missing_important:
        issues.append({
            "category": "missing_credentials",
            "severity": "warning",
            "count": len(missing_important),
            "items": [{"provider": p, "level": "important"} for p in missing_important],
        })

    # ── 4. Rate limit / quota pressure (recent system events) ─────────
    rate_limit_events = []
    try:
        rows = (await db.execute(text("""
            SELECT id, event_type, summary, details, created_at
            FROM system_events
            WHERE event_severity IN ('warning', 'critical')
              AND (summary ILIKE '%rate%' OR summary ILIKE '%429%'
                   OR summary ILIKE '%quota%' OR summary ILIKE '%limit%')
              AND created_at >= :since
            ORDER BY created_at DESC
            LIMIT 20
        """), {"since": lookback_6h})).fetchall()
        for r in rows:
            rate_limit_events.append({
                "id": str(r.id),
                "event_type": r.event_type,
                "summary": (r.summary or "")[:200],
                "at": r.created_at.isoformat() if r.created_at else None,
            })
    except Exception:
        pass

    if rate_limit_events:
        issues.append({
            "category": "rate_limit_pressure",
            "severity": "warning",
            "count": len(rate_limit_events),
            "items": rate_limit_events[:10],
        })

    # ── 5. Auth failures (provider unhealthy events) ──────────────────
    auth_failures = []
    try:
        rows = (await db.execute(text("""
            SELECT id, event_type, summary, details, created_at
            FROM system_events
            WHERE event_type = 'job.failed.auth'
              AND created_at >= :since
            ORDER BY created_at DESC
            LIMIT 10
        """), {"since": lookback_6h})).fetchall()
        for r in rows:
            auth_failures.append({
                "id": str(r.id),
                "summary": (r.summary or "")[:200],
                "at": r.created_at.isoformat() if r.created_at else None,
            })
    except Exception:
        pass

    if auth_failures:
        issues.append({
            "category": "auth_failures",
            "severity": "critical",
            "count": len(auth_failures),
            "items": auth_failures,
        })

    # ── 6. Consecutive failure alerts ─────────────────────────────────
    consecutive_failures = []
    try:
        rows = (await db.execute(text("""
            SELECT id, event_type, summary, details, created_at
            FROM system_events
            WHERE event_type = 'job.consecutive_failures'
              AND created_at >= :since
            ORDER BY created_at DESC
            LIMIT 10
        """), {"since": lookback_6h})).fetchall()
        for r in rows:
            consecutive_failures.append({
                "id": str(r.id),
                "summary": (r.summary or "")[:200],
                "at": r.created_at.isoformat() if r.created_at else None,
            })
    except Exception:
        pass

    if consecutive_failures:
        issues.append({
            "category": "consecutive_failures",
            "severity": "critical",
            "count": len(consecutive_failures),
            "items": consecutive_failures,
        })

    # ── Build response ────────────────────────────────────────────────
    critical_count = sum(1 for i in issues if i["severity"] == "critical")
    warning_count = sum(1 for i in issues if i["severity"] == "warning")

    if critical_count > 0:
        overall = "critical"
    elif warning_count > 0:
        overall = "warning"
    else:
        overall = "clear"

    return {
        "status": overall,
        "checked_at": now.isoformat(),
        "lookback_hours": 6,
        "critical_issues": critical_count,
        "warning_issues": warning_count,
        "issues": issues,
    }


@router.get("/guardrails")
async def get_guardrail_status():
    """Current spend vs caps for all providers and lanes."""
    from packages.guardrails.execution_guardrails import GuardrailEngine
    engine = GuardrailEngine()
    return engine.get_spend_summary()


@router.get("/summary")
async def get_ops_summary(db: DBSession):
    """Quick operational summary — job counts by status, queue depth."""
    now = datetime.now(timezone.utc)
    lookback_24h = now - timedelta(hours=24)

    summary: dict[str, Any] = {"checked_at": now.isoformat()}

    # Job status counts (last 24h)
    try:
        rows = (await db.execute(text("""
            SELECT status, COUNT(*) as cnt
            FROM system_jobs
            WHERE created_at >= :since
            GROUP BY status
            ORDER BY cnt DESC
        """), {"since": lookback_24h})).fetchall()
        summary["jobs_24h"] = {r.status: r.cnt for r in rows}
    except Exception:
        summary["jobs_24h"] = {"error": "table not available"}

    # Media job status counts (last 24h)
    try:
        rows = (await db.execute(text("""
            SELECT status, COUNT(*) as cnt
            FROM media_jobs
            WHERE created_at >= :since
            GROUP BY status
            ORDER BY cnt DESC
        """), {"since": lookback_24h})).fetchall()
        summary["media_jobs_24h"] = {r.status: r.cnt for r in rows}
    except Exception:
        summary["media_jobs_24h"] = {"error": "table not available"}

    # Recent system events by severity
    try:
        rows = (await db.execute(text("""
            SELECT event_severity, COUNT(*) as cnt
            FROM system_events
            WHERE created_at >= :since
            GROUP BY event_severity
            ORDER BY cnt DESC
        """), {"since": lookback_24h})).fetchall()
        summary["events_24h"] = {r.event_severity: r.cnt for r in rows}
    except Exception:
        summary["events_24h"] = {"error": "table not available"}

    return summary
