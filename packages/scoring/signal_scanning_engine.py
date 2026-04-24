"""Signal scanning engine — normalize, classify, score, and queue raw signals.

Pure functions only (no I/O, no SQLAlchemy). All logic deterministic.
"""
from __future__ import annotations

import math
from typing import Any

SSE = "signal_scanning_engine"

SIGNAL_TYPES = [
    "rising_topic",
    "niche_whitespace",
    "comment_demand",
    "competitor_gap",
    "seasonal_window",
    "fatigue_signal",
    "high_intent",
    "sponsor_friendly",
    "affiliate_opportunity",
    "recurring_theme",
    "objection_pattern",
]

SIGNAL_SOURCES = [
    "trend_api",
    "comment_analysis",
    "competitor_monitor",
    "search_console",
    "social_listening",
    "audience_survey",
    "affiliate_network",
    "sponsor_inbound",
    "internal_analytics",
    "seasonal_calendar",
]

_FRESHNESS_HALF_LIFE_HOURS: dict[str, float] = {
    "rising_topic": 48.0,
    "niche_whitespace": 336.0,
    "comment_demand": 72.0,
    "competitor_gap": 168.0,
    "seasonal_window": 720.0,
    "fatigue_signal": 120.0,
    "high_intent": 24.0,
    "sponsor_friendly": 168.0,
    "affiliate_opportunity": 240.0,
    "recurring_theme": 480.0,
    "objection_pattern": 336.0,
}

_MONETIZATION_WEIGHTS: dict[str, float] = {
    "rising_topic": 0.4,
    "niche_whitespace": 0.6,
    "comment_demand": 0.5,
    "competitor_gap": 0.7,
    "seasonal_window": 0.5,
    "fatigue_signal": 0.1,
    "high_intent": 0.9,
    "sponsor_friendly": 0.85,
    "affiliate_opportunity": 0.8,
    "recurring_theme": 0.3,
    "objection_pattern": 0.55,
}

_URGENCY_BASE: dict[str, float] = {
    "rising_topic": 0.8,
    "niche_whitespace": 0.5,
    "comment_demand": 0.7,
    "competitor_gap": 0.6,
    "seasonal_window": 0.9,
    "fatigue_signal": 0.3,
    "high_intent": 0.95,
    "sponsor_friendly": 0.5,
    "affiliate_opportunity": 0.55,
    "recurring_theme": 0.25,
    "objection_pattern": 0.4,
}

_QUEUE_ITEM_TYPES = [
    "new_content",
    "repurpose",
    "reply_thread",
    "offer_push",
    "engagement_play",
    "suppressed",
]

_MONETIZATION_PATHS = [
    "affiliate",
    "sponsor",
    "owned_product",
    "lead_gen",
    "ad_revenue",
    "community",
    "none",
]


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _exponential_decay(age_hours: float, half_life_hours: float) -> float:
    """Compute exponential decay factor from age and half-life."""
    if half_life_hours <= 0:
        return 0.0
    return math.exp(-0.693 * age_hours / half_life_hours)


def _niche_overlap(signal_keywords: list[str], brand_keywords: list[str]) -> float:
    """Jaccard-like overlap between signal keywords and brand niche keywords."""
    if not signal_keywords or not brand_keywords:
        return 0.0
    s_set = {k.lower().strip() for k in signal_keywords}
    b_set = {k.lower().strip() for k in brand_keywords}
    intersection = len(s_set & b_set)
    union = len(s_set | b_set)
    return intersection / union if union > 0 else 0.0


