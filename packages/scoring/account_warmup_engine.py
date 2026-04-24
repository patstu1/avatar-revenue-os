"""Account warmup engine — warmup plans, output control, maturity state, ramp events.

Pure functions only (no I/O, no SQLAlchemy). All logic deterministic.
Uses PLATFORM_SPECS from packages/scoring/growth_pack/platform_os.py as source of truth.
"""
from __future__ import annotations

from typing import Any

from packages.scoring.growth_pack.platform_os import PLATFORM_SPECS

AWE = "account_warmup_engine"

MATURITY_STATES = [
    "newborn",
    "warming",
    "stable",
    "scaling",
    "max_output",
    "saturated",
    "cooling",
    "at_risk",
]

WARMUP_PHASES = [
    "phase_1_warmup",
    "phase_2_ramp",
    "phase_3_max_output",
    "phase_4_adaptive_throttle",
]

RAMP_EVENT_TYPES = [
    "increase",
    "decrease",
    "hold",
    "pause",
    "resume",
    "split",
]

_WARMUP_PHASE_THRESHOLDS = {
    "phase_1_warmup": {"min_posts": 0, "min_days": 0},
    "phase_2_ramp": {"min_posts": 5, "min_days": 14},
    "phase_3_max_output": {"min_posts": 20, "min_days": 30},
    "phase_4_adaptive_throttle": {"min_posts": 50, "min_days": 60},
}

_CONTENT_MIX_BY_PHASE: dict[str, dict[str, float]] = {
    "phase_1_warmup": {
        "value_content": 0.60,
        "engagement_content": 0.30,
        "offer_content": 0.05,
        "repurpose_content": 0.05,
    },
    "phase_2_ramp": {
        "value_content": 0.45,
        "engagement_content": 0.25,
        "offer_content": 0.15,
        "repurpose_content": 0.15,
    },
    "phase_3_max_output": {
        "value_content": 0.35,
        "engagement_content": 0.20,
        "offer_content": 0.25,
        "repurpose_content": 0.20,
    },
    "phase_4_adaptive_throttle": {
        "value_content": 0.40,
        "engagement_content": 0.15,
        "offer_content": 0.30,
        "repurpose_content": 0.15,
    },
}

_HEALTH_WEIGHTS = {
    "engagement_rate": 0.25,
    "follower_velocity": 0.20,
    "no_violations": 0.25,
    "monetization_response": 0.15,
    "consistency": 0.15,
}


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _get_platform_spec(platform: str) -> dict[str, Any]:
    """Resolve platform spec with fallback to youtube."""
    p = platform.lower().strip()
    if p in ("x", "twitter"):
        p = "twitter"
    return PLATFORM_SPECS.get(p, PLATFORM_SPECS["youtube"])


def _determine_warmup_phase(
    posts_published: int,
    account_age_days: int,
    has_violations: bool,
    engagement_rate: float,
) -> str:
    """Classify the current warmup phase based on account maturity signals."""
    if has_violations:
        return "phase_1_warmup"

    p4 = _WARMUP_PHASE_THRESHOLDS["phase_4_adaptive_throttle"]
    if posts_published >= p4["min_posts"] and account_age_days >= p4["min_days"]:
        return "phase_4_adaptive_throttle"

    p3 = _WARMUP_PHASE_THRESHOLDS["phase_3_max_output"]
    if posts_published >= p3["min_posts"] and account_age_days >= p3["min_days"]:
        if engagement_rate >= 0.02:
            return "phase_3_max_output"
        return "phase_2_ramp"

    p2 = _WARMUP_PHASE_THRESHOLDS["phase_2_ramp"]
    if posts_published >= p2["min_posts"] and account_age_days >= p2["min_days"]:
        return "phase_2_ramp"

    return "phase_1_warmup"


