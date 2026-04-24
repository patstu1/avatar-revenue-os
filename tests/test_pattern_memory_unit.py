"""Unit tests for pattern memory engine — pure functions, no DB."""
import pytest

from packages.scoring.pattern_memory_engine import (
    LOSE_THRESHOLD,
    PATTERN_TYPES,
    WIN_THRESHOLD,
    cluster_patterns,
    compute_pattern_allocation_weights,
    detect_decay,
    extract_patterns_from_content,
    ingest_experiment_outcome,
    recommend_reuse,
    score_pattern,
    suggest_experiments_from_patterns,
)

# ── fixtures ────────────────────────────────────────────────────────────

def _ci(cid, platform="tiktok", title="Don't buy this until you see the results", form="avatar_short_form", monetization="affiliate"):
    return {"id": cid, "platform": platform, "content_form": form, "content_type": form, "title": title, "tags": {}, "monetization_method": monetization}


def _perf(imp=10000, clicks=500, eng=0.08, rev=45.0, cvr=0.05, profit=30.0):
    return {"impressions": imp, "clicks": clicks, "engagement_rate": eng, "revenue": rev, "conversion_rate": cvr, "profit": profit}


# ── pattern types ───────────────────────────────────────────────────────

def test_pattern_types_minimum():
    assert len(PATTERN_TYPES) >= 7
    for required in ("hook", "creative_structure", "content_form", "offer_angle", "cta", "monetization", "audience_response"):
        assert required in PATTERN_TYPES


# ── extraction ──────────────────────────────────────────────────────────

class TestExtraction:
    def test_extracts_patterns_from_content(self):
        items = [_ci("c1"), _ci("c2", title="Which is better A or B?")]
        perf = {"c1": _perf(), "c2": _perf(imp=20000)}
        patterns = extract_patterns_from_content(items, perf, niche="tech")
        assert len(patterns) > 0
        types = {p["pattern_type"] for p in patterns}
        assert "hook" in types
        assert "content_form" in types

    def test_no_content_gives_no_patterns(self):
        assert extract_patterns_from_content([], {}) == []

    def test_hook_types_inferred(self):
        titles = {
            "dont_buy_until": "Don't buy this until you see the results",
            "things_i_wish": "Things I wish I knew about investing",
            "comparison": "iPhone vs Samsung — which is better?",
            "curiosity": "The secret nobody tells you about fitness",
            "direct_pain": "Frustrated with slow internet?",
        }
        for expected_hook, title in titles.items():
            items = [_ci("x1", title=title)]
            perf = {"x1": _perf()}
            patterns = extract_patterns_from_content(items, perf)
            hooks = [p for p in patterns if p["pattern_type"] == "hook"]
            assert len(hooks) > 0
            assert hooks[0]["pattern_name"] == expected_hook, f"Expected {expected_hook} for '{title}'"


# ── scoring ─────────────────────────────────────────────────────────────

class TestScoring:
    def test_empty_evidence(self):
        r = score_pattern([])
        assert r["win_score"] == 0
        assert r["confidence"] == 0
        assert r["is_winner"] is False
        assert r["is_loser"] is False

    def test_strong_evidence_winner(self):
        evidence = [{"engagement_rate": 0.12, "conversion_rate": 0.08, "profit": 80, "impressions": 15000}] * 5
        r = score_pattern(evidence)
        assert r["win_score"] >= WIN_THRESHOLD
        assert r["is_winner"] is True

    def test_weak_evidence_loser(self):
        evidence = [{"engagement_rate": 0.001, "conversion_rate": 0.001, "profit": 0.5, "impressions": 100}] * 5
        r = score_pattern(evidence)
        assert r["win_score"] < LOSE_THRESHOLD
        assert r["is_loser"] is True

    def test_small_sample_penalty(self):
        evidence = [{"engagement_rate": 0.12, "conversion_rate": 0.08, "profit": 80, "impressions": 15000}]
        r = score_pattern(evidence)
        assert r["confidence"] < r["win_score"]

    def test_performance_bands(self):
        hero = score_pattern([{"engagement_rate": 0.15, "conversion_rate": 0.10, "profit": 150, "impressions": 80000}] * 10)
        assert hero["performance_band"] == "hero"
        weak = score_pattern([{"engagement_rate": 0.005, "conversion_rate": 0.002, "profit": 1, "impressions": 200}] * 10)
        assert weak["performance_band"] == "weak"


