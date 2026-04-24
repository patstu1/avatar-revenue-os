"""Brain Architecture Phase B — decision, policy, confidence, cost/upside, arbitration engines."""

from __future__ import annotations

from typing import Any

DECISION_CLASSES = [
    "launch",
    "hold",
    "scale",
    "suppress",
    "monetize",
    "reroute",
    "recover",
    "escalate",
    "throttle",
    "split_account",
    "merge_lane",
    "test",
    "kill",
]

POLICY_MODES = ["autonomous", "guarded", "manual"]
CONFIDENCE_BANDS = ["very_high", "high", "medium", "low", "very_low"]

ARBITRATION_CATEGORIES = [
    "new_launch",
    "more_output",
    "funnel_fix",
    "monetization_fix",
    "paid_promotion",
    "recovery_action",
    "retention_action",
    "sponsor_action",
]


# ── Master Decision Engine ────────────────────────────────────────────


def compute_brain_decision(ctx: dict[str, Any]) -> dict[str, Any]:
    account_state = ctx.get("account_state", "warming")
    opp_state = ctx.get("opportunity_state", "monitor")
    exec_state = ctx.get("execution_state", "queued")
    audience_state = ctx.get("audience_state", "unaware")
    profit_per_post = ctx.get("profit_per_post", 0.0)
    saturation = ctx.get("saturation_score", 0.0)
    fatigue = ctx.get("fatigue_score", 0.0)
    blocker = ctx.get("has_blocker", False)
    confidence = ctx.get("confidence", 0.5)
    churn_risk = ctx.get("churn_risk", 0.0)

    alternatives: list[dict[str, Any]] = []

    if blocker:
        action = "escalate"
        objective = "Resolve blocker preventing execution"
        downstream = "Create operator escalation event"
        alternatives.append({"action": "hold", "reason": "Wait for blocker resolution"})
    elif exec_state == "failed":
        action = "recover"
        objective = "Recover from execution failure"
        downstream = "Trigger recovery flow; reroute if needed"
        alternatives.append({"action": "kill", "reason": "Abandon if recovery cost > upside"})
    elif saturation > 0.7 or opp_state == "suppress":
        action = "suppress"
        objective = "Reduce output for saturated or suppressed lane"
        downstream = "Pause or throttle content output"
        alternatives.append({"action": "throttle", "reason": "Partial reduction rather than full suppress"})
        alternatives.append({"action": "reroute", "reason": "Move resources to better opportunity"})
    elif fatigue > 0.6:
        action = "throttle"
        objective = "Reduce cadence to address audience fatigue"
        downstream = "Lower posting frequency; adjust content mix"
        alternatives.append({"action": "reroute", "reason": "Shift to less fatigued platform"})
    elif account_state == "at_risk":
        action = "recover"
        objective = "Stabilize at-risk account"
        downstream = "Apply recovery actions; monitor health"
    elif churn_risk > 0.5 and audience_state in ("bought_once", "churn_risk"):
        action = "monetize"
        objective = "Retain churning customers with targeted offers"
        downstream = "Trigger retention flow"
        alternatives.append({"action": "reroute", "reason": "Switch to reactivation campaign"})
    elif account_state == "newborn":
        action = "launch"
        objective = "Continue warmup for new account"
        downstream = "Follow warmup plan; queue initial content"
    elif opp_state == "test":
        action = "test"
        objective = "Run controlled experiment on promising opportunity"
        downstream = "Create experiment; allocate small budget"
        alternatives.append({"action": "hold", "reason": "Wait for more signal"})
    elif opp_state == "scale" and profit_per_post > 8:
        action = "scale"
        objective = "Increase output on proven winner"
        downstream = "Raise posting cadence; expand to derivative platforms"
        alternatives.append({"action": "split_account", "reason": "Create new account for sub-niche"})
    elif profit_per_post > 5 and account_state in ("stable", "scaling"):
        action = "monetize"
        objective = "Optimize monetization for stable/scaling account"
        downstream = "Review offer routing; test higher-ticket offers"
        alternatives.append({"action": "scale", "reason": "Increase output volume"})
    elif account_state == "max_output":
        action = "hold"
        objective = "Maintain max output; avoid burnout"
        downstream = "Monitor for saturation; prepare split strategy"
        alternatives.append({"action": "split_account", "reason": "Clone winning strategy into new account"})
    else:
        action = "hold"
        objective = "Insufficient signal to act — continue monitoring"
        downstream = "Queue for next recompute cycle"
        alternatives.append({"action": "test", "reason": "Small test if readiness improves"})

    return {
        "decision_class": action,
        "objective": objective,
        "selected_action": action,
        "alternatives": alternatives,
        "downstream_action": downstream,
        "confidence": round(confidence, 3),
        "explanation": f"Decision: {action}. {objective}.",
    }


