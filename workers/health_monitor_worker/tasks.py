"""Health Monitor Worker — periodic system health checks with self-healing signals.

Checks:
  a) All configured providers: credential health + live API connectivity
  b) Stuck MediaJobs (processing longer than typical)
  c) Failed SystemJobs that haven't been retried
  d) Emits a health report event with green/yellow/red status per component
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache

import httpx
import structlog
from celery import shared_task
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from packages.db.models.integration_registry import IntegrationProvider
from packages.db.models.media_jobs import MediaJob
from packages.db.models.system import SystemJob
from packages.db.models.system_events import SystemEvent
from packages.db.session import get_sync_engine
from workers.base_task import TrackedTask

logger = structlog.get_logger()

# Thresholds
STUCK_MEDIA_JOB_MINUTES = 30  # MediaJob processing longer than this is "stuck"
FAILED_JOB_LOOKBACK_HOURS = 6  # Look for unretried failures in this window
HEALTH_PING_TIMEOUT = 5.0  # seconds for provider health pings

# Lightweight health-check endpoints per provider (cheap/free calls)
_HEALTH_ENDPOINTS: dict[str, dict] = {
    "claude": {"url": "https://api.anthropic.com/v1/models", "method": "GET", "auth_header": "x-api-key"},
    "gemini_flash": {"url": "https://generativelanguage.googleapis.com/v1beta/models", "method": "GET", "auth_param": "key"},
    "openai_image": {"url": "https://api.openai.com/v1/models", "method": "GET", "auth_header": "Authorization", "auth_prefix": "Bearer "},
    "deepseek": {"url": "https://api.deepseek.com/models", "method": "GET", "auth_header": "Authorization", "auth_prefix": "Bearer "},
    # /v1/models works with any valid API key; /v1/user requires user_read scope which not all keys have
    "elevenlabs": {"url": "https://api.elevenlabs.io/v1/models", "method": "GET", "auth_header": "xi-api-key"},
    "heygen": {"url": "https://api.heygen.com/v2/user/remaining_quota", "method": "GET", "auth_header": "X-Api-Key"},
    "runway": {"url": "https://api.dev.runwayml.com/v1/tasks", "method": "GET", "auth_header": "Authorization", "auth_prefix": "Bearer "},
    "stripe": {"url": "https://api.stripe.com/v1/balance", "method": "GET", "auth_header": "Authorization", "auth_prefix": "Bearer "},
    "buffer": {"url": "https://api.buffer.com", "method": "POST", "auth_header": "Authorization", "auth_prefix": "Bearer ",
               "body": {"query": "{ account { id } }"}},
}


@lru_cache(maxsize=1)
def _engine():
    return get_sync_engine()


def _ping_provider(api_key: str, provider_key: str) -> dict:
    """Make a lightweight API call to verify the provider is reachable and the key is valid.

    Returns dict with: reachable (bool), latency_ms (int), status_code (int), error (str|None)
    """
    endpoint = _HEALTH_ENDPOINTS.get(provider_key)
    if not endpoint or not api_key:
        return {"reachable": None, "latency_ms": None, "status_code": None, "error": "no health endpoint defined"}

    url = endpoint["url"]
    method = endpoint.get("method", "GET")
    headers: dict[str, str] = {}
    params: dict[str, str] = {}

    # Build auth
    if "auth_header" in endpoint:
        prefix = endpoint.get("auth_prefix", "")
        headers[endpoint["auth_header"]] = f"{prefix}{api_key}"
    if "auth_param" in endpoint:
        params[endpoint["auth_param"]] = api_key

    try:
        start = datetime.now(timezone.utc)
        with httpx.Client(timeout=HEALTH_PING_TIMEOUT) as client:
            if method == "POST":
                resp = client.post(url, headers=headers, params=params, json=endpoint.get("body"))
            else:
                resp = client.get(url, headers=headers, params=params)
        elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

        if resp.status_code in (200, 201):
            return {"reachable": True, "latency_ms": elapsed_ms, "status_code": resp.status_code, "error": None}
        elif resp.status_code in (401, 403):
            return {"reachable": True, "latency_ms": elapsed_ms, "status_code": resp.status_code, "error": "auth_invalid"}
        elif resp.status_code == 429:
            return {"reachable": True, "latency_ms": elapsed_ms, "status_code": resp.status_code, "error": "rate_limited"}
        else:
            return {"reachable": True, "latency_ms": elapsed_ms, "status_code": resp.status_code, "error": f"HTTP {resp.status_code}"}
    except httpx.ConnectTimeout:
        return {"reachable": False, "latency_ms": None, "status_code": None, "error": "connect_timeout"}
    except httpx.ReadTimeout:
        return {"reachable": False, "latency_ms": None, "status_code": None, "error": "read_timeout"}
    except Exception as exc:
        return {"reachable": False, "latency_ms": None, "status_code": None, "error": str(exc)[:200]}


def _check_providers(session: Session) -> dict:
    """Check all enabled integration providers: credential health + live API ping."""
    from apps.api.services.integration_manager import _decrypt

    providers = session.execute(
        select(IntegrationProvider).where(IntegrationProvider.is_enabled.is_(True))
    ).scalars().all()

    results = {}
    unhealthy_count = 0

    for p in providers:
        key = p.provider_key
        has_db_cred = bool(p.api_key_encrypted)

        # Can we decrypt the stored key?
        decrypted_ok = False
        decrypted_key = None
        if has_db_cred:
            try:
                decrypted_key = _decrypt(p.api_key_encrypted)
                decrypted_ok = bool(decrypted_key)
            except Exception:
                decrypted_ok = False

        # Live connectivity ping (only if we have a key to test)
        ping_result = None
        if decrypted_key and key in _HEALTH_ENDPOINTS:
            ping_result = _ping_provider(decrypted_key, key)

            # Update provider health state in DB
            if ping_result["reachable"] and ping_result.get("status_code") in (200, 201):
                p.health_status = "healthy"
                p.last_health_check = datetime.now(timezone.utc)
                if ping_result.get("latency_ms") is not None:
                    p.avg_latency_ms = ping_result["latency_ms"]
            elif ping_result.get("error") == "auth_invalid":
                p.health_status = "auth_failed"
                p.last_health_check = datetime.now(timezone.utc)
            elif ping_result["reachable"] is False:
                p.health_status = "unreachable"
                p.last_health_check = datetime.now(timezone.utc)

        healthy = decrypted_ok and (
            ping_result is None  # no endpoint to test = trust credential
            or (ping_result.get("reachable") and ping_result.get("status_code") in (200, 201, 429))
        )
        if not healthy:
            unhealthy_count += 1

        results[key] = {
            "healthy": healthy,
            "has_db_credential": has_db_cred,
            "decrypt_ok": decrypted_ok,
            "ping": ping_result,
        }

    session.commit()  # persist health_status updates

    status = "green"
    if unhealthy_count > 0:
        status = "yellow" if unhealthy_count < len(results) / 2 else "red"

    return {
        "status": status,
        "total": len(results),
        "unhealthy": unhealthy_count,
        "providers": results,
    }


def _check_stuck_media_jobs(session: Session) -> dict:
    """Find MediaJobs stuck in 'processing' longer than the threshold."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=STUCK_MEDIA_JOB_MINUTES)

    stuck_jobs = session.execute(
        select(MediaJob.id, MediaJob.provider, MediaJob.job_type, MediaJob.dispatched_at)
        .where(
            and_(
                MediaJob.status.in_(["dispatched", "processing"]),
                MediaJob.dispatched_at < cutoff,
            )
        )
    ).all()

    stuck_list = [
        {
            "id": str(j.id),
            "provider": j.provider,
            "job_type": j.job_type,
            "dispatched_at": j.dispatched_at.isoformat() if j.dispatched_at else None,
        }
        for j in stuck_jobs
    ]

    status = "green"
    if len(stuck_list) > 10:
        status = "red"
    elif len(stuck_list) > 0:
        status = "yellow"

    return {
        "status": status,
        "stuck_count": len(stuck_list),
        "stuck_jobs": stuck_list[:20],  # cap details to first 20 for event payload size
    }


