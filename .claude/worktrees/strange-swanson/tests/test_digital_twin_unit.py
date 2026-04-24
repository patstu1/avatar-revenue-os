"""Unit tests for digital twin engine."""
import pytest
from packages.scoring.digital_twin_engine import (
    SCENARIO_TYPES, generate_scenarios, estimate_outcome, compare_options, build_recommendation,
)


class TestScenarioTypes:
    def test_8_types(self):
        assert len(SCENARIO_TYPES) == 8


class TestGeneration:
    def test_generates_from_accounts(self):
        state = {"scaling_accounts": [{"id": "a1", "name": "acct1", "state": "scaling"}]}
        scenarios = generate_scenarios(state)
        assert len(scenarios) >= 1
        assert scenarios[0]["scenario_type"] == "push_volume_vs_launch_account"

    def test_generates_from_winners(self):
        state = {"experiment_winners": [{"id": "w1", "confidence": 0.85}]}
        scenarios = generate_scenarios(state)
        assert any(s["scenario_type"] == "push_winner_vs_wait" for s in scenarios)

    def test_generates_from_weak_offers(self):
        state = {"offers": [{"id": "o1", "rank_score": 0.2, "name": "Weak"}]}
        scenarios = generate_scenarios(state)
        assert any(s["scenario_type"] == "push_offer_vs_switch_offer" for s in scenarios)

    def test_empty_state(self):
        assert generate_scenarios({}) == []


class TestOutcome:
    def test_positive_profit(self):
        r = estimate_outcome({"upside": 50, "cost": 10, "risk": 0.2, "time": 7})
        assert r["expected_profit"] == 40
        assert r["risk_adjusted_profit"] == 32
        assert r["confidence"] > 0

    def test_zero_upside(self):
        r = estimate_outcome({"upside": 0, "cost": 0, "risk": 0})
        assert r["expected_profit"] == 0


class TestComparison:
    def test_picks_better_option(self):
        a = {"label": "Push volume", "upside": 40, "cost": 5, "risk": 0.2, "time": 7}
        b = {"label": "Launch new", "upside": 20, "cost": 15, "risk": 0.4, "time": 30}
        r = compare_options(a, b)
        assert r["winner"] == "a"
        assert r["profit_delta"] > 0
        assert r["recommendation"] == "Push volume"

    def test_identifies_missing_evidence(self):
        a = {"label": "Risky A", "upside": 10, "cost": 50, "risk": 0.8, "time": 7}
        b = {"label": "Risky B", "upside": 10, "cost": 50, "risk": 0.8, "time": 14}
        r = compare_options(a, b)
        assert len(r["missing_evidence"]) >= 1


class TestRecommendation:
    def test_builds_from_scenario(self):
        scenario = {
            "scenario_type": "push_volume_vs_launch_account",
            "option_a": {"label": "Push volume", "upside": 40, "cost": 5, "risk": 0.2, "time": 7},
            "option_b": {"label": "Launch new", "upside": 20, "cost": 15, "risk": 0.4, "time": 30},
            "context": {},
        }
        rec = build_recommendation(scenario)
        assert rec["scenario_type"] == "push_volume_vs_launch_account"
        assert rec["recommended_action"] == "Push volume"
        assert rec["expected_profit_delta"] > 0
