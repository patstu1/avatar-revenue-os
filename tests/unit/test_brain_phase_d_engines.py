"""Unit tests for Brain Architecture Phase D — meta-monitoring, self-correction, readiness, escalation."""

from packages.scoring.brain_phase_d_engine import (
    HEALTH_BANDS,
    READINESS_BANDS,
    compute_brain_escalations,
    compute_meta_monitoring,
    compute_readiness_brain,
    compute_self_corrections,
)

# ── Meta-Monitoring Engine ────────────────────────────────────────────

class TestComputeMetaMonitoring:
    def test_healthy_system(self):
        r = compute_meta_monitoring({
            "total_decisions": 10, "low_confidence_decisions": 1,
            "manual_mode_count": 1, "total_policies": 10,
            "execution_failures": 0, "total_executions": 10,
            "memory_entries": 10, "stale_memory_entries": 0,
            "escalation_count": 0, "agent_run_count": 12,
            "dead_agent_count": 0, "low_signal_agent_count": 0,
            "wasted_action_count": 0, "queue_depth": 5,
        })
        assert r["health_band"] in ("excellent", "good")
        assert r["health_score"] >= 0.7

    def test_degraded_system(self):
        r = compute_meta_monitoring({
            "total_decisions": 10, "low_confidence_decisions": 7,
            "manual_mode_count": 8, "total_policies": 10,
            "execution_failures": 5, "total_executions": 10,
            "memory_entries": 10, "stale_memory_entries": 8,
            "escalation_count": 5, "agent_run_count": 12,
            "dead_agent_count": 3, "low_signal_agent_count": 5,
            "wasted_action_count": 4, "queue_depth": 80,
        })
        assert r["health_band"] in ("degraded", "critical")
        assert len(r["weak_areas"]) >= 3
        assert len(r["recommended_corrections"]) >= 3

    def test_health_score_bounded(self):
        r = compute_meta_monitoring({})
        assert 0.0 <= r["health_score"] <= 1.0

    def test_band_is_valid(self):
        r = compute_meta_monitoring({})
        assert r["health_band"] in HEALTH_BANDS

    def test_weak_areas_for_low_decision_quality(self):
        r = compute_meta_monitoring({"total_decisions": 10, "low_confidence_decisions": 8})
        assert "decision_quality" in r["weak_areas"]

    def test_weak_areas_for_high_failure_rate(self):
        r = compute_meta_monitoring({"execution_failures": 5, "total_executions": 10})
        assert "execution_failures" in r["weak_areas"]

    def test_weak_areas_for_dead_agents(self):
        r = compute_meta_monitoring({"dead_agent_count": 2, "agent_run_count": 12})
        assert "dead_agent_paths" in r["weak_areas"]

    def test_confidence_increases_with_data(self):
        sparse = compute_meta_monitoring({})
        rich = compute_meta_monitoring({"total_decisions": 10, "memory_entries": 10})
        assert rich["confidence"] > sparse["confidence"]

    def test_empty_context(self):
        r = compute_meta_monitoring({})
        assert r["health_band"] in HEALTH_BANDS
        assert isinstance(r["weak_areas"], list)


# ── Self-Correction Engine ────────────────────────────────────────────

class TestComputeSelfCorrections:
    def test_corrections_from_monitoring(self):
        mon = compute_meta_monitoring({
            "total_decisions": 10, "low_confidence_decisions": 8,
            "execution_failures": 5, "total_executions": 10,
        })
        corrections = compute_self_corrections(mon)
        assert len(corrections) >= 1
        assert all("correction_type" in c for c in corrections)

    def test_critical_failure_forces_guard_mode(self):
        mon = compute_meta_monitoring({"execution_failures": 6, "total_executions": 10})
        mon["execution_failure_rate"] = 0.6
        corrections = compute_self_corrections(mon)
        guard_modes = [c for c in corrections if c["correction_type"] == "increase_guard_mode"]
        assert len(guard_modes) >= 1
        assert guard_modes[0]["severity"] == "critical"

    def test_queue_congestion_pauses_paid(self):
        mon = {"health_score": 0.5, "confidence": 0.7, "queue_congestion": 0.9, "recommended_corrections": []}
        corrections = compute_self_corrections(mon)
        paid_pauses = [c for c in corrections if c["correction_type"] == "pause_paid"]
        assert len(paid_pauses) >= 1

    def test_healthy_system_no_corrections(self):
        mon = {"health_score": 0.9, "confidence": 0.8, "recommended_corrections": [], "execution_failure_rate": 0.0, "queue_congestion": 0.0}
        corrections = compute_self_corrections(mon)
        assert len(corrections) == 0

    def test_correction_has_structure(self):
        mon = compute_meta_monitoring({"total_decisions": 10, "low_confidence_decisions": 8})
        corrections = compute_self_corrections(mon)
        for c in corrections:
            assert "correction_type" in c
            assert "reason" in c
            assert "effect_target" in c
            assert "severity" in c
            assert "confidence" in c


