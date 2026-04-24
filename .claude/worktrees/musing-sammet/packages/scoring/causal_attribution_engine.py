"""Causal Attribution Engine — change-point, candidate cause, confidence, credit. Pure functions."""
from __future__ import annotations
from typing import Any
import math

DRIVER_TYPES = ["content_change", "offer_change", "campaign_change", "platform_shift", "seasonal_pattern", "experiment_result", "account_state_change", "provider_change", "external_event", "audience_shift"]
NOISE_THRESHOLD = 0.10
HIGH_CONFIDENCE = 0.70
CAUTIOUS_THRESHOLD = 0.50


def detect_change_points(time_series: list[float], threshold_pct: float = 0.15) -> list[dict[str, Any]]:
    """Detect significant change points in a metric time series."""
    changes = []
    if len(time_series) < 3:
        return changes
    for i in range(1, len(time_series)):
        prev = time_series[i - 1]
        curr = time_series[i]
        if prev == 0:
            continue
        change = (curr - prev) / abs(prev)
        if abs(change) >= threshold_pct:
            changes.append({"index": i, "before": prev, "after": curr, "change_pct": round(change * 100, 2), "direction": "lift" if change > 0 else "drop"})
    return changes


def extract_candidate_causes(changes: list[dict[str, Any]], system_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Match change points to potential causal events."""
    candidates = []
    for change in changes:
        idx = change["index"]
        for event in system_events:
            evt_idx = event.get("index", event.get("period", 0))
            if abs(evt_idx - idx) <= 1:
                candidates.append({
                    "change": change,
                    "driver_type": event.get("driver_type", "unknown"),
                    "driver_name": event.get("driver_name", "unknown event"),
                    "temporal_proximity": abs(evt_idx - idx),
                    "event_data": event,
                })
    return candidates


def score_causal_confidence(candidate: dict[str, Any]) -> dict[str, Any]:
    """Score the causal confidence of a candidate driver."""
    proximity = candidate.get("temporal_proximity", 2)
    change_magnitude = abs(candidate.get("change", {}).get("change_pct", 0))
    driver_type = candidate.get("driver_type", "unknown")

    temporal_score = max(0, 1.0 - proximity * 0.3)
    magnitude_score = min(1.0, change_magnitude / 50)

    directness_map = {"experiment_result": 0.9, "offer_change": 0.7, "content_change": 0.6, "campaign_change": 0.6, "platform_shift": 0.4, "account_state_change": 0.5, "provider_change": 0.5, "seasonal_pattern": 0.2, "external_event": 0.15, "audience_shift": 0.3}
    directness = directness_map.get(driver_type, 0.3)

    confidence = round(0.40 * temporal_score + 0.30 * directness + 0.30 * magnitude_score, 3)

    competing = []
    if confidence < HIGH_CONFIDENCE:
        competing.append("Other factors may have contributed — confidence below threshold")
    if driver_type in ("seasonal_pattern", "external_event"):
        competing.append(f"External/seasonal factor ({driver_type}) — not controllable")

    noise_flag = confidence < NOISE_THRESHOLD or change_magnitude < 5
    recommended = _recommend(driver_type, candidate.get("change", {}).get("direction", ""), confidence)

    return {
        "driver_type": driver_type,
        "driver_name": candidate.get("driver_name", ""),
        "estimated_lift_pct": round(candidate.get("change", {}).get("change_pct", 0), 2),
        "confidence": confidence,
        "competing_explanations": competing,
        "noise_flag": noise_flag,
        "recommended_action": recommended,
    }


def allocate_credit(hypotheses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Allocate credit proportionally among competing hypotheses."""
    if not hypotheses:
        return []
    total_conf = sum(h.get("confidence", 0) for h in hypotheses)
    if total_conf <= 0:
        total_conf = 1.0

    allocations = []
    for h in hypotheses:
        share = h.get("confidence", 0) / total_conf
        cautious = h.get("confidence", 0) < CAUTIOUS_THRESHOLD or h.get("noise_flag", False)
        allocations.append({
            "driver_name": h.get("driver_name", ""),
            "credit_pct": round(share * 100, 1),
            "confidence": h.get("confidence", 0),
            "promote_cautiously": cautious,
        })
    return sorted(allocations, key=lambda a: -a["credit_pct"])


def build_confidence_summary(hypotheses: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize confidence across all hypotheses."""
    total = len(hypotheses)
    high = sum(1 for h in hypotheses if h.get("confidence", 0) >= HIGH_CONFIDENCE)
    noise = sum(1 for h in hypotheses if h.get("noise_flag", False))

    if high == 0 and total > 0:
        rec = "All hypotheses below confidence threshold — do not promote any winner yet"
    elif noise > total / 2:
        rec = "Majority of signals may be noise — collect more data before acting"
    elif high == total:
        rec = "All hypotheses high confidence — safe to promote winners"
    else:
        rec = f"{high}/{total} high confidence — promote cautiously for the rest"

    return {"hypothesis_count": total, "high_confidence_count": high, "noise_flagged_count": noise, "recommendation": rec}


def _recommend(driver_type: str, direction: str, confidence: float) -> str:
    if confidence >= HIGH_CONFIDENCE:
        if direction == "lift":
            return "Promote confidently — high causal confidence on this driver"
        return "Investigate urgently — high confidence this caused the drop"
    if confidence >= CAUTIOUS_THRESHOLD:
        return "Promote cautiously — moderate confidence, monitor closely"
    return "Do not act yet — insufficient causal confidence, may be noise"
