"""Unit tests for Autonomous Execution Phase D pure scoring engines."""
from packages.scoring.autonomous_phase_d_engine import (
    AGENT_TYPES,
    compute_override_policies,
    compute_revenue_pressure,
    detect_blockers,
    generate_escalations,
    run_agent_cycle,
)


def _base_ctx() -> dict:
    return {
        "accounts_count": 3,
        "offers_count": 2,
        "queue_depth": 8,
        "avg_health": 0.6,
        "avg_engagement": 0.03,
        "revenue_trend": "flat",
        "suppression_count": 1,
        "funnel_leak_score": 0.25,
        "paid_active": False,
        "sponsor_pipeline": 4,
        "retention_risk": 0.2,
        "provider_failures": False,
    }


# ---- Agent orchestration ----

def test_agent_cycle_returns_all_agents():
    results = run_agent_cycle(_base_ctx())
    batch = results[0]
    agent_types_returned = [r["agent_type"] for r in batch["runs"]]
    assert set(AGENT_TYPES) == set(agent_types_returned)


def test_agent_cycle_messages_not_empty():
    results = run_agent_cycle(_base_ctx())
    assert len(results[0]["messages"]) > 0


def test_agent_cycle_completed_status():
    results = run_agent_cycle(_base_ctx())
    for r in results[0]["runs"]:
        assert r["run_status"] == "completed"


def test_agent_cycle_with_low_health():
    ctx = _base_ctx()
    ctx["avg_health"] = 0.2
    ctx["provider_failures"] = True
    results = run_agent_cycle(ctx)
    ops_run = [r for r in results[0]["runs"] if r["agent_type"] == "ops_watchdog"][0]
    assert "avg_health_critical" in ops_run["output_json"]["issues"]
    assert "provider_failure" in ops_run["output_json"]["issues"]


# ---- Revenue pressure ----

def _pressure_ctx() -> dict:
    return {
        "active_monetization_classes": ["affiliate"],
        "active_platforms": ["youtube"],
        "accounts": 2,
        "offers_count": 1,
        "queue_winners_unexploited": 3,
        "funnel_leak_score": 0.55,
        "inactive_asset_classes": ["community"],
        "revenue_trend": "flat",
        "avg_health": 0.5,
        "suppression_count": 1,
        "next_launch_candidates": [],
    }


def test_pressure_identifies_underused_monetization():
    result = compute_revenue_pressure(_pressure_ctx())
    assert result["underused_monetization_class"] is not None
    assert result["pressure_score"] > 0.3


def test_pressure_next_commands_limited():
    result = compute_revenue_pressure(_pressure_ctx())
    assert len(result["next_commands_json"]) <= 5


def test_pressure_revenue_declining():
    ctx = _pressure_ctx()
    ctx["revenue_trend"] = "down"
    result = compute_revenue_pressure(ctx)
    assert result["biggest_blocker"] == "revenue_declining"
    any_emergency = any(c["priority"] == "critical" for c in result["next_commands_json"])
    assert any_emergency


def test_pressure_launches_populated():
    result = compute_revenue_pressure(_pressure_ctx())
    assert len(result["next_launches_json"]) <= 3


# ---- Override policies ----

def test_override_default_guarded():
    policies = compute_override_policies(
        ["publish_content", "launch_new_account"],
        {"default_mode": "guarded"},
    )
    assert len(policies) == 2
    pub = [p for p in policies if p["action_ref"] == "publish_content"][0]
    assert pub["override_mode"] == "guarded"


def test_override_manual_overrides_all():
    policies = compute_override_policies(
        ["suppress_lane", "create_content_brief"],
        {"default_mode": "manual"},
    )
    for p in policies:
        assert p["override_mode"] == "manual"
        assert p["approval_needed"] is True


def test_override_includes_rollback():
    policies = compute_override_policies(["increase_paid_spend"], {"default_mode": "guarded"})
    assert policies[0]["rollback_available"] is True
    assert policies[0]["rollback_plan"] is not None


# ---- Blocker detection ----

def test_blockers_missing_credential():
    state = {"credentials_missing": ["youtube_api", "tiktok_api"], "offers_count": 1}
    blockers = detect_blockers(state)
    cred_blockers = [b for b in blockers if b["blocker"] == "missing_credential"]
    assert len(cred_blockers) == 2


def test_blockers_missing_offer():
    state = {"offers_count": 0}
    blockers = detect_blockers(state)
    offer_blockers = [b for b in blockers if b["blocker"] == "missing_offer"]
    assert len(offer_blockers) == 1
    assert offer_blockers[0]["severity"] == "critical"


def test_blockers_funnel_leak():
    state = {"funnel_leak_score": 0.7, "offers_count": 1}
    blockers = detect_blockers(state)
    funnel_blockers = [b for b in blockers if b["blocker"] == "funnel_blocked"]
    assert len(funnel_blockers) == 1


def test_blockers_budget():
    state = {"budget_remaining": 10, "offers_count": 1}
    blockers = detect_blockers(state)
    budget_blockers = [b for b in blockers if b["blocker"] == "budget_blocked"]
    assert len(budget_blockers) == 1


def test_blockers_provider_unavailable():
    state = {"provider_available": False, "offers_count": 1}
    blockers = detect_blockers(state)
    prov_blockers = [b for b in blockers if b["blocker"] == "provider_unavailable"]
    assert len(prov_blockers) == 1


def test_blockers_queue_failure():
    state = {"queue_failure_rate": 0.25, "offers_count": 1}
    blockers = detect_blockers(state)
    q_blockers = [b for b in blockers if b["blocker"] == "queue_failure"]
    assert len(q_blockers) == 1


def test_blockers_clean_state_no_blockers():
    state = {"offers_count": 5, "budget_remaining": 5000}
    blockers = detect_blockers(state)
    assert len(blockers) == 0


# ---- Escalation generation ----

def test_escalations_from_blockers():
    blockers = [{
        "blocker": "missing_credential",
        "severity": "high",
        "affected_scope": "credential:youtube",
        "operator_action_needed": "Connect YouTube API.",
        "deadline_or_urgency": "within_24h",
        "consequence_if_ignored": "YouTube publishing blocked.",
        "explanation": "YouTube credential missing.",
    }]
    pressure = {"next_commands_json": []}
    escalations = generate_escalations(blockers, pressure)
    assert len(escalations) == 1
    assert escalations[0]["urgency"] == "high"
    assert escalations[0]["confidence"] == 0.85


def test_escalations_from_pressure():
    blockers = []
    pressure = {
        "next_commands_json": [
            {"action": "activate_lead_gen", "priority": "high", "explanation": "Lead gen inactive."},
        ]
    }
    escalations = generate_escalations(blockers, pressure)
    assert len(escalations) == 1
    assert escalations[0]["command"] == "activate_lead_gen"


def test_escalations_combined():
    blockers = [{
        "blocker": "budget_blocked",
        "severity": "high",
        "affected_scope": "brand:paid",
        "operator_action_needed": "Increase budget.",
        "deadline_or_urgency": "immediate",
        "consequence_if_ignored": "Paid tests stop.",
        "explanation": "Budget depleted.",
    }]
    pressure = {
        "next_commands_json": [
            {"action": "scale_winner_x", "priority": "medium", "explanation": "Winner X not scaled."},
            {"action": "launch_ig", "priority": "medium", "explanation": "IG not built."},
        ]
    }
    escalations = generate_escalations(blockers, pressure)
    assert len(escalations) == 3
