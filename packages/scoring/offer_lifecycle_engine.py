"""Offer lifecycle engine — state assessment, decay detection, transition recommendations."""

from __future__ import annotations

from typing import Any

OLC = "offer_lifecycle"

LIFECYCLE_STATES = [
    "onboarding",
    "probation",
    "active",
    "scaling",
    "plateauing",
    "decaying",
    "seasonal_pause",
    "retired",
    "relaunch_candidate",
]

_MATURITY_AGE_DAYS = 90
_SCALING_AGE_DAYS = 30
_VOLUME_SCALING_THRESHOLD = 50
_DECAY_CVR_DROP_PCT = 0.20
_DEPENDENCY_REVENUE_CONCENTRATION = 0.60
_PLATEAU_GROWTH_THRESHOLD = 0.03


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _compute_decay_score(offer: dict, history: list[dict]) -> float:
    """Higher = more decay detected (0=healthy, 1=fully decayed)."""
    recent = [h for h in history if h.get("offer_id") == offer.get("offer_id")]
    if len(recent) < 2:
        return 0.0

    recent_sorted = sorted(recent, key=lambda h: h.get("period_index", 0))
    latest = recent_sorted[-1]
    prior = recent_sorted[-2]

    latest_cvr = float(latest.get("conversion_rate", 0))
    prior_cvr = float(prior.get("conversion_rate", 0))

    if prior_cvr <= 0:
        return 0.0

    drop_pct = (prior_cvr - latest_cvr) / prior_cvr
    if drop_pct <= 0:
        return 0.0

    return _clamp(drop_pct / _DECAY_CVR_DROP_PCT)


def _compute_dependency_risk(offer: dict, all_offers_revenue: float) -> float:
    """Revenue concentration risk — higher = more dependent on this single offer."""
    offer_revenue = float(offer.get("revenue", 0))
    if all_offers_revenue <= 0:
        return 0.0
    concentration = offer_revenue / all_offers_revenue
    return _clamp(concentration / _DEPENDENCY_REVENUE_CONCENTRATION)


def _determine_state(
    offer: dict,
    decay_score: float,
    history: list[dict],
) -> str:
    age_days = int(offer.get("age_days", 0))
    total_conversions = int(offer.get("total_conversions", 0))
    is_paused = bool(offer.get("is_paused", False))
    is_retired = bool(offer.get("is_retired", False))
    growth_rate = float(offer.get("growth_rate", 0.0))

    if is_retired:
        if decay_score < 0.3 and total_conversions > 20:
            return "relaunch_candidate"
        return "retired"
    if is_paused:
        return "seasonal_pause"
    if age_days < 14:
        return "onboarding"
    if age_days < _SCALING_AGE_DAYS:
        return "probation"
    if decay_score > 0.7:
        return "decaying"
    if growth_rate < _PLATEAU_GROWTH_THRESHOLD and age_days > _MATURITY_AGE_DAYS:
        return "plateauing"
    if total_conversions > _VOLUME_SCALING_THRESHOLD and growth_rate > _PLATEAU_GROWTH_THRESHOLD:
        return "scaling"
    return "active"


def _health_score(
    state: str,
    decay_score: float,
    dep_risk: float,
    growth_rate: float,
) -> float:
    base = {
        "onboarding": 0.60,
        "probation": 0.55,
        "active": 0.75,
        "scaling": 0.90,
        "plateauing": 0.50,
        "decaying": 0.25,
        "seasonal_pause": 0.45,
        "retired": 0.10,
        "relaunch_candidate": 0.40,
    }.get(state, 0.50)

    adj = base - decay_score * 0.20 - dep_risk * 0.15 + _clamp(growth_rate) * 0.10
    return round(_clamp(adj), 4)


def _recommended_action(state: str, decay_score: float, dep_risk: float) -> str:
    actions = {
        "onboarding": "Monitor initial metrics; set conversion baseline.",
        "probation": "Validate offer-market fit; gather early feedback.",
        "active": "Maintain and optimise; test upsells.",
        "scaling": "Increase traffic allocation; duplicate to new channels.",
        "plateauing": "Refresh creative; test new angles or bundles.",
        "decaying": "Audit funnel leaks; consider price adjustment or sunset.",
        "seasonal_pause": "Queue re-launch plan for next season.",
        "retired": "Archive; reallocate budget to active offers.",
        "relaunch_candidate": "Redesign positioning; A/B test relaunch variant.",
    }
    action = actions.get(state, "Review manually.")
    if dep_risk > 0.7:
        action += " HIGH DEPENDENCY RISK — diversify revenue sources."
    if decay_score > 0.5 and state not in ("decaying", "retired"):
        action += " Warning: decay signal detected, accelerate optimisation."
    return action