# ── decay ───────────────────────────────────────────────────────────────

class TestDecay:
    def test_no_history(self):
        r = detect_decay(0, 0.5, 5)
        assert r["decaying"] is False

    def test_score_decline(self):
        r = detect_decay(0.8, 0.5, 10)
        assert r["decaying"] is True
        assert "score_decline" in r["decay_reason"]

    def test_overuse_saturation(self):
        r = detect_decay(0.8, 0.78, 25)
        assert "overuse_saturation" in r["decay_reason"]

    def test_stable_pattern(self):
        r = detect_decay(0.7, 0.68, 10)
        assert r["decaying"] is False


# ── clustering ──────────────────────────────────────────────────────────

class TestClustering:
    def test_clusters_by_type_and_platform(self):
        patterns = [
            {"id": "p1", "pattern_type": "hook", "platform": "tiktok", "win_score": 0.8},
            {"id": "p2", "pattern_type": "hook", "platform": "tiktok", "win_score": 0.7},
            {"id": "p3", "pattern_type": "hook", "platform": "instagram", "win_score": 0.6},
        ]
        clusters = cluster_patterns(patterns)
        assert len(clusters) >= 2
        tiktok_clusters = [c for c in clusters if c["platform"] == "tiktok"]
        assert len(tiktok_clusters) == 1
        assert tiktok_clusters[0]["pattern_count"] == 2

    def test_empty_patterns(self):
        assert cluster_patterns([]) == []


# ── reuse ───────────────────────────────────────────────────────────────

class TestReuse:
    def test_recommends_cross_platform(self):
        patterns = [
            {"id": "p1", "pattern_type": "hook", "pattern_name": "curiosity", "platform": "tiktok", "content_form": "short_form", "win_score": 0.8, "confidence": 0.7, "is_winner": True},
        ]
        recs = recommend_reuse(patterns, ["tiktok", "instagram", "youtube"])
        assert len(recs) >= 2
        targets = {r["target_platform"] for r in recs}
        assert "tiktok" not in targets
        assert "instagram" in targets

    def test_skips_non_winners(self):
        patterns = [
            {"id": "p1", "pattern_type": "hook", "pattern_name": "weak", "platform": "tiktok", "content_form": "short_form", "win_score": 0.3, "confidence": 0.2, "is_winner": False},
        ]
        recs = recommend_reuse(patterns, ["instagram"])
        assert len(recs) == 0


# ── structured metadata extraction ─────────────────────────────────────

class TestStructuredMetadata:
    def test_cta_extracted_from_metadata(self):
        items = [_ci("c1", title="Some generic title")]
        items[0]["cta_type"] = "urgency"
        patterns = extract_patterns_from_content(items, {"c1": _perf()})
        cta_pats = [p for p in patterns if p["pattern_type"] == "cta"]
        assert len(cta_pats) == 1
        assert cta_pats[0]["pattern_name"] == "urgency"

    def test_offer_angle_from_metadata(self):
        items = [_ci("c1")]
        items[0]["offer_angle"] = "premium"
        patterns = extract_patterns_from_content(items, {"c1": _perf()})
        angle_pats = [p for p in patterns if p["pattern_type"] == "offer_angle"]
        assert len(angle_pats) == 1
        assert angle_pats[0]["pattern_name"] == "premium"

    def test_hook_from_metadata_overrides_inference(self):
        items = [_ci("c1", title="Some generic title")]
        items[0]["hook_type"] = "authority_led"
        patterns = extract_patterns_from_content(items, {"c1": _perf()})
        hooks = [p for p in patterns if p["pattern_type"] == "hook"]
        assert hooks[0]["pattern_name"] == "authority_led"

    def test_creative_structure_from_metadata(self):
        items = [_ci("c1")]
        items[0]["creative_structure"] = "before_after"
        patterns = extract_patterns_from_content(items, {"c1": _perf()})
        structs = [p for p in patterns if p["pattern_type"] == "creative_structure"]
        assert structs[0]["pattern_name"] == "before_after"


