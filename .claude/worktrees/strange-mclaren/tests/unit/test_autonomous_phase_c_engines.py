"""Unit tests for Autonomous Phase C engines."""

from packages.scoring.autonomous_phase_c_engine import (
    APCE,
    compute_funnel_executions,
    compute_paid_operator_decision,
    compute_paid_operator_runs,
    compute_retention_actions,
    compute_self_healing_action,
    compute_sponsor_autonomous_actions,
    detect_recovery_incidents,
)


class TestFunnel:
    def test_leak_triggers_patch(self):
        rows = compute_funnel_executions({"funnel_leak_score": 0.7, "default_execution_mode": "guarded"})
        assert any(r["funnel_action"] == "diagnose_and_patch_leak" for r in rows)
        assert all(APCE in r for r in rows)

    def test_high_intent_routes_concierge(self):
        rows = compute_funnel_executions({
            "funnel_leak_score": 0.2, "high_intent_share": 0.5, "default_execution_mode": "autonomous",
        })
        assert any(r["funnel_action"] == "route_high_intent_concierge" for r in rows)

    def test_outputs_required_fields(self):
        rows = compute_funnel_executions({})
        for r in rows:
            for k in ("funnel_action", "target_funnel_path", "execution_mode", "expected_upside", "confidence", "explanation"):
                assert k in r


class TestPaidOperator:
    def test_winner_enters_paid(self):
        winners = [{
            "content_item_id": "x", "autonomous_run_id": None,
            "engagement_score": 0.88, "revenue_proxy": 300, "days_since_publish": 5,
        }]
        runs = compute_paid_operator_runs(winners, {"default_execution_mode": "guarded"})
        assert len(runs) >= 1
        assert runs[0]["paid_action"] in ("start_paid_test", "scale_paid_test")
        assert runs[0]["budget_band"]
        assert runs[0]["expected_cac"] > 0

    def test_low_eng_excluded(self):
        winners = [{"engagement_score": 0.3, "revenue_proxy": 10, "days_since_publish": 3}]
        assert compute_paid_operator_runs(winners, {}) == []

    def test_decision_stop_on_bad_cpa(self):
        d = compute_paid_operator_decision({}, {"cpa_actual": 120, "cpa_target": 50, "spend_7d": 250, "conversions_7d": 0, "roi_actual": 0})
        assert d["decision_type"] == "stop"

    def test_decision_scale_on_strong_roi(self):
        d = compute_paid_operator_decision({}, {"cpa_actual": 40, "cpa_target": 50, "spend_7d": 200, "conversions_7d": 5, "roi_actual": 1.3})
        assert d["decision_type"] == "scale"


class TestSponsor:
    def test_returns_actions(self):
        rows = compute_sponsor_autonomous_actions({})
        assert len(rows) >= 2
        assert any(r["sponsor_action"] == "rank_categories" for r in rows)


class TestRetention:
    def test_churn_triggers_reactivation(self):
        rows = compute_retention_actions({"churn_risk_score": 0.7})
        assert any(r["retention_action"] == "reactivation_flow" for r in rows)

    def test_integration_churn_cohort(self):
        rows = compute_retention_actions({"churn_risk_score": 0.62, "ltv_tier": "mid"})
        types = {r["retention_action"] for r in rows}
        assert "reactivation_flow" in types


class TestRecovery:
    def test_detects_multiple(self):
        sig = {
            "provider_failure": True,
            "queue_congestion_score": 0.8,
            "budget_overspend_pct": 0.15,
        }
        inc = detect_recovery_incidents(sig)
        types = {i["incident_type"] for i in inc}
        assert "provider_failure" in types
        assert "queue_congestion" in types
        assert "budget_overspend" in types

    def test_self_healing_maps(self):
        inc = {"incident_type": "fatigue_spike", "severity": "medium"}
        h = compute_self_healing_action(inc)
        assert h["action_taken"] == "suppress_output_rotate_creative"
        assert h["action_mode"] in ("autonomous", "guarded")
        assert h["escalation_requirement"] in ("none", "operator_review", "immediate_operator")

    def test_integration_recovery_triggers_heal(self):
        inc = detect_recovery_incidents({"conversion_drop_pct": 0.3})[0]
        h = compute_self_healing_action(inc)
        assert h["incident_type"] == "conversion_drop"
        assert "throttle" in h["action_taken"] or "funnel" in h["action_taken"]