# ── Readiness Brain ───────────────────────────────────────────────────

class TestComputeReadinessBrain:
    def test_ready_system(self):
        r = compute_readiness_brain({
            "health_score": 0.9, "has_offers": True, "has_accounts": True,
            "has_warmup_plans": True, "has_memory": True,
            "account_health_avg": 0.9, "execution_failure_rate": 0.05,
            "confidence_avg": 0.8, "has_platform_credentials": True,
            "active_blocker_count": 0, "escalation_rate": 0.0,
        })
        assert r["readiness_band"] in ("ready", "mostly_ready")
        assert len(r["allowed_actions"]) >= 4

    def test_blocked_system(self):
        r = compute_readiness_brain({
            "health_score": 0.1, "has_offers": False, "has_accounts": False,
            "has_platform_credentials": False,
        })
        assert r["readiness_band"] in ("not_ready", "blocked")
        assert len(r["blockers"]) >= 3
        assert len(r["forbidden_actions"]) > len(r["allowed_actions"])

    def test_auto_run_requires_high_readiness(self):
        r = compute_readiness_brain({
            "health_score": 0.5, "has_offers": True, "has_accounts": True,
            "execution_failure_rate": 0.3, "confidence_avg": 0.4,
        })
        assert "auto_run" in r["forbidden_actions"]

    def test_launch_allowed_with_moderate_readiness(self):
        r = compute_readiness_brain({
            "health_score": 0.6, "has_offers": True, "has_accounts": True,
            "has_warmup_plans": True, "account_health_avg": 0.7,
        })
        assert "launch" in r["allowed_actions"]

    def test_band_is_valid(self):
        r = compute_readiness_brain({})
        assert r["readiness_band"] in READINESS_BANDS

    def test_score_bounded(self):
        r = compute_readiness_brain({})
        assert 0.0 <= r["readiness_score"] <= 1.0

    def test_no_credentials_is_blocker(self):
        r = compute_readiness_brain({"has_platform_credentials": False})
        assert "Platform credentials not connected" in r["blockers"]


# ── Brain-Level Escalation ────────────────────────────────────────────

class TestComputeBrainEscalations:
    def test_missing_credentials(self):
        esc = compute_brain_escalations({"has_platform_credentials": False})
        types = [e["escalation_type"] for e in esc]
        assert "connect_credential" in types

    def test_missing_offers(self):
        esc = compute_brain_escalations({"has_offers": False})
        types = [e["escalation_type"] for e in esc]
        assert "add_offer" in types

    def test_missing_accounts(self):
        esc = compute_brain_escalations({"has_accounts": False})
        types = [e["escalation_type"] for e in esc]
        assert "create_account" in types

    def test_high_failure_rate(self):
        esc = compute_brain_escalations({"execution_failure_rate": 0.5, "has_offers": True, "has_accounts": True, "has_platform_credentials": True})
        types = [e["escalation_type"] for e in esc]
        assert "fix_execution_failures" in types

    def test_low_health(self):
        esc = compute_brain_escalations({"health_score": 0.2, "has_offers": True, "has_accounts": True, "has_platform_credentials": True})
        types = [e["escalation_type"] for e in esc]
        assert "review_brain_health" in types

    def test_forbidden_auto_run(self):
        esc = compute_brain_escalations({"forbidden_actions": ["auto_run"], "health_score": 0.6, "has_offers": True, "has_accounts": True, "has_platform_credentials": True})
        types = [e["escalation_type"] for e in esc]
        assert "approve_auto_run" in types

    def test_no_escalations_when_healthy(self):
        esc = compute_brain_escalations({
            "has_platform_credentials": True, "has_offers": True, "has_accounts": True,
            "health_score": 0.9, "execution_failure_rate": 0.05,
            "active_blocker_count": 0, "forbidden_actions": [],
        })
        assert len(esc) == 0

    def test_escalation_structure(self):
        esc = compute_brain_escalations({"has_platform_credentials": False})
        for e in esc:
            assert "escalation_type" in e
            assert "command" in e
            assert "urgency" in e
            assert "expected_upside_unlocked" in e
            assert "expected_cost_of_delay" in e
            assert "confidence" in e
