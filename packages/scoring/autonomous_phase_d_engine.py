"""Autonomous Phase D — agent orchestration, revenue pressure, overrides, blockers, escalations (pure functions)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

APDE = "autonomous_phase_d_engine"

AGENT_TYPES = [
    "trend_scout",
    "niche_allocator",
    "monetization_router",
    "funnel_optimizer",
    "scale_commander",
    "account_launcher",
    "recovery_agent",
    "sponsor_strategist",
    "pricing_strategist",
    "retention_strategist",
    "paid_amplification_agent",
    "ops_watchdog",
]


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# Agent orchestration
# ---------------------------------------------------------------------------

def run_agent_cycle(
    brand_context: dict[str, Any],
) -> list[dict[str, Any]]:
    """Run one orchestration cycle for all specialist agents.

    brand_context keys: accounts_count, offers_count, queue_depth, avg_health,
    avg_engagement, revenue_trend, suppression_count, funnel_leak_score,
    paid_active, sponsor_pipeline, retention_risk, provider_failures
    """
    accts = int(brand_context.get("accounts_count", 0))
    offers = int(brand_context.get("offers_count", 0))
    q_depth = int(brand_context.get("queue_depth", 0))
    health = _clamp(float(brand_context.get("avg_health", 0.5)))
    eng = _clamp(float(brand_context.get("avg_engagement", 0.02)))
    rev_trend = str(brand_context.get("revenue_trend", "flat"))
    supp_count = int(brand_context.get("suppression_count", 0))
    leak = _clamp(float(brand_context.get("funnel_leak_score", 0.3)))
    paid = bool(brand_context.get("paid_active", False))
    sponsor_pipe = int(brand_context.get("sponsor_pipeline", 0))
    ret_risk = _clamp(float(brand_context.get("retention_risk", 0.2)))
    prov_fail = bool(brand_context.get("provider_failures", False))

    runs: list[dict[str, Any]] = []
    messages: list[dict[str, Any]] = []

    def add(agent: str, output: dict, cmds: list[dict] | None = None, msgs: list[dict] | None = None):
        runs.append({
            "agent_type": agent,
            "run_status": "completed",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "input_context_json": brand_context,
            "output_json": output,
            "commands_json": cmds or [],
            APDE: True,
        })
        for m in (msgs or []):
            messages.append({
                "sender_agent": agent,
                "receiver_agent": m.get("to"),
                "message_type": m.get("type", "recommendation"),
                "payload_json": m.get("payload"),
                "explanation": m.get("explanation"),
                APDE: True,
            })

    add("trend_scout", {
        "signals_reviewed": q_depth,
        "top_opportunity": "rising_niche_gap" if eng > 0.02 else "content_refresh_needed",
        "recommendation": "prioritize_emerging_niches" if q_depth > 5 else "scan_more_signals",
    }, msgs=[{
        "to": "niche_allocator",
        "type": "signal_handoff",
        "payload": {"priority_niches": ["ai_tools", "productivity"]},
        "explanation": "Handing top signals to niche allocator.",
    }])

    add("niche_allocator", {
        "accounts_evaluated": accts,
        "allocation_action": "rebalance" if accts > 3 and health < 0.5 else "hold",
        "recommendation": "shift_allocation_to_healthier_accounts" if health < 0.5 else "maintain_current_allocation",
    }, msgs=[{
        "to": "scale_commander",
        "type": "allocation_update",
        "payload": {"shift": "healthier_accounts"},
        "explanation": f"Avg health {health:.2f}, recommending rebalance." if health < 0.5 else "Allocation stable.",
    }])

    mon_output = {
        "routes_active": offers,
        "underused_class": "lead_gen" if offers < 3 else "none",
        "recommendation": "add_lead_gen_or_recurring" if offers < 3 else "optimize_existing_routes",
    }
    add("monetization_router", mon_output, msgs=[{
        "to": "pricing_strategist",
        "type": "route_gap",
        "payload": {"gap": mon_output["underused_class"]},
        "explanation": "Monetization gap detected." if offers < 3 else "Routes balanced.",
    }])

    add("funnel_optimizer", {
        "leak_score": leak,
        "recommendation": "patch_mid_funnel" if leak > 0.4 else "monitor",
    }, msgs=[{
        "to": "recovery_agent",
        "type": "funnel_health",
        "payload": {"leak": leak},
        "explanation": f"Leak score {leak:.2f}.",
    }])

    scale_cmd = "scale_winners" if rev_trend == "up" and health >= 0.6 else "hold_and_diagnose"
    add("scale_commander", {
        "revenue_trend": rev_trend,
        "scale_action": scale_cmd,
        "recommendation": f"{scale_cmd}: health={health:.2f}, trend={rev_trend}",
    })

    launch_action = "propose_new_account" if accts < 3 else "evaluate_expansion" if accts < 7 else "monitor"
    add("account_launcher", {
        "current_accounts": accts,
        "action": launch_action,
        "recommendation": launch_action,
    })

    add("recovery_agent", {
        "suppressions": supp_count,
        "provider_failures": prov_fail,
        "recommendation": "reroute_provider" if prov_fail else ("reduce_suppressions" if supp_count > 3 else "healthy"),
    })

    add("sponsor_strategist", {
        "pipeline_depth": sponsor_pipe,
        "recommendation": "expand_pipeline" if sponsor_pipe < 5 else "nurture_existing",
    })

    add("pricing_strategist", {
        "offers_count": offers,
        "recommendation": "introduce_tiered_pricing" if offers >= 2 else "build_first_offer_ladder",
    })

    add("retention_strategist", {
        "retention_risk": ret_risk,
        "recommendation": "trigger_reactivation" if ret_risk > 0.5 else "upsell_window_check",
    })

    add("paid_amplification_agent", {
        "paid_active": paid,
        "recommendation": "identify_new_winners_for_paid" if not paid else "monitor_and_optimize",
    })

    watchdog_issues: list[str] = []
    if health < 0.35:
        watchdog_issues.append("avg_health_critical")
    if supp_count > 5:
        watchdog_issues.append("excessive_suppressions")
    if prov_fail:
        watchdog_issues.append("provider_failure")
    add("ops_watchdog", {
        "issues": watchdog_issues,
        "recommendation": "escalate_operator" if watchdog_issues else "all_clear",
    })

    return [{"runs": runs, "messages": messages}]


# ---------------------------------------------------------------------------
# Revenue pressure
# ---------------------------------------------------------------------------

MONETIZATION_CLASSES = [
    "affiliate", "owned_product", "lead_gen", "sponsors", "recurring_subscription",
    "community", "high_ticket", "services", "licensing", "paid_amplification",
]

SUPPORTED_PLATFORMS = ["tiktok", "instagram", "youtube", "twitter", "reddit", "linkedin", "facebook"]


def compute_revenue_pressure(brand_snapshot: dict[str, Any]) -> dict[str, Any]:
    """Compute revenue pressure report: where money is left on the table.

    brand_snapshot keys: active_monetization_classes, active_platforms, accounts,
    offers_count, queue_winners_unexploited, funnel_leak_score, inactive_asset_classes,
    revenue_trend, avg_health, suppression_count, next_launch_candidates
    """
    active_mon = set(brand_snapshot.get("active_monetization_classes", []))
    active_plats = set(brand_snapshot.get("active_platforms", []))
    accts = int(brand_snapshot.get("accounts", 0))
    int(brand_snapshot.get("offers_count", 0))
    winners_unexpl = int(brand_snapshot.get("queue_winners_unexploited", 0))
    leak = _clamp(float(brand_snapshot.get("funnel_leak_score", 0.3)))
    inactive_assets = brand_snapshot.get("inactive_asset_classes", [])
    rev_trend = str(brand_snapshot.get("revenue_trend", "flat"))
    health = _clamp(float(brand_snapshot.get("avg_health", 0.5)))
    supp_count = int(brand_snapshot.get("suppression_count", 0))
    launch_cands = brand_snapshot.get("next_launch_candidates", [])

    underused = [c for c in MONETIZATION_CLASSES if c not in active_mon]
    underbuilt = [p for p in SUPPORTED_PLATFORMS if p not in active_plats]

    commands: list[dict[str, Any]] = []

    if underused:
        commands.append({"action": f"activate_monetization_{underused[0]}", "priority": "high",
                         "explanation": f"Monetization class '{underused[0]}' not active."})
    if winners_unexpl > 0:
        commands.append({"action": "exploit_proven_winners", "priority": "high",
                         "explanation": f"{winners_unexpl} winners not yet in paid or derivative pipeline."})
    if leak > 0.4:
        commands.append({"action": "patch_funnel_leaks", "priority": "high",
                         "explanation": f"Funnel leak score {leak:.2f} — mid-funnel drop likely."})
    if underbuilt:
        commands.append({"action": f"build_on_{underbuilt[0]}", "priority": "medium",
                         "explanation": f"Platform '{underbuilt[0]}' has no active account."})
    if supp_count > 3:
        commands.append({"action": "investigate_suppression_cluster", "priority": "medium",
                         "explanation": f"{supp_count} active suppressions — possible systemic issue."})
    if rev_trend == "down":
        commands.append({"action": "emergency_revenue_recovery", "priority": "critical",
                         "explanation": "Revenue trending down — immediate triage required."})
    if accts < 3:
        commands.append({"action": "launch_new_account", "priority": "medium",
                         "explanation": "Fewer than 3 accounts limits diversification."})

    commands = commands[:5]

    launches = []
    for cand in launch_cands[:3]:
        launches.append({
            "launch": cand.get("name", "unknown"),
            "platform": cand.get("platform", "youtube"),
            "expected_revenue": cand.get("expected_revenue", 0),
        })
    while len(launches) < 3 and underbuilt:
        p = underbuilt.pop(0)
        launches.append({"launch": f"new_{p}_account", "platform": p, "expected_revenue": 0})

    biggest_blocker = "none"
    if rev_trend == "down":
        biggest_blocker = "revenue_declining"
    elif leak > 0.5:
        biggest_blocker = f"funnel_leak_{leak:.2f}"
    elif health < 0.35:
        biggest_blocker = "avg_account_health_critical"

    biggest_missed = "none"
    if underused:
        biggest_missed = f"monetization_class_{underused[0]}_inactive"
    elif winners_unexpl > 0:
        biggest_missed = f"{winners_unexpl}_proven_winners_not_exploited"

    biggest_weak = "none"
    if supp_count > 3:
        biggest_weak = "suppressed_lanes_cluster"
    elif health < 0.4:
        biggest_weak = "low_health_accounts"

    pressure = _clamp(
        0.2
        + len(underused) * 0.08
        + len(underbuilt) * 0.05
        + (winners_unexpl * 0.06)
        + (leak * 0.15)
        + (0.2 if rev_trend == "down" else 0)
        + (supp_count * 0.03)
    )

    return {
        "next_commands_json": commands,
        "next_launches_json": launches[:3],
        "biggest_blocker": biggest_blocker,
        "biggest_missed_opportunity": biggest_missed,
        "biggest_weak_lane_to_kill": biggest_weak,
        "underused_monetization_class": underused[0] if underused else None,
        "underbuilt_platform": underbuilt[0] if underbuilt else None,
        "missing_account_suggestion": f"Launch on {underbuilt[0]}" if underbuilt else None,
        "unexploited_winner": f"{winners_unexpl} winners waiting" if winners_unexpl else None,
        "leaking_funnel": f"leak_score={leak:.2f}" if leak > 0.3 else None,
        "inactive_asset_class": inactive_assets[0] if inactive_assets else None,
        "pressure_score": round(pressure, 4),
        "explanation": f"Revenue pressure {pressure:.2f}: {len(commands)} commands, {len(launches)} launches.",
        APDE: True,
    }


# ---------------------------------------------------------------------------
# Override policies
# ---------------------------------------------------------------------------

OVERRIDE_MODES = ["autonomous", "guarded", "manual"]

_RISK_MAP: dict[str, tuple[str, bool, bool, str | None]] = {
    "publish_content": ("guarded", False, True, "Unpublish within 1h if flagged."),
    "increase_paid_spend": ("guarded", True, True, "Pause spend and revert budget."),
    "pause_account": ("guarded", True, True, "Reactivate within 24h if mistaken."),
    "launch_new_account": ("manual", True, False, None),
    "approve_sponsor_deal": ("manual", True, False, None),
    "send_outreach_email": ("guarded", False, True, "Mark as recall in CRM."),
    "change_pricing": ("manual", True, True, "Revert to previous price within 48h."),
    "suppress_lane": ("autonomous", False, True, "Re-enable lane when lift condition met."),
    "scale_winner": ("guarded", False, True, "Reduce back to prior output."),
    "emergency_budget_cap": ("autonomous", False, False, None),
    "create_content_brief": ("autonomous", False, False, None),
    "trigger_reactivation": ("guarded", False, True, "Cancel sequence if churn reverses."),
}


def compute_override_policies(
    action_refs: list[str],
    brand_context: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generate override policies for a list of action references."""
    default_mode = str(brand_context.get("default_mode", "guarded"))
    policies: list[dict[str, Any]] = []

    for ref in action_refs:
        mode, approval, rollback, plan = _RISK_MAP.get(
            ref, ("guarded", False, False, None)
        )
        if default_mode == "manual":
            mode = "manual"
            approval = True
        elif default_mode == "guarded" and mode == "autonomous":
            mode = "guarded"

        hard_stop = None
        if ref in ("increase_paid_spend", "change_pricing"):
            hard_stop = "Halt if cumulative spend exceeds daily budget ceiling."
        elif ref == "launch_new_account":
            hard_stop = "Block if compliance check pending."

        policies.append({
            "action_ref": ref,
            "override_mode": mode,
            "confidence_threshold": 0.7 if mode == "autonomous" else 0.85,
            "approval_needed": approval,
            "rollback_available": rollback,
            "rollback_plan": plan,
            "hard_stop_rule": hard_stop,
            "audit_trail_json": {"generated_at": datetime.now(timezone.utc).isoformat()},
            "explanation": f"Override for '{ref}': mode={mode}, approval={'yes' if approval else 'no'}, rollback={'yes' if rollback else 'no'}.",
            APDE: True,
        })

    return policies


