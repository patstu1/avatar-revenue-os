"""Portfolio Capital Allocator Engine — expected return, constrained solver, rebalancing.

Pure functions. No I/O.
"""
from __future__ import annotations

from typing import Any

TARGET_TYPES = ["account", "platform", "offer", "content_form", "monetization_path", "experiment", "creator_revenue_avenue", "brand"]

EXPERIMENT_RESERVE_PCT = 0.10
STARVATION_THRESHOLD = 0.15
HERO_THRESHOLD = 0.55
MIN_ALLOCATION_PCT = 0.02


def score_expected_return(target: dict[str, Any]) -> float:
    """Score a target's expected return on a 0-1 scale."""
    upside = float(target.get("expected_return", 0) or 0)
    cost = float(target.get("expected_cost", 0) or 0)
    confidence = float(target.get("confidence", 0.5) or 0.5)
    health = float(target.get("account_health", 1.0) or 1.0)
    fatigue = float(target.get("fatigue_score", 0) or 0)
    pattern_win = float(target.get("pattern_win_score", 0) or 0)
    conversion_quality = float(target.get("conversion_quality", 0) or 0)

    roi = (upside - cost) / max(cost, 1.0)
    fatigue_penalty = max(0, 1.0 - fatigue)

    raw = (
        0.30 * min(1.0, roi)
        + 0.20 * confidence
        + 0.15 * health
        + 0.15 * pattern_win
        + 0.10 * fatigue_penalty
        + 0.10 * min(1.0, conversion_quality)
    )
    return round(max(0.0, min(1.0, raw)), 4)


def determine_provider_tier(return_score: float, target: dict[str, Any]) -> str:
    """Decide hero vs bulk provider tier based on return score and context."""
    if return_score >= HERO_THRESHOLD:
        return "hero"
    if target.get("target_type") == "experiment":
        return "standard"
    if float(target.get("pattern_win_score", 0) or 0) >= 0.6:
        return "hero"
    return "bulk"


def solve_allocation(
    targets: list[dict[str, Any]],
    total_budget: float,
    constraints: list[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Constrained allocation solver. Returns decisions + report summary."""
    if not targets or total_budget <= 0:
        return {"decisions": [], "report": _empty_report(total_budget)}

    experiment_reserve = round(total_budget * EXPERIMENT_RESERVE_PCT, 2)
    allocatable = total_budget - experiment_reserve

    scored = []
    for t in targets:
        rs = score_expected_return(t)
        tier = determine_provider_tier(rs, t)
        scored.append({**t, "_return_score": rs, "_tier": tier})

    scored.sort(key=lambda x: -x["_return_score"])

    constraint_map = _build_constraint_map(constraints or [])

    decisions = []
    remaining = allocatable
    hero_total = 0.0
    bulk_total = 0.0
    starved = 0
    total_score = sum(max(s["_return_score"], 0.01) for s in scored)

    for s in scored:
        share = max(s["_return_score"], 0.01) / max(total_score, 0.01)
        ckey = f"{s.get('target_type', '')}:{s.get('target_key', '')}"
        cmin = constraint_map.get(ckey, {}).get("min", 0.0)
        cmax = constraint_map.get(ckey, {}).get("max", 1.0)
        share = max(cmin, min(cmax, share))

        is_starved = s["_return_score"] < STARVATION_THRESHOLD
        if is_starved:
            share = min(share, MIN_ALLOCATION_PCT)
            starved += 1

        budget_alloc = round(share * allocatable, 2)
        budget_alloc = min(budget_alloc, remaining)
        remaining -= budget_alloc

        tier = s["_tier"]
        if tier == "hero":
            hero_total += budget_alloc
        else:
            bulk_total += budget_alloc

        volume = max(1, int(budget_alloc / max(float(s.get("expected_cost", 1) or 1), 0.01)))

        decisions.append({
            "target_type": s.get("target_type", ""),
            "target_key": s.get("target_key", ""),
            "target_id": s.get("target_id"),
            "return_score": s["_return_score"],
            "allocated_budget": budget_alloc,
            "allocated_volume": volume,
            "provider_tier": tier,
            "allocation_pct": round(share * 100, 1),
            "starved": is_starved,
            "explanation": _build_explanation(s, share, is_starved, tier),
        })

    for exp_t in [s for s in scored if s.get("target_type") == "experiment"]:
        for d in decisions:
            if d["target_key"] == exp_t.get("target_key"):
                bonus = round(experiment_reserve / max(1, sum(1 for s in scored if s.get("target_type") == "experiment")), 2)
                d["allocated_budget"] = round(d["allocated_budget"] + bonus, 2)
                break

    report = {
        "total_budget": total_budget,
        "allocated_budget": round(total_budget - remaining, 2),
        "experiment_reserve": experiment_reserve,
        "hero_spend": round(hero_total, 2),
        "bulk_spend": round(bulk_total, 2),
        "target_count": len(decisions),
        "starved_count": starved,
    }
    return {"decisions": decisions, "report": report}


def rebalance(
    current_decisions: list[dict[str, Any]],
    performance_updates: dict[str, dict[str, float]],
) -> dict[str, Any]:
    """Rebalance allocations based on new performance data."""
    changes = []
    starved = 0
    boosted = 0

    for d in current_decisions:
        key = d.get("target_key", "")
        perf = performance_updates.get(key, {})
        if not perf:
            continue

        new_return = float(perf.get("actual_roi", 0) or 0)
        old_return = float(d.get("return_score", 0) or 0)
        delta = new_return - old_return

        if delta > 0.1:
            changes.append({"target_key": key, "action": "boost", "delta": round(delta, 3)})
            boosted += 1
        elif delta < -0.15:
            changes.append({"target_key": key, "action": "starve", "delta": round(delta, 3)})
            starved += 1

    reason = "performance_rebalance"
    if starved > 0 and boosted == 0:
        reason = "underperformance_contraction"
    elif boosted > 0 and starved == 0:
        reason = "outperformance_expansion"

    return {
        "rebalance_reason": reason,
        "changes": changes,
        "targets_starved": starved,
        "targets_boosted": boosted,
    }


def _build_constraint_map(constraints: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    m: dict[str, dict[str, float]] = {}
    for c in constraints:
        key = f"{c.get('constraint_type', '')}:{c.get('constraint_key', '')}"
        m[key] = {"min": float(c.get("min_value", 0)), "max": float(c.get("max_value", 1))}
    return m


def _build_explanation(s: dict, share: float, starved: bool, tier: str) -> str:
    parts = [f"{s.get('target_type', '')}:{s.get('target_key', '')}"]
    parts.append(f"return={s['_return_score']:.2f}")
    parts.append(f"share={share*100:.1f}%")
    parts.append(f"tier={tier}")
    if starved:
        parts.append("STARVED")
    return " | ".join(parts)


def _empty_report(total_budget: float) -> dict[str, Any]:
    return {"total_budget": total_budget, "allocated_budget": 0, "experiment_reserve": 0, "hero_spend": 0, "bulk_spend": 0, "target_count": 0, "starved_count": 0}
