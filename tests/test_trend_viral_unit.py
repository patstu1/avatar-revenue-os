"""Unit tests for trend/viral engine."""

from packages.scoring.trend_viral_engine import (
    OPPORTUNITY_TYPES,
    check_duplicate,
    classify_opportunity,
    compute_velocity,
    detect_blockers,
    extract_signals,
    score_opportunity,
    should_suppress,
)


class TestSignalExtraction:
    def test_extracts_new(self):
        raw = [{"topic": "AI trends 2026", "source": "discovery", "signal_strength": 500, "velocity": 2.0}]
        signals = extract_signals(raw, [])
        assert len(signals) == 1
        assert signals[0]["is_new"] is True

    def test_dedup_existing(self):
        raw = [{"topic": "AI trends 2026", "source": "discovery"}]
        signals = extract_signals(raw, ["AI trends 2026"])
        assert signals[0]["is_new"] is False

    def test_skips_short(self):
        raw = [{"topic": "ab"}]
        assert extract_signals(raw, []) == []


class TestVelocity:
    def test_breakout(self):
        r = compute_velocity(3.0, 1.0)
        assert r["breakout"] is True
        assert r["acceleration"] > 0

    def test_stable(self):
        r = compute_velocity(1.0, 1.0)
        assert r["acceleration"] == 0

    def test_zero_previous(self):
        r = compute_velocity(3.0, 0)
        assert r["breakout"] is True


class TestDuplicate:
    def test_detects_near_dup(self):
        assert check_duplicate("best AI tools 2026", ["best AI tools 2026 review"]) is not None

    def test_no_dup(self):
        assert check_duplicate("quantum computing advances", ["best AI tools"]) is None


class TestScoring:
    def test_high_velocity_high_score(self):
        signal = {"topic": "tech breakout", "velocity": 4.0, "signal_strength": 8000, "is_new": True}
        scores = score_opportunity(signal, {"niche": "tech"})
        assert scores["composite_score"] > 0.4
        assert scores["velocity_score"] > 0.5

    def test_low_signal_low_score(self):
        signal = {"topic": "random thing", "velocity": 0.1, "signal_strength": 50, "is_new": False}
        scores = score_opportunity(signal, {"niche": "tech"})
        assert scores["composite_score"] < 0.4


class TestClassification:
    def test_monetization(self):
        scores = {"revenue_potential_score": 0.8, "velocity_score": 0.5, "relevance_score": 0.7, "novelty_score": 0.8}
        c = classify_opportunity(scores)
        assert c["opportunity_type"] == "monetization"
        assert c["recommended_monetization"] == "affiliate"

    def test_pure_reach(self):
        scores = {"revenue_potential_score": 0.1, "velocity_score": 0.9, "relevance_score": 0.3, "novelty_score": 0.9}
        c = classify_opportunity(scores)
        assert c["opportunity_type"] == "pure_reach"
        assert "none" in c["recommended_monetization"]

    def test_authority(self):
        scores = {"revenue_potential_score": 0.3, "velocity_score": 0.2, "relevance_score": 0.8, "novelty_score": 0.5}
        c = classify_opportunity(scores)
        assert c["opportunity_type"] == "authority_building"


class TestSuppression:
    def test_low_score_suppressed(self):
        r = should_suppress({"topic": "test"}, {"composite_score": 0.05, "saturation_risk": 0.2}, [])
        assert r is not None

    def test_high_saturation_suppressed(self):
        r = should_suppress({"topic": "test"}, {"composite_score": 0.5, "saturation_risk": 0.9}, [])
        assert r is not None

    def test_rule_match_suppressed(self):
        r = should_suppress(
            {"topic": "gambling tips"},
            {"composite_score": 0.5, "saturation_risk": 0.2},
            [{"pattern": "gambling", "reason": "off-brand"}],
        )
        assert r is not None

    def test_passes(self):
        r = should_suppress({"topic": "tech review"}, {"composite_score": 0.6, "saturation_risk": 0.3}, [])
        assert r is None


class TestBlockers:
    def test_blocked_source(self):
        b = detect_blockers({"truth_label": "blocked_by_credentials"}, {"has_accounts": True})
        assert any(x["blocker_type"] == "source_blocked" for x in b)

    def test_no_accounts(self):
        b = detect_blockers({"truth_label": "internal_proxy"}, {"has_accounts": False})
        assert any(x["blocker_type"] == "no_accounts" for x in b)

    def test_clean(self):
        assert detect_blockers({"truth_label": "live_source"}, {"has_accounts": True}) == []


class TestTypes:
    def test_7_types(self):
        assert len(OPPORTUNITY_TYPES) == 7
