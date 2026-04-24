"""Unit tests for failure-family suppression engine — pure functions, no DB."""
from datetime import datetime, timedelta, timezone

from packages.scoring.failure_family_engine import (
    FAMILY_TYPES,
    build_suppression_rules,
    check_suppression_decay,
    cluster_failures,
    detect_repeat_failures,
    get_active_suppressions,
    is_suppressed,
)


class TestFamilyTypes:
    def test_all_9_types(self):
        assert len(FAMILY_TYPES) == 9
        for t in ("hook_type", "content_form", "offer_angle", "cta_style", "platform_mismatch",
                   "publish_timing", "avatar_mode", "creative_structure", "monetization_path"):
            assert t in FAMILY_TYPES


class TestClustering:
    def test_groups_by_attribute(self):
        items = [
            {"hook_type": "curiosity", "fail_score": 0.8},
            {"hook_type": "curiosity", "fail_score": 0.7},
            {"hook_type": "direct_pain", "fail_score": 0.6},
            {"content_form": "carousel", "fail_score": 0.9},
        ]
        families = cluster_failures(items)
        assert len(families) >= 3
        curiosity = [f for f in families if f["family_key"] == "curiosity"]
        assert curiosity[0]["failure_count"] == 2

    def test_empty_items(self):
        assert cluster_failures([]) == []

    def test_sorted_by_count(self):
        items = [{"hook_type": "a", "fail_score": 0.5}] * 5 + [{"hook_type": "b", "fail_score": 0.5}] * 2
        families = cluster_failures(items)
        assert families[0]["failure_count"] >= families[-1]["failure_count"]


class TestRepeatDetection:
    def test_detects_above_threshold(self):
        families = [
            {"family_type": "hook_type", "family_key": "curiosity", "failure_count": 5, "avg_fail_score": 0.8},
            {"family_type": "hook_type", "family_key": "pain", "failure_count": 1, "avg_fail_score": 0.5},
        ]
        repeats = detect_repeat_failures(families)
        assert len(repeats) == 1
        assert repeats[0]["family_key"] == "curiosity"
        assert repeats[0]["should_suppress"] is True

    def test_persistent_mode_at_6(self):
        families = [{"family_type": "content_form", "family_key": "carousel", "failure_count": 7, "avg_fail_score": 0.9}]
        repeats = detect_repeat_failures(families)
        assert repeats[0]["mode"] == "persistent"

    def test_temporary_mode_at_3(self):
        families = [{"family_type": "content_form", "family_key": "text", "failure_count": 4, "avg_fail_score": 0.6}]
        repeats = detect_repeat_failures(families)
        assert repeats[0]["mode"] == "temporary"


class TestSuppressionRules:
    def test_generates_rules(self):
        repeats = [{"family_type": "hook_type", "family_key": "curiosity", "failure_count": 5, "avg_fail_score": 0.8, "should_suppress": True, "mode": "temporary"}]
        rules = build_suppression_rules(repeats)
        assert len(rules) == 1
        assert rules[0]["suppression_mode"] == "temporary"
        assert rules[0]["retest_after_days"] == 30
        assert "recommended_alternative" in rules[0]

    def test_persistent_gets_90_days(self):
        repeats = [{"family_type": "content_form", "family_key": "x", "failure_count": 8, "avg_fail_score": 0.9, "should_suppress": True, "mode": "persistent"}]
        rules = build_suppression_rules(repeats)
        assert rules[0]["retest_after_days"] == 90

    def test_no_rules_without_suppress(self):
        repeats = [{"family_type": "hook_type", "family_key": "x", "should_suppress": False}]
        assert build_suppression_rules(repeats) == []


class TestDecay:
    def test_expired_detected(self):
        now = datetime.now(timezone.utc)
        rules = [{"family_type": "hook_type", "family_key": "x", "expires_at": now - timedelta(days=1), "is_active": True}]
        expired = check_suppression_decay(rules, now)
        assert len(expired) == 1

    def test_active_not_expired(self):
        now = datetime.now(timezone.utc)
        rules = [{"family_type": "hook_type", "family_key": "x", "expires_at": now + timedelta(days=10), "is_active": True}]
        expired = check_suppression_decay(rules, now)
        assert len(expired) == 0


class TestIsSuppressed:
    def test_suppressed_when_active_rule(self):
        rules = [{"family_type": "hook_type", "family_key": "curiosity", "is_active": True}]
        assert is_suppressed("hook_type", "curiosity", rules) is True

    def test_not_suppressed_when_no_match(self):
        rules = [{"family_type": "hook_type", "family_key": "curiosity", "is_active": True}]
        assert is_suppressed("hook_type", "pain", rules) is False


class TestActiveSuppressions:
    def test_returns_active_only(self):
        rules = [
            {"family_type": "hook_type", "family_key": "curiosity", "suppression_mode": "temporary", "reason": "test", "expires_at": "2026-01-01", "is_active": True},
            {"family_type": "cta_style", "family_key": "soft", "suppression_mode": "persistent", "reason": "test2", "expires_at": "2026-06-01", "is_active": False},
        ]
        active = get_active_suppressions(rules)
        assert len(active) == 1
        assert active[0]["family_key"] == "curiosity"
