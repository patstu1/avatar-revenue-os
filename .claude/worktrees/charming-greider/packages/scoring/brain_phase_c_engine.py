"""Brain Architecture Phase C — agent mesh, workflow coordination, context bus, memory binding engines."""
from __future__ import annotations

from typing import Any

# ── Agent Registry ────────────────────────────────────────────────────

AGENT_CATALOG: list[dict[str, Any]] = [
    {
        "slug": "trend_scout",
        "label": "Trend Scout",
        "description": "Scans signals for profitable emerging trends and niches",
        "inputs": ["signal_scan_runs", "trend_signals", "market_timing_reports"],
        "outputs": ["opportunity_candidates", "niche_recommendations"],
        "memory_scopes": ["winner", "loser", "saturated_pattern", "platform_learning"],
        "upstream": [],
        "downstream": ["niche_allocator", "monetization_router"],
    },
    {
        "slug": "niche_allocator",
        "label": "Niche Allocator",
        "description": "Assigns niche/topic to accounts based on opportunity fit and saturation",
        "inputs": ["opportunity_candidates", "account_states", "saturation_reports"],
        "outputs": ["niche_assignments", "allocation_decisions"],
        "memory_scopes": ["best_niche", "saturated_pattern", "platform_learning"],
        "upstream": ["trend_scout"],
        "downstream": ["account_launcher", "scale_commander"],
    },
    {
        "slug": "monetization_router",
        "label": "Monetization Router",
        "description": "Selects optimal monetization path for content/offers",
        "inputs": ["content_items", "offers", "audience_states", "monetization_routes"],
        "outputs": ["monetization_decisions", "funnel_assignments"],
        "memory_scopes": ["best_monetization_route", "winner", "loser"],
        "upstream": ["trend_scout", "content_runner"],
        "downstream": ["funnel_optimizer", "pricing_strategist"],
    },
    {
        "slug": "funnel_optimizer",
        "label": "Funnel Optimizer",
        "description": "Diagnoses funnel leaks and triggers fixes or page generation",
        "inputs": ["funnel_stage_metrics", "funnel_execution_runs", "conversion_rates"],
        "outputs": ["funnel_fix_actions", "page_generation_jobs"],
        "memory_scopes": ["common_fix", "winner", "loser"],
        "upstream": ["monetization_router"],
        "downstream": ["recovery_agent", "retention_strategist"],
    },
    {
        "slug": "scale_commander",
        "label": "Scale Commander",
        "description": "Decides when and how to scale winning lanes",
        "inputs": ["account_states", "profit_forecasts", "scale_recommendations"],
        "outputs": ["scale_decisions", "output_ramp_events"],
        "memory_scopes": ["winner", "best_pacing_pattern", "platform_learning"],
        "upstream": ["niche_allocator"],
        "downstream": ["account_launcher", "paid_amplification_agent"],
    },
    {
        "slug": "account_launcher",
        "label": "Account Launcher",
        "description": "Launches new accounts or clones winning strategies",
        "inputs": ["launch_candidates", "account_warmup_plans", "niche_assignments"],
        "outputs": ["account_launch_blueprints", "warmup_plan_updates"],
        "memory_scopes": ["best_account_type", "platform_learning", "common_blocker"],
        "upstream": ["niche_allocator", "scale_commander"],
        "downstream": ["ops_watchdog"],
    },
    {
        "slug": "recovery_agent",
        "label": "Recovery Agent",
        "description": "Detects and resolves failures, stagnation, and performance drops",
        "inputs": ["recovery_incidents", "execution_failures", "blocker_detection_reports"],
        "outputs": ["recovery_actions", "self_healing_actions", "escalation_events"],
        "memory_scopes": ["common_blocker", "common_fix", "platform_learning"],
        "upstream": ["funnel_optimizer", "ops_watchdog"],
        "downstream": ["retention_strategist"],
    },
    {
        "slug": "sponsor_strategist",
        "label": "Sponsor Strategist",
        "description": "Builds sponsor inventory, packages, target lists, and outreach",
        "inputs": ["sponsor_inventory", "audience_states", "content_performance"],
        "outputs": ["sponsor_packages", "outreach_sequences", "pricing_recommendations"],
        "memory_scopes": ["winner", "best_monetization_route"],
        "upstream": [],
        "downstream": ["pricing_strategist"],
    },
    {
        "slug": "pricing_strategist",
        "label": "Pricing Strategist",
        "description": "Optimizes pricing for offers, sponsors, and services",
        "inputs": ["pricing_recommendations", "revenue_density_reports", "market_data"],
        "outputs": ["pricing_decisions", "bundle_recommendations"],
        "memory_scopes": ["winner", "loser", "best_monetization_route"],
        "upstream": ["monetization_router", "sponsor_strategist"],
        "downstream": ["retention_strategist"],
    },
    {
        "slug": "retention_strategist",
        "label": "Retention Strategist",
        "description": "Detects churn risk and triggers reactivation, upsell, and loyalty flows",
        "inputs": ["audience_states", "retention_automation_actions", "ltv_models"],
        "outputs": ["retention_actions", "reactivation_campaigns"],
        "memory_scopes": ["winner", "loser", "platform_learning"],
        "upstream": ["funnel_optimizer", "recovery_agent", "pricing_strategist"],
        "downstream": [],
    },
    {
        "slug": "paid_amplification_agent",
        "label": "Paid Amplification Agent",
        "description": "Identifies organic winners for paid testing and scales strong performers",
        "inputs": ["paid_operator_decisions", "content_performance", "budget_data"],
        "outputs": ["paid_test_decisions", "budget_allocation_updates"],
        "memory_scopes": ["winner", "loser", "platform_learning"],
        "upstream": ["scale_commander"],
        "downstream": ["recovery_agent"],
    },
    {
        "slug": "ops_watchdog",
        "label": "Ops Watchdog",
        "description": "Monitors system health, queue congestion, provider failures, and budget overspend",
        "inputs": ["system_jobs", "execution_failures", "provider_usage_costs", "queue_metrics"],
        "outputs": ["operational_alerts", "throttle_decisions", "escalation_events"],
        "memory_scopes": ["common_blocker", "common_fix"],
        "upstream": ["account_launcher"],
        "downstream": ["recovery_agent"],
    },
]