def normalize_signal(
    signal_type: str,
    source: str,
    raw_data: dict[str, Any],
    brand_context: dict[str, Any],
) -> dict[str, Any]:
    """Normalize a raw signal into scored, actionable form.

    Parameters
    ----------
    signal_type:
        One of SIGNAL_TYPES.
    source:
        One of SIGNAL_SOURCES.
    raw_data:
        Raw signal payload. Expected keys: title (str), description (str),
        age_hours (float), keywords (list[str]), metrics (dict),
        competitive_pressure (float, 0-1), data_completeness (float, 0-1).
    brand_context:
        Brand profile. Expected keys: niche (str), niche_keywords (list[str]),
        active_offers (list[str]), monetization_modes (list[str]).

    Returns
    -------
    dict with normalized_title, normalized_description, freshness_score,
    monetization_relevance, urgency_score, confidence, is_actionable, explanation.
    """
    title = str(raw_data.get("title", "")).strip() or "Untitled Signal"
    description = str(raw_data.get("description", "")).strip()
    age_hours = max(0.0, float(raw_data.get("age_hours", 0)))
    keywords = raw_data.get("keywords", [])
    competitive_pressure = _clamp(float(raw_data.get("competitive_pressure", 0.0)))
    data_completeness = _clamp(float(raw_data.get("data_completeness", 0.5)))

    niche_keywords = brand_context.get("niche_keywords", [])
    active_offers = brand_context.get("active_offers", [])

    half_life = _FRESHNESS_HALF_LIFE_HOURS.get(signal_type, 168.0)
    freshness_score = round(_exponential_decay(age_hours, half_life), 4)

    overlap = _niche_overlap(keywords, niche_keywords)
    base_mon_weight = _MONETIZATION_WEIGHTS.get(signal_type, 0.3)
    offer_bonus = min(0.2, len(active_offers) * 0.04) if active_offers else 0.0
    monetization_relevance = round(_clamp(base_mon_weight * 0.5 + overlap * 0.35 + offer_bonus), 4)

    base_urgency = _URGENCY_BASE.get(signal_type, 0.4)
    decay_pressure = (1.0 - freshness_score) * 0.3
    urgency_score = round(_clamp(base_urgency * 0.5 + competitive_pressure * 0.3 + decay_pressure), 4)

    required_fields = ["title", "age_hours", "keywords"]
    present = sum(1 for f in required_fields if raw_data.get(f))
    base_conf = present / len(required_fields) * 0.6
    confidence = round(_clamp(base_conf + data_completeness * 0.4), 4)

    is_actionable = (
        freshness_score >= 0.15
        and monetization_relevance >= 0.2
        and confidence >= 0.3
    )

    normalized_title = f"[{signal_type.upper()}] {title}"
    normalized_description = description or f"Signal from {source}: {title}"

    explanation = (
        f"Signal '{title}' ({signal_type} via {source}): "
        f"freshness={freshness_score:.2f}, monetization={monetization_relevance:.2f}, "
        f"urgency={urgency_score:.2f}, confidence={confidence:.2f}. "
        f"{'Actionable' if is_actionable else 'Filtered out (stale/low-relevance)'}."
    )

    return {
        "normalized_title": normalized_title,
        "normalized_description": normalized_description,
        "signal_type": signal_type,
        "source": source,
        "freshness_score": freshness_score,
        "monetization_relevance": monetization_relevance,
        "urgency_score": urgency_score,
        "confidence": confidence,
        "is_actionable": is_actionable,
        "explanation": explanation,
        SSE: True,
    }


