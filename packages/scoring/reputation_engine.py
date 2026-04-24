"""Reputation engine — platform risk, spam drift, trust decline, disclosure gaps,
claim accumulation, synthetic patterns, engagement quality, sponsor risk
(pure functions, no I/O, no SQLAlchemy)."""

from __future__ import annotations

from typing import Any

REPUTATION = "reputation_engine"

# ---------------------------------------------------------------------------
# Risk type weights (sum to 1.0)
# ---------------------------------------------------------------------------

_RISK_WEIGHTS: dict[str, float] = {
    "platform_warning_risk": 0.18,
    "spam_pattern_drift": 0.12,
    "audience_trust_decline": 0.16,
    "disclosure_inconsistency": 0.10,
    "claim_risk_accumulation": 0.12,
    "synthetic_pattern_risk": 0.10,
    "engagement_quality_degradation": 0.12,
    "sponsor_risk_drift": 0.10,
}

# ---------------------------------------------------------------------------
# Keyword / signal banks
# ---------------------------------------------------------------------------

_PLATFORM_WARNING_KW: list[str] = [
    "strike",
    "warning",
    "policy",
    "violation",
    "restricted",
    "flagged",
    "demonetized",
    "suspended",
    "shadowban",
    "appeal",
]

_SPAM_DRIFT_KW: list[str] = [
    "giveaway",
    "subscribe",
    "follow for follow",
    "spam",
    "bot",
    "fake",
    "engagement pod",
    "loop",
    "comment swap",
    "mass follow",
]

_TRUST_DECLINE_KW: list[str] = [
    "unsubscribe",
    "unfollow",
    "disappointed",
    "scam",
    "misleading",
    "clickbait",
    "waste",
    "refund",
    "lied",
    "not worth",
]

_DISCLOSURE_KW: list[str] = [
    "ad",
    "sponsored",
    "paid",
    "affiliate",
    "partner",
    "collab",
    "#ad",
    "#sponsored",
    "disclosure",
]

_CLAIM_RISK_KW: list[str] = [
    "guarantee",
    "proven",
    "scientifically",
    "cure",
    "results guaranteed",
    "100%",
    "risk free",
    "no risk",
    "miracle",
    "secret",
]

_SYNTHETIC_KW: list[str] = [
    "ai generated",
    "deepfake",
    "synthetic",
    "fake voice",
    "cloned",
    "auto generated",
    "bot content",
    "mass produced",
]

_ENG_QUALITY_KW: list[str] = [
    "nice",
    "great",
    "cool",
    "fire",
    "emoji only",
    "first",
    "generic",
    "copy paste",
    "irrelevant",
]