def build_agent_registry() -> list[dict[str, Any]]:
    return [
        {
            "agent_slug": a["slug"],
            "agent_label": a["label"],
            "description": a["description"],
            "input_schema": a["inputs"],
            "output_schema": a["outputs"],
            "memory_scopes": a["memory_scopes"],
            "upstream_agents": a["upstream"],
            "downstream_agents": a["downstream"],
        }
        for a in AGENT_CATALOG
    ]


# ── Agent Run Simulation ─────────────────────────────────────────────

def run_agent(slug: str, ctx: dict[str, Any], memory: list[dict[str, Any]]) -> dict[str, Any]:
    conf = 0.5
    mem_refs: list[str] = []
    for m in memory:
        if m.get("entry_type") in ("winner", "best_niche", "best_monetization_route"):
            conf = min(1.0, conf + 0.1)
            mem_refs.append(f"{m.get('entry_type')}:{str(m.get('id', ''))[:8]}")
        elif m.get("entry_type") in ("loser", "common_blocker"):
            mem_refs.append(f"{m.get('entry_type')}:{str(m.get('id', ''))[:8]}")

    catalog = {a["slug"]: a for a in AGENT_CATALOG}
    agent_def = catalog.get(slug)
    if not agent_def:
        return {
            "outputs": {}, "confidence": 0.0, "explanation": f"Unknown agent: {slug}",
            "memory_refs": [], "status": "error",
        }

    account_state = ctx.get("account_state", "warming")
    opp_state = ctx.get("opportunity_state", "monitor")
    has_blocker = ctx.get("has_blocker", False)
    saturation = ctx.get("saturation_score", 0.0)

    outputs: dict[str, Any] = {}

    if slug == "trend_scout":
        outputs = {
            "top_opportunities": ctx.get("top_signals", [])[:5],
            "recommendation": "test" if opp_state == "monitor" else "scale" if opp_state == "scale" else "hold",
        }
        conf = min(1.0, conf + 0.1 * len(ctx.get("top_signals", [])))
    elif slug == "niche_allocator":
        outputs = {
            "allocation": ctx.get("suggested_niche", "general"),
            "fit_score": min(1.0, 0.5 + len(memory) * 0.05),
        }
    elif slug == "monetization_router":
        route = ctx.get("best_route", "affiliate")
        outputs = {"selected_route": route, "funnel_path": f"{route}_standard"}
    elif slug == "funnel_optimizer":
        leak = ctx.get("biggest_leak_stage", "unknown")
        outputs = {"leak_stage": leak, "fix_action": f"optimize_{leak}" if leak != "unknown" else "audit_funnel"}
    elif slug == "scale_commander":
        if account_state in ("stable", "scaling") and saturation < 0.5:
            outputs = {"action": "increase_output", "factor": 1.2}
        else:
            outputs = {"action": "hold", "factor": 1.0}
    elif slug == "account_launcher":
        if account_state == "newborn" or ctx.get("launch_needed", False):
            outputs = {"action": "launch", "platform": ctx.get("platform", "tiktok")}
        else:
            outputs = {"action": "skip", "reason": "No launch needed"}
    elif slug == "recovery_agent":
        if has_blocker:
            outputs = {"action": "escalate", "blocker": ctx.get("blocker_type", "unknown")}
            conf = max(0.3, conf - 0.2)
        else:
            outputs = {"action": "monitor", "status": "healthy"}
    elif slug == "sponsor_strategist":
        outputs = {
            "packages_identified": ctx.get("sponsor_inventory_count", 0),
            "top_category": ctx.get("top_sponsor_category", "tech"),
        }
    elif slug == "pricing_strategist":
        outputs = {
            "pricing_action": "maintain" if saturation < 0.3 else "discount_test",
            "current_margin": ctx.get("margin", 0.3),
        }
    elif slug == "retention_strategist":
        churn = ctx.get("churn_risk", 0.0)
        if churn > 0.5:
            outputs = {"action": "reactivation_campaign", "target_segment": "churn_risk"}
        else:
            outputs = {"action": "nurture", "target_segment": "engaged"}
    elif slug == "paid_amplification_agent":
        if ctx.get("organic_winner", False):
            outputs = {"action": "test_paid", "budget": ctx.get("safe_budget", 25)}
        else:
            outputs = {"action": "wait", "reason": "No organic winner yet"}
    elif slug == "ops_watchdog":
        failures = ctx.get("active_failures", 0)
        if failures > 3:
            outputs = {"action": "throttle", "severity": "high"}
        else:
            outputs = {"action": "ok", "severity": "none"}

    explanation = f"Agent '{slug}' produced {len(outputs)} output fields with {len(mem_refs)} memory refs."
    return {
        "outputs": outputs,
        "confidence": round(conf, 3),
        "memory_refs": mem_refs,
        "explanation": explanation,
        "status": "completed",
    }


