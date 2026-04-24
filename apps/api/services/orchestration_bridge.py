"""Orchestration Bridge — makes the job/worker/provider layer observable and actionable.

This service integrates the orchestration layer with the control layer by:

1. Aggregating real job/worker state into an operational view
2. Connecting provider health to content routing decisions
3. Linking job failures to recovery engine and operator actions
4. Making beat schedule execution visible
5. Tracking provider health over time

The existing worker infrastructure (TrackedTask, SystemJob, ProviderRegistry)
handles execution. This bridge makes it visible and connected.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_action, emit_event
from packages.db.enums import JobStatus
from packages.db.models.provider_registry import (
    ProviderBlocker,
    ProviderRegistryEntry,
)
from packages.db.models.system import SystemJob

logger = structlog.get_logger()


# ── Job State Aggregation ──────────────────────────────────────────


async def get_orchestration_state(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> dict:
    """Build a real-time orchestration view for the control layer.

    Shows job pipeline state, worker activity, provider health,
    and recent failures — everything an operator needs to understand
    what the machine is doing and where it's stuck.
    """
    now = datetime.now(timezone.utc)
    hour_1 = now - timedelta(hours=1)
    hour_24 = now - timedelta(hours=24)

    # --- Job state distribution ---
    job_status_q = await db.execute(select(SystemJob.status, func.count()).group_by(SystemJob.status))
    jobs_by_status = {}
    for row in job_status_q.all():
        key = row[0].value if hasattr(row[0], "value") else str(row[0])
        jobs_by_status[key] = row[1]

    # --- Jobs by queue (last 24h) ---
    queue_q = await db.execute(
        select(SystemJob.queue, func.count())
        .where(SystemJob.created_at >= hour_24)
        .group_by(SystemJob.queue)
        .order_by(func.count().desc())
        .limit(20)
    )
    jobs_by_queue = {str(row[0]): row[1] for row in queue_q.all()}

    # --- Recent failures (last 24h) ---
    failures_q = await db.execute(
        select(SystemJob)
        .where(
            SystemJob.status == JobStatus.FAILED,
            SystemJob.completed_at >= hour_24,
        )
        .order_by(SystemJob.completed_at.desc())
        .limit(20)
    )
    recent_failures = [
        {
            "id": str(j.id),
            "job_name": j.job_name,
            "queue": j.queue,
            "error_message": (j.error_message or "")[:200],
            "retries": j.retries,
            "max_retries": j.max_retries,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "duration_seconds": j.duration_seconds,
        }
        for j in failures_q.scalars().all()
    ]

    # --- Currently running jobs ---
    running_q = await db.execute(
        select(SystemJob).where(SystemJob.status == JobStatus.RUNNING).order_by(SystemJob.started_at.desc()).limit(20)
    )
    running_jobs = [
        {
            "id": str(j.id),
            "job_name": j.job_name,
            "queue": j.queue,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "retries": j.retries,
        }
        for j in running_q.scalars().all()
    ]

    # --- Job throughput (1h vs 24h) ---
    completed_1h = (
        await db.execute(
            select(func.count())
            .select_from(SystemJob)
            .where(
                SystemJob.status == JobStatus.COMPLETED,
                SystemJob.completed_at >= hour_1,
            )
        )
    ).scalar() or 0

    completed_24h = (
        await db.execute(
            select(func.count())
            .select_from(SystemJob)
            .where(
                SystemJob.status == JobStatus.COMPLETED,
                SystemJob.completed_at >= hour_24,
            )
        )
    ).scalar() or 0

    failed_24h = (
        await db.execute(
            select(func.count())
            .select_from(SystemJob)
            .where(
                SystemJob.status == JobStatus.FAILED,
                SystemJob.completed_at >= hour_24,
            )
        )
    ).scalar() or 0

    # --- Average duration for completed jobs ---
    avg_duration = (
        await db.execute(
            select(func.avg(SystemJob.duration_seconds)).where(
                SystemJob.status == JobStatus.COMPLETED,
                SystemJob.completed_at >= hour_24,
                SystemJob.duration_seconds.isnot(None),
            )
        )
    ).scalar()

    # --- Retry rate ---
    retried_24h = (
        await db.execute(
            select(func.count())
            .select_from(SystemJob)
            .where(
                SystemJob.retries > 0,
                SystemJob.created_at >= hour_24,
            )
        )
    ).scalar() or 0

    total_24h = completed_24h + failed_24h
    success_rate = (completed_24h / total_24h * 100) if total_24h > 0 else 100.0

    return {
        "jobs_by_status": jobs_by_status,
        "jobs_by_queue": jobs_by_queue,
        "running_jobs": running_jobs,
        "recent_failures": recent_failures,
        "throughput": {
            "completed_1h": completed_1h,
            "completed_24h": completed_24h,
            "failed_24h": failed_24h,
            "success_rate": round(success_rate, 1),
            "avg_duration_seconds": round(float(avg_duration), 1) if avg_duration else None,
            "retry_count_24h": retried_24h,
        },
    }


# ── Provider Health ──────────────────────────────────────────────────


async def get_provider_health(
    db: AsyncSession,
    brand_id: Optional[uuid.UUID] = None,
) -> dict:
    """Get provider health state — which providers are working and which are blocked."""
    # All providers
    providers_q = await db.execute(
        select(ProviderRegistryEntry)
        .where(ProviderRegistryEntry.is_active.is_(True))
        .order_by(ProviderRegistryEntry.provider_key)
    )
    providers = providers_q.scalars().all()

    # Blockers
    blocker_query = select(ProviderBlocker).where(ProviderBlocker.resolved.is_(False))
    if brand_id:
        blocker_query = blocker_query.where(ProviderBlocker.brand_id == brand_id)
    blockers_q = await db.execute(blocker_query.limit(20))
    blockers = blockers_q.scalars().all()

    blocked_providers = {b.provider_key for b in blockers if hasattr(b, "provider_key")}

    healthy = 0
    degraded = 0
    blocked = 0

    provider_list = []
    for p in providers:
        status = "healthy"
        if p.provider_key in blocked_providers:
            status = "blocked"
            blocked += 1
        elif p.credential_status == "missing" or p.integration_status == "error":
            status = "degraded"
            degraded += 1
        else:
            healthy += 1

        provider_list.append(
            {
                "provider_key": p.provider_key,
                "display_name": p.display_name,
                "category": p.category,
                "provider_type": p.provider_type,
                "status": status,
                "credential_status": p.credential_status,
                "is_primary": p.is_primary,
                "is_fallback": p.is_fallback,
            }
        )

    blocker_list = [
        {
            "id": str(b.id),
            "provider_key": b.provider_key if hasattr(b, "provider_key") else None,
            "blocker_type": b.blocker_type,
            "severity": b.severity,
            "detail": b.description[:200] if b.description else None,
            "operator_action_needed": b.operator_action_needed if hasattr(b, "operator_action_needed") else True,
        }
        for b in blockers
    ]

    return {
        "providers": provider_list,
        "blockers": blocker_list,
        "counts": {
            "healthy": healthy,
            "degraded": degraded,
            "blocked": blocked,
            "total": len(providers),
        },
    }


async def check_provider_ready(
    db: AsyncSession,
    provider_key: str,
    brand_id: Optional[uuid.UUID] = None,
) -> dict:
    """Check if a specific provider is ready for use.

    Called before content generation routing to prevent dispatching
    to unhealthy providers.
    """
    # Check for blockers
    blocker_query = select(ProviderBlocker).where(
        ProviderBlocker.resolved.is_(False),
    )
    if brand_id:
        blocker_query = blocker_query.where(ProviderBlocker.brand_id == brand_id)
    blockers = (await db.execute(blocker_query.limit(5))).scalars().all()

    # Check provider entry
    provider = (
        await db.execute(
            select(ProviderRegistryEntry).where(
                ProviderRegistryEntry.provider_key == provider_key,
                ProviderRegistryEntry.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()

    if not provider:
        return {"ready": False, "reason": f"Provider '{provider_key}' not found or inactive"}

    matching_blockers = [b for b in blockers if hasattr(b, "provider_key") and b.provider_key == provider_key]

    if matching_blockers:
        return {
            "ready": False,
            "reason": f"Provider '{provider_key}' has {len(matching_blockers)} active blockers",
            "blockers": [b.blocker_type for b in matching_blockers],
        }

    if provider.credential_status == "missing":
        return {"ready": False, "reason": f"Provider '{provider_key}' credentials not configured"}

    return {"ready": True, "provider_key": provider_key}


# ── Surface Orchestration Actions ──────────────────────────────────


async def surface_orchestration_actions(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> list[dict]:
    """Scan orchestration state and create operator actions.

    Identifies stuck jobs, provider failures, and execution issues
    that need operator attention.
    """
    actions_created = []
    now = datetime.now(timezone.utc)
    hour_24 = now - timedelta(hours=24)

    # 1. Jobs stuck in running state (> 30 minutes)
    stuck_threshold = now - timedelta(minutes=30)
    stuck_jobs = await db.execute(
        select(SystemJob)
        .where(
            SystemJob.status == JobStatus.RUNNING,
            SystemJob.started_at < stuck_threshold,
        )
        .limit(5)
    )
    for job in stuck_jobs.scalars().all():
        minutes_running = int((now - job.started_at).total_seconds() / 60) if job.started_at else 0
        action = await emit_action(
            db,
            org_id=org_id,
            action_type="investigate_stuck_job",
            title=f"Job stuck: {job.job_name[:50]} ({minutes_running}min)",
            description=f"Job has been running for {minutes_running} minutes in queue '{job.queue}'. "
            f"May need manual intervention or restart.",
            category="failure",
            priority="high",
            entity_type="system_job",
            entity_id=job.id,
            source_module="orchestration_bridge",
        )
        actions_created.append({"type": "stuck_job", "action_id": str(action.id)})

    # 2. Jobs that exhausted retries
    exhausted_q = await db.execute(
        select(SystemJob)
        .where(
            SystemJob.status == JobStatus.FAILED,
            SystemJob.retries >= SystemJob.max_retries,
            SystemJob.completed_at >= hour_24,
        )
        .limit(5)
    )
    for job in exhausted_q.scalars().all():
        action = await emit_action(
            db,
            org_id=org_id,
            action_type="retry_exhausted_job",
            title=f"Max retries: {job.job_name[:50]}",
            description=f"Job failed after {job.retries} retries. Error: {(job.error_message or '')[:200]}",
            category="failure",
            priority="high",
            entity_type="system_job",
            entity_id=job.id,
            source_module="orchestration_bridge",
            action_payload={"error": (job.error_message or "")[:500]},
        )
        actions_created.append({"type": "exhausted_retries", "action_id": str(action.id)})

    # 3. Provider blockers needing operator action
    blocker_q = await db.execute(
        select(ProviderBlocker)
        .where(
            ProviderBlocker.resolved.is_(False),
        )
        .limit(5)
    )
    for b in blocker_q.scalars().all():
        if hasattr(b, "operator_action_needed") and b.operator_action_needed:
            action = await emit_action(
                db,
                org_id=org_id,
                action_type="resolve_provider_blocker",
                title=f"Provider blocked: {b.provider_key if hasattr(b, 'provider_key') else 'unknown'}",
                description=f"Type: {b.blocker_type}. Severity: {b.severity}. Detail: {(b.description or '')[:200]}",
                category="health",
                priority="critical" if b.severity == "critical" else "high",
                entity_type="provider_blocker",
                entity_id=b.id,
                source_module="provider_registry",
            )
            actions_created.append({"type": "provider_blocker", "action_id": str(action.id)})

    # 4. High failure rate warning
    total_24h = (
        await db.execute(select(func.count()).select_from(SystemJob).where(SystemJob.created_at >= hour_24))
    ).scalar() or 0

    failed_24h = (
        await db.execute(
            select(func.count())
            .select_from(SystemJob)
            .where(
                SystemJob.status == JobStatus.FAILED,
                SystemJob.completed_at >= hour_24,
            )
        )
    ).scalar() or 0

    if total_24h > 10 and failed_24h / total_24h > 0.2:
        await emit_event(
            db,
            domain="orchestration",
            event_type="orchestration.high_failure_rate",
            summary=f"High failure rate: {failed_24h}/{total_24h} jobs failed in last 24h ({failed_24h / total_24h:.0%})",
            org_id=org_id,
            severity="error",
            requires_action=True,
            details={"total": total_24h, "failed": failed_24h, "rate": failed_24h / total_24h},
        )

    await db.flush()
    return actions_created
