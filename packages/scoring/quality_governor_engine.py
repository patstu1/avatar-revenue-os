"""Quality Governor Engine — 10-dimension scoring, auto-block, improvement recs.

Pure functions. No I/O.
"""

from __future__ import annotations

import hashlib
from typing import Any

DIMENSIONS = [
    "hook_strength",
    "clarity",
    "novelty",
    "conversion_fit",
    "trust_risk",
    "fatigue_risk",
    "duplication_risk",
    "platform_fit",
    "offer_fit",
    "brand_fit",
]

WEIGHTS = {
    "hook_strength": 0.15,
    "clarity": 0.10,
    "novelty": 0.10,
    "conversion_fit": 0.15,
    "trust_risk": 0.10,
    "fatigue_risk": 0.10,
    "duplication_risk": 0.10,
    "platform_fit": 0.08,
    "offer_fit": 0.07,
    "brand_fit": 0.05,
}

PASS_THRESHOLD = 0.60
WARN_THRESHOLD = 0.40
BLOCK_DIMENSIONS = {"trust_risk", "duplication_risk"}
BLOCK_FLOOR = 0.20


def score_content(
    content: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    """Score content across all 10 dimensions. Returns verdict + dimension details."""
    dims = {}
    dims["hook_strength"] = _score_hook(content)
    dims["clarity"] = _score_clarity(content)
    dims["novelty"] = _score_novelty(content, context)
    dims["conversion_fit"] = _score_conversion_fit(content, context)
    dims["trust_risk"] = _score_trust_risk(content, context)
    dims["fatigue_risk"] = _score_fatigue_risk(content, context)
    dims["duplication_risk"] = _score_duplication_risk(content, context)
    dims["platform_fit"] = _score_platform_fit(content, context)
    dims["offer_fit"] = _score_offer_fit(content, context)
    dims["brand_fit"] = _score_brand_fit(content, context)

    total = sum(dims[d]["score"] * WEIGHTS[d] for d in DIMENSIONS)
    total = round(total, 3)

    blocks = []
    reasons = []
    for d in DIMENSIONS:
        s = dims[d]["score"]
        if d in BLOCK_DIMENSIONS and s < BLOCK_FLOOR:
            blocks.append({"dimension": d, "score": s, "reason": dims[d]["explanation"]})
        if s < WARN_THRESHOLD:
            reasons.append(f"{d}: {dims[d]['explanation']}")

    if blocks:
        verdict = "fail"
        publish_allowed = False
    elif total >= PASS_THRESHOLD:
        verdict = "pass"
        publish_allowed = True
    elif total >= WARN_THRESHOLD:
        verdict = "warn"
        publish_allowed = True
    else:
        verdict = "fail"
        publish_allowed = False

    improvements = _generate_improvements(dims)
    confidence = min(1.0, 0.5 + len([d for d in dims.values() if d.get("data_present")]) * 0.05)

    return {
        "total_score": total,
        "verdict": verdict,
        "publish_allowed": publish_allowed,
        "confidence": round(confidence, 3),
        "reasons": reasons,
        "blocks": blocks,
        "dimensions": dims,
        "improvements": improvements,
    }


def _score_hook(content: dict) -> dict:
    hook = content.get("hook_text") or content.get("title", "")
    length = len(hook)
    has_question = "?" in hook
    has_power_word = any(
        w in hook.lower() for w in ("secret", "never", "stop", "don't", "best", "worst", "free", "proven", "how", "why")
    )

    score = 0.3
    if length > 10:
        score += 0.2
    if length > 30:
        score += 0.1
    if has_question:
        score += 0.15
    if has_power_word:
        score += 0.25
    return {
        "score": round(min(1.0, score), 3),
        "explanation": f"Hook length {length}, question={has_question}, power_words={has_power_word}",
        "data_present": bool(hook),
    }


def _score_clarity(content: dict) -> dict:
    body = content.get("body_text") or content.get("description", "")
    words = len(body.split())
    score = 0.5
    if words > 20:
        score += 0.2
    if words > 100:
        score += 0.15
    if words < 5:
        score = 0.15
    return {"score": round(min(1.0, score), 3), "explanation": f"{words} words in body", "data_present": words > 0}


def _score_novelty(content: dict, ctx: dict) -> dict:
    recent_titles = ctx.get("recent_titles", [])
    title = (content.get("title") or "").lower()
    similar = sum(1 for t in recent_titles if _jaccard(title, t.lower()) > 0.5)
    score = max(0.1, 1.0 - similar * 0.25)
    return {
        "score": round(score, 3),
        "explanation": f"{similar} similar recent titles found",
        "data_present": bool(recent_titles),
    }


def _score_conversion_fit(content: dict, ctx: dict) -> dict:
    has_cta = bool(content.get("cta_text") or content.get("cta_type"))
    has_offer = bool(content.get("offer_id") or content.get("monetization_method"))
    score = 0.3
    if has_cta:
        score += 0.35
    if has_offer:
        score += 0.35
    return {
        "score": round(min(1.0, score), 3),
        "explanation": f"CTA={has_cta}, offer={has_offer}",
        "data_present": has_cta or has_offer,
    }


def _score_trust_risk(content: dict, ctx: dict) -> dict:
    text = ((content.get("body_text") or "") + " " + (content.get("hook_text") or "")).lower()
    risk_words = sum(
        1 for w in ("guaranteed", "100%", "risk-free", "get rich", "no risk", "instant results", "miracle") if w in text
    )
    account_health = ctx.get("account_health", "healthy")
    health_penalty = 0.3 if account_health in ("critical", "warning") else 0
    score = max(0.0, 1.0 - risk_words * 0.25 - health_penalty)
    return {
        "score": round(score, 3),
        "explanation": f"{risk_words} trust-risk phrases, health={account_health}",
        "data_present": True,
    }


def _score_fatigue_risk(content: dict, ctx: dict) -> dict:
    fatigue = float(ctx.get("fatigue_score", 0) or 0)
    recent_count = int(ctx.get("recent_post_count", 0) or 0)
    score = max(0.1, 1.0 - fatigue - (recent_count / 50))
    return {
        "score": round(min(1.0, score), 3),
        "explanation": f"fatigue={fatigue:.2f}, recent_posts={recent_count}",
        "data_present": True,
    }


def _score_duplication_risk(content: dict, ctx: dict) -> dict:
    existing_hashes = ctx.get("existing_content_hashes", [])
    body = content.get("body_text") or content.get("description") or ""
    if not body:
        return {"score": 0.5, "explanation": "No body text to check", "data_present": False}
    content_hash = hashlib.sha256(body.encode()).hexdigest()[:16]
    is_duplicate = content_hash in existing_hashes
    score = 0.0 if is_duplicate else 1.0
    return {
        "score": score,
        "explanation": "Exact duplicate detected" if is_duplicate else "No duplication",
        "data_present": True,
    }


def _score_platform_fit(content: dict, ctx: dict) -> dict:
    platform = content.get("platform", "")
    content_type = content.get("content_type", "")
    fit_map = {
        "tiktok": {"short_video": 1.0, "text_post": 0.3, "long_video": 0.4, "carousel": 0.5},
        "instagram": {"short_video": 0.9, "carousel": 1.0, "story": 0.9, "static_image": 0.8, "text_post": 0.4},
        "youtube": {"long_video": 1.0, "short_video": 0.8, "text_post": 0.2},
        "twitter": {"text_post": 1.0, "short_video": 0.7, "static_image": 0.6},
        "linkedin": {"text_post": 1.0, "long_video": 0.7, "carousel": 0.8},
    }
    score = fit_map.get(platform, {}).get(content_type, 0.5)
    return {
        "score": round(score, 3),
        "explanation": f"{content_type} on {platform}",
        "data_present": bool(platform and content_type),
    }


def _score_offer_fit(content: dict, ctx: dict) -> dict:
    has_offer = bool(content.get("offer_id"))
    offer_cvr = float(ctx.get("offer_conversion_rate", 0) or 0)
    if not has_offer:
        return {"score": 0.5, "explanation": "No offer attached", "data_present": False}
    score = min(1.0, 0.4 + offer_cvr * 10)
    return {"score": round(score, 3), "explanation": f"Offer CVR={offer_cvr:.2%}", "data_present": True}


def _score_brand_fit(content: dict, ctx: dict) -> dict:
    niche = ctx.get("niche", "")
    tone = ctx.get("tone_of_voice", "")
    score = 0.5
    if niche:
        score += 0.25
    if tone:
        score += 0.25
    return {
        "score": round(min(1.0, score), 3),
        "explanation": f"niche={'set' if niche else 'missing'}, tone={'set' if tone else 'missing'}",
        "data_present": bool(niche),
    }


def _generate_improvements(dims: dict[str, dict]) -> list[dict[str, Any]]:
    improvements = []
    for d, info in dims.items():
        if info["score"] < WARN_THRESHOLD:
            improvements.append(
                {
                    "dimension": d,
                    "action": _improvement_action(d, info),
                    "priority": "critical" if info["score"] < BLOCK_FLOOR else "high",
                }
            )
        elif info["score"] < PASS_THRESHOLD:
            improvements.append(
                {
                    "dimension": d,
                    "action": _improvement_action(d, info),
                    "priority": "medium",
                }
            )
    return sorted(improvements, key=lambda x: {"critical": 0, "high": 1, "medium": 2}.get(x["priority"], 3))


def _improvement_action(dim: str, info: dict) -> str:
    actions = {
        "hook_strength": "Rewrite hook with a power word, question, or specific claim",
        "clarity": "Expand body text with clearer structure and more detail",
        "novelty": "Differentiate from recent content — change angle, format, or hook",
        "conversion_fit": "Add a clear CTA and attach an offer",
        "trust_risk": "Remove trust-risk language (guaranteed, risk-free, etc.)",
        "fatigue_risk": "Reduce posting frequency or change content format",
        "duplication_risk": "Rewrite — this is too similar to existing content",
        "platform_fit": "Switch to a content type that fits the target platform better",
        "offer_fit": "Attach a higher-converting offer or improve offer landing page",
        "brand_fit": "Align content with brand niche and tone of voice",
    }
    return actions.get(dim, "Review and improve this dimension")


def _jaccard(a: str, b: str) -> float:
    sa = set(a.split())
    sb = set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)