def _check_unretried_failures(session: Session) -> dict:
    """Find failed SystemJobs that haven't been retried within the lookback window."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=FAILED_JOB_LOOKBACK_HOURS)

    failed_count = session.execute(
        select(func.count(SystemJob.id))
        .where(
            and_(
                SystemJob.status == "failed",
                SystemJob.completed_at >= cutoff,
            )
        )
    ).scalar_one()

    status = "green"
    if failed_count > 50:
        status = "red"
    elif failed_count > 10:
        status = "yellow"

    return {
        "status": status,
        "failed_count": failed_count,
        "lookback_hours": FAILED_JOB_LOOKBACK_HOURS,
    }


def _overall_status(*components: dict) -> str:
    """Derive overall status from component statuses."""
    statuses = [c["status"] for c in components]
    if "red" in statuses:
        return "red"
    if "yellow" in statuses:
        return "yellow"
    return "green"


@shared_task(base=TrackedTask, name="workers.health_monitor_worker.tasks.check_system_health")
def check_system_health() -> dict:
    """Run full system health check and emit report event.

    Covers:
      - Provider credential health + live API connectivity
      - Stuck media generation jobs
      - Unretried job failures
    """
    engine = _engine()
    with Session(engine) as session:
        provider_health = _check_providers(session)
        media_health = _check_stuck_media_jobs(session)
        failure_health = _check_unretried_failures(session)

        overall = _overall_status(provider_health, media_health, failure_health)

        report = {
            "overall_status": overall,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "components": {
                "providers": provider_health,
                "media_jobs": media_health,
                "unretried_failures": failure_health,
            },
        }

        severity = {"green": "info", "yellow": "warning", "red": "critical"}[overall]

        # Emit health report as a system event
        event = SystemEvent(
            event_domain="health",
            event_type="health.system_report",
            event_severity=severity,
            entity_type="system",
            actor_type="worker",
            actor_id="health_monitor",
            summary=f"System health: {overall.upper()} — providers={provider_health['status']}, media_jobs={media_health['status']}, failures={failure_health['status']}",
            details=report,
            requires_action=(overall == "red"),
        )
        session.add(event)
        session.commit()

        logger.info(
            "health_monitor.report",
            overall=overall,
            providers_status=provider_health["status"],
            media_jobs_status=media_health["status"],
            failures_status=failure_health["status"],
        )

    return report
