"""Brain Architecture Phase D — meta-monitoring, self-correction, readiness, escalation engines."""
from __future__ import annotations

from typing import Any

HEALTH_BANDS = ["excellent", "good", "medium", "degraded", "critical"]
READINESS_BANDS = ["ready", "mostly_ready", "partially_ready", "not_ready", "blocked"]
URGENCY_LEVELS = ["critical", "high", "medium", "low"]
CORRECTION_TYPES = [
    "lower_confidence", "increase_guard_mode", "reduce_output",
    "increase_suppression", "rerank_priorities", "escalate_missing_data",
    "pause_paid", "tighten_budget", "flag_dead_agent",
]

READINESS_ACTIONS = [
    "launch", "scale", "auto_run", "paid_amplify",
    "sponsor_push", "high_ticket_push", "expand_platform_count",
]


# ── Meta-Monitoring Engine ────────────────────────────────────────────

def compute_meta_monitoring(ctx: dict[str, Any]) -> dict[str, Any]:
    total_decisions = ctx.get("total_decisions", 0)
    low_confidence_decisions = ctx.get("low_confidence_decisions", 0)
    manual_mode_count = ctx.get("manual_mode_count", 0)
    total_policies = ctx.get("total_policies", 0)
    execution_failures = ctx.get("execution_failures", 0)
    total_executions = ctx.get("total_executions", 0)
    memory_entries = ctx.get("memory_entries", 0)
    stale_memory = ctx.get("stale_memory_entries", 0)
    escalation_count = ctx.get("escalation_count", 0)
    agent_run_count = ctx.get("agent_run_count", 0)
    dead_agents = ctx.get("dead_agent_count", 0)
    low_signal_agents = ctx.get("low_signal_agent_count", 0)
    wasted_actions = ctx.get("wasted_action_count", 0)
    queue_depth = ctx.get("queue_depth", 0)

    decision_quality = 1.0
    if total_decisions > 0:
        decision_quality = max(0.0, 1.0 - (low_confidence_decisions / total_decisions))

    confidence_drift = 0.0
    if total_decisions > 0:
        confidence_drift = low_confidence_decisions / total_decisions

    policy_drift = 0.0
    if total_policies > 0:
        policy_drift = manual_mode_count / total_policies

    failure_rate = 0.0
    if total_executions > 0:
        failure_rate = execution_failures / total_executions

    memory_quality = 1.0
    if memory_entries > 0:
        memory_quality = max(0.0, 1.0 - (stale_memory / memory_entries))

    esc_rate = min(1.0, escalation_count / max(total_decisions, 1) * 5)
    congestion = min(1.0, queue_depth / 100)

    health = (
        decision_quality * 0.20
        + (1.0 - confidence_drift) * 0.15
        + (1.0 - policy_drift) * 0.10
        + (1.0 - failure_rate) * 0.20
        + memory_quality * 0.10
        + (1.0 - esc_rate) * 0.05
        + (1.0 - congestion) * 0.05
        + (1.0 - min(1.0, dead_agents / max(agent_run_count, 1))) * 0.05
        + (1.0 - min(1.0, low_signal_agents / max(agent_run_count, 1))) * 0.05
        + (1.0 - min(1.0, wasted_actions / max(total_decisions, 1))) * 0.05
    )
    health = max(0.0, min(1.0, health))

    if health >= 0.85:
        band = "excellent"
    elif health >= 0.70:
        band = "good"
    elif health >= 0.50:
        band = "medium"
    elif health >= 0.30:
        band = "degraded"
    else:
        band = "critical"

    weak_areas: list[str] = []
    corrections: list[dict[str, str]] = []

    if decision_quality < 0.6:
        weak_areas.append("decision_quality")
        corrections.append({"type": "lower_confidence", "target": "brain_decisions", "reason": "Many low-confidence decisions"})
    if confidence_drift > 0.4:
        weak_areas.append("confidence_drift")
        corrections.append({"type": "increase_guard_mode", "target": "policy_engine", "reason": f"Confidence drift at {confidence_drift:.0%}"})
    if failure_rate > 0.3:
        weak_areas.append("execution_failures")
        corrections.append({"type": "reduce_output", "target": "content_runner", "reason": f"Failure rate {failure_rate:.0%}"})
    if memory_quality < 0.5:
        weak_areas.append("memory_quality")
        corrections.append({"type": "escalate_missing_data", "target": "brain_memory", "reason": "Low memory quality / stale entries"})
    if esc_rate > 0.5:
        weak_areas.append("excessive_escalation")
        corrections.append({"type": "increase_suppression", "target": "escalation_engine", "reason": f"Escalation rate {esc_rate:.0%}"})
    if congestion > 0.6:
        weak_areas.append("queue_congestion")
        corrections.append({"type": "reduce_output", "target": "queue", "reason": f"Queue congestion {congestion:.0%}"})
    if dead_agents > 0:
        weak_areas.append("dead_agent_paths")
        corrections.append({"type": "flag_dead_agent", "target": "agent_mesh", "reason": f"{dead_agents} dead agent paths"})
    if wasted_actions > 2:
        weak_areas.append("wasted_actions")
        corrections.append({"type": "increase_suppression", "target": "arbitration", "reason": f"{wasted_actions} wasted actions"})

    conf = 0.5 + health * 0.3 + (0.1 if total_decisions > 5 else 0) + (0.1 if memory_entries > 5 else 0)
    conf = min(1.0, conf)

    return {
        "health_score": round(health, 3),
        "health_band": band,
        "decision_quality_score": round(decision_quality, 3),
        "confidence_drift_score": round(confidence_drift, 3),
        "policy_drift_score": round(policy_drift, 3),
        "execution_failure_rate": round(failure_rate, 3),
        "memory_quality_score": round(memory_quality, 3),
        "escalation_rate": round(esc_rate, 3),
        "queue_congestion": round(congestion, 3),
        "dead_agent_count": dead_agents,
        "low_signal_count": low_signal_agents,
        "wasted_action_count": wasted_actions,
        "weak_areas": weak_areas,
        "recommended_corrections": corrections,
        "confidence": round(conf, 3),
        "explanation": f"Brain health {health:.0%} ({band}). {len(weak_areas)} weak areas identified.",
    }