_SPONSOR_RISK_KW: list[str] = [
    "controversy",
    "recall",
    "lawsuit",
    "unethical",
    "fraud",
    "complaint",
    "reputation damage",
    "brand safety",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _kw_score(texts: list[str], keywords: list[str]) -> float:
    """Count keyword hits across all texts; 1/3 of keywords → ~1.0."""
    combined = " ".join(t.lower() for t in texts)
    found = sum(1 for kw in keywords if kw in combined)
    return min(1.0, found / max(1, len(keywords)) * 3.0)


def _signal_score(signals: list[dict], key: str, threshold: float) -> float:
    """Fraction of signals where signal[key] exceeds threshold."""
    if not signals:
        return 0.0
    hits = sum(1 for s in signals if float(s.get(key, 0)) > threshold)
    return _clamp(hits / len(signals))


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------


def assess_reputation(
    brand_data: dict,
    account_signals: list[dict],
    content_signals: list[dict],
) -> dict[str, Any]:
    """Assess brand reputation risk across 8 dimensions.

    Parameters
    ----------
    brand_data:
        Dict with optional keys: niche, platform_warnings (int), disclosure_policy (bool),
        sponsor_names (list[str]), audience_size (int), avg_engagement_rate (float).
    account_signals:
        List of dicts, each representing account-level data: {platform, follower_delta,
        unfollow_rate, strike_count, engagement_rate, bot_follower_pct, comment_texts (list)}.
    content_signals:
        List of dicts, each representing content-level data: {title, description,
        has_disclosure (bool), claims (list[str]), engagement_rate, comment_sentiment,
        generic_comment_pct, sponsor_name}.

    Returns
    -------
    dict with reputation_risk_score, primary_risks, recommended_mitigation,
    expected_impact_if_unresolved, confidence, explanation, REPUTATION marker.
    """
    # Collect all textual material for keyword scans
    account_texts: list[str] = []
    for sig in account_signals:
        account_texts.extend(sig.get("comment_texts", []))

    content_texts: list[str] = [
        " ".join(filter(None, [s.get("title", ""), s.get("description", "")])) for s in content_signals
    ]
    claim_texts: list[str] = []
    for s in content_signals:
        claim_texts.extend(s.get("claims", []))

    all_texts = account_texts + content_texts + claim_texts

    warnings_count = int(brand_data.get("platform_warnings", 0))
    has_policy = bool(brand_data.get("disclosure_policy", False))
    int(brand_data.get("audience_size", 0))
    avg_engagement = float(brand_data.get("avg_engagement_rate", 0.0))

    # ------------------------------------------------------------------ score each risk
    risk_scores: dict[str, float] = {}

    # 1. platform_warning_risk
    kw_signal = _kw_score(all_texts, _PLATFORM_WARNING_KW)
    warning_signal = _clamp(warnings_count / 3.0)
    strike_avg = 0.0
    if account_signals:
        strike_avg = sum(float(a.get("strike_count", 0)) for a in account_signals) / len(account_signals)
    risk_scores["platform_warning_risk"] = round(
        _clamp(kw_signal * 0.40 + warning_signal * 0.40 + _clamp(strike_avg / 2.0) * 0.20), 3
    )

    # 2. spam_pattern_drift
    spam_kw = _kw_score(all_texts, _SPAM_DRIFT_KW)
    bot_pct_avg = 0.0
    if account_signals:
        bot_pct_avg = sum(float(a.get("bot_follower_pct", 0)) for a in account_signals) / len(account_signals)
    risk_scores["spam_pattern_drift"] = round(_clamp(spam_kw * 0.50 + _clamp(bot_pct_avg) * 0.50), 3)

    # 3. audience_trust_decline
    trust_kw = _kw_score(all_texts, _TRUST_DECLINE_KW)
    unfollow_avg = 0.0
    if account_signals:
        unfollow_avg = sum(float(a.get("unfollow_rate", 0)) for a in account_signals) / len(account_signals)
    risk_scores["audience_trust_decline"] = round(
        _clamp(trust_kw * 0.45 + _clamp(unfollow_avg * 10.0) * 0.35 + (0.20 if avg_engagement < 0.02 else 0.0)), 3
    )

    # 4. disclosure_inconsistency
    total_sponsored = sum(1 for s in content_signals if s.get("sponsor_name"))
    disclosed = sum(1 for s in content_signals if s.get("has_disclosure"))
    if total_sponsored > 0:
        disclosure_gap = _clamp(1.0 - disclosed / total_sponsored)
    else:
        disclosure_gap = 0.0
    policy_penalty = 0.0 if has_policy else 0.20
    disc_kw = _kw_score(content_texts, _DISCLOSURE_KW)
    risk_scores["disclosure_inconsistency"] = round(
        _clamp(disclosure_gap * 0.50 + policy_penalty + (1.0 - disc_kw) * 0.10), 3
    )

    # 5. claim_risk_accumulation
    claim_kw = _kw_score(claim_texts + content_texts, _CLAIM_RISK_KW)
    claim_density = _clamp(len(claim_texts) / max(1, len(content_signals)) / 3.0)
    risk_scores["claim_risk_accumulation"] = round(_clamp(claim_kw * 0.60 + claim_density * 0.40), 3)

    # 6. synthetic_pattern_risk
    synth_kw = _kw_score(all_texts, _SYNTHETIC_KW)
    risk_scores["synthetic_pattern_risk"] = round(_clamp(synth_kw), 3)

    # 7. engagement_quality_degradation
    generic_kw = _kw_score(account_texts, _ENG_QUALITY_KW)
    generic_pct_avg = 0.0
    if content_signals:
        generic_pct_avg = sum(float(s.get("generic_comment_pct", 0)) for s in content_signals) / len(content_signals)
    risk_scores["engagement_quality_degradation"] = round(
        _clamp(generic_kw * 0.40 + _clamp(generic_pct_avg) * 0.40 + (0.20 if avg_engagement < 0.015 else 0.0)), 3
    )

    # 8. sponsor_risk_drift
    sponsor_kw = _kw_score(all_texts, _SPONSOR_RISK_KW)
    sponsor_names = brand_data.get("sponsor_names", [])
    sponsor_diversity_penalty = (
        _clamp(1.0 - len(set(sponsor_names)) / max(1, len(sponsor_names))) if sponsor_names else 0.0
    )
    risk_scores["sponsor_risk_drift"] = round(_clamp(sponsor_kw * 0.60 + sponsor_diversity_penalty * 0.40), 3)

    # ------------------------------------------------------------------ aggregate
    reputation_risk_score = round(sum(risk_scores[k] * _RISK_WEIGHTS[k] for k in _RISK_WEIGHTS), 3)

    # ------------------------------------------------------------------ primary risks (top 3)
    sorted_risks = sorted(risk_scores.items(), key=lambda kv: kv[1], reverse=True)
    primary_risks: list[dict[str, Any]] = [
        {"risk_type": rt, "score": round(sc, 3), "detail": _risk_detail(rt, sc)}
        for rt, sc in sorted_risks[:3]
        if sc > 0.05
    ]

    # ------------------------------------------------------------------ mitigation
    recommended_mitigation = _build_mitigation(risk_scores)

    # ------------------------------------------------------------------ expected impact
    expected_impact_if_unresolved = round(
        _clamp(reputation_risk_score * 0.35 + max(rs for rs in risk_scores.values()) * 0.15), 3
    )

    # ------------------------------------------------------------------ confidence
    data_richness = _clamp((len(account_signals) + len(content_signals)) / 20.0)
    confidence = round(_clamp(0.35 + data_richness * 0.35 + (1.0 - reputation_risk_score) * 0.15 + 0.15), 3)

    # ------------------------------------------------------------------ explanation
    top_str = ", ".join(f"{r['risk_type']} {r['score']:.2f}" for r in primary_risks[:3])
    explanation = (
        f"Reputation risk score {reputation_risk_score:.2f} across "
        f"{len(account_signals)} accounts and {len(content_signals)} content items. "
        f"Top risks: {top_str or 'none above threshold'}. "
        f"Expected impact if unresolved: {expected_impact_if_unresolved:.2f}. "
        f"Confidence {confidence:.2f}."
    )

    return {
        "reputation_risk_score": reputation_risk_score,
        "primary_risks": primary_risks,
        "recommended_mitigation": recommended_mitigation,
        "expected_impact_if_unresolved": expected_impact_if_unresolved,
        "confidence": confidence,
        "explanation": explanation,
        REPUTATION: True,
    }


# ---------------------------------------------------------------------------
# Mitigation builder
# ---------------------------------------------------------------------------

_MITIGATION_MAP: dict[str, list[str]] = {
    "platform_warning_risk": [
        "Audit all flagged content and remove policy-violating material within 48 h",
        "Review platform TOS changes monthly; adjust content guidelines accordingly",
    ],
    "spam_pattern_drift": [
        "Cease engagement-pod and follow-for-follow tactics immediately",
        "Run a bot follower audit and purge synthetic followers",
    ],
    "audience_trust_decline": [
        "Survey top 100 engaged followers to surface trust-eroding friction points",
        "Publish a transparent brand update addressing any recent controversies",
    ],
    "disclosure_inconsistency": [
        "Implement a mandatory disclosure checklist for every sponsored content item",
        "Add FTC/ASA-compliant disclosure language to all active sponsor posts retroactively",
    ],
    "claim_risk_accumulation": [
        "Audit all marketing claims; remove or qualify any lacking third-party evidence",
        "Add disclaimers to high-claim content and reduce guarantee language",
    ],
    "synthetic_pattern_risk": [
        "Clearly label any AI-generated or avatar-driven content per platform policy",
        "Establish a synthetic-content disclosure standard for the brand",
    ],
    "engagement_quality_degradation": [
        "Shift CTA strategy to encourage substantive comments over generic reactions",
        "Pin and reply to high-quality comments to raise the baseline of discourse",
    ],
    "sponsor_risk_drift": [
        "Diversify sponsor portfolio — reduce single-sponsor revenue dependency below 30 %",
        "Pre-screen new sponsors against a brand-safety checklist before signing",
    ],
}


def _build_mitigation(risk_scores: dict[str, float]) -> list[dict[str, Any]]:
    """Return prioritised mitigation actions for risks scoring above 0.20."""
    actions: list[dict[str, Any]] = []
    for risk_type, score in sorted(risk_scores.items(), key=lambda kv: kv[1], reverse=True):
        if score < 0.20:
            continue
        for action_text in _MITIGATION_MAP.get(risk_type, []):
            actions.append(
                {
                    "risk_type": risk_type,
                    "action": action_text,
                    "urgency": "high" if score >= 0.60 else ("medium" if score >= 0.35 else "low"),
                }
            )
    return actions


def _risk_detail(risk_type: str, score: float) -> str:
    severity = "critical" if score >= 0.70 else ("elevated" if score >= 0.40 else "moderate")
    return f"{risk_type.replace('_', ' ').title()} is {severity} at {score:.2f}"