# ── audience response ───────────────────────────────────────────────────

class TestAudienceResponse:
    def test_conversion_winner(self):
        items = [_ci("c1")]
        perf = {"c1": _perf(cvr=0.08, profit=50.0)}
        patterns = extract_patterns_from_content(items, perf)
        ar = [p for p in patterns if p["pattern_type"] == "audience_response"]
        assert len(ar) == 1
        assert ar[0]["pattern_name"] == "conversion_winner"

    def test_reach_winner(self):
        items = [_ci("c1")]
        perf = {"c1": _perf(imp=50000, eng=0.02, cvr=0.01, profit=5.0)}
        patterns = extract_patterns_from_content(items, perf)
        ar = [p for p in patterns if p["pattern_type"] == "audience_response"]
        assert any(p["pattern_name"] == "reach_winner" for p in ar)

    def test_objection_heavy_from_comment_data(self):
        items = [_ci("c1")]
        perf = {"c1": _perf(cvr=0.05, profit=20.0)}
        comment_data = {"c1": {"avg_sentiment": 0.3, "purchase_intent_pct": 0.1, "objection_pct": 0.5}}
        patterns = extract_patterns_from_content(items, perf, comment_data=comment_data)
        ar = [p for p in patterns if p["pattern_type"] == "audience_response"]
        assert any(p["pattern_name"] == "objection_heavy_high_conversion" for p in ar)


# ── experiment integration ──────────────────────────────────────────────

class TestExperimentIntegration:
    def test_suggest_experiments_from_gaps(self):
        winners = [{"pattern_type": "hook", "pattern_name": "curiosity", "win_score": 0.8, "usage_count": 10}]
        losers = [{"pattern_type": "content_form", "pattern_name": "carousel", "fail_score": 0.9}]
        existing = ["hook"]
        suggestions = suggest_experiments_from_patterns(winners, losers, existing)
        tested_vars = {s["tested_variable"] for s in suggestions}
        assert "cta" in tested_vars or "offer_angle" in tested_vars or "monetization" in tested_vars

    def test_suggest_underexploited_winner(self):
        winners = [{"pattern_type": "hook", "pattern_name": "authority_led", "win_score": 0.75, "usage_count": 2}]
        suggestions = suggest_experiments_from_patterns(winners, [], [])
        assert any(s["source"] == "underexploited_winner" for s in suggestions)

    def test_ingest_experiment_outcome(self):
        result = ingest_experiment_outcome(
            "hook",
            {"pattern_name": "curiosity", "variant_label": "A"},
            [{"pattern_name": "direct_pain", "variant_label": "B"}],
            {"engagement_rate": 0.12, "conversion_rate": 0.06},
        )
        assert len(result["winners"]) == 1
        assert len(result["losers"]) == 1
        assert result["winners"][0]["source"] == "experiment_winner"


# ── portfolio allocation ────────────────────────────────────────────────

class TestPortfolioAllocation:
    def test_allocation_weights(self):
        clusters = [
            {"cluster_type": "hook", "platform": "tiktok", "cluster_name": "hook winners on tiktok", "avg_win_score": 0.8, "pattern_count": 5},
            {"cluster_type": "cta", "platform": "instagram", "cluster_name": "cta winners on instagram", "avg_win_score": 0.3, "pattern_count": 2},
        ]
        weights = compute_pattern_allocation_weights(clusters, 1000.0)
        assert len(weights) == 2
        assert sum(w["allocation_pct"] for w in weights) == pytest.approx(100.0, abs=0.5)
        assert weights[0]["allocation_pct"] > weights[1]["allocation_pct"]
        assert weights[0]["hero_eligible"] is True
        assert weights[1]["hero_eligible"] is False

    def test_empty_clusters(self):
        assert compute_pattern_allocation_weights([], 1000.0) == []

    def test_hero_tier_assignment(self):
        clusters = [
            {"cluster_type": "hook", "platform": "tiktok", "cluster_name": "strong", "avg_win_score": 0.7, "pattern_count": 3},
        ]
        weights = compute_pattern_allocation_weights(clusters, 500.0)
        assert weights[0]["provider_tier"] == "hero"
        assert weights[0]["allocated_budget"] == pytest.approx(500.0, abs=1.0)