def classify_signal_type(
    raw_title: str,
    raw_description: str,
    raw_metrics: dict[str, Any],
) -> str:
    """Classify a raw signal into one of SIGNAL_TYPES using heuristic rules.

    Parameters
    ----------
    raw_title:
        Raw signal title/headline text.
    raw_description:
        Raw signal body/description text.
    raw_metrics:
        Signal metrics dict. Expected keys: search_volume_delta (float),
        comment_count (int), competitor_count (int), conversion_intent (float, 0-1),
        sponsor_match (float, 0-1), affiliate_payout (float),
        recurrence_count (int), objection_count (int), engagement_velocity (float),
        seasonality_score (float, 0-1), fatigue_indicator (float, 0-1),
        gap_score (float, 0-1).

    Returns
    -------
    str — one of SIGNAL_TYPES.
    """
    text = f"{raw_title} {raw_description}".lower()

    search_vol_delta = float(raw_metrics.get("search_volume_delta", 0))
    comment_count = int(raw_metrics.get("comment_count", 0))
    competitor_count = int(raw_metrics.get("competitor_count", 0))
    conversion_intent = float(raw_metrics.get("conversion_intent", 0))
    sponsor_match = float(raw_metrics.get("sponsor_match", 0))
    affiliate_payout = float(raw_metrics.get("affiliate_payout", 0))
    recurrence = int(raw_metrics.get("recurrence_count", 0))
    objection_count = int(raw_metrics.get("objection_count", 0))
    engagement_vel = float(raw_metrics.get("engagement_velocity", 0))
    seasonality = float(raw_metrics.get("seasonality_score", 0))
    fatigue = float(raw_metrics.get("fatigue_indicator", 0))
    gap_score = float(raw_metrics.get("gap_score", 0))

    scores: dict[str, float] = {
        "rising_topic": (
            min(1.0, search_vol_delta / 100) * 0.5
            + min(1.0, engagement_vel / 10) * 0.3
            + (0.2 if any(w in text for w in ("trending", "viral", "surge", "breakout")) else 0.0)
        ),
        "niche_whitespace": (
            gap_score * 0.5
            + (0.3 if competitor_count < 3 else 0.0)
            + (0.2 if any(w in text for w in ("untapped", "gap", "underserved", "whitespace")) else 0.0)
        ),
        "comment_demand": (
            min(1.0, comment_count / 50) * 0.5
            + min(1.0, engagement_vel / 5) * 0.3
            + (0.2 if any(w in text for w in ("comment", "request", "ask", "demand", "question")) else 0.0)
        ),
        "competitor_gap": (
            gap_score * 0.4
            + min(1.0, competitor_count / 10) * 0.3
            + (0.3 if any(w in text for w in ("competitor", "rival", "alternative", "vs")) else 0.0)
        ),
        "seasonal_window": (
            seasonality * 0.6
            + (0.4 if any(w in text for w in ("season", "holiday", "event", "annual", "black friday", "q4")) else 0.0)
        ),
        "fatigue_signal": (
            fatigue * 0.7
            + (0.3 if any(w in text for w in ("fatigue", "decline", "saturated", "overused")) else 0.0)
        ),
        "high_intent": (
            conversion_intent * 0.6
            + (0.4 if any(w in text for w in ("buy", "purchase", "subscribe", "sign up", "pricing", "deal")) else 0.0)
        ),
        "sponsor_friendly": (
            sponsor_match * 0.6
            + (0.4 if any(w in text for w in ("sponsor", "brand deal", "partnership", "collab")) else 0.0)
        ),
        "affiliate_opportunity": (
            min(1.0, affiliate_payout / 100) * 0.5
            + conversion_intent * 0.3
            + (0.2 if any(w in text for w in ("affiliate", "commission", "referral", "partner program")) else 0.0)
        ),
        "recurring_theme": (
            min(1.0, recurrence / 5) * 0.6
            + (0.4 if any(w in text for w in ("recurring", "repeat", "evergreen", "perennial")) else 0.0)
        ),
        "objection_pattern": (
            min(1.0, objection_count / 10) * 0.5
            + (0.3 if any(w in text for w in ("objection", "concern", "doubt", "hesitation", "but")) else 0.0)
            + (0.2 if comment_count > 20 and conversion_intent < 0.3 else 0.0)
        ),
    }

    best_type = max(scores, key=lambda k: scores[k])
    return best_type if scores[best_type] > 0.0 else "rising_topic"


