"""Hyper-Scale Execution Engine — partitioning, burst, degradation, ceilings. Pure functions."""
from __future__ import annotations

from typing import Any

SEGMENT_TYPES = ["brand", "team", "region", "workflow", "language", "priority"]
BURST_THRESHOLD_QPS = 5.0
DEGRADATION_QUEUE_DEPTH = 500
CEILING_WARN_PCT = 0.80


def partition_workload(tasks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Partition tasks into queue segments by brand/type/priority."""
    segments: dict[str, list[dict]] = {}
    for t in tasks:
        key = f"{t.get('brand_id', 'default')}:{t.get('task_type', 'general')}:{t.get('priority', 50)}"
        segments.setdefault(key, []).append(t)
    return segments


def evaluate_capacity(segments: dict[str, list], max_concurrency: int = 50) -> dict[str, Any]:
    """Evaluate overall capacity from queue segments."""
    total_queued = sum(len(v) for v in segments.values())
    segment_count = len(segments)
    utilization = total_queued / max(max_concurrency, 1)

    if utilization > 2.0:
        health = "critical"
    elif utilization > 1.0:
        health = "degraded"
    elif utilization > 0.7:
        health = "busy"
    else:
        health = "healthy"

    return {
        "total_queued": total_queued,
        "segment_count": segment_count,
        "utilization": round(utilization, 3),
        "health_status": health,
        "burst_active": total_queued > DEGRADATION_QUEUE_DEPTH,
    }


def detect_burst(current_qps: float, queue_depth: int) -> dict[str, Any]:
    """Detect if a burst condition exists."""
    is_burst = current_qps > BURST_THRESHOLD_QPS or queue_depth > DEGRADATION_QUEUE_DEPTH
    return {
        "burst_detected": is_burst,
        "peak_qps": current_qps,
        "queue_depth": queue_depth,
        "severity": "critical" if queue_depth > DEGRADATION_QUEUE_DEPTH * 2 else "high" if is_burst else "normal",
    }


def plan_degradation(capacity: dict[str, Any], burst: dict[str, Any]) -> dict[str, Any]:
    """Plan graceful degradation response."""
    actions = []

    if capacity.get("health_status") == "critical":
        actions.append({"action": "pause_bulk_generation", "reason": "Queue depth critical — pause non-hero generation"})
        actions.append({"action": "downgrade_provider_tier", "reason": "Switch all non-hero to cheapest provider"})
    elif capacity.get("health_status") == "degraded":
        actions.append({"action": "throttle_new_tasks", "reason": "Queue congested — reduce intake rate"})
        actions.append({"action": "defer_experiments", "reason": "Pause experiment tasks until queue normalizes"})

    if burst.get("burst_detected"):
        actions.append({"action": "activate_burst_mode", "reason": f"Burst detected at {burst.get('peak_qps', 0):.1f} QPS"})

    return {
        "degradation_needed": len(actions) > 0,
        "actions": actions,
        "health_status": capacity.get("health_status", "healthy"),
    }


def enforce_ceiling(ceiling_type: str, max_value: float, current_value: float) -> dict[str, Any]:
    """Check if a usage ceiling is exceeded."""
    utilization = current_value / max(max_value, 0.01)
    exceeded = current_value >= max_value
    warning = utilization >= CEILING_WARN_PCT and not exceeded

    return {
        "ceiling_type": ceiling_type,
        "max_value": max_value,
        "current_value": current_value,
        "utilization_pct": round(utilization * 100, 1),
        "exceeded": exceeded,
        "warning": warning,
        "action": "block" if exceeded else "warn" if warning else "allow",
    }


def schedule_priority(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort tasks by priority (highest first), then by creation order."""
    return sorted(tasks, key=lambda t: (-int(t.get("priority", 50)), t.get("created_at", "")))


def balance_market_workload(allocations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Balance workload across markets/languages."""
    sum(a.get("allocated_capacity", 0) for a in allocations)
    sum(a.get("used_capacity", 0) for a in allocations)

    balanced = []
    for a in allocations:
        alloc = a.get("allocated_capacity", 0)
        used = a.get("used_capacity", 0)
        utilization = used / max(alloc, 1)
        headroom = max(0, alloc - used)
        balanced.append({
            **a,
            "utilization_pct": round(utilization * 100, 1),
            "headroom": headroom,
            "status": "overloaded" if utilization > 1.0 else "busy" if utilization > 0.8 else "healthy",
        })

    return sorted(balanced, key=lambda b: -b["utilization_pct"])


def build_scale_health(capacity: dict, ceilings: list[dict], bursts_24h: int, degradations_24h: int) -> dict[str, Any]:
    """Build overall scale health report."""
    ceiling_util = max((c.get("utilization_pct", 0) for c in ceilings), default=0)
    health = capacity.get("health_status", "healthy")
    if degradations_24h > 3:
        health = "critical"
    elif bursts_24h > 5:
        health = "degraded"

    rec = "System operating normally"
    if health == "critical":
        rec = "Increase worker concurrency or add queue partitions"
    elif health == "degraded":
        rec = "Monitor burst frequency — consider scaling workers"

    return {
        "health_status": health,
        "queue_depth_total": capacity.get("total_queued", 0),
        "ceiling_utilization_pct": ceiling_util,
        "burst_count_24h": bursts_24h,
        "degradation_count_24h": degradations_24h,
        "recommendation": rec,
    }
