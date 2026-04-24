"""Unit tests for causal attribution engine."""
import pytest

from packages.scoring.causal_attribution_engine import (
    DRIVER_TYPES,
    allocate_credit,
    build_confidence_summary,
    detect_change_points,
    extract_candidate_causes,
    score_causal_confidence,
)


class TestChangePoint:
    def test_detects_lift(self):
        series = [100, 100, 100, 130, 130]
        changes = detect_change_points(series)
        assert len(changes) >= 1
        assert changes[0]["direction"] == "lift"

    def test_detects_drop(self):
        series = [100, 100, 70, 70]
        changes = detect_change_points(series)
        assert any(c["direction"] == "drop" for c in changes)

    def test_stable_no_change(self):
        series = [100, 101, 99, 100, 102]
        assert detect_change_points(series) == []

    def test_short_series(self):
        assert detect_change_points([100]) == []


class TestCandidateCause:
    def test_matches_temporal(self):
        changes = [{"index": 3, "change_pct": 30, "direction": "lift"}]
        events = [{"index": 3, "driver_type": "offer_change", "driver_name": "Switched offer"}]
        candidates = extract_candidate_causes(changes, events)
        assert len(candidates) == 1
        assert candidates[0]["driver_type"] == "offer_change"

    def test_no_match_far(self):
        changes = [{"index": 3, "change_pct": 30}]
        events = [{"index": 10, "driver_type": "test"}]
        assert extract_candidate_causes(changes, events) == []


class TestConfidence:
    def test_experiment_high_confidence(self):
        c = {"change": {"change_pct": 40, "direction": "lift"}, "driver_type": "experiment_result", "driver_name": "Exp A", "temporal_proximity": 0}
        r = score_causal_confidence(c)
        assert r["confidence"] >= 0.6
        assert "Promote" in r["recommended_action"]

    def test_seasonal_low_confidence(self):
        c = {"change": {"change_pct": 15, "direction": "lift"}, "driver_type": "seasonal_pattern", "driver_name": "Holiday", "temporal_proximity": 1}
        r = score_causal_confidence(c)
        assert r["confidence"] < 0.5
        assert "seasonal" in str(r["competing_explanations"]).lower()

    def test_noise_flagged(self):
        c = {"change": {"change_pct": 3, "direction": "lift"}, "driver_type": "external_event", "driver_name": "Minor", "temporal_proximity": 2}
        r = score_causal_confidence(c)
        assert r["noise_flag"] is True


class TestCreditAllocation:
    def test_proportional(self):
        hypos = [{"driver_name": "A", "confidence": 0.8}, {"driver_name": "B", "confidence": 0.2}]
        credits = allocate_credit(hypos)
        assert credits[0]["driver_name"] == "A"
        assert credits[0]["credit_pct"] > credits[1]["credit_pct"]
        assert sum(c["credit_pct"] for c in credits) == pytest.approx(100, abs=0.5)

    def test_cautious_flag(self):
        hypos = [{"driver_name": "X", "confidence": 0.3, "noise_flag": True}]
        credits = allocate_credit(hypos)
        assert credits[0]["promote_cautiously"] is True

    def test_empty(self):
        assert allocate_credit([]) == []


class TestConfidenceSummary:
    def test_all_high(self):
        hypos = [{"confidence": 0.8}, {"confidence": 0.75}]
        s = build_confidence_summary(hypos)
        assert s["high_confidence_count"] == 2
        assert "safe to promote" in s["recommendation"]

    def test_mostly_noise(self):
        hypos = [{"confidence": 0.05, "noise_flag": True}, {"confidence": 0.03, "noise_flag": True}, {"confidence": 0.8}]
        s = build_confidence_summary(hypos)
        assert s["noise_flagged_count"] == 2

    def test_mixed(self):
        hypos = [{"confidence": 0.8}, {"confidence": 0.3}]
        s = build_confidence_summary(hypos)
        assert "cautiously" in s["recommendation"]


class TestDriverTypes:
    def test_10_types(self):
        assert len(DRIVER_TYPES) == 10