# ── Policy Engine ─────────────────────────────────────────────────────


def compute_policy_evaluation(ctx: dict[str, Any]) -> dict[str, Any]:
    confidence = ctx.get("confidence", 0.5)
    risk = ctx.get("risk_score", 0.3)
    cost = ctx.get("cost", 0.0)
    platform_sensitivity = ctx.get("platform_sensitivity", 0.3)
    compliance_sensitivity = ctx.get("compliance_sensitivity", 0.2)
    account_health = ctx.get("account_health_score", 0.8)
    budget_impact = ctx.get("budget_impact", 0.0)
    cost_threshold = ctx.get("auto_approve_cost_limit", 50.0)
    operator_override = ctx.get("operator_override_mode", None)

    if operator_override in POLICY_MODES:
        mode = operator_override
        reason = f"Operator manually set mode to '{operator_override}'"
        approval = mode != "autonomous"
    elif compliance_sensitivity > 0.7:
        mode = "manual"
        reason = f"Compliance sensitivity {compliance_sensitivity:.0%} requires manual review"
        approval = True
    elif risk > 0.7 or account_health < 0.3:
        mode = "manual"
        reason = f"High risk ({risk:.0%}) or poor account health ({account_health:.0%})"
        approval = True
    elif cost > cost_threshold or budget_impact > 100:
        mode = "guarded"
        reason = f"Cost ${cost:.0f} exceeds auto-approve limit ${cost_threshold:.0f}"
        approval = True
    elif confidence < 0.5 or platform_sensitivity > 0.6:
        mode = "guarded"
        reason = f"Low confidence ({confidence:.0%}) or platform sensitive ({platform_sensitivity:.0%})"
        approval = True
    elif confidence >= 0.7 and risk <= 0.3 and cost <= cost_threshold:
        mode = "autonomous"
        reason = f"High confidence ({confidence:.0%}), low risk ({risk:.0%}), cost ${cost:.0f} within limit"
        approval = False
    else:
        mode = "guarded"
        reason = "Mixed signals — defaulting to guarded"
        approval = True

    hard_stop = None
    if compliance_sensitivity > 0.8:
        hard_stop = "Compliance review required before any execution"
    elif risk > 0.85:
        hard_stop = "Risk exceeds safety threshold — block execution"

    rollback = None
    if cost > 20:
        rollback = f"Revert action and recover up to ${cost:.0f} if outcome negative within 7 days"

    return {
        "policy_mode": mode,
        "reason": reason,
        "approval_needed": approval,
        "hard_stop_rule": hard_stop,
        "rollback_rule": rollback,
        "risk_score": round(risk, 3),
        "cost_impact": round(cost, 2),
        "explanation": f"Policy: {mode}. {reason}.",
    }


# ── Confidence Engine ─────────────────────────────────────────────────


def compute_confidence_report(ctx: dict[str, Any]) -> dict[str, Any]:
    signal_strength = ctx.get("signal_strength", 0.5)
    historical_precedent = ctx.get("historical_precedent", 0.5)
    saturation_risk = ctx.get("saturation_risk", 0.0)
    memory_support = ctx.get("memory_support", 0.3)
    data_completeness = ctx.get("data_completeness", 0.5)
    execution_history = ctx.get("execution_history", 0.5)
    blocker_severity = ctx.get("blocker_severity", 0.0)

    w = {
        "signal_strength": 0.25,
        "historical_precedent": 0.20,
        "data_completeness": 0.20,
        "execution_history": 0.15,
        "memory_support": 0.10,
        "sat_penalty": 0.05,
        "blocker_penalty": 0.05,
    }
    raw = (
        signal_strength * w["signal_strength"]
        + historical_precedent * w["historical_precedent"]
        + data_completeness * w["data_completeness"]
        + execution_history * w["execution_history"]
        + memory_support * w["memory_support"]
        - saturation_risk * w["sat_penalty"]
        - blocker_severity * w["blocker_penalty"]
    )
    score = max(0.0, min(1.0, raw))

    if score >= 0.85:
        band = "very_high"
    elif score >= 0.7:
        band = "high"
    elif score >= 0.5:
        band = "medium"
    elif score >= 0.3:
        band = "low"
    else:
        band = "very_low"

    factors: list[str] = []
    if data_completeness < 0.4:
        factors.append("Incomplete data reduces reliability")
    if saturation_risk > 0.5:
        factors.append(f"Saturation risk at {saturation_risk:.0%}")
    if blocker_severity > 0.5:
        factors.append(f"Active blockers (severity {blocker_severity:.0%})")
    if signal_strength < 0.3:
        factors.append("Weak signal strength")
    if historical_precedent < 0.3:
        factors.append("Limited historical precedent")

    return {
        "confidence_score": round(score, 3),
        "confidence_band": band,
        "signal_strength": round(signal_strength, 3),
        "historical_precedent": round(historical_precedent, 3),
        "saturation_risk": round(saturation_risk, 3),
        "memory_support": round(memory_support, 3),
        "data_completeness": round(data_completeness, 3),
        "execution_history": round(execution_history, 3),
        "blocker_severity": round(blocker_severity, 3),
        "uncertainty_factors": factors,
        "explanation": f"Confidence {score:.0%} ({band}). {'; '.join(factors) if factors else 'No major uncertainty.'}",
    }


