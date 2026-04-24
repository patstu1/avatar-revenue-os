"""Unit tests for Brain Architecture Phase C — agent mesh, workflows, context bus, memory binding."""
import pytest

from packages.scoring.brain_phase_c_engine import (
    AGENT_CATALOG,
    WORKFLOW_TEMPLATES,
    build_agent_registry,
    run_agent,
    run_workflow,
    derive_context_events,
)


# ── Agent Registry ────────────────────────────────────────────────────

class TestBuildAgentRegistry:
    def test_returns_12_agents(self):
        reg = build_agent_registry()
        assert len(reg) == 12

    def test_each_has_required_fields(self):
        for a in build_agent_registry():
            assert "agent_slug" in a
            assert "agent_label" in a
            assert "memory_scopes" in a
            assert isinstance(a["memory_scopes"], list)

    def test_all_slugs_unique(self):
        slugs = [a["agent_slug"] for a in build_agent_registry()]
        assert len(slugs) == len(set(slugs))


# ── Agent Runs ────────────────────────────────────────────────────────

class TestRunAgent:
    @pytest.mark.parametrize("slug", [a["slug"] for a in AGENT_CATALOG])
    def test_each_agent_runs(self, slug):
        result = run_agent(slug, {}, [])
        assert result["status"] in ("completed", "error")
        assert "outputs" in result
        assert "confidence" in result
        assert "memory_refs" in result

    def test_unknown_agent_errors(self):
        r = run_agent("nonexistent_agent", {}, [])
        assert r["status"] == "error"

    def test_trend_scout_uses_signals(self):
        r = run_agent("trend_scout", {"top_signals": ["a", "b", "c"]}, [])
        assert r["status"] == "completed"
        assert r["outputs"]["top_opportunities"] == ["a", "b", "c"]

    def test_recovery_agent_with_blocker(self):
        r = run_agent("recovery_agent", {"has_blocker": True, "blocker_type": "missing_credential"}, [])
        assert r["outputs"]["action"] == "escalate"

    def test_scale_commander_with_stable_account(self):
        r = run_agent("scale_commander", {"account_state": "stable", "saturation_score": 0.2}, [])
        assert r["outputs"]["action"] == "increase_output"

    def test_scale_commander_high_saturation_holds(self):
        r = run_agent("scale_commander", {"account_state": "stable", "saturation_score": 0.7}, [])
        assert r["outputs"]["action"] == "hold"

    def test_retention_strategist_churn(self):
        r = run_agent("retention_strategist", {"churn_risk": 0.7}, [])
        assert r["outputs"]["action"] == "reactivation_campaign"

    def test_retention_strategist_no_churn(self):
        r = run_agent("retention_strategist", {"churn_risk": 0.1}, [])
        assert r["outputs"]["action"] == "nurture"

    def test_paid_amplification_organic_winner(self):
        r = run_agent("paid_amplification_agent", {"organic_winner": True, "safe_budget": 50}, [])
        assert r["outputs"]["action"] == "test_paid"
        assert r["outputs"]["budget"] == 50

    def test_ops_watchdog_high_failures(self):
        r = run_agent("ops_watchdog", {"active_failures": 5}, [])
        assert r["outputs"]["action"] == "throttle"

    def test_ops_watchdog_no_failures(self):
        r = run_agent("ops_watchdog", {"active_failures": 1}, [])
        assert r["outputs"]["action"] == "ok"


class TestMemoryBinding:
    def test_winner_memory_increases_confidence(self):
        mem = [{"id": "abc", "entry_type": "winner", "summary": "test", "confidence": 0.8}]
        r1 = run_agent("trend_scout", {}, [])
        r2 = run_agent("trend_scout", {}, mem)
        assert r2["confidence"] >= r1["confidence"]
        assert len(r2["memory_refs"]) >= 1

    def test_multiple_memories(self):
        mem = [
            {"id": "a", "entry_type": "winner", "summary": "w", "confidence": 0.9},
            {"id": "b", "entry_type": "best_niche", "summary": "n", "confidence": 0.7},
            {"id": "c", "entry_type": "loser", "summary": "l", "confidence": 0.3},
        ]
        r = run_agent("niche_allocator", {}, mem)
        assert len(r["memory_refs"]) >= 2