def score_signal_batch(
    signals: list[dict[str, Any]],
    brand_offers: list[dict[str, Any]],
    brand_niche: str,
) -> list[dict[str, Any]]:
    """Score and rank a batch of raw signals, filtering stale/irrelevant ones.

    Parameters
    ----------
    signals:
        List of raw signal dicts. Each should have: title (str), description (str),
        age_hours (float), keywords (list[str]), metrics (dict),
        competitive_pressure (float), data_completeness (float),
        signal_type (str, optional), source (str, optional).
    brand_offers:
        List of offer dicts with: name (str), keywords (list[str]).
    brand_niche:
        Primary brand niche string.

    Returns
    -------
    list[dict] — scored signals sorted by urgency × monetization_relevance,
    stale/irrelevant signals excluded.
    """
    niche_keywords = [brand_niche] + [
        kw
        for offer in brand_offers
        for kw in offer.get("keywords", [])
    ]
    brand_context: dict[str, Any] = {
        "niche": brand_niche,
        "niche_keywords": niche_keywords,
        "active_offers": [o.get("name", "") for o in brand_offers],
        "monetization_modes": [],
    }

    scored: list[dict[str, Any]] = []
    for sig in signals:
        sig_type = sig.get("signal_type") or classify_signal_type(
            str(sig.get("title", "")),
            str(sig.get("description", "")),
            sig.get("metrics", {}),
        )
        source = sig.get("source", "internal_analytics")

        result = normalize_signal(sig_type, source, sig, brand_context)
        if not result["is_actionable"]:
            continue

        result["composite_score"] = round(
            result["urgency_score"] * result["monetization_relevance"], 4
        )
        result["raw_signal"] = sig
        scored.append(result)

    scored.sort(key=lambda s: s["composite_score"], reverse=True)
    return scored


