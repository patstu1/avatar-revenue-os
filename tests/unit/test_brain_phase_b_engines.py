"""Unit tests for Brain Architecture Phase B scoring engines."""

from packages.scoring.brain_phase_b_engine import (
    CONFIDENCE_BANDS,
    DECISION_CLASSES,
    POLICY_MODES,
    compute_arbitration,
    compute_brain_decision,
    compute_confidence_report,
    compute_policy_evaluation,
    compute_upside_cost_estimate,
)

# ── Master Decision Engine ────────────────────────────────────────────

class TestComputeBrainDecision:
    def test_blocker_escalates(self):
        r = compute_brain_decision({"has_blocker": True})
        assert r["decision_class"] == "escalate"

    def test_failed_execution_recovers(self):
        r = compute_brain_decision({"execution_state": "failed"})
        assert r["decision_class"] == "recover"

    def test_high_saturation_suppresses(self):
        r = compute_brain_decision({"saturation_score": 0.8})
        assert r["decision_class"] == "suppress"

    def test_high_fatigue_throttles(self):
        r = compute_brain_decision({"fatigue_score": 0.7, "saturation_score": 0.3})
        assert r["decision_class"] == "throttle"

    def test_at_risk_recovers(self):
        r = compute_brain_decision({"account_state": "at_risk"})
        assert r["decision_class"] == "recover"

    def test_churn_risk_monetizes(self):
        r = compute_brain_decision({"churn_risk": 0.6, "audience_state": "churn_risk"})
        assert r["decision_class"] == "monetize"

    def test_newborn_launches(self):
        r = compute_brain_decision({"account_state": "newborn"})
        assert r["decision_class"] == "launch"

    def test_test_phase(self):
        r = compute_brain_decision({"opportunity_state": "test", "account_state": "stable"})
        assert r["decision_class"] == "test"

    def test_scale_winner(self):
        r = compute_brain_decision({"opportunity_state": "scale", "profit_per_post": 12, "account_state": "stable"})
        assert r["decision_class"] == "scale"

    def test_stable_monetizes(self):
        r = compute_brain_decision({"profit_per_post": 7, "account_state": "stable"})
        assert r["decision_class"] == "monetize"

    def test_max_output_holds(self):
        r = compute_brain_decision({"account_state": "max_output"})
        assert r["decision_class"] == "hold"

    def test_default_hold(self):
        r = compute_brain_decision({})
        assert r["decision_class"] in DECISION_CLASSES

    def test_has_alternatives(self):
        r = compute_brain_decision({"has_blocker": True})
        assert isinstance(r["alternatives"], list)
        assert len(r["alternatives"]) >= 1

    def test_has_downstream_action(self):
        r = compute_brain_decision({"account_state": "newborn"})
        assert r["downstream_action"] is not None

    def test_output_fields(self):
        r = compute_brain_decision({})
        for key in ["decision_class", "objective", "selected_action", "alternatives", "downstream_action", "confidence", "explanation"]:
            assert key in r


# ── Policy Engine ─────────────────────────────────────────────────────

class TestComputePolicyEvaluation:
    def test_operator_override(self):
        r = compute_policy_evaluation({"operator_override_mode": "manual"})
        assert r["policy_mode"] == "manual"

    def test_high_compliance_forces_manual(self):
        r = compute_policy_evaluation({"compliance_sensitivity": 0.8})
        assert r["policy_mode"] == "manual"
        assert r["approval_needed"] is True

    def test_high_risk_forces_manual(self):
        r = compute_policy_evaluation({"risk_score": 0.8})
        assert r["policy_mode"] == "manual"

    def test_low_health_forces_manual(self):
        r = compute_policy_evaluation({"account_health_score": 0.2})
        assert r["policy_mode"] == "manual"

    def test_high_cost_forces_guarded(self):
        r = compute_policy_evaluation({"cost": 100, "confidence": 0.9, "risk_score": 0.1})
        assert r["policy_mode"] == "guarded"

    def test_low_confidence_forces_guarded(self):
        r = compute_policy_evaluation({"confidence": 0.3})
        assert r["policy_mode"] == "guarded"

    def test_autonomous_when_safe(self):
        r = compute_policy_evaluation({"confidence": 0.8, "risk_score": 0.1, "cost": 10})
        assert r["policy_mode"] == "autonomous"
        assert r["approval_needed"] is False

    def test_hard_stop_on_very_high_compliance(self):
        r = compute_policy_evaluation({"compliance_sensitivity": 0.9})
        assert r["hard_stop_rule"] is not None

    def test_rollback_on_cost(self):
        r = compute_policy_evaluation({"cost": 50, "confidence": 0.8, "risk_score": 0.1})
        assert r["rollback_rule"] is not None

    def test_mode_is_valid(self):
        r = compute_policy_evaluation({})
        assert r["policy_mode"] in POLICY_MODES


# ── Confidence Engine ─────────────────────────────────────────────────