def assess_offer_lifecycle(
    offers: list[dict[str, Any]],
    performance_history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Assess lifecycle state, health, decay, and dependency risk per offer.

    Parameters
    ----------
    offers:
        Each dict: offer_id, name, age_days, total_conversions, revenue,
        growth_rate (period-over-period), is_paused, is_retired.
    performance_history:
        Each dict: offer_id, period_index (int, ascending), conversion_rate, revenue.

    Returns
    -------
    list[dict] per offer with lifecycle_state, health_score, dependency_risk,
    decay_score, recommended_action, expected_impact, confidence, explanation.
    """
    total_revenue = sum(float(o.get("revenue", 0)) for o in offers) or 1.0

    results: list[dict[str, Any]] = []
    for offer in offers:
        oid = offer.get("offer_id")
        decay = _compute_decay_score(offer, performance_history)
        dep_risk = _compute_dependency_risk(offer, total_revenue)
        state = _determine_state(offer, decay, performance_history)
        health = _health_score(state, decay, dep_risk, float(offer.get("growth_rate", 0)))
        action = _recommended_action(state, decay, dep_risk)

        revenue = float(offer.get("revenue", 0))
        if state == "scaling":
            expected_impact = round(revenue * 0.25, 2)
        elif state == "decaying":
            expected_impact = round(-revenue * decay * 0.5, 2)
        elif state == "plateauing":
            expected_impact = round(revenue * 0.05, 2)
        else:
            expected_impact = round(revenue * 0.10, 2)

        age = int(offer.get("age_days", 0))
        hist_count = len([h for h in performance_history if h.get("offer_id") == oid])
        conf = _clamp(0.45 + min(0.25, age / 365) + min(0.20, hist_count * 0.04))

        explanation = (
            f"Offer {offer.get('name', oid)}: state={state}, "
            f"health={health:.2f}, decay={decay:.2f}, dep_risk={dep_risk:.2f}. "
            f"Age {age}d, {offer.get('total_conversions', 0)} conversions, "
            f"growth {offer.get('growth_rate', 0):.2%}. {action}"
        )

        results.append(
            {
                "offer_id": oid,
                "lifecycle_state": state,
                "health_score": health,
                "dependency_risk_score": round(dep_risk, 4),
                "decay_score": round(decay, 4),
                "recommended_action": action,
                "expected_impact": {
                    "revenue_delta": expected_impact,
                    "direction": "positive" if expected_impact >= 0 else "negative",
                },
                "confidence": round(conf, 4),
                "explanation": explanation,
                OLC: True,
            }
        )

    return results


def recommend_lifecycle_transition(
    offer_report: dict[str, Any],
) -> dict[str, Any]:
    """Determine whether a state change is warranted for a single offer report.

    Parameters
    ----------
    offer_report:
        Single dict from assess_offer_lifecycle output, plus optional
        current_db_state (str) representing persisted state.

    Returns
    -------
    dict with event_type, from_state, to_state, reason, confidence.
    """
    current_state = offer_report.get("current_db_state", offer_report.get("lifecycle_state"))
    assessed_state = offer_report.get("lifecycle_state", "active")
    health = float(offer_report.get("health_score", 0.5))
    decay = float(offer_report.get("decay_score", 0))
    dep_risk = float(offer_report.get("dependency_risk_score", 0))
    conf = float(offer_report.get("confidence", 0.5))

    if current_state == assessed_state:
        return {
            "event_type": "no_change",
            "from_state": current_state,
            "to_state": current_state,
            "reason": f"State {current_state} remains appropriate (health={health:.2f}).",
            "confidence": round(conf, 4),
            OLC: True,
        }

    _TRANSITION_MAP = {
        ("onboarding", "probation"): "graduated_onboarding",
        ("probation", "active"): "validated_fit",
        ("active", "scaling"): "growth_breakout",
        ("active", "plateauing"): "growth_stall",
        ("active", "decaying"): "performance_decline",
        ("scaling", "plateauing"): "growth_ceiling",
        ("scaling", "active"): "normalised_growth",
        ("plateauing", "decaying"): "continued_decline",
        ("plateauing", "active"): "recovery",
        ("decaying", "retired"): "sunset",
        ("retired", "relaunch_candidate"): "relaunch_evaluation",
        ("relaunch_candidate", "probation"): "relaunch_attempt",
        ("seasonal_pause", "active"): "season_resume",
        ("active", "seasonal_pause"): "season_pause",
    }

    pair = (current_state, assessed_state)
    event_type = _TRANSITION_MAP.get(pair, f"transition_{current_state}_to_{assessed_state}")

    reasons = []
    if decay > 0.5:
        reasons.append(f"decay score {decay:.2f} above threshold")
    if health < 0.4:
        reasons.append(f"health {health:.2f} below healthy range")
    if dep_risk > 0.7:
        reasons.append(f"dependency risk {dep_risk:.2f} is high")
    if not reasons:
        reasons.append(f"metrics support transition to {assessed_state}")

    return {
        "event_type": event_type,
        "from_state": current_state,
        "to_state": assessed_state,
        "reason": "; ".join(reasons) + ".",
        "confidence": round(_clamp(conf * 0.95), 4),
        OLC: True,
    }
