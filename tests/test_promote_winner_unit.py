"""Unit tests for promote-winner engine — pure functions, no DB."""
import pytest

from packages.scoring.promote_winner_engine import (
    EXPERIMENT_TYPES,
    assign_variant,
    build_promotion_rules,
    build_suppression_rules,
    check_decay_retest,
    create_experiment,
    detect_winner,
)


class TestCreateExperiment:
    def test_creates_with_two_variants(self):
        result = create_experiment("hook", [{"name": "A"}, {"name": "B"}], hypothesis="Test hooks")
        assert result["status"] == "active"
        assert len(result["variants"]) == 2
        assert result["variants"][0]["is_control"] is True
        assert result["variants"][1]["is_control"] is False

    def test_requires_two_variants(self):
        with pytest.raises(ValueError):
            create_experiment("hook", [{"name": "A"}])

    def test_normalizes_unknown_type(self):
        result = create_experiment("unknown_type", [{"name": "A"}, {"name": "B"}])
        assert result["tested_variable"] == "custom"

    def test_all_experiment_types(self):
        assert len(EXPERIMENT_TYPES) >= 11
        for t in ("hook", "content_form", "cta_type", "offer_angle", "avatar_vs_non_avatar",
                   "faceless_vs_face_forward", "short_vs_long", "monetization_path"):
            assert t in EXPERIMENT_TYPES


class TestAssignment:
    def test_deterministic_for_same_key(self):
        variants = [{"variant_name": "A", "is_active": True}, {"variant_name": "B", "is_active": True}]
        r1 = assign_variant(variants, "content_123")
        r2 = assign_variant(variants, "content_123")
        assert r1["variant_name"] == r2["variant_name"]

    def test_different_keys_can_vary(self):
        variants = [{"variant_name": "A", "is_active": True}, {"variant_name": "B", "is_active": True}]
        results = {assign_variant(variants, f"key_{i}")["variant_name"] for i in range(20)}
        assert len(results) >= 2


class TestDetectWinner:
    def test_insufficient_variants(self):
        r = detect_winner([{"sample_count": 50, "primary_metric_value": 0.1}])
        assert r["status"] == "insufficient_variants"

    def test_insufficient_sample(self):
        r = detect_winner([
            {"sample_count": 5, "primary_metric_value": 0.1},
            {"sample_count": 5, "primary_metric_value": 0.05},
        ], min_sample_size=30)
        assert r["status"] == "insufficient_sample"
        assert "progress_pct" in r

    def test_clear_winner(self):
        r = detect_winner([
            {"id": "v1", "variant_name": "A", "sample_count": 100, "primary_metric_value": 0.15, "variant_config": {}, "is_control": True, "is_active": True},
            {"id": "v2", "variant_name": "B", "sample_count": 100, "primary_metric_value": 0.05, "variant_config": {}, "is_control": False, "is_active": True},
        ], min_sample_size=30, confidence_threshold=0.80)
        assert r["status"] == "winner_found"
        assert r["winner"]["variant_name"] == "A"
        assert len(r["losers"]) == 1
        assert r["confidence"] >= 0.80

    def test_inconclusive(self):
        r = detect_winner([
            {"id": "v1", "variant_name": "A", "sample_count": 30, "primary_metric_value": 0.10, "variant_config": {}, "is_control": True, "is_active": True},
            {"id": "v2", "variant_name": "B", "sample_count": 30, "primary_metric_value": 0.099, "variant_config": {}, "is_control": False, "is_active": True},
        ], min_sample_size=30, confidence_threshold=0.95)
        assert r["status"] in ("inconclusive", "winner_found")


class TestPromotionRules:
    def test_generates_rules(self):
        exp = {"tested_variable": "hook", "platform": "tiktok"}
        winner = {"variant_name": "curiosity", "variant_config": {"hook": "curiosity"}}
        rules = build_promotion_rules(exp, winner, 0.4, 0.92)
        assert len(rules) >= 1
        assert rules[0]["rule_type"] == "default_hook"
        assert rules[0]["weight_boost"] > 0

    def test_brief_injection_for_hook(self):
        exp = {"tested_variable": "hook", "platform": "tiktok"}
        winner = {"variant_name": "curiosity", "variant_config": {}}
        rules = build_promotion_rules(exp, winner, 0.3, 0.90)
        brief_rules = [r for r in rules if r["rule_type"] == "brief_injection"]
        assert len(brief_rules) == 1

    def test_monetization_default(self):
        exp = {"tested_variable": "monetization_path", "platform": None}
        winner = {"variant_name": "affiliate", "variant_config": {}}
        rules = build_promotion_rules(exp, winner, 0.5, 0.95)
        mono_rules = [r for r in rules if r["rule_type"] == "monetization_default"]
        assert len(mono_rules) == 1


class TestSuppression:
    def test_generates_suppression(self):
        exp = {"tested_variable": "cta_type", "platform": "instagram"}
        losers = [{"variant_name": "soft_cta"}, {"variant_name": "link_in_bio"}]
        rules = build_suppression_rules(exp, losers)
        assert len(rules) == 2
        assert all("suppress" in r["rule_type"] for r in rules)


class TestDecayRetest:
    def test_no_decay(self):
        r = check_decay_retest(30, 0.95, 0.40, 0.42)
        assert r["needs_retest"] is False

    def test_performance_drop(self):
        r = check_decay_retest(30, 0.95, 0.10, 0.42)
        assert r["needs_retest"] is True
        assert "performance_dropped" in r["reasons"][0]

    def test_stale_winner(self):
        r = check_decay_retest(120, 0.95, 0.40, 0.42)
        assert r["needs_retest"] is True

    def test_confidence_erosion(self):
        r = check_decay_retest(30, 0.80, 0.40, 0.42)
        assert r["needs_retest"] is True
