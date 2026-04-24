"""Trend / Viral Opportunity Engine — scan, score, classify, suppress, route. Pure functions."""

from __future__ import annotations

from typing import Any

OPPORTUNITY_TYPES = [
    "pure_reach",
    "monetization",
    "authority_building",
    "creator_acquisition",
    "product_promotion",
    "community_engagement",
    "retention",
]
BREAKOUT_VELOCITY = 2.0
SCORE_DIMENSIONS = [
    "velocity",
    "novelty",
    "relevance",
    "revenue_potential",
    "platform_fit",
    "account_fit",
    "content_form_fit",
]


def extract_signals(raw_data: list[dict[str, Any]], existing_topics: list[str]) -> list[dict[str, Any]]:
    """Extract and normalize trend signals from raw scan data."""
    signals = []
    seen = set(t.lower() for t in existing_topics)
    for item in raw_data:
        topic = item.get("topic", "").strip()
        if not topic or len(topic) < 3:
            continue
        strength = float(item.get("signal_strength", 0) or item.get("impressions", 0) or 0)
        velocity = float(item.get("velocity", 0) or 0)
        is_new = topic.lower() not in seen
        signals.append(
            {
                "topic": topic,
                "source": item.get("source", "internal"),
                "signal_strength": strength,
                "velocity": velocity,
                "is_new": is_new,
                "truth_label": item.get("truth_label", "internal_proxy"),
            }
        )
        seen.add(topic.lower())
    return signals


def compute_velocity(current: float, previous: float) -> dict[str, Any]:
    """Compute velocity and acceleration between snapshots."""
    if previous <= 0:
        return {
            "current_velocity": current,
            "previous_velocity": 0,
            "acceleration": 0,
            "breakout": current > BREAKOUT_VELOCITY,
        }
    accel = (current - previous) / max(abs(previous), 0.01)
    return {
        "current_velocity": current,
        "previous_velocity": previous,
        "acceleration": round(accel, 3),
        "breakout": accel > 1.0 or current > BREAKOUT_VELOCITY,
    }


def check_duplicate(topic: str, existing: list[str], threshold: float = 0.6) -> str | None:
    """Check if a topic is a near-duplicate of existing ones."""
    topic_words = set(topic.lower().split())
    for ex in existing:
        ex_words = set(ex.lower().split())
        if not topic_words or not ex_words:
            continue
        jaccard = len(topic_words & ex_words) / len(topic_words | ex_words)
        if jaccard >= threshold:
            return ex
    return None


def score_opportunity(signal: dict[str, Any], brand_context: dict[str, Any]) -> dict[str, Any]:
    """Score a trend signal across all dimensions."""
    velocity = min(1.0, float(signal.get("velocity", 0)) / 5)
    novelty = 1.0 if signal.get("is_new") else 0.3
    niche = brand_context.get("niche", "").lower()
    topic_lower = signal.get("topic", "").lower()
    relevance = 0.8 if niche and niche in topic_lower else 0.4

    strength = float(signal.get("signal_strength", 0))
    revenue = min(1.0, strength / max(strength + 1, 1)) * 0.6 + relevance * 0.4  # Self-relative
    platform_fit = 0.7
    account_fit = 0.6
    form_fit = 0.7
    saturation = min(1.0, max(0, 1.0 - novelty))
    compliance = 0.1

    composite = round(
        0.20 * velocity
        + 0.15 * novelty
        + 0.10 * relevance
        + 0.20 * revenue
        + 0.10 * platform_fit
        + 0.10 * account_fit
        + 0.05 * form_fit
        - 0.05 * saturation
        - 0.05 * compliance,
        4,
    )

    return {
        "velocity_score": round(velocity, 3),
        "novelty_score": round(novelty, 3),
        "relevance_score": round(relevance, 3),
        "revenue_potential_score": round(revenue, 3),
        "platform_fit_score": round(platform_fit, 3),
        "account_fit_score": round(account_fit, 3),
        "content_form_fit_score": round(form_fit, 3),
        "saturation_risk": round(saturation, 3),
        "compliance_risk": round(compliance, 3),
        "composite_score": max(0, composite),
        "confidence": round(min(0.95, 0.3 + velocity * 0.3 + novelty * 0.2), 3),
    }


def classify_opportunity(scores: dict[str, Any]) -> dict[str, Any]:
    """Classify whether a trend is for reach, monetization, authority, etc."""
    rev = scores.get("revenue_potential_score", 0)
    vel = scores.get("velocity_score", 0)
    rel = scores.get("relevance_score", 0)

    if rev > 0.6 and rel > 0.5:
        otype = "monetization"
        monetization = "affiliate"
    elif vel > 0.7 and rev < 0.3:
        otype = "pure_reach"
        monetization = "none_growth_only"
    elif rel > 0.6 and vel < 0.4:
        otype = "authority_building"
        monetization = "organic"
    else:
        otype = "growth" if vel > 0.4 else "community_engagement"
        monetization = "soft_monetization" if rev > 0.3 else "none_growth_only"

    form = "short_video" if vel > 0.5 else "text_post" if rel > 0.6 else "carousel"
    platform = "tiktok" if vel > 0.6 else "youtube" if rel > 0.5 else "instagram"
    urgency = min(1.0, vel * 0.6 + scores.get("novelty_score", 0) * 0.4)

    return {
        "opportunity_type": otype,
        "recommended_platform": platform,
        "recommended_content_form": form,
        "recommended_monetization": monetization,
        "recommended_account_role": "flagship" if rev > 0.5 else "experimental",
        "urgency": round(urgency, 3),
    }


def should_suppress(signal: dict[str, Any], scores: dict[str, Any], rules: list[dict[str, Any]]) -> str | None:
    """Check if a signal should be suppressed."""
    topic = signal.get("topic", "").lower()
    for r in rules:
        if r.get("pattern", "").lower() in topic:
            return r.get("reason", "Matched suppression rule")
    if scores.get("composite_score", 0) < 0.15:
        return "Score too low — not worth pursuing"
    if scores.get("saturation_risk", 0) > 0.8:
        return "Too saturated"
    return None


def detect_blockers(signal: dict[str, Any], system_state: dict[str, Any]) -> list[dict[str, Any]]:
    """Detect blockers for a trend opportunity."""
    blockers = []
    if signal.get("truth_label") == "blocked_by_credentials":
        blockers.append(
            {"blocker_type": "source_blocked", "description": "Trend source requires credentials", "severity": "medium"}
        )
    if not system_state.get("has_accounts"):
        blockers.append(
            {
                "blocker_type": "no_accounts",
                "description": "No active accounts to publish trend content",
                "severity": "high",
            }
        )
    return blockers