# ── Workflow Coordination ─────────────────────────────────────────────

WORKFLOW_TEMPLATES: list[dict[str, Any]] = [
    {
        "type": "opportunity_to_launch",
        "sequence": ["trend_scout", "niche_allocator", "account_launcher"],
        "description": "End-to-end: discover opportunity, assign niche, launch account",
    },
    {
        "type": "content_to_monetization",
        "sequence": ["monetization_router", "funnel_optimizer"],
        "description": "Route content to monetization and optimize funnel",
    },
    {
        "type": "paid_amplification",
        "sequence": ["scale_commander", "paid_amplification_agent", "recovery_agent"],
        "description": "Scale winner via paid, recover if failure",
    },
    {
        "type": "retention_loop",
        "sequence": ["retention_strategist", "pricing_strategist"],
        "description": "Detect churn, trigger retention, adjust pricing",
    },
    {
        "type": "recovery_chain",
        "sequence": ["ops_watchdog", "recovery_agent"],
        "description": "Detect operational issue, trigger recovery",
    },
    {
        "type": "sponsor_pipeline",
        "sequence": ["sponsor_strategist", "pricing_strategist", "monetization_router"],
        "description": "Build sponsor packages, price, route monetization",
    },
]


def run_workflow(workflow_type: str, ctx: dict[str, Any], memory: list[dict[str, Any]]) -> dict[str, Any]:
    template = None
    for t in WORKFLOW_TEMPLATES:
        if t["type"] == workflow_type:
            template = t
            break
    if not template:
        return {
            "status": "error",
            "sequence": [],
            "handoff_events": [],
            "failure_points": [],
            "outputs": {},
            "explanation": f"Unknown workflow: {workflow_type}",
        }

    sequence = template["sequence"]
    handoff_events: list[dict[str, Any]] = []
    failure_points: list[dict[str, Any]] = []
    cumulative_ctx = dict(ctx)
    final_outputs: dict[str, Any] = {}

    for i, agent_slug in enumerate(sequence):
        result = run_agent(agent_slug, cumulative_ctx, memory)

        if result["status"] == "error":
            failure_points.append({"step": i, "agent": agent_slug, "error": result["explanation"]})
            return {
                "status": "failed",
                "sequence": sequence,
                "handoff_events": handoff_events,
                "failure_points": failure_points,
                "outputs": final_outputs,
                "explanation": f"Workflow '{workflow_type}' failed at step {i} ({agent_slug})",
            }

        cumulative_ctx.update(result["outputs"])
        final_outputs[agent_slug] = result["outputs"]

        if i < len(sequence) - 1:
            handoff_events.append({
                "from_agent": agent_slug,
                "to_agent": sequence[i + 1],
                "step_index": i,
                "payload_keys": list(result["outputs"].keys()),
                "confidence": result["confidence"],
            })

    return {
        "status": "completed",
        "sequence": sequence,
        "handoff_events": handoff_events,
        "failure_points": failure_points,
        "outputs": final_outputs,
        "explanation": f"Workflow '{workflow_type}' completed {len(sequence)} steps with {len(handoff_events)} handoffs.",
    }


