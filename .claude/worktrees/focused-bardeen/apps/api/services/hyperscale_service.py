"""Hyper-Scale Execution Service — capacity, segments, ceilings, health."""
from __future__ import annotations
import uuid
from typing import Any
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from packages.db.models.hyperscale import (
    ExecutionCapacityReport, ExecutionQueueSegment, WorkloadAllocation,
    ThroughputEvent, BurstEvent, UsageCeilingRule, DegradationEvent, ScaleHealthReport,
)
from packages.db.models.system import SystemJob
from packages.scoring.hyperscale_engine import evaluate_capacity, detect_burst, plan_degradation, enforce_ceiling, build_scale_health


async def recompute_capacity(db: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(delete(ExecutionCapacityReport).where(ExecutionCapacityReport.organization_id == org_id))
    await db.execute(delete(ScaleHealthReport).where(ScaleHealthReport.organization_id == org_id))

    segments = list((await db.execute(select(ExecutionQueueSegment).where(ExecutionQueueSegment.organization_id == org_id, ExecutionQueueSegment.is_active.is_(True)))).scalars().all())
    seg_dict = {s.segment_key: [{"task_type": s.segment_type}] * s.queue_depth for s in segments}

    total_max_conc = sum(s.max_concurrency for s in segments) if segments else 50
    capacity = evaluate_capacity(seg_dict, total_max_conc)

    total_queued = sum(s.queue_depth for s in segments)
    total_running = sum(s.running_count for s in segments)
    burst = detect_burst(total_queued / 3600.0 if total_queued > 0 else 0, total_queued)
    degradation = plan_degradation(capacity, burst)

    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    burst_count = (await db.execute(select(func.count()).select_from(BurstEvent).where(BurstEvent.organization_id == org_id, BurstEvent.created_at >= day_ago))).scalar() or 0
    deg_count = (await db.execute(select(func.count()).select_from(DegradationEvent).where(DegradationEvent.organization_id == org_id, DegradationEvent.created_at >= day_ago))).scalar() or 0

    ceilings = list((await db.execute(select(UsageCeilingRule).where(UsageCeilingRule.organization_id == org_id, UsageCeilingRule.is_active.is_(True)))).scalars().all())
    ceiling_results = [enforce_ceiling(c.ceiling_type, c.max_value, c.current_value) for c in ceilings]

    health = build_scale_health(capacity, ceiling_results, burst_count, deg_count)

    db.add(ExecutionCapacityReport(
        organization_id=org_id, total_queued=total_queued, total_running=total_running,
        throughput_per_hour=capacity.get("utilization", 0) * total_max_conc,
        burst_active=burst.get("burst_detected", False), degraded=degradation.get("degradation_needed", False),
        health_status=health["health_status"],
        summary_json={"capacity": capacity, "burst": burst, "degradation": degradation},
    ))

    if burst.get("burst_detected"):
        db.add(BurstEvent(organization_id=org_id, burst_type="queue_spike", peak_qps=burst.get("peak_qps", 0), tasks_queued=total_queued, degradation_triggered=degradation.get("degradation_needed", False)))

    if degradation.get("degradation_needed"):
        for a in degradation.get("actions", []):
            db.add(DegradationEvent(organization_id=org_id, degradation_type=a["action"], trigger_reason=a["reason"], action_taken=a["action"]))

    db.add(ScaleHealthReport(organization_id=org_id, **health))
    await db.flush()
    return {"rows_processed": len(segments) + 1, "status": "completed"}


async def list_capacity(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(ExecutionCapacityReport).where(ExecutionCapacityReport.organization_id == org_id).order_by(ExecutionCapacityReport.created_at.desc()).limit(10))).scalars().all())

async def list_segments(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(ExecutionQueueSegment).where(ExecutionQueueSegment.organization_id == org_id, ExecutionQueueSegment.is_active.is_(True)))).scalars().all())

async def list_ceilings(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(UsageCeilingRule).where(UsageCeilingRule.organization_id == org_id, UsageCeilingRule.is_active.is_(True)))).scalars().all())

async def list_scale_health(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(ScaleHealthReport).where(ScaleHealthReport.organization_id == org_id).order_by(ScaleHealthReport.created_at.desc()).limit(5))).scalars().all())

async def get_execution_health(db: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    """Downstream: quick health check for workers/copilot."""
    report = (await db.execute(select(ScaleHealthReport).where(ScaleHealthReport.organization_id == org_id).order_by(ScaleHealthReport.created_at.desc()).limit(1))).scalar_one_or_none()
    if not report:
        return {"health_status": "unknown", "recommendation": "Run capacity recompute"}
    return {"health_status": report.health_status, "queue_depth": report.queue_depth_total, "ceiling_pct": report.ceiling_utilization_pct, "recommendation": report.recommendation}
