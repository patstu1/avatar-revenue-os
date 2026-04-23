"""Health Monitor Worker — periodic system health checks with self-healing signals.

Checks:
  a) All configured providers via integration_manager credential loader
  b) Stuck MediaJobs (processing longer than typical)
  c) Failed SystemJobs that haven't been retried
  d) Emits a health report event with green/yellow/red status per component
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import structlog
from celery import shared_task
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from packages.db.models.media_jobs import MediaJob
from packages.db.models.system import SystemJob
from packages.db.models.system_events import SystemEvent
from packages.db.models.integration_registry import IntegrationProvider
from packages.db.session import get_sync_engine
from workers.base_task import TrackedTask

logger = structlog.get_logger()

# Thresholds
STUCK_MEDIA_JOB_MINUTES = 30  # MediaJob processing longer than this is "stuck"
FAILED_JOB_LOOKBACK_HOURS = 6  # Look for unretried failures in this window


@lru_cache(maxsize=1)
def _engine():
    return get_sync_engine()


def _check_providers(session: Session) -> dict:
    """Check all enabled integration providers for credential health."""
    from apps.api.services.integration_manager import _decrypt, PROVIDER_ENV_KEYS
    import os

    providers = session.execute(
        select(IntegrationProvider).where(IntegrationProvider.is_enabled.is_(True))
    ).scalars().all()

    results = {}
    unhealthy_count = 0

    for p in providers:
        key = p.provider_key
        has_db_cred = bool(p.api_key_encrypted)
        has_env_cred = False
        env_var = PROVIDER_ENV_KEYS.get(key)
        if env_var:
            has_env_cred = bool(os.getenv(env_var))

        # Can we decrypt the stored key?
        decrypted_ok = False
        if has_db_cred:
            try:
                val = _decrypt(p.api_key_encrypted)
                decrypted_ok = bool(val)
            except Exception:
                decrypted_ok = False

        healthy = decrypted_ok or has_env_cred
        if not healthy:
            unhealthy_count += 1

        results[key] = {
            "healthy": healthy,
            "has_db_credential": has_db_cred,
            "has_env_fallback": has_env_cred,
            "decrypt_ok": decrypted_ok,
        }

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
      - Provider credential health
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
