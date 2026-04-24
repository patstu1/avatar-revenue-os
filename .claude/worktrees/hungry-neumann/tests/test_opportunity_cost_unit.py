"""Unit tests for opportunity-cost ranking engine — pure functions, no DB."""
import pytest
from packages.scoring.opportunity_cost_engine import (
    ACTION_TYPES, SAFE_WAIT_THRESHOLD,
    generate_candidates, score_upside, score_cost_of_delay,
    score_urgency, rank_actions, build_report,
)


class TestActionTypes:
    def test_all_10_types(self):
        assert len(ACTION_TYPES) == 10
        for t in ("push_volume", "launch_account", "switch_content_form", "promote_winner",
                   "kill_weak_lane", "activate_monetization", "fix_blocker", "run_experiment",
                   "upgrade_provider", "publish_asset"):
            assert t in ACTION_TYPES


class TestCandidateGeneration:
    def test_generates_from_accounts(self):
        state = {"accounts": [{"id": "a1", "name": "acct1", "state": "scaling"}, {"id": "a2", "name": "acct2", "state": "weak"}]}
        candidates = generate_candidates(state)
        types = {c["action_type"] for c in candidates}
        assert "push_volume" in types
        assert "kill_weak_lane" in types

    def test_generates_from_winners(self):
        state = {"experiment_winners": [{"id": "w1", "name": "exp1", "confidence": 0.9}]}
        candidates = generate_candidates(state)
        assert any(c["action_type"] == "promote_winner" for c in candidates)

    def test_generates_from_blockers(self):
        state = {"blockers": [{"id": "b1", "name": "quality block"}]}
        candidates = generate_candidates(state)
        assert any(c["action_type"] == "fix_blocker" for c in candidates)

    def test_generates_from_ready_assets(self):
        state = {"ready_assets": [{"id": "ci1", "title": "Ready content"}]}
        candidates = generate_candidates(state)
        assert any(c["action_type"] == "publish_asset" for c in candidates)

    def test_empty_state(self):
        assert generate_candidates({}) == []


class TestScoring:
    def test_upside_normalized(self):
        assert 0 <= score_upside({"expected_upside": 30}) <= 1
        assert score_upside({"expected_upside": 100}) == 1.0
        assert score_upside({"expected_upside": 0}) == 0.0

    def test_cost_of_delay_varies_by_type(self):
        blocker = score_cost_of_delay({"action_type": "fix_blocker", "expected_upside": 20})
        experiment = score_cost_of_delay({"action_type": "run_experiment", "expected_upside": 20})
        assert blocker["daily_cost"] > experiment["daily_cost"]
        assert blocker["time_sensitivity"] == "critical"
        assert experiment["time_sensitivity"] == "low"

    def test_cost_of_delay_weekly(self):
        delay = score_cost_of_delay({"action_type": "fix_blocker", "expected_upside": 10})
        assert delay["weekly_cost"] == pytest.approx(delay["daily_cost"] * 7, abs=0.1)

    def test_urgency_critical_higher(self):
        critical_delay = {"daily_cost": 12, "time_sensitivity": "critical"}
        low_delay = {"daily_cost": 1, "time_sensitivity": "low"}
        u_crit = score_urgency({"confidence": 0.8}, critical_delay)
        u_low = score_urgency({"confidence": 0.3}, low_delay)
        assert u_crit > u_low


class TestRanking:
    def test_ranks_by_composite(self):
        candidates = [
            {"action_type": "fix_blocker", "action_key": "fix:block1", "expected_upside": 25, "confidence": 0.9},
            {"action_type": "run_experiment", "action_key": "exp:test1", "expected_upside": 10, "confidence": 0.4},
        ]
        ranked = rank_actions(candidates)
        assert len(ranked) == 2
        assert ranked[0]["rank_position"] == 1
        assert ranked[0]["composite_rank"] >= ranked[1]["composite_rank"]
        assert ranked[0]["action_type"] == "fix_blocker"

    def test_safe_to_wait_marked(self):
        candidates = [
            {"action_type": "run_experiment", "action_key": "exp:small", "expected_upside": 1, "confidence": 0.2},
        ]
        ranked = rank_actions(candidates)
        assert ranked[0]["safe_to_wait"] is True

    def test_high_urgency_not_safe(self):
        candidates = [
            {"action_type": "fix_blocker", "action_key": "fix:critical", "expected_upside": 40, "confidence": 0.9},
        ]
        ranked = rank_actions(candidates)
        assert ranked[0]["safe_to_wait"] is False

    def test_empty_candidates(self):
        assert rank_actions([]) == []


class TestReport:
    def test_builds_report(self):
        ranked = [
            {"action_type": "fix_blocker", "cost_of_delay": 12, "safe_to_wait": False},
            {"action_type": "run_experiment", "cost_of_delay": 1, "safe_to_wait": True},
        ]
        report = build_report(ranked)
        assert report["total_actions"] == 2
        assert report["total_opportunity_cost"] == 13
        assert report["safe_to_wait_count"] == 1
        assert report["top_action_type"] == "fix_blocker"
        assert "$13" in report["summary"]
