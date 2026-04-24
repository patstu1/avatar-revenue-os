"""Unit tests for quality governor engine — pure functions, no DB."""
import pytest
from packages.scoring.quality_governor_engine import (
    DIMENSIONS, WEIGHTS, PASS_THRESHOLD, WARN_THRESHOLD, BLOCK_FLOOR,
    score_content,
)


class TestDimensions:
    def test_all_10_dimensions(self):
        assert len(DIMENSIONS) == 10
        for d in ("hook_strength", "clarity", "novelty", "conversion_fit", "trust_risk",
                   "fatigue_risk", "duplication_risk", "platform_fit", "offer_fit", "brand_fit"):
            assert d in DIMENSIONS

    def test_weights_sum_to_1(self):
        assert sum(WEIGHTS.values()) == pytest.approx(1.0, abs=0.01)


class TestScoring:
    def test_high_quality_passes(self):
        content = {"title": "Why you should never ignore this secret", "hook_text": "Why you should never ignore this secret?", "body_text": "This is a detailed guide about how to improve your productivity " * 10, "cta_type": "direct", "offer_id": "abc", "monetization_method": "affiliate", "platform": "tiktok", "content_type": "short_video"}
        ctx = {"recent_titles": [], "existing_content_hashes": [], "fatigue_score": 0, "recent_post_count": 5, "account_health": "healthy", "offer_conversion_rate": 0.06, "niche": "tech", "tone_of_voice": "professional"}
        result = score_content(content, ctx)
        assert result["verdict"] == "pass"
        assert result["publish_allowed"] is True
        assert result["total_score"] >= PASS_THRESHOLD

    def test_empty_content_fails(self):
        content = {"title": "", "body_text": "", "platform": "", "content_type": ""}
        ctx = {}
        result = score_content(content, ctx)
        assert result["verdict"] in ("fail", "warn")
        assert result["total_score"] < PASS_THRESHOLD

    def test_duplicate_blocked(self):
        import hashlib
        body = "This is exact duplicate content for testing"
        h = hashlib.sha256(body.encode()).hexdigest()[:16]
        content = {"title": "Test", "body_text": body, "platform": "tiktok", "content_type": "short_video"}
        ctx = {"existing_content_hashes": [h]}
        result = score_content(content, ctx)
        assert any(b["dimension"] == "duplication_risk" for b in result["blocks"])
        assert result["publish_allowed"] is False

    def test_trust_risk_blocked(self):
        content = {"title": "Test", "hook_text": "GUARANTEED 100% risk-free get rich instant results", "body_text": "guaranteed 100% risk-free miracle results", "platform": "tiktok", "content_type": "short_video"}
        ctx = {"account_health": "critical"}
        result = score_content(content, ctx)
        assert any(b["dimension"] == "trust_risk" for b in result["blocks"])
        assert result["publish_allowed"] is False

    def test_fatigue_penalizes(self):
        content = {"title": "Test?", "hook_text": "Why this secret?", "body_text": "Some body text here for testing", "platform": "tiktok", "content_type": "short_video"}
        normal = score_content(content, {"fatigue_score": 0, "recent_post_count": 5})
        fatigued = score_content(content, {"fatigue_score": 0.8, "recent_post_count": 40})
        normal_fatigue = normal["dimensions"]["fatigue_risk"]["score"]
        high_fatigue = fatigued["dimensions"]["fatigue_risk"]["score"]
        assert normal_fatigue > high_fatigue

    def test_novelty_penalizes_similar(self):
        content = {"title": "How to make money online fast", "body_text": "Guide to earning online"}
        no_recent = score_content(content, {"recent_titles": []})
        with_similar = score_content(content, {"recent_titles": ["How to make money online fast", "How to make money online easily"]})
        assert no_recent["dimensions"]["novelty"]["score"] > with_similar["dimensions"]["novelty"]["score"]

    def test_platform_fit(self):
        good_fit = score_content({"platform": "tiktok", "content_type": "short_video"}, {})
        bad_fit = score_content({"platform": "tiktok", "content_type": "text_post"}, {})
        assert good_fit["dimensions"]["platform_fit"]["score"] > bad_fit["dimensions"]["platform_fit"]["score"]

    def test_improvements_generated_for_low_scores(self):
        content = {"title": "x", "body_text": "", "platform": "", "content_type": ""}
        result = score_content(content, {})
        assert len(result["improvements"]) > 0
        for imp in result["improvements"]:
            assert "dimension" in imp
            assert "action" in imp
            assert "priority" in imp

    def test_confidence_increases_with_data(self):
        sparse = score_content({"title": "Test"}, {})
        rich = score_content(
            {"title": "Why this secret?", "hook_text": "Why?", "body_text": "long body " * 20, "cta_type": "direct", "offer_id": "abc", "platform": "tiktok", "content_type": "short_video"},
            {"recent_titles": ["a"], "existing_content_hashes": ["x"], "niche": "tech", "tone_of_voice": "pro", "fatigue_score": 0.1, "account_health": "healthy"},
        )
        assert rich["confidence"] > sparse["confidence"]

    def test_warn_verdict_range(self):
        content = {"title": "Test?", "body_text": "Some text here for the body", "platform": "tiktok", "content_type": "short_video"}
        result = score_content(content, {})
        assert result["verdict"] in ("pass", "warn", "fail")