# ── Self-Correction Engine ────────────────────────────────────────────

def compute_self_corrections(monitoring: dict[str, Any]) -> list[dict[str, Any]]:
    corrections: list[dict[str, Any]] = []

    for rec in monitoring.get("recommended_corrections", []):
        severity = "high" if monitoring["health_score"] < 0.5 else "medium"
        corrections.append({
            "correction_type": rec["type"],
            "reason": rec["reason"],
            "effect_target": rec["target"],
            "severity": severity,
            "confidence": monitoring["confidence"],
            "explanation": f"Self-correction: {rec['type']} on {rec['target']}. {rec['reason']}.",
        })

    if monitoring.get("execution_failure_rate", 0) > 0.5:
        corrections.append({
            "correction_type": "increase_guard_mode",
            "reason": f"Execution failure rate {monitoring['execution_failure_rate']:.0%} is dangerous",
            "effect_target": "all_execution_policies",
            "severity": "critical",
            "confidence": 0.9,
            "explanation": "Critical: high failure rate forces guarded mode across all policies.",
        })

    if monitoring.get("queue_congestion", 0) > 0.8:
        corrections.append({
            "correction_type": "pause_paid",
            "reason": "Queue congestion too high for additional paid traffic",
            "effect_target": "paid_amplification_agent",
            "severity": "high",
            "confidence": 0.85,
            "explanation": "Pause paid amplification until queue congestion drops below threshold.",
        })

    return corrections


# ── Readiness Brain ───────────────────────────────────────────────────