# ── Workflow Coordination ─────────────────────────────────────────────

class TestRunWorkflow:
    def test_opportunity_to_launch(self):
        r = run_workflow("opportunity_to_launch", {"account_state": "newborn"}, [])
        assert r["status"] == "completed"
        assert len(r["sequence"]) == 3
        assert len(r["handoff_events"]) == 2
        assert "trend_scout" in r["outputs"]
        assert "account_launcher" in r["outputs"]

    def test_content_to_monetization(self):
        r = run_workflow("content_to_monetization", {}, [])
        assert r["status"] == "completed"
        assert len(r["handoff_events"]) == 1

    def test_paid_amplification_workflow(self):
        r = run_workflow("paid_amplification", {"account_state": "scaling", "saturation_score": 0.1}, [])
        assert r["status"] == "completed"

    def test_recovery_chain(self):
        r = run_workflow("recovery_chain", {"active_failures": 5}, [])
        assert r["status"] == "completed"

    def test_sponsor_pipeline(self):
        r = run_workflow("sponsor_pipeline", {}, [])
        assert r["status"] == "completed"
        assert len(r["sequence"]) == 3

    def test_unknown_workflow(self):
        r = run_workflow("nonexistent", {}, [])
        assert r["status"] == "error"

    def test_handoff_events_have_structure(self):
        r = run_workflow("opportunity_to_launch", {}, [])
        for he in r["handoff_events"]:
            assert "from_agent" in he
            assert "to_agent" in he
            assert "step_index" in he
            assert "confidence" in he

    def test_all_templates_run(self):
        for tmpl in WORKFLOW_TEMPLATES:
            r = run_workflow(tmpl["type"], {}, [])
            assert r["status"] in ("completed", "failed")


# ── Context Bus Events ────────────────────────────────────────────────

class TestDeriveContextEvents:
    def test_trend_scout_scale_emits_winner(self):
        events = derive_context_events("trend_scout", {"recommendation": "scale"}, {})
        assert len(events) >= 1
        assert events[0]["event_type"] == "winner_promoted"

    def test_recovery_agent_escalate_emits_blocked(self):
        events = derive_context_events("recovery_agent", {"action": "escalate", "blocker": "cred"}, {})
        assert len(events) >= 1
        assert events[0]["event_type"] == "launch_blocked"

    def test_funnel_optimizer_leak(self):
        events = derive_context_events("funnel_optimizer", {"leak_stage": "checkout", "fix_action": "optimize_checkout"}, {})
        assert len(events) >= 1
        assert events[0]["event_type"] == "funnel_leaking"

    def test_retention_reactivation(self):
        events = derive_context_events("retention_strategist", {"action": "reactivation_campaign", "target_segment": "churn_risk"}, {})
        assert len(events) >= 1
        assert events[0]["event_type"] == "retention_action_triggered"

    def test_scale_commander_scaling(self):
        events = derive_context_events("scale_commander", {"action": "increase_output", "factor": 1.2}, {})
        assert len(events) >= 1
        assert events[0]["event_type"] == "account_scaling"

    def test_sponsor_opportunity(self):
        events = derive_context_events("sponsor_strategist", {"packages_identified": 3}, {})
        assert len(events) >= 1
        assert events[0]["event_type"] == "sponsor_opportunity_detected"

    def test_ops_watchdog_throttle(self):
        events = derive_context_events("ops_watchdog", {"action": "throttle", "severity": "high"}, {})
        assert len(events) >= 1
        assert events[0]["event_type"] == "system_throttle"

    def test_no_event_when_no_trigger(self):
        events = derive_context_events("trend_scout", {"recommendation": "hold"}, {})
        assert len(events) == 0

    def test_event_structure(self):
        events = derive_context_events("recovery_agent", {"action": "escalate"}, {})
        for e in events:
            assert "event_type" in e
            assert "source_module" in e
            assert "target_modules" in e
            assert "payload" in e
            assert "priority" in e