# ── Shared Context Bus ────────────────────────────────────────────────

def derive_context_events(
    agent_slug: str,
    agent_outputs: dict[str, Any],
    ctx: dict[str, Any],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    if agent_slug == "trend_scout" and agent_outputs.get("recommendation") == "scale":
        events.append({
            "event_type": "winner_promoted",
            "source_module": "trend_scout",
            "target_modules": ["scale_commander", "monetization_router"],
            "payload": {"recommendation": "scale", "opportunities": agent_outputs.get("top_opportunities", [])},
            "priority": 3,
            "explanation": "Trend scout identified scalable winner",
        })

    if agent_slug == "recovery_agent" and agent_outputs.get("action") == "escalate":
        events.append({
            "event_type": "launch_blocked",
            "source_module": "recovery_agent",
            "target_modules": ["ops_watchdog", "account_launcher"],
            "payload": {"blocker": agent_outputs.get("blocker", "unknown")},
            "priority": 1,
            "explanation": "Recovery agent detected blocker requiring escalation",
        })

    if agent_slug == "funnel_optimizer" and agent_outputs.get("leak_stage") not in (None, "unknown"):
        events.append({
            "event_type": "funnel_leaking",
            "source_module": "funnel_optimizer",
            "target_modules": ["monetization_router", "recovery_agent"],
            "payload": {"leak_stage": agent_outputs["leak_stage"], "fix_action": agent_outputs.get("fix_action")},
            "priority": 2,
            "explanation": f"Funnel leak detected at {agent_outputs['leak_stage']}",
        })

    if agent_slug == "retention_strategist" and agent_outputs.get("action") == "reactivation_campaign":
        events.append({
            "event_type": "retention_action_triggered",
            "source_module": "retention_strategist",
            "target_modules": ["monetization_router", "pricing_strategist"],
            "payload": {"target_segment": agent_outputs.get("target_segment")},
            "priority": 4,
            "explanation": "Retention action triggered for churn-risk segment",
        })

    if agent_slug == "scale_commander" and agent_outputs.get("action") == "increase_output":
        events.append({
            "event_type": "account_scaling",
            "source_module": "scale_commander",
            "target_modules": ["paid_amplification_agent", "ops_watchdog"],
            "payload": {"factor": agent_outputs.get("factor", 1.0)},
            "priority": 3,
            "explanation": "Scale commander increasing output",
        })

    if agent_slug == "sponsor_strategist" and agent_outputs.get("packages_identified", 0) > 0:
        events.append({
            "event_type": "sponsor_opportunity_detected",
            "source_module": "sponsor_strategist",
            "target_modules": ["pricing_strategist", "monetization_router"],
            "payload": {"packages": agent_outputs.get("packages_identified")},
            "priority": 4,
            "explanation": "Sponsor opportunities identified",
        })

    if agent_slug == "ops_watchdog" and agent_outputs.get("action") == "throttle":
        events.append({
            "event_type": "system_throttle",
            "source_module": "ops_watchdog",
            "target_modules": ["scale_commander", "account_launcher", "paid_amplification_agent"],
            "payload": {"severity": agent_outputs.get("severity")},
            "priority": 1,
            "explanation": "Ops watchdog triggered system throttle",
        })

    return events
