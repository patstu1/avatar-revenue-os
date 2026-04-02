"""Unit tests for capital allocator engine — pure functions, no DB."""
import pytest
from packages.scoring.capital_allocator_engine import (
    score_expected_return,
    determine_provider_tier,
    solve_allocation,
    rebalance,
    STARVATION_THRESHOLD,
    HERO_THRESHOLD,
    EXPERIMENT_RESERVE_PCT,
)


class TestExpectedReturn:
    def test_high_roi_high_confidence(self):
        score = score_expected_return({
            "expected_return": 50, "expected_cost": 5, "confidence": 0.9,
            "account_health": 1.0, "fatigue_score": 0, "pattern_win_score": 0.8,
            "conversion_quality": 0.5,
        })
        assert score > 0.6

    def test_negative_roi(self):
        score = score_expected_return({
            "expected_return": 1, "expected_cost": 100, "confidence": 0.3,
            "account_health": 0.5, "fatigue_score": 0.8, "pattern_win_score": 0,
        })
        assert score < 0.3

    def test_zero_inputs(self):
        score = score_expected_return({})
        assert 0 <= score <= 1

    def test_fatigue_penalizes(self):
        base = score_expected_return({"expected_return": 20, "expected_cost": 5, "confidence": 0.7, "fatigue_score": 0})
        fatigued = score_expected_return({"expected_return": 20, "expected_cost": 5, "confidence": 0.7, "fatigue_score": 0.9})
        assert base > fatigued


class TestProviderTier:
    def test_hero_for_high_return(self):
        assert determine_provider_tier(0.7, {}) == "hero"

    def test_bulk_for_low_return(self):
        assert determine_provider_tier(0.2, {}) == "bulk"

    def test_standard_for_experiments(self):
        assert determine_provider_tier(0.3, {"target_type": "experiment"}) == "standard"

    def test_hero_for_strong_pattern(self):
        assert determine_provider_tier(0.4, {"pattern_win_score": 0.7}) == "hero"


class TestSolveAllocation:
    def test_empty_targets(self):
        result = solve_allocation([], 1000.0)
        assert result["decisions"] == []
        assert result["report"]["total_budget"] == 1000.0

    def test_zero_budget(self):
        result = solve_allocation([{"target_type": "account", "target_key": "a"}], 0)
        assert result["decisions"] == []

    def test_allocates_proportionally(self):
        targets = [
            {"target_type": "account", "target_key": "a", "expected_return": 50, "expected_cost": 5, "confidence": 0.9, "account_health": 1.0, "pattern_win_score": 0.8},
            {"target_type": "account", "target_key": "b", "expected_return": 5, "expected_cost": 5, "confidence": 0.3, "account_health": 0.5, "pattern_win_score": 0.1},
        ]
        result = solve_allocation(targets, 1000.0)
        assert len(result["decisions"]) == 2
        assert result["decisions"][0]["allocated_budget"] > result["decisions"][1]["allocated_budget"]

    def test_experiment_reserve(self):
        targets = [{"target_type": "experiment", "target_key": "exp1", "expected_return": 15, "expected_cost": 5, "confidence": 0.4}]
        result = solve_allocation(targets, 1000.0)
        assert result["report"]["experiment_reserve"] == pytest.approx(1000.0 * EXPERIMENT_RESERVE_PCT, abs=1.0)

    def test_starvation(self):
        targets = [
            {"target_type": "account", "target_key": "strong", "expected_return": 80, "expected_cost": 5, "confidence": 0.9, "account_health": 1.0, "pattern_win_score": 0.9},
            {"target_type": "account", "target_key": "weak", "expected_return": 0.1, "expected_cost": 10, "confidence": 0.1, "account_health": 0.2, "pattern_win_score": 0},
        ]
        result = solve_allocation(targets, 1000.0)
        weak_dec = [d for d in result["decisions"] if d["target_key"] == "weak"]
        assert len(weak_dec) == 1
        assert weak_dec[0]["starved"] is True
        assert result["report"]["starved_count"] >= 1

    def test_hero_vs_bulk_tier(self):
        targets = [
            {"target_type": "account", "target_key": "hero", "expected_return": 80, "expected_cost": 5, "confidence": 0.95, "account_health": 1.0, "pattern_win_score": 0.9},
            {"target_type": "account", "target_key": "bulk", "expected_return": 3, "expected_cost": 5, "confidence": 0.3, "account_health": 0.5, "pattern_win_score": 0.1},
        ]
        result = solve_allocation(targets, 1000.0)
        hero_dec = [d for d in result["decisions"] if d["target_key"] == "hero"]
        bulk_dec = [d for d in result["decisions"] if d["target_key"] == "bulk"]
        assert hero_dec[0]["provider_tier"] == "hero"
        assert bulk_dec[0]["provider_tier"] == "bulk"
        assert result["report"]["hero_spend"] > 0
        assert result["report"]["bulk_spend"] > 0

    def test_constraints_applied(self):
        targets = [
            {"target_type": "offer", "target_key": "constrained", "expected_return": 50, "expected_cost": 5, "confidence": 0.9},
        ]
        constraints = [{"constraint_type": "offer", "constraint_key": "constrained", "min_value": 0.05, "max_value": 0.10}]
        result = solve_allocation(targets, 1000.0, constraints)
        assert result["decisions"][0]["allocation_pct"] <= 10.1

    def test_volume_calculated(self):
        targets = [{"target_type": "account", "target_key": "a", "expected_return": 30, "expected_cost": 10, "confidence": 0.7}]
        result = solve_allocation(targets, 500.0)
        assert result["decisions"][0]["allocated_volume"] >= 1


class TestRebalance:
    def test_boost_on_outperformance(self):
        decisions = [{"target_key": "a", "return_score": 0.5}]
        perf = {"a": {"actual_roi": 0.7}}
        result = rebalance(decisions, perf)
        assert result["targets_boosted"] == 1

    def test_starve_on_underperformance(self):
        decisions = [{"target_key": "a", "return_score": 0.5}]
        perf = {"a": {"actual_roi": 0.2}}
        result = rebalance(decisions, perf)
        assert result["targets_starved"] == 1

    def test_no_change_when_stable(self):
        decisions = [{"target_key": "a", "return_score": 0.5}]
        perf = {"a": {"actual_roi": 0.52}}
        result = rebalance(decisions, perf)
        assert result["targets_boosted"] == 0
        assert result["targets_starved"] == 0