def compute_warmup_plan(
    account: dict[str, Any],
    platform_policy: dict[str, Any],
    performance_history: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute a warmup plan for an account based on its age, output, and health.

    Parameters
    ----------
    account:
        Account dict. Expected keys: account_id (str), platform (str),
        account_age_days (int), posts_published (int), engagement_rate (float),
        has_violations (bool), follower_count (int).
    platform_policy:
        Platform policy dict from seed_platform_warmup_policies or equivalent.
        Expected keys: platform, warmup_cadence, max_safe_output_per_day,
        scale_ready_conditions, spam_fatigue_signals, ramp_behavior.
    performance_history:
        List of recent performance dicts. Expected keys: week_number (int),
        posts_count (int), engagement_rate (float), follower_delta (int).

    Returns
    -------
    dict with all fields needed for AccountWarmupPlan.
    """
    platform = str(account.get("platform", "youtube"))
    spec = _get_platform_spec(platform)
    posts = int(account.get("posts_published", 0))
    age_days = int(account.get("account_age_days", 0))
    eng_rate = float(account.get("engagement_rate", 0.0))
    has_violations = bool(account.get("has_violations", False))

    warmup_cadence = platform_policy.get("warmup_cadence", spec.get("warmup_cadence", {}))
    max_safe_daily = int(platform_policy.get("max_safe_output_per_day", spec.get("max_safe_output_per_day", 3)))
    cadence = spec.get("posting_cadence_posts_per_week", {"min": 3, "max": 14})

    phase = _determine_warmup_phase(posts, age_days, has_violations, eng_rate)

    initial_ppw = int(warmup_cadence.get("week_1", 1))
    if phase == "phase_1_warmup":
        current_ppw = int(warmup_cadence.get("week_1", 1))
    elif phase == "phase_2_ramp":
        current_ppw = int(warmup_cadence.get("week_3_4", 3))
    elif phase == "phase_3_max_output":
        current_ppw = int(cadence.get("max", 14))
    else:
        recent_avg = _avg_weekly_posts(performance_history, lookback=4)
        current_ppw = max(1, int(recent_avg * 0.85)) if recent_avg > 0 else int(warmup_cadence.get("week_3_4", 3))

    target_ppw = min(int(cadence.get("max", 14)), max_safe_daily * 7)
    if phase in ("phase_1_warmup", "phase_2_ramp"):
        target_ppw = min(target_ppw, int(warmup_cadence.get("steady_state_min", cadence.get("min", 3))))

    engagement_target = 0.03 if phase in ("phase_1_warmup", "phase_2_ramp") else 0.02
    trust_target = 0.0
    if phase == "phase_1_warmup":
        trust_target = 0.0
    elif phase == "phase_2_ramp":
        trust_target = 0.3
    elif phase == "phase_3_max_output":
        trust_target = 0.7
    else:
        trust_target = 0.85

    content_mix = _CONTENT_MIX_BY_PHASE.get(phase, _CONTENT_MIX_BY_PHASE["phase_1_warmup"])

    failure_signals = list(platform_policy.get("spam_fatigue_signals", spec.get("spam_fatigue_signals", [])))
    if has_violations:
        failure_signals.append("existing_violations_present")

    ramp_conditions = list(platform_policy.get("scale_ready_conditions", spec.get("scale_ready_conditions", [])))

    explanation = (
        f"Account {account.get('account_id', '?')} on {platform}: "
        f"phase={phase}, age={age_days}d, {posts} posts. "
        f"Cadence {current_ppw}→{target_ppw}/wk. "
        f"Engagement target {engagement_target:.1%}, trust target {trust_target:.0%}."
    )

    return {
        "account_id": account.get("account_id"),
        "platform": platform,
        "warmup_phase": phase,
        "initial_posts_per_week": initial_ppw,
        "current_posts_per_week": current_ppw,
        "target_posts_per_week": target_ppw,
        "engagement_target": engagement_target,
        "trust_target": trust_target,
        "content_mix": content_mix,
        "failure_signals": failure_signals,
        "ramp_conditions": ramp_conditions,
        "ramp_behavior": platform_policy.get("ramp_behavior", spec.get("ramp_behavior", "moderate")),
        "account_age_days": age_days,
        "posts_published": posts,
        "explanation": explanation,
        AWE: True,
    }


def compute_account_output(
    account: dict[str, Any],
    warmup_plan: dict[str, Any],
    platform_policy: dict[str, Any],
    performance_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Compute current, recommended, and max output rates for an account.

    Parameters
    ----------
    account:
        Account dict (same shape as compute_warmup_plan).
    warmup_plan:
        Output of compute_warmup_plan.
    platform_policy:
        Platform policy dict.
    performance_metrics:
        Recent performance. Expected keys: posts_last_7d (int),
        engagement_rate_7d (float), monetization_revenue_7d (float),
        monetization_cost_7d (float), follower_delta_7d (int).

    Returns
    -------
    dict with all fields for AccountOutputReport.
    """
    platform = str(account.get("platform", "youtube"))
    spec = _get_platform_spec(platform)

    posts_7d = int(performance_metrics.get("posts_last_7d", 0))
    eng_rate = float(performance_metrics.get("engagement_rate_7d", 0.0))
    mon_revenue = float(performance_metrics.get("monetization_revenue_7d", 0.0))
    mon_cost = float(performance_metrics.get("monetization_cost_7d", 0.0))
    follower_delta = int(performance_metrics.get("follower_delta_7d", 0))

    current_output = posts_7d

    plan_target = int(warmup_plan.get("target_posts_per_week", 7))
    plan_current = int(warmup_plan.get("current_posts_per_week", 3))
    health = _compute_health_from_metrics(eng_rate, follower_delta, account)

    if health >= 0.7:
        recommended_output = min(plan_target, plan_current + 2)
    elif health >= 0.4:
        recommended_output = plan_current
    else:
        recommended_output = max(1, plan_current - 2)

    max_safe_daily = int(platform_policy.get("max_safe_output_per_day", spec.get("max_safe_output_per_day", 3)))
    max_safe_output = max_safe_daily * 7

    if mon_cost > 0 and mon_revenue > 0:
        roas = mon_revenue / mon_cost
        if roas >= 2.0:
            max_profitable_output = max_safe_output
        elif roas >= 1.0:
            max_profitable_output = int(max_safe_output * 0.7)
        else:
            max_profitable_output = max(1, int(current_output * 0.5))
    else:
        max_profitable_output = recommended_output

    recommended_output = min(recommended_output, max_safe_output, max_profitable_output)

    throttle_reason: str | None = None
    if recommended_output < plan_current:
        if health < 0.4:
            throttle_reason = f"Health score {health:.2f} below safe threshold."
        elif max_profitable_output < plan_current:
            throttle_reason = f"ROAS insufficient — profitable cap at {max_profitable_output}/wk."

    warmup_phase = warmup_plan.get("warmup_phase", "phase_1_warmup")
    if warmup_phase == "phase_1_warmup":
        next_increase_days = 14
    elif warmup_phase == "phase_2_ramp":
        next_increase_days = 7
    elif warmup_phase == "phase_3_max_output":
        next_increase_days = 14 if health >= 0.6 else 21
    else:
        next_increase_days = 7 if health >= 0.7 else 28

    explanation = (
        f"Account {account.get('account_id', '?')} output: "
        f"current={current_output}/wk, recommended={recommended_output}/wk, "
        f"max_safe={max_safe_output}/wk, max_profitable={max_profitable_output}/wk. "
        f"Health={health:.2f}."
    )
    if throttle_reason:
        explanation += f" Throttled: {throttle_reason}"

    return {
        "account_id": account.get("account_id"),
        "platform": platform,
        "warmup_phase": warmup_phase,
        "current_output_per_week": current_output,
        "recommended_output_per_week": recommended_output,
        "max_safe_output_per_week": max_safe_output,
        "max_profitable_output_per_week": max_profitable_output,
        "throttle_reason": throttle_reason,
        "health_score": round(health, 4),
        "next_increase_days": next_increase_days,
        "explanation": explanation,
        AWE: True,
    }


def compute_maturity_state(
    account: dict[str, Any],
    performance_history: list[dict[str, Any]],
    platform_policy: dict[str, Any],
) -> dict[str, Any]:
    """Classify account maturity state and compute transition-ready metrics.

    Parameters
    ----------
    account:
        Account dict. Expected keys: account_id, platform, account_age_days,
        posts_published, engagement_rate, follower_count, has_violations,
        current_maturity_state (str, optional), days_in_current_state (int, optional).
    performance_history:
        List of weekly dicts: week_number, posts_count, engagement_rate,
        follower_delta, revenue.
    platform_policy:
        Platform policy dict.

    Returns
    -------
    dict with all fields for AccountMaturityReport.
    """
    platform = str(account.get("platform", "youtube"))
    spec = _get_platform_spec(platform)
    posts = int(account.get("posts_published", 0))
    age_days = int(account.get("account_age_days", 0))
    float(account.get("engagement_rate", 0.0))
    int(account.get("follower_count", 0))
    has_violations = bool(account.get("has_violations", False))
    current_state = account.get("current_maturity_state", None)
    days_current = int(account.get("days_in_current_state", 0))

    max_safe_daily = int(platform_policy.get("max_safe_output_per_day", spec.get("max_safe_output_per_day", 3)))
    max_weekly = max_safe_daily * 7

    avg_eng = _avg_engagement(performance_history, lookback=4)
    follower_vel = _follower_velocity(performance_history, lookback=4)
    avg_weekly_posts = _avg_weekly_posts(performance_history, lookback=4)

    health = _compute_health_from_metrics(avg_eng, follower_vel, account)

    new_state = _classify_maturity(
        age_days=age_days,
        posts=posts,
        avg_eng=avg_eng,
        follower_vel=follower_vel,
        avg_weekly_posts=avg_weekly_posts,
        max_weekly=max_weekly,
        has_violations=has_violations,
        health=health,
    )

    state_changed = current_state is not None and new_state != current_state
    if state_changed:
        days_in_new = 0
        transition_from = current_state
        transition_to = new_state
    else:
        days_in_new = days_current
        transition_from = None
        transition_to = None

    explanation = (
        f"Account {account.get('account_id', '?')} maturity: {new_state}. "
        f"Age {age_days}d, {posts} posts, avg engagement {avg_eng:.3f}, "
        f"follower velocity {follower_vel:+.0f}/wk, health {health:.2f}."
    )
    if state_changed:
        explanation += f" Transition: {transition_from} → {transition_to}."

    return {
        "account_id": account.get("account_id"),
        "platform": platform,
        "maturity_state": new_state,
        "previous_state": current_state,
        "state_changed": state_changed,
        "transition_from": transition_from,
        "transition_to": transition_to,
        "days_in_current_state": days_in_new,
        "posts_published": posts,
        "avg_engagement_rate": round(avg_eng, 4),
        "follower_velocity": round(follower_vel, 2),
        "avg_weekly_posts": round(avg_weekly_posts, 2),
        "health_score": round(health, 4),
        "explanation": explanation,
        AWE: True,
    }


def compute_output_ramp_event(
    current_output: int,
    account_maturity: dict[str, Any],
    platform_policy: dict[str, Any],
    account_health: float,
) -> dict[str, Any] | None:
    """Decide if an output ramp event should occur.

    Parameters
    ----------
    current_output:
        Current posts per week.
    account_maturity:
        Output of compute_maturity_state.
    platform_policy:
        Platform policy dict.
    account_health:
        Health score (0-1).

    Returns
    -------
    dict with event_type, from_output, to_output, reason, confidence — or None
    if no ramp change is needed.
    """
    state = account_maturity.get("maturity_state", "stable")
    platform = account_maturity.get("platform", "youtube")
    spec = _get_platform_spec(platform)

    max_safe_daily = int(platform_policy.get("max_safe_output_per_day", spec.get("max_safe_output_per_day", 3)))
    max_weekly = max_safe_daily * 7
    cadence = spec.get("posting_cadence_posts_per_week", {"min": 3, "max": 14})
    min_weekly = int(cadence.get("min", 3))

    if account_health < 0.2:
        return {
            "event_type": "pause",
            "from_output": current_output,
            "to_output": 0,
            "reason": f"Health critically low ({account_health:.2f}). Pause output.",
            "confidence": 0.90,
            AWE: True,
        }

    if account_health < 0.35:
        target = max(1, current_output - 2)
        if target < current_output:
            return {
                "event_type": "decrease",
                "from_output": current_output,
                "to_output": target,
                "reason": f"Health below threshold ({account_health:.2f}). Reducing output.",
                "confidence": 0.80,
                AWE: True,
            }

    if state == "at_risk":
        target = max(min_weekly, current_output - 3)
        if target < current_output:
            return {
                "event_type": "decrease",
                "from_output": current_output,
                "to_output": target,
                "reason": "Account at risk — reducing output to stabilize.",
                "confidence": 0.85,
                AWE: True,
            }

    if state == "cooling":
        target = max(min_weekly, int(current_output * 0.7))
        if target < current_output:
            return {
                "event_type": "decrease",
                "from_output": current_output,
                "to_output": target,
                "reason": "Cooling state — tapering output.",
                "confidence": 0.75,
                AWE: True,
            }

    if state == "saturated" and current_output >= max_weekly:
        return {
            "event_type": "split",
            "from_output": current_output,
            "to_output": int(current_output * 0.6),
            "reason": "Saturated at max output — recommend splitting to new account.",
            "confidence": 0.70,
            AWE: True,
        }

    if state in ("warming", "stable", "scaling") and account_health >= 0.6:
        headroom = max_weekly - current_output
        if headroom >= 2:
            increment = min(3, headroom)
            if state == "scaling":
                increment = min(5, headroom)
            return {
                "event_type": "increase",
                "from_output": current_output,
                "to_output": current_output + increment,
                "reason": (
                    f"State '{state}', health {account_health:.2f} — "
                    f"increasing by {increment}/wk."
                ),
                "confidence": round(_clamp(0.55 + account_health * 0.3), 4),
                AWE: True,
            }

    if current_output == 0 and account_health >= 0.4 and state not in ("at_risk",):
        return {
            "event_type": "resume",
            "from_output": 0,
            "to_output": min_weekly,
            "reason": f"Resuming at minimum cadence ({min_weekly}/wk).",
            "confidence": 0.65,
            AWE: True,
        }

    return None


def seed_platform_warmup_policies() -> list[dict[str, Any]]:
    """Generate warmup policies for all 7 supported platforms from PLATFORM_SPECS.

    Returns
    -------
    list[dict] — one dict per platform matching PlatformWarmupPolicy fields.
    """
    policies: list[dict[str, Any]] = []

    for platform, spec in PLATFORM_SPECS.items():
        cadence = spec.get("posting_cadence_posts_per_week", {"min": 3, "max": 14})
        warmup = spec.get("warmup_cadence", {})
        max_safe = spec.get("max_safe_output_per_day", 3)

        policies.append({
            "platform": platform,
            "posting_cadence_min": cadence.get("min", 3),
            "posting_cadence_max": cadence.get("max", 14),
            "warmup_cadence": warmup,
            "max_safe_output_per_day": max_safe,
            "ramp_behavior": spec.get("ramp_behavior", "moderate"),
            "scale_ready_conditions": spec.get("scale_ready_conditions", []),
            "spam_fatigue_signals": spec.get("spam_fatigue_signals", []),
            "account_health_signals": spec.get("account_health_signals", []),
            "saturation_indicators": spec.get("saturation_indicators", []),
            "expansion_conditions": spec.get("expansion_conditions", []),
            "time_to_signal_days_min": spec.get("time_to_signal_days_range", {}).get("min", 7),
            "time_to_signal_days_max": spec.get("time_to_signal_days_range", {}).get("max", 30),
            "recommended_roles": spec.get("recommended_roles", []),
            "monetization_styles": spec.get("monetization_styles", []),
            AWE: True,
        })

    return policies


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _avg_weekly_posts(history: list[dict[str, Any]], lookback: int = 4) -> float:
    """Average posts/week from most recent N weeks of history."""
    if not history:
        return 0.0
    recent = sorted(history, key=lambda h: h.get("week_number", 0), reverse=True)[:lookback]
    total = sum(int(h.get("posts_count", 0)) for h in recent)
    return total / len(recent) if recent else 0.0


def _avg_engagement(history: list[dict[str, Any]], lookback: int = 4) -> float:
    recent = sorted(history, key=lambda h: h.get("week_number", 0), reverse=True)[:lookback]
    if not recent:
        return 0.0
    total = sum(float(h.get("engagement_rate", 0)) for h in recent)
    return total / len(recent)


def _follower_velocity(history: list[dict[str, Any]], lookback: int = 4) -> float:
    """Average follower delta per week over recent history."""
    recent = sorted(history, key=lambda h: h.get("week_number", 0), reverse=True)[:lookback]
    if not recent:
        return 0.0
    total = sum(int(h.get("follower_delta", 0)) for h in recent)
    return total / len(recent)


def _compute_health_from_metrics(
    engagement_rate: float,
    follower_velocity: float,
    account: dict[str, Any],
) -> float:
    """Weighted health score from engagement, growth, and violations."""
    eng_score = _clamp(engagement_rate / 0.05)
    fv_score = _clamp((follower_velocity + 50) / 100)
    violation_penalty = 0.3 if account.get("has_violations") else 0.0

    health = (
        eng_score * _HEALTH_WEIGHTS["engagement_rate"]
        + fv_score * _HEALTH_WEIGHTS["follower_velocity"]
        + (1.0 - violation_penalty) * _HEALTH_WEIGHTS["no_violations"]
        + 0.5 * _HEALTH_WEIGHTS["monetization_response"]
        + 0.5 * _HEALTH_WEIGHTS["consistency"]
    )
    return _clamp(health)


def _classify_maturity(
    *,
    age_days: int,
    posts: int,
    avg_eng: float,
    follower_vel: float,
    avg_weekly_posts: float,
    max_weekly: int,
    has_violations: bool,
    health: float,
) -> str:
    """Deterministic maturity classification."""
    if has_violations and health < 0.3:
        return "at_risk"

    if age_days < 7:
        return "newborn"

    if age_days < 21 or posts < 5:
        return "warming"

    if health < 0.25:
        return "at_risk"

    if health < 0.4 and follower_vel < -10:
        return "cooling"

    if avg_weekly_posts >= max_weekly * 0.9 and avg_eng < 0.015:
        return "saturated"

    if avg_weekly_posts >= max_weekly * 0.85:
        return "max_output"

    if follower_vel > 20 and avg_eng >= 0.025 and posts >= 20:
        return "scaling"

    if posts >= 10 and avg_eng >= 0.015:
        return "stable"

    return "warming"
