"""Unit tests for Creator Revenue Avenues Phase D hub engine."""
from __future__ import annotations

from packages.scoring.creator_revenue_engine import (
    AVENUE_DISPLAY_NAMES,
    AVENUE_MISSING_INTEGRATIONS,
    AVENUE_TYPES,
    build_event_rollup,
    classify_avenue_truth_state,
    determine_operator_next_action,
    rank_hub_entries,
)

# ── classify_avenue_truth_state ────────────────────────────────────────

class TestClassifyAvenueTruthState:
    def test_live_when_revenue(self):
        assert classify_avenue_truth_state(5, 0, 0, True) == "live"

    def test_recommended_when_no_actions(self):
        assert classify_avenue_truth_state(0, 0, 0, False) == "recommended"

    def test_blocked_when_all_blocked(self):
        assert classify_avenue_truth_state(3, 3, 2, False) == "blocked"

    def test_queued_when_some_blocked_with_blockers(self):
        assert classify_avenue_truth_state(5, 2, 3, False) == "queued"

    def test_executing_when_actions_no_blockers(self):
        assert classify_avenue_truth_state(5, 0, 0, False) == "executing"

    def test_live_overrides_blocked(self):
        assert classify_avenue_truth_state(5, 5, 3, True) == "live"

    def test_all_valid_states(self):
        valid = {"recommended", "queued", "executing", "blocked", "live"}
        for ac in range(4):
            for bl in range(ac + 1):
                for bc in range(3):
                    for has_rev in [True, False]:
                        state = classify_avenue_truth_state(ac, bl, bc, has_rev)
                        assert state in valid, f"Invalid state {state} for ({ac}, {bl}, {bc}, {has_rev})"


# ── determine_operator_next_action ─────────────────────────────────────

class TestDetermineOperatorNextAction:
    def test_live_returns_monitor(self):
        action = determine_operator_next_action("merch", "live", [])
        assert "Monitor" in action

    def test_blocked_with_payment(self):
        action = determine_operator_next_action("merch", "blocked", ["no_payment_processor"])
        assert "payment processor" in action.lower()

    def test_blocked_with_portfolio(self):
        action = determine_operator_next_action("ugc_services", "blocked", ["insufficient_portfolio"])
        assert "portfolio" in action.lower()

    def test_blocked_with_offers(self):
        action = determine_operator_next_action("consulting", "blocked", ["no_offers_defined"])
        assert "offer" in action.lower()

    def test_queued_mentions_review(self):
        action = determine_operator_next_action("licensing", "queued", [])
        assert "Review" in action or "resolve" in action.lower()

    def test_executing_mentions_execute(self):
        action = determine_operator_next_action("merch", "executing", [])
        assert "Execute" in action or "execute" in action.lower()

    def test_recommended_mentions_recompute(self):
        action = determine_operator_next_action("merch", "recommended", [])
        assert "Recompute" in action or "recompute" in action.lower()


# ── rank_hub_entries ───────────────────────────────────────────────────

class TestRankHubEntries:
    def test_adds_hub_score(self):
        entries = [
            {"avenue_type": "merch", "truth_state": "executing", "total_expected_value": 10000, "avg_confidence": 0.5},
            {"avenue_type": "licensing", "truth_state": "blocked", "total_expected_value": 20000, "avg_confidence": 0.3},
        ]
        ranked = rank_hub_entries(entries)
        assert "hub_score" in ranked[0]
        assert "hub_score" in ranked[1]

    def test_sorted_descending_by_score(self):
        entries = [
            {"avenue_type": "a", "truth_state": "blocked", "total_expected_value": 100, "avg_confidence": 0.1},
            {"avenue_type": "b", "truth_state": "live", "total_expected_value": 50000, "avg_confidence": 0.8},
            {"avenue_type": "c", "truth_state": "executing", "total_expected_value": 20000, "avg_confidence": 0.6},
        ]
        ranked = rank_hub_entries(entries)
        scores = [e["hub_score"] for e in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_live_beats_blocked_at_same_value(self):
        entries = [
            {"avenue_type": "a", "truth_state": "blocked", "total_expected_value": 10000, "avg_confidence": 0.5},
            {"avenue_type": "b", "truth_state": "live", "total_expected_value": 10000, "avg_confidence": 0.5},
        ]
        ranked = rank_hub_entries(entries)
        assert ranked[0]["avenue_type"] == "b"

    def test_empty_entries(self):
        assert rank_hub_entries([]) == []


# ── build_event_rollup ─────────────────────────────────────────────────

class TestBuildEventRollup:
    def test_empty_events(self):
        rollup = build_event_rollup([])
        assert rollup["total_revenue"] == 0
        assert rollup["event_count"] == 0
        assert rollup["by_avenue"] == {}

    def test_single_event(self):
        events = [{"avenue_type": "merch", "revenue": 100, "cost": 20, "profit": 80}]
        rollup = build_event_rollup(events)
        assert rollup["total_revenue"] == 100
        assert rollup["total_profit"] == 80
        assert rollup["event_count"] == 1
        assert "merch" in rollup["by_avenue"]

    def test_multi_avenue_aggregation(self):
        events = [
            {"avenue_type": "merch", "revenue": 100, "cost": 20, "profit": 80},
            {"avenue_type": "merch", "revenue": 200, "cost": 30, "profit": 170},
            {"avenue_type": "licensing", "revenue": 500, "cost": 0, "profit": 500},
        ]
        rollup = build_event_rollup(events)
        assert rollup["total_revenue"] == 800
        assert rollup["event_count"] == 3
        assert rollup["by_avenue"]["merch"]["revenue"] == 300
        assert rollup["by_avenue"]["merch"]["count"] == 2
        assert rollup["by_avenue"]["licensing"]["revenue"] == 500

    def test_precision(self):
        events = [
            {"avenue_type": "x", "revenue": 0.1, "cost": 0.0, "profit": 0.1},
            {"avenue_type": "x", "revenue": 0.2, "cost": 0.0, "profit": 0.2},
        ]
        rollup = build_event_rollup(events)
        assert rollup["total_revenue"] == 0.3


# ── AVENUE constants ───────────────────────────────────────────────────

class TestAvenueConstants:
    def test_all_9_avenues(self):
        assert len(AVENUE_TYPES) == 9

    def test_display_names_cover_all(self):
        for at in AVENUE_TYPES:
            assert at in AVENUE_DISPLAY_NAMES

    def test_missing_integrations_cover_all(self):
        for at in AVENUE_TYPES:
            assert at in AVENUE_MISSING_INTEGRATIONS
