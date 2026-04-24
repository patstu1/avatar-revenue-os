"""Capacity engine — detect bottlenecks, overproduction, and allocate queues by ROI."""
from __future__ import annotations

from typing import Any

CAP = "capacity"

CAPACITY_TYPES = [
    "content_generation",
    "media_render",
    "qa_review",
    "publishing",
    "paid_test",
    "sponsor_sales",
    "operator_bandwidth",
]

_OVERPRODUCTION_THRESHOLD = 0.85
_BOTTLENECK_THRESHOLD = 0.95


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def compute_capacity_reports(
    capacity_data: list[dict[str, Any]],
    cost_ceilings: dict[str, Any],
) -> list[dict[str, Any]]:
    """Analyse capacity for each type, detect overproduction and bottlenecks.

    Parameters
    ----------
    capacity_data:
        Each dict: capacity_type (str), current_capacity (float),
        used_capacity (float), unit_cost (float, optional),
        revenue_per_unit (float, optional).
    cost_ceilings:
        Keys are capacity_type, values are max-spend floats.

    Returns
    -------
    list[dict] with capacity_type, current, used, utilization_pct,
    recommended_volume, recommended_throttle, expected_profit_impact,
    bottleneck_reason, confidence, explanation.
    """
    reports: list[dict[str, Any]] = []

    for item in capacity_data:
        cap_type = item.get("capacity_type", "unknown")
        current = float(item.get("current_capacity", 0))
        used = float(item.get("used_capacity", 0))
        unit_cost = float(item.get("unit_cost", 1.0))
        revenue_per = float(item.get("revenue_per_unit", 0.0))

        ceiling = float(cost_ceilings.get(cap_type, float("inf")))

        utilization = used / current if current > 0 else 0.0

        is_bottleneck = utilization >= _BOTTLENECK_THRESHOLD
        is_overproduction = (
            utilization >= _OVERPRODUCTION_THRESHOLD and not is_bottleneck
        )

        if is_bottleneck:
            recommended_volume = current * 0.90
            recommended_throttle = 0.90
            bottleneck_reason = (
                f"Utilization {utilization:.1%} exceeds bottleneck threshold "
                f"({_BOTTLENECK_THRESHOLD:.0%}). Risk of queue stalls."
            )
        elif is_overproduction:
            recommended_volume = current * 0.80
            recommended_throttle = 0.85
            bottleneck_reason = (
                f"Utilization {utilization:.1%} in overproduction zone. "
                "Quality may degrade."
            )
        else:
            headroom = current - used
            recommended_volume = min(current, used + headroom * 0.6)
            recommended_throttle = None
            bottleneck_reason = None

        max_affordable_units = ceiling / unit_cost if unit_cost > 0 else current
        recommended_volume = min(recommended_volume, max_affordable_units)

        profit_per_unit = revenue_per - unit_cost
        if recommended_throttle is not None:
            volume_change = recommended_volume - used
        else:
            volume_change = recommended_volume - used
        expected_profit_impact = round(volume_change * profit_per_unit, 2)

        conf_base = 0.60
        if current > 0 and used > 0:
            conf_base += 0.20
        if is_bottleneck:
            conf_base += 0.10
        conf = _clamp(conf_base)

        explanation = (
            f"{cap_type}: {used:.0f}/{current:.0f} used "
            f"({utilization:.1%} util). "
        )
        if is_bottleneck:
            explanation += f"BOTTLENECK — throttle to {recommended_throttle}. "
        elif is_overproduction:
            explanation += f"Overproduction — throttle to {recommended_throttle}. "
        else:
            explanation += "Within safe range. "
        explanation += (
            f"Recommended volume {recommended_volume:.0f}. "
            f"Expected profit delta ${expected_profit_impact:+.2f}."
        )

        reports.append({
            "capacity_type": cap_type,
            "current_capacity": round(current, 2),
            "used_capacity": round(used, 2),
            "utilization_pct": round(_clamp(utilization, 0.0, 10.0), 4),
            "recommended_volume": round(recommended_volume, 2),
            "recommended_throttle": recommended_throttle,
            "expected_profit_impact": expected_profit_impact,
            "bottleneck_reason": bottleneck_reason,
            "confidence": round(conf, 4),
            "explanation": explanation,
            "constrained_scope": {
                "ceiling": ceiling,
                "cap_type": cap_type,
            },
            CAP: True,
        })

    if not reports:
        reports.append({
            "capacity_type": "none",
            "current_capacity": 0.0,
            "used_capacity": 0.0,
            "utilization_pct": 0.0,
            "recommended_volume": 0.0,
            "recommended_throttle": None,
            "expected_profit_impact": 0.0,
            "bottleneck_reason": "No capacity data provided.",
            "confidence": 0.2,
            "explanation": "No capacity data to evaluate.",
            "constrained_scope": {},
            CAP: True,
        })

    return reports


def allocate_queues(
    capacity_reports: list[dict[str, Any]],
    queue_priorities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Allocate available capacity to queues ranked by ROI, defer low-priority when constrained.

    Parameters
    ----------
    capacity_reports:
        Output of compute_capacity_reports.
    queue_priorities:
        Each dict: queue_name (str), capacity_type (str), requested_capacity (float),
        expected_roi (float, 0-1+), priority_tier (int, 1=highest).

    Returns
    -------
    list[dict] with queue_name, priority_score, allocated_capacity,
    deferred_capacity, reason, explanation.
    """
    available_by_type: dict[str, float] = {}
    for r in capacity_reports:
        cap_type = r.get("capacity_type", "")
        avail = r.get("recommended_volume", 0) - r.get("used_capacity", 0)
        available_by_type[cap_type] = available_by_type.get(cap_type, 0) + max(avail, 0)

    sorted_queues = sorted(
        queue_priorities,
        key=lambda q: (q.get("priority_tier", 99), -q.get("expected_roi", 0)),
    )

    results: list[dict[str, Any]] = []

    for q in sorted_queues:
        q_name = q.get("queue_name", "unknown")
        cap_type = q.get("capacity_type", "unknown")
        requested = float(q.get("requested_capacity", 0))
        roi = float(q.get("expected_roi", 0))
        tier = int(q.get("priority_tier", 99))

        priority_score = _clamp(roi * 0.6 + (1 - tier / 10) * 0.4)

        remaining = available_by_type.get(cap_type, 0)

        if remaining >= requested:
            allocated = requested
            deferred = 0.0
            reason = f"Fully allocated from {cap_type} pool."
        elif remaining > 0:
            allocated = remaining
            deferred = requested - remaining
            reason = (
                f"Partially allocated — only {remaining:.0f} available of "
                f"{requested:.0f} requested in {cap_type}."
            )
        else:
            allocated = 0.0
            deferred = requested
            reason = f"No remaining {cap_type} capacity. Fully deferred."

        available_by_type[cap_type] = max(remaining - allocated, 0)

        explanation = (
            f"Queue '{q_name}' (tier {tier}, ROI {roi:.2f}): "
            f"allocated {allocated:.0f}, deferred {deferred:.0f}. "
            f"{reason}"
        )

        results.append({
            "queue_name": q_name,
            "priority_score": round(priority_score, 4),
            "allocated_capacity": round(allocated, 2),
            "deferred_capacity": round(deferred, 2),
            "reason": reason,
            "explanation": explanation,
            CAP: True,
        })

    return results