def build_auto_queue_items(
    scored_signals: list[dict[str, Any]],
    accounts: list[dict[str, Any]],
    platform_policies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Turn scored signals into posting queue candidates matched to accounts.

    Parameters
    ----------
    scored_signals:
        Output of score_signal_batch.
    accounts:
        List of account dicts. Expected keys: account_id (str), platform (str),
        role (str), niche (str), sub_niche (str), maturity_state (str),
        health_score (float, 0-1), current_output_per_week (int).
    platform_policies:
        List of platform policy dicts. Expected keys: platform (str),
        max_safe_output_per_day (int), suppressed_signal_types (list[str], optional),
        hold_reasons (list[str], optional).

    Returns
    -------
    list[dict] — queue items with queue_item_type, target_account_id,
    target_account_role, platform, niche, sub_niche, content_family,
    monetization_path, priority_score, urgency_score, queue_status,
    suppression_flags, hold_reason, explanation.
    """
    policy_by_platform: dict[str, dict[str, Any]] = {
        p.get("platform", ""): p for p in platform_policies
    }

    queue_items: list[dict[str, Any]] = []

    for sig in scored_signals:
        sig_type = sig.get("signal_type", "rising_topic")
        urgency = float(sig.get("urgency_score", 0))
        mon_rel = float(sig.get("monetization_relevance", 0))
        title = sig.get("normalized_title", "")

        best_account = _match_account(sig, accounts)
        if best_account is None:
            continue

        platform = best_account.get("platform", "youtube")
        policy = policy_by_platform.get(platform, {})

        suppressed_types = policy.get("suppressed_signal_types", [])
        suppression_flags: list[str] = []
        hold_reason: str | None = None

        if sig_type in suppressed_types:
            suppression_flags.append(f"signal_type_{sig_type}_suppressed_on_{platform}")

        account_health = float(best_account.get("health_score", 0.5))
        if account_health < 0.3:
            suppression_flags.append("account_health_below_threshold")

        maturity = best_account.get("maturity_state", "stable")
        if maturity in ("newborn", "at_risk"):
            hold_reason = f"Account maturity '{maturity}' requires manual review."

        max_daily = int(policy.get("max_safe_output_per_day", 3))
        current_weekly = int(best_account.get("current_output_per_week", 0))
        if current_weekly >= max_daily * 7:
            hold_reason = hold_reason or f"Account at max safe weekly output ({max_daily * 7})."

        queue_item_type = _determine_queue_item_type(sig_type, mon_rel)
        monetization_path = _determine_monetization_path(sig_type, mon_rel)
        content_family = _determine_content_family(sig_type)
        priority_score = round(_clamp(urgency * 0.5 + mon_rel * 0.3 + account_health * 0.2), 4)

        if suppression_flags:
            queue_status = "suppressed"
        elif hold_reason:
            queue_status = "held"
        else:
            queue_status = "ready"

        explanation = (
            f"Signal '{title}' → {queue_item_type} on {platform} "
            f"(account {best_account.get('account_id', '?')}). "
            f"Priority {priority_score:.2f}, monetization={monetization_path}. "
            f"Status: {queue_status}."
        )
        if hold_reason:
            explanation += f" Hold: {hold_reason}"
        if suppression_flags:
            explanation += f" Suppressed: {', '.join(suppression_flags)}."

        queue_items.append({
            "queue_item_type": queue_item_type,
            "target_account_id": best_account.get("account_id"),
            "target_account_role": best_account.get("role", "general"),
            "platform": platform,
            "niche": best_account.get("niche", ""),
            "sub_niche": best_account.get("sub_niche", ""),
            "content_family": content_family,
            "monetization_path": monetization_path,
            "priority_score": priority_score,
            "urgency_score": urgency,
            "queue_status": queue_status,
            "suppression_flags": suppression_flags,
            "hold_reason": hold_reason,
            "signal_title": title,
            "explanation": explanation,
            SSE: True,
        })

    queue_items.sort(key=lambda q: q["priority_score"], reverse=True)
    return queue_items


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _match_account(
    signal: dict[str, Any],
    accounts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Pick the best account for a signal based on niche overlap and maturity."""
    if not accounts:
        return None

    sig_keywords = set()
    raw = signal.get("raw_signal", {})
    for kw in raw.get("keywords", []):
        sig_keywords.add(kw.lower().strip())
    signal.get("signal_type", "")

    best: dict[str, Any] | None = None
    best_score = -1.0

    for acct in accounts:
        niche = acct.get("niche", "").lower()
        sub_niche = acct.get("sub_niche", "").lower()
        acct_keywords = {niche, sub_niche} - {""}
        health = float(acct.get("health_score", 0.5))
        maturity = acct.get("maturity_state", "stable")

        overlap = len(sig_keywords & acct_keywords) / max(len(sig_keywords | acct_keywords), 1)

        maturity_bonus = {
            "stable": 0.3,
            "scaling": 0.35,
            "max_output": 0.25,
            "warming": 0.15,
            "newborn": 0.05,
            "saturated": 0.1,
            "cooling": 0.1,
            "at_risk": 0.0,
        }.get(maturity, 0.2)

        score = overlap * 0.4 + health * 0.3 + maturity_bonus
        if score > best_score:
            best_score = score
            best = acct

    return best


def _determine_queue_item_type(signal_type: str, mon_relevance: float) -> str:
    if signal_type in ("high_intent", "affiliate_opportunity", "sponsor_friendly"):
        return "offer_push"
    if signal_type in ("comment_demand", "objection_pattern"):
        return "reply_thread"
    if signal_type == "fatigue_signal":
        return "suppressed"
    if signal_type == "recurring_theme" and mon_relevance < 0.3:
        return "repurpose"
    if mon_relevance >= 0.5:
        return "new_content"
    return "engagement_play"


def _determine_monetization_path(signal_type: str, mon_relevance: float) -> str:
    path_map: dict[str, str] = {
        "affiliate_opportunity": "affiliate",
        "sponsor_friendly": "sponsor",
        "high_intent": "owned_product",
        "comment_demand": "lead_gen",
        "rising_topic": "ad_revenue",
        "niche_whitespace": "owned_product",
        "competitor_gap": "owned_product",
        "seasonal_window": "affiliate",
    }
    if mon_relevance < 0.15:
        return "none"
    return path_map.get(signal_type, "community")


def _determine_content_family(signal_type: str) -> str:
    family_map: dict[str, str] = {
        "rising_topic": "trend_response",
        "niche_whitespace": "authority_piece",
        "comment_demand": "audience_response",
        "competitor_gap": "differentiation",
        "seasonal_window": "seasonal_campaign",
        "fatigue_signal": "creative_refresh",
        "high_intent": "conversion_content",
        "sponsor_friendly": "branded_integration",
        "affiliate_opportunity": "review_comparison",
        "recurring_theme": "evergreen_series",
        "objection_pattern": "trust_building",
    }
    return family_map.get(signal_type, "general")
