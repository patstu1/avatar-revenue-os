"""Unit tests for account-state intelligence engine — pure functions, no DB."""
import pytest
from packages.scoring.account_state_intel_engine import (
    ACCOUNT_STATES, STATE_POLICIES,
    classify_account_state, detect_transition, generate_actions,
)


class TestStates:
    def test_all_12_states(self):
        assert len(ACCOUNT_STATES) == 12
        for s in ("newborn", "warming", "early_signal", "scaling", "monetizing",
                   "authority_building", "trust_repair", "saturated", "cooling",
                   "weak", "suppressed", "blocked"):
            assert s in ACCOUNT_STATES

    def test_every_state_has_policy(self):
        for s in ACCOUNT_STATES:
            assert s in STATE_POLICIES
            p = STATE_POLICIES[s]
            assert "monetization_intensity" in p
            assert "posting_cadence" in p
            assert "expansion_eligible" in p
            assert "content_forms" in p
            assert "blocked_actions" in p


class TestClassify:
    def test_blocked_account(self):
        r = classify_account_state({"blocker_state": "blocked"})
        assert r["current_state"] == "blocked"
        assert r["posting_cadence"] == "paused"
        assert r["expansion_eligible"] is False

    def test_suspended_account(self):
        r = classify_account_state({"account_health": "suspended"})
        assert r["current_state"] == "suppressed"

    def test_critical_health(self):
        r = classify_account_state({"account_health": "critical"})
        assert r["current_state"] == "trust_repair"
        assert r["monetization_intensity"] == "none"

    def test_newborn(self):
        r = classify_account_state({"age_days": 3, "post_count": 2})
        assert r["current_state"] == "newborn"

    def test_warming(self):
        r = classify_account_state({"age_days": 15, "impressions": 2000, "post_count": 10})
        assert r["current_state"] == "warming"

    def test_saturated(self):
        r = classify_account_state({"saturation_score": 0.8, "age_days": 100, "post_count": 200})
        assert r["current_state"] == "saturated"

    def test_cooling(self):
        r = classify_account_state({"fatigue_score": 0.7, "engagement_rate": 0.02, "age_days": 60, "post_count": 50})
        assert r["current_state"] == "cooling"

    def test_weak(self):
        r = classify_account_state({"account_health": "warning", "engagement_rate": 0.01, "age_days": 45, "post_count": 30})
        assert r["current_state"] == "weak"

    def test_monetizing(self):
        r = classify_account_state({"total_revenue": 200, "conversion_rate": 0.05, "total_profit": 50, "age_days": 90, "post_count": 100, "impressions": 30000, "engagement_rate": 0.06})
        assert r["current_state"] == "monetizing"
        assert r["monetization_intensity"] == "high"

    def test_scaling(self):
        r = classify_account_state({"impressions": 60000, "engagement_rate": 0.06, "total_profit": 10, "age_days": 60, "post_count": 80})
        assert r["current_state"] == "scaling"
        assert r["expansion_eligible"] is True

    def test_authority_building(self):
        r = classify_account_state({"impressions": 25000, "engagement_rate": 0.07, "age_days": 90, "post_count": 100})
        assert r["current_state"] == "authority_building"

    def test_early_signal(self):
        r = classify_account_state({"engagement_rate": 0.05, "impressions": 12000, "age_days": 40, "post_count": 20})
        assert r["current_state"] == "early_signal"

    def test_empty_inputs_default(self):
        r = classify_account_state({})
        assert r["current_state"] in ACCOUNT_STATES
        assert 0 <= r["confidence"] <= 1

    def test_next_best_move_always_set(self):
        for state in ACCOUNT_STATES:
            r = classify_account_state({"blocker_state": "blocked"} if state == "blocked" else {"account_health": "suspended"} if state == "suppressed" else {})
            assert r["next_best_move"] is not None


class TestTransition:
    def test_no_transition_when_same(self):
        assert detect_transition("scaling", "scaling", {}) is None

    def test_upgrade_detected(self):
        t = detect_transition("warming", "scaling", {})
        assert t is not None
        assert t["direction"] == "upgrade"

    def test_downgrade_detected(self):
        t = detect_transition("scaling", "weak", {})
        assert t is not None
        assert t["direction"] == "downgrade"


class TestActions:
    def test_newborn_actions(self):
        actions = generate_actions("newborn", {})
        assert len(actions) >= 1
        assert actions[0]["action_type"] == "publish_content"

    def test_trust_repair_pauses_monetization(self):
        actions = generate_actions("trust_repair", {})
        types = {a["action_type"] for a in actions}
        assert "pause_monetization" in types

    def test_scaling_increases_volume(self):
        actions = generate_actions("scaling", {})
        types = {a["action_type"] for a in actions}
        assert "volume_increase" in types

    def test_every_state_has_actions(self):
        for state in ACCOUNT_STATES:
            actions = generate_actions(state, {})
            assert len(actions) >= 1