def compute_readiness_brain(ctx: dict[str, Any]) -> dict[str, Any]:
    health = ctx.get("health_score", 0.5)
    has_offers = ctx.get("has_offers", False)
    has_accounts = ctx.get("has_accounts", False)
    has_warmup = ctx.get("has_warmup_plans", False)
    has_memory = ctx.get("has_memory", False)
    account_health_avg = ctx.get("account_health_avg", 0.5)
    failure_rate = ctx.get("execution_failure_rate", 0.0)
    confidence_avg = ctx.get("confidence_avg", 0.5)
    has_credentials = ctx.get("has_platform_credentials", False)
    active_blockers = ctx.get("active_blocker_count", 0)
    escalation_rate = ctx.get("escalation_rate", 0.0)

    blockers: list[str] = []
    if not has_offers:
        blockers.append("No active offers configured")
    if not has_accounts:
        blockers.append("No active creator accounts")
    if not has_credentials:
        blockers.append("Platform credentials not connected")
    if active_blockers > 0:
        blockers.append(f"{active_blockers} active blockers unresolved")
    if failure_rate > 0.4:
        blockers.append(f"Execution failure rate {failure_rate:.0%} is too high")
    if health < 0.3:
        blockers.append(f"Brain health score {health:.0%} is critical")

    base = health * 0.25
    if has_offers:
        base += 0.15
    if has_accounts:
        base += 0.15
    if has_warmup:
        base += 0.05
    if has_memory:
        base += 0.05
    base += account_health_avg * 0.10
    base += confidence_avg * 0.10
    base += (1.0 - failure_rate) * 0.10
    base += (1.0 - escalation_rate) * 0.05
    score = max(0.0, min(1.0, base - len(blockers) * 0.08))

    if score >= 0.80:
        band = "ready"
    elif score >= 0.65:
        band = "mostly_ready"
    elif score >= 0.45:
        band = "partially_ready"
    elif score >= 0.20:
        band = "not_ready"
    else:
        band = "blocked"

    allowed: list[str] = []
    forbidden: list[str] = []

    for action in READINESS_ACTIONS:
        if action == "launch" and score >= 0.4 and has_accounts and has_offers:
            allowed.append(action)
        elif action == "scale" and score >= 0.6 and account_health_avg > 0.6:
            allowed.append(action)
        elif action == "auto_run" and score >= 0.7 and failure_rate < 0.2 and confidence_avg > 0.6:
            allowed.append(action)
        elif action == "paid_amplify" and score >= 0.6 and has_credentials and failure_rate < 0.3:
            allowed.append(action)
        elif action == "sponsor_push" and score >= 0.5 and has_offers:
            allowed.append(action)
        elif action == "high_ticket_push" and score >= 0.65 and confidence_avg > 0.6:
            allowed.append(action)
        elif action == "expand_platform_count" and score >= 0.55 and has_credentials:
            allowed.append(action)
        else:
            forbidden.append(action)

    conf = min(1.0, 0.4 + score * 0.4 + (0.1 if has_memory else 0) + (0.1 if health > 0.6 else 0))

    return {
        "readiness_score": round(score, 3),
        "readiness_band": band,
        "blockers": blockers,
        "allowed_actions": allowed,
        "forbidden_actions": forbidden,
        "confidence": round(conf, 3),
        "explanation": (
            f"Readiness {score:.0%} ({band}). "
            f"{len(allowed)} actions allowed, {len(forbidden)} forbidden. "
            f"{len(blockers)} blockers."
        ),
    }


# ── Brain-Level Escalation ────────────────────────────────────────────