class TestComputeConfidenceReport:
    def test_high_confidence(self):
        r = compute_confidence_report({
            "signal_strength": 0.9, "historical_precedent": 0.8,
            "data_completeness": 0.9, "execution_history": 0.8,
            "memory_support": 0.7,
        })
        assert r["confidence_band"] in ("high", "very_high")
        assert r["confidence_score"] >= 0.7

    def test_low_confidence(self):
        r = compute_confidence_report({
            "signal_strength": 0.1, "historical_precedent": 0.1,
            "data_completeness": 0.1,
        })
        assert r["confidence_band"] in ("low", "very_low")

    def test_saturation_reduces_confidence(self):
        base = compute_confidence_report({"saturation_risk": 0.0})
        sat = compute_confidence_report({"saturation_risk": 0.9})
        assert sat["confidence_score"] < base["confidence_score"]

    def test_blocker_reduces_confidence(self):
        base = compute_confidence_report({"blocker_severity": 0.0})
        blk = compute_confidence_report({"blocker_severity": 0.9})
        assert blk["confidence_score"] < base["confidence_score"]

    def test_uncertainty_factors(self):
        r = compute_confidence_report({"data_completeness": 0.2, "signal_strength": 0.1})
        assert len(r["uncertainty_factors"]) >= 1

    def test_band_is_valid(self):
        r = compute_confidence_report({})
        assert r["confidence_band"] in CONFIDENCE_BANDS

    def test_score_bounded(self):
        r = compute_confidence_report({"signal_strength": 2.0, "blocker_severity": 5.0})
        assert 0.0 <= r["confidence_score"] <= 1.0


# ── Cost / Upside Estimation ─────────────────────────────────────────

class TestComputeUpsideCostEstimate:
    def test_positive_net(self):
        r = compute_upside_cost_estimate({
            "revenue_potential": 10.0, "conversion_rate": 0.05,
            "traffic_estimate": 5000, "content_cost": 5, "tool_cost": 2,
        })
        assert r["expected_upside"] > 0
        assert r["net_value"] > 0

    def test_negative_net_high_cost(self):
        r = compute_upside_cost_estimate({
            "revenue_potential": 0.5, "conversion_rate": 0.01,
            "traffic_estimate": 100, "content_cost": 100,
        })
        assert r["net_value"] < 0

    def test_payback_days(self):
        r = compute_upside_cost_estimate({"time_to_revenue_days": 14})
        assert r["expected_payback_days"] >= 14 or r["expected_payback_days"] == 999

    def test_concentration_risk(self):
        r = compute_upside_cost_estimate({"concentration_share": 0.8})
        assert r["concentration_risk"] > 0.5

    def test_ops_burden_increases_with_spend(self):
        low = compute_upside_cost_estimate({"paid_spend": 0})
        high = compute_upside_cost_estimate({"paid_spend": 200})
        assert high["operational_burden"] >= low["operational_burden"]


# ── Priority Arbitration ─────────────────────────────────────────────

class TestComputeArbitration:
    def test_empty_candidates(self):
        r = compute_arbitration([])
        assert r["chosen_winner_class"] == "hold"
        assert r["competing_count"] == 0

    def test_single_candidate_wins(self):
        r = compute_arbitration([{"category": "new_launch", "label": "Launch X", "net_value": 100, "confidence": 0.8, "urgency": 0.6}])
        assert r["chosen_winner_class"] == "new_launch"
        assert r["competing_count"] == 1

    def test_recovery_beats_output(self):
        r = compute_arbitration([
            {"category": "recovery_action", "label": "Fix failure", "net_value": 50, "confidence": 0.7, "urgency": 0.9},
            {"category": "more_output", "label": "Post more", "net_value": 60, "confidence": 0.7, "urgency": 0.3},
        ])
        assert r["chosen_winner_class"] == "recovery_action"

    def test_rejected_has_reasons(self):
        r = compute_arbitration([
            {"category": "new_launch", "label": "A", "net_value": 100, "confidence": 0.8, "urgency": 0.5},
            {"category": "more_output", "label": "B", "net_value": 50, "confidence": 0.5, "urgency": 0.3},
        ])
        assert len(r["rejected_actions"]) == 1
        assert "reason" in r["rejected_actions"][0]

    def test_ranked_priorities_ordered(self):
        r = compute_arbitration([
            {"category": "new_launch", "label": "A", "net_value": 100, "confidence": 0.8, "urgency": 0.5},
            {"category": "funnel_fix", "label": "B", "net_value": 80, "confidence": 0.8, "urgency": 0.7},
            {"category": "sponsor_action", "label": "C", "net_value": 40, "confidence": 0.6, "urgency": 0.3},
        ])
        assert r["ranked_priorities"][0]["rank"] == 1
        assert r["competing_count"] == 3

    def test_high_urgency_recovery_wins(self):
        r = compute_arbitration([
            {"category": "recovery_action", "label": "Critical fix", "net_value": 50, "confidence": 0.7, "urgency": 1.0},
            {"category": "new_launch", "label": "Big launch", "net_value": 55, "confidence": 0.8, "urgency": 0.2},
        ])
        assert r["chosen_winner_class"] == "recovery_action"
