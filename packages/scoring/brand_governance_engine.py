"""Brand Governance Engine — rule eval, off-brand detection, editorial scoring. Pure functions."""
from __future__ import annotations

from typing import Any

RULE_TYPES = ["banned_phrase", "required_phrase", "tone", "claim", "cta", "disclosure", "trust_risk", "style"]
EDITORIAL_CATEGORIES = ["tone_compliance", "disclosure_compliance", "claim_accuracy", "style_standard", "proof_completeness", "cta_completeness"]


def evaluate_voice_rules(text: str, rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Evaluate content text against brand voice rules. Returns violations."""
    violations = []
    lower = text.lower()
    for rule in rules:
        rt = rule.get("rule_type", "")
        rk = rule.get("rule_key", "").lower()
        rv = rule.get("rule_value") or {}

        if rt == "banned_phrase" and rk in lower:
            violations.append({"violation_type": "banned_phrase", "severity": rule.get("severity", "hard"), "detail": f"Banned phrase '{rk}' found in content", "rule_id": rule.get("id")})

        elif rt == "required_phrase" and rk not in lower:
            violations.append({"violation_type": "missing_required_phrase", "severity": rule.get("severity", "soft"), "detail": f"Required phrase '{rk}' missing", "rule_id": rule.get("id")})

        elif rt == "claim":
            banned_claims = rv.get("banned_claims", [])
            for bc in banned_claims:
                if bc.lower() in lower:
                    violations.append({"violation_type": "banned_claim", "severity": "hard", "detail": f"Banned claim '{bc}' detected", "rule_id": rule.get("id")})

        elif rt == "disclosure":
            req = rv.get("required_text", "")
            if req and req.lower() not in lower:
                violations.append({"violation_type": "missing_disclosure", "severity": "hard", "detail": f"Required disclosure '{req[:50]}...' missing", "rule_id": rule.get("id")})

    return violations


def score_editorial_compliance(content: dict[str, Any], rules: list[dict[str, Any]], governance_profile: dict[str, Any]) -> dict[str, Any]:
    """Score content against editorial standards."""
    scores: dict[str, float] = {}
    text = (content.get("body_text", "") + " " + content.get("hook_text", "")).lower()

    tone = governance_profile.get("tone_profile", "")
    if tone:
        tone_words = [w.strip().lower() for w in tone.split(",") if w.strip()]
        matches = sum(1 for tw in tone_words if tw in text)
        scores["tone_compliance"] = min(1.0, matches / max(1, len(tone_words)))
    else:
        scores["tone_compliance"] = 0.5

    disclosure_rules = [r for r in rules if r.get("rule_category") == "disclosure"]
    if disclosure_rules:
        passed = sum(1 for r in disclosure_rules if _check_editorial(text, r))
        scores["disclosure_compliance"] = passed / max(1, len(disclosure_rules))
    else:
        scores["disclosure_compliance"] = 0.5

    claim_rules = [r for r in rules if r.get("rule_category") == "claim"]
    if claim_rules:
        clean = sum(1 for r in claim_rules if _check_editorial(text, r))
        scores["claim_accuracy"] = clean / max(1, len(claim_rules))
    else:
        scores["claim_accuracy"] = 0.5

    has_proof = bool(content.get("proof_blocks")) or "proof" in text or "result" in text
    has_cta = bool(content.get("cta_blocks")) or "click" in text or "link" in text or "sign up" in text
    scores["proof_completeness"] = 1.0 if has_proof else 0.3
    scores["cta_completeness"] = 1.0 if has_cta else 0.3
    scores["style_standard"] = 0.5

    total = sum(scores.values()) / max(1, len(scores))
    verdict = "pass" if total >= 0.6 else "warn" if total >= 0.4 else "fail"

    return {"total_score": round(total, 3), "dimension_scores": scores, "verdict": verdict}


def _check_editorial(text: str, rule: dict) -> bool:
    ct = rule.get("check_type", "")
    cv = rule.get("check_value") or {}
    if ct == "contains_required":
        return cv.get("text", "").lower() in text
    if ct == "excludes_banned":
        return cv.get("text", "").lower() not in text
    return True


def check_audience_fit(content: dict[str, Any], audience: dict[str, Any]) -> dict[str, Any]:
    """Check content against audience profile."""
    trust = audience.get("trust_level", "medium")
    sensitivity = audience.get("monetization_sensitivity", "medium")
    preferred_forms = audience.get("preferred_content_forms") or []

    issues = []
    content_form = content.get("content_form", "")
    if preferred_forms and content_form and content_form not in preferred_forms:
        issues.append(f"Content form '{content_form}' not in audience preferred forms")

    if trust == "low" and content.get("monetization_method"):
        issues.append("Low-trust audience — monetization may reduce engagement")

    if sensitivity == "high" and content.get("cta_type") in ("direct", "urgency"):
        issues.append("High-sensitivity audience — aggressive CTA may backfire")

    fit_score = max(0.0, 1.0 - len(issues) * 0.25)
    return {"fit_score": round(fit_score, 3), "issues": issues, "verdict": "pass" if fit_score >= 0.6 else "warn"}


def check_multi_brand_isolation(brand_id: str, content_brand_id: str) -> dict[str, Any]:
    """Verify content is not crossing brand boundaries."""
    if brand_id != content_brand_id:
        return {"isolated": False, "violation": "Content brand_id does not match governance brand_id"}
    return {"isolated": True, "violation": None}