# ── Cost / Upside Estimation ─────────────────────────────────────────


def compute_upside_cost_estimate(ctx: dict[str, Any]) -> dict[str, Any]:
    revenue_potential = ctx.get("revenue_potential", 0.0)
    conversion_rate = ctx.get("conversion_rate", 0.03)
    traffic_estimate = ctx.get("traffic_estimate", 1000)
    content_cost = ctx.get("content_cost", 10.0)
    platform_cost = ctx.get("platform_cost", 0.0)
    paid_spend = ctx.get("paid_spend", 0.0)
    tool_cost = ctx.get("tool_cost", 5.0)
    time_to_revenue_days = ctx.get("time_to_revenue_days", 30)
    concentration = ctx.get("concentration_share", 0.0)

    upside = revenue_potential * conversion_rate * traffic_estimate / 100
    cost = content_cost + platform_cost + paid_spend + tool_cost
    net = upside - cost
    payback = time_to_revenue_days if net > 0 else 999

    ops_burden = 0.2
    if paid_spend > 100:
        ops_burden += 0.3
    if content_cost > 50:
        ops_burden += 0.2
    ops_burden = min(1.0, ops_burden)

    conc_risk = concentration
    if conc_risk > 0.5:
        conc_risk = min(1.0, conc_risk * 1.3)

    return {
        "expected_upside": round(upside, 2),
        "expected_cost": round(cost, 2),
        "expected_payback_days": payback,
        "operational_burden": round(ops_burden, 3),
        "concentration_risk": round(conc_risk, 3),
        "net_value": round(net, 2),
        "explanation": (
            f"Upside ${upside:.0f}, cost ${cost:.0f}, net ${net:.0f}. "
            f"Payback ~{payback}d. Ops burden {ops_burden:.0%}, concentration risk {conc_risk:.0%}."
        ),
    }


# ── Priority Arbitration ─────────────────────────────────────────────


def compute_arbitration(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    if not candidates:
        return {
            "ranked_priorities": [],
            "chosen_winner_class": "hold",
            "chosen_winner_label": "No competing actions to arbitrate",
            "rejected_actions": [],
            "competing_count": 0,
            "net_value_chosen": 0.0,
            "explanation": "No candidates for arbitration.",
        }

    weight_map = {
        "recovery_action": 1.5,
        "funnel_fix": 1.3,
        "monetization_fix": 1.2,
        "retention_action": 1.15,
        "new_launch": 1.0,
        "more_output": 0.95,
        "paid_promotion": 0.90,
        "sponsor_action": 0.85,
    }

    scored = []
    for c in candidates:
        cat = c.get("category", "more_output")
        net = c.get("net_value", 0.0)
        conf = c.get("confidence", 0.5)
        urgency = c.get("urgency", 0.5)
        cat_weight = weight_map.get(cat, 1.0)
        composite = (net * 0.4 + conf * 30 * 0.3 + urgency * 30 * 0.3) * cat_weight
        scored.append({**c, "_composite": composite})

    scored.sort(key=lambda x: x["_composite"], reverse=True)

    winner = scored[0]
    rejected = []
    for s in scored[1:]:
        rejected.append(
            {
                "category": s.get("category"),
                "label": s.get("label", ""),
                "reason": f"Lower composite score ({s['_composite']:.1f} vs {winner['_composite']:.1f})",
            }
        )

    ranked = [
        {"rank": i + 1, "category": s.get("category"), "label": s.get("label", ""), "score": round(s["_composite"], 2)}
        for i, s in enumerate(scored)
    ]

    return {
        "ranked_priorities": ranked,
        "chosen_winner_class": winner.get("category", "hold"),
        "chosen_winner_label": winner.get("label", ""),
        "rejected_actions": rejected,
        "competing_count": len(candidates),
        "net_value_chosen": round(winner.get("net_value", 0.0), 2),
        "explanation": f"Winner: {winner.get('category')} — '{winner.get('label', '')}' (score {winner['_composite']:.1f}). {len(rejected)} alternatives rejected.",
    }