# ---------------------------------------------------------------------------
# Blocker detection
# ---------------------------------------------------------------------------

BLOCKER_TYPES = [
    "missing_credential",
    "missing_offer",
    "account_not_ready",
    "funnel_blocked",
    "budget_blocked",
    "compliance_hold",
    "platform_capacity_full",
    "provider_unavailable",
    "queue_failure",
    "policy_sensitive_lane",
]


def detect_blockers(system_state: dict[str, Any]) -> list[dict[str, Any]]:
    """Detect blockers from system health signals.

    system_state keys: credentials_missing (list[str]), offers_count, accounts_not_ready (list),
    funnel_leak_score, budget_remaining, compliance_holds (list), platform_capacity (dict),
    provider_available (bool), queue_failure_rate, policy_sensitive_lanes (list)
    """
    blockers: list[dict[str, Any]] = []

    for cred in system_state.get("credentials_missing", []):
        blockers.append({
            "blocker": "missing_credential",
            "severity": "high",
            "affected_scope": f"credential:{cred}",
            "operator_action_needed": f"Connect {cred} API credentials in Settings → Providers.",
            "deadline_or_urgency": "within_24h",
            "consequence_if_ignored": f"All {cred}-dependent publishing and analytics blocked.",
            "explanation": f"Credential for '{cred}' is missing or expired.",
            APDE: True,
        })

    if system_state.get("offers_count", 1) == 0:
        blockers.append({
            "blocker": "missing_offer",
            "severity": "critical",
            "affected_scope": "brand:monetization",
            "operator_action_needed": "Create at least one active offer in Offers.",
            "deadline_or_urgency": "immediate",
            "consequence_if_ignored": "No monetization path available; all content runs unbacked.",
            "explanation": "No active offers configured.",
            APDE: True,
        })

    for acct in system_state.get("accounts_not_ready", []):
        blockers.append({
            "blocker": "account_not_ready",
            "severity": "medium",
            "affected_scope": f"account:{acct}",
            "operator_action_needed": f"Complete warm-up or platform verification for account {acct}.",
            "deadline_or_urgency": "within_48h",
            "consequence_if_ignored": "Account excluded from content distribution pipeline.",
            "explanation": f"Account {acct} is not in a publishable state.",
            APDE: True,
        })

    leak = float(system_state.get("funnel_leak_score", 0))
    if leak > 0.55:
        blockers.append({
            "blocker": "funnel_blocked",
            "severity": "high",
            "affected_scope": "brand:funnel",
            "operator_action_needed": "Review funnel diagnostics and patch mid-funnel drop.",
            "deadline_or_urgency": "within_24h",
            "consequence_if_ignored": f"Estimated ${leak * 12000:.0f}/mo revenue leak continues.",
            "explanation": f"Funnel leak score {leak:.2f} above threshold.",
            APDE: True,
        })

    budget = float(system_state.get("budget_remaining", 1000))
    if budget < 50:
        blockers.append({
            "blocker": "budget_blocked",
            "severity": "high",
            "affected_scope": "brand:paid_amplification",
            "operator_action_needed": "Increase paid budget or pause paid tests.",
            "deadline_or_urgency": "immediate",
            "consequence_if_ignored": "Paid tests will auto-stop; winners not amplified.",
            "explanation": f"Budget remaining ${budget:.0f} — below safe threshold.",
            APDE: True,
        })

    for hold in system_state.get("compliance_holds", []):
        blockers.append({
            "blocker": "compliance_hold",
            "severity": "critical",
            "affected_scope": f"compliance:{hold}",
            "operator_action_needed": f"Resolve compliance issue: {hold}.",
            "deadline_or_urgency": "immediate",
            "consequence_if_ignored": "Platform account may be suspended.",
            "explanation": f"Compliance hold: {hold}.",
            APDE: True,
        })

    cap = system_state.get("platform_capacity", {})
    for plat, pct in cap.items():
        if float(pct) >= 0.95:
            blockers.append({
                "blocker": "platform_capacity_full",
                "severity": "medium",
                "affected_scope": f"platform:{plat}",
                "operator_action_needed": f"Reduce output on {plat} or add another account.",
                "deadline_or_urgency": "within_48h",
                "consequence_if_ignored": f"{plat} output capped; new content not distributed.",
                "explanation": f"{plat} at {float(pct)*100:.0f}% capacity.",
                APDE: True,
            })

    if not system_state.get("provider_available", True):
        blockers.append({
            "blocker": "provider_unavailable",
            "severity": "high",
            "affected_scope": "system:generation_provider",
            "operator_action_needed": "Check provider status or switch to backup.",
            "deadline_or_urgency": "within_1h",
            "consequence_if_ignored": "Content generation pipeline halted.",
            "explanation": "Primary generation provider not responding.",
            APDE: True,
        })

    qfr = float(system_state.get("queue_failure_rate", 0))
    if qfr > 0.1:
        blockers.append({
            "blocker": "queue_failure",
            "severity": "medium",
            "affected_scope": "system:task_queue",
            "operator_action_needed": "Inspect Celery queue health and restart stuck workers.",
            "deadline_or_urgency": "within_4h",
            "consequence_if_ignored": "Background tasks delayed or dropped.",
            "explanation": f"Queue failure rate {qfr*100:.0f}%.",
            APDE: True,
        })

    for lane in system_state.get("policy_sensitive_lanes", []):
        blockers.append({
            "blocker": "policy_sensitive_lane",
            "severity": "medium",
            "affected_scope": f"lane:{lane}",
            "operator_action_needed": f"Review and approve lane '{lane}' before execution.",
            "deadline_or_urgency": "before_next_publish_cycle",
            "consequence_if_ignored": "Content in this lane held indefinitely.",
            "explanation": f"Lane '{lane}' flagged as policy-sensitive.",
            APDE: True,
        })

    return blockers


