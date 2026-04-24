"""Unit tests for brand governance engine."""
from packages.scoring.brand_governance_engine import (
    check_audience_fit,
    check_multi_brand_isolation,
    evaluate_voice_rules,
    score_editorial_compliance,
)


class TestVoiceRules:
    def test_banned_phrase_detected(self):
        rules = [{"rule_type": "banned_phrase", "rule_key": "guaranteed results", "severity": "hard"}]
        violations = evaluate_voice_rules("Get guaranteed results today!", rules)
        assert len(violations) == 1
        assert violations[0]["violation_type"] == "banned_phrase"

    def test_missing_required_phrase(self):
        rules = [{"rule_type": "required_phrase", "rule_key": "affiliate disclosure", "severity": "soft"}]
        violations = evaluate_voice_rules("Check out this product!", rules)
        assert len(violations) == 1
        assert violations[0]["violation_type"] == "missing_required_phrase"

    def test_required_phrase_present(self):
        rules = [{"rule_type": "required_phrase", "rule_key": "affiliate disclosure", "severity": "soft"}]
        violations = evaluate_voice_rules("This contains an affiliate disclosure notice", rules)
        assert len(violations) == 0

    def test_banned_claim(self):
        rules = [{"rule_type": "claim", "rule_key": "claims", "rule_value": {"banned_claims": ["100% risk-free"]}, "severity": "hard"}]
        violations = evaluate_voice_rules("This is 100% risk-free!", rules)
        assert any(v["violation_type"] == "banned_claim" for v in violations)

    def test_missing_disclosure(self):
        rules = [{"rule_type": "disclosure", "rule_key": "ftc", "rule_value": {"required_text": "paid partnership"}, "severity": "hard"}]
        violations = evaluate_voice_rules("Buy this product now!", rules)
        assert any(v["violation_type"] == "missing_disclosure" for v in violations)

    def test_no_rules_no_violations(self):
        assert evaluate_voice_rules("Any text", []) == []


class TestEditorial:
    def test_good_editorial(self):
        content = {"body_text": "proof results data click link sign up", "hook_text": "professional", "proof_blocks": [1], "cta_blocks": [1]}
        profile = {"tone_profile": "professional, data-driven"}
        result = score_editorial_compliance(content, [], profile)
        assert result["verdict"] in ("pass", "warn")

    def test_empty_content(self):
        result = score_editorial_compliance({}, [], {})
        assert result["verdict"] in ("fail", "warn")


class TestAudienceFit:
    def test_good_fit(self):
        content = {"content_form": "short_video"}
        audience = {"preferred_content_forms": ["short_video", "carousel"], "trust_level": "high", "monetization_sensitivity": "low"}
        result = check_audience_fit(content, audience)
        assert result["verdict"] == "pass"

    def test_wrong_form(self):
        content = {"content_form": "long_video"}
        audience = {"preferred_content_forms": ["short_video"], "trust_level": "medium", "monetization_sensitivity": "medium"}
        result = check_audience_fit(content, audience)
        assert len(result["issues"]) >= 1

    def test_aggressive_cta_high_sensitivity(self):
        content = {"cta_type": "urgency", "monetization_method": "affiliate"}
        audience = {"monetization_sensitivity": "high", "trust_level": "low"}
        result = check_audience_fit(content, audience)
        assert len(result["issues"]) >= 1


class TestMultiBrandIsolation:
    def test_same_brand(self):
        r = check_multi_brand_isolation("brand_a", "brand_a")
        assert r["isolated"] is True

    def test_different_brand(self):
        r = check_multi_brand_isolation("brand_a", "brand_b")
        assert r["isolated"] is False
        assert r["violation"] is not None