def compute_brain_escalations(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    escalations: list[dict[str, Any]] = []
    blockers = ctx.get("blockers", [])
    health = ctx.get("health_score", 0.5)
    has_offers = ctx.get("has_offers", False)
    has_accounts = ctx.get("has_accounts", False)
    has_credentials = ctx.get("has_platform_credentials", False)
    failure_rate = ctx.get("execution_failure_rate", 0.0)
    active_blocker_count = ctx.get("active_blocker_count", 0)
    forbidden = ctx.get("forbidden_actions", [])

    if not has_credentials:
        escalations.append({
            "escalation_type": "connect_credential",
            "command": "Connect platform API credentials (TikTok, Instagram, YouTube, X, etc.)",
            "urgency": "critical",
            "expected_upside_unlocked": 500.0,
            "expected_cost_of_delay": 50.0,
            "value_basis": "illustrative_estimate",
            "affected_scope": "all_platforms",
            "confidence": 0.95,
            "explanation": "Platform credentials required for publishing, analytics, and audience data.",
        })

    if not has_offers:
        escalations.append({
            "escalation_type": "add_offer",
            "command": "Add at least one active monetization offer (affiliate, product, service)",
            "urgency": "critical",
            "expected_upside_unlocked": 300.0,
            "expected_cost_of_delay": 30.0,
            "value_basis": "illustrative_estimate",
            "affected_scope": "monetization",
            "confidence": 0.95,
            "explanation": "No offers configured — monetization cannot proceed.",
        })

    if not has_accounts:
        escalations.append({
            "escalation_type": "create_account",
            "command": "Create at least one creator account for content distribution",
            "urgency": "high",
            "expected_upside_unlocked": 200.0,
            "expected_cost_of_delay": 20.0,
            "value_basis": "illustrative_estimate",
            "affected_scope": "content_distribution",
            "confidence": 0.9,
            "explanation": "No creator accounts — content cannot be published.",
        })

    if failure_rate > 0.4:
        escalations.append({
            "escalation_type": "fix_execution_failures",
            "command": "Review and fix recurring execution failures before scaling",
            "urgency": "high",
            "expected_upside_unlocked": 150.0,
            "expected_cost_of_delay": 40.0,
            "value_basis": "illustrative_estimate",
            "affected_scope": "execution_pipeline",
            "confidence": 0.85,
            "explanation": f"Execution failure rate {failure_rate:.0%} is blocking safe operation.",
        })

    if health < 0.4:
        escalations.append({
            "escalation_type": "review_brain_health",
            "command": "Review meta-monitoring report and address weak areas",
            "urgency": "high",
            "expected_upside_unlocked": 100.0,
            "expected_cost_of_delay": 25.0,
            "value_basis": "illustrative_estimate",
            "affected_scope": "brain_health",
            "confidence": 0.8,
            "explanation": f"Brain health {health:.0%} is degraded — decision quality at risk.",
        })

    if active_blocker_count > 3:
        escalations.append({
            "escalation_type": "resolve_blockers",
            "command": f"Resolve {active_blocker_count} active blockers preventing autonomous operation",
            "urgency": "high",
            "expected_upside_unlocked": 80.0,
            "expected_cost_of_delay": 15.0,
            "value_basis": "illustrative_estimate",
            "affected_scope": "multiple_modules",
            "confidence": 0.8,
            "explanation": f"{active_blocker_count} unresolved blockers are constraining system throughput.",
        })

    if "auto_run" in forbidden and health > 0.5:
        escalations.append({
            "escalation_type": "approve_auto_run",
            "command": "Review and approve autonomous execution mode if system health permits",
            "urgency": "medium",
            "expected_upside_unlocked": 60.0,
            "expected_cost_of_delay": 10.0,
            "value_basis": "illustrative_estimate",
            "affected_scope": "execution_mode",
            "confidence": 0.7,
            "explanation": "Auto-run is forbidden but health is acceptable. Operator review may unlock it.",
        })

    if "paid_amplify" in forbidden and has_credentials:
        escalations.append({
            "escalation_type": "approve_paid_amplification",
            "command": "Approve paid amplification budget and review safety guardrails",
            "urgency": "medium",
            "expected_upside_unlocked": 100.0,
            "expected_cost_of_delay": 15.0,
            "value_basis": "illustrative_estimate",
            "affected_scope": "paid_traffic",
            "confidence": 0.7,
            "explanation": "Paid amplification is blocked. Operator approval and budget allocation needed.",
        })

    return escalations