# ---------------------------------------------------------------------------
# Operator escalation
# ---------------------------------------------------------------------------

def generate_escalations(
    blockers: list[dict[str, Any]],
    pressure: dict[str, Any],
) -> list[dict[str, Any]]:
    """Convert blockers + revenue pressure into operator escalation events."""
    escalations: list[dict[str, Any]] = []

    for b in blockers:
        sev = b.get("severity", "medium")
        urgency = "critical" if sev == "critical" else ("high" if sev == "high" else "medium")
        upside = 0.0
        if b["blocker"] == "funnel_blocked":
            upside = float(b.get("consequence_if_ignored", "0").replace("$", "").split("/")[0].replace("Estimated", "").strip() or 0)
        elif b["blocker"] == "missing_credential":
            upside = 5000.0

        escalations.append({
            "command": b["operator_action_needed"],
            "reason": b["explanation"],
            "supporting_data_json": {"blocker": b["blocker"], "scope": b["affected_scope"]},
            "confidence": 0.85 if sev in ("critical", "high") else 0.65,
            "urgency": urgency,
            "expected_upside": upside,
            "expected_cost": 0.0,
            "time_to_signal": b.get("deadline_or_urgency", "within_24h"),
            "time_to_profit": "after_resolution",
            "risk": sev,
            "required_resources": "operator_time",
            "consequence_if_ignored": b["consequence_if_ignored"],
            APDE: True,
        })

    commands = pressure.get("next_commands_json", [])
    for cmd in commands[:3]:
        prio = cmd.get("priority", "medium")
        urgency = "critical" if prio == "critical" else ("high" if prio == "high" else "medium")
        escalations.append({
            "command": cmd["action"],
            "reason": cmd.get("explanation", "Revenue pressure command."),
            "supporting_data_json": {"source": "revenue_pressure", "priority": prio},
            "confidence": 0.7,
            "urgency": urgency,
            "expected_upside": 3000.0 if prio == "high" else 1000.0,
            "expected_cost": 0.0,
            "time_to_signal": "within_24h" if prio in ("critical", "high") else "within_72h",
            "time_to_profit": "7-14d",
            "risk": "low",
            "required_resources": "operator_time",
            "consequence_if_ignored": "Revenue left on the table.",
            APDE: True,
        })

    return escalations
