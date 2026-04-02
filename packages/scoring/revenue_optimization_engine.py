"""Revenue-Per-Post Optimization Engine.

Scores content ideas by expected revenue rather than just engagement.
Expected revenue = offer_payout * historical_CVR * estimated_impressions * monetization_density.
"""
from __future__ import annotations
from typing import Any


def score_revenue_potential(
    offer_payout: float = 0.0,
    historical_cvr: float = 0.02,
    estimated_impressions: float = 1000,
    monetization_density: float = 0.5,
    niche_cpm: float = 10.0,
    content_type_multiplier: float = 1.0,
) -> dict[str, Any]:
    """Score a content idea by expected revenue."""
    affiliate_revenue = offer_payout * historical_cvr * (estimated_impressions / 1000) * monetization_density
    ad_revenue = (estimated_impressions / 1000) * niche_cpm / 1000  # CPM-based
    total_expected = (affiliate_revenue + ad_revenue) * content_type_multiplier

    return {
        "expected_revenue": round(total_expected, 4),
        "affiliate_component": round(affiliate_revenue, 4),
        "ad_component": round(ad_revenue, 4),
        "confidence": min(1.0, estimated_impressions / 10000),
    }


CONTENT_TYPE_REVENUE_MULTIPLIERS = {
    "SHORT_VIDEO": 1.0,
    "LONG_VIDEO": 2.5,
    "TEXT_POST": 0.3,
    "CAROUSEL": 0.7,
    "REEL": 1.0,
    "STORY": 0.2,
}

NICHE_CPM_ESTIMATES = {
    "personal_finance": 18.0, "make_money_online": 22.0, "health_fitness": 10.0,
    "tech_reviews": 14.0, "ai_tools": 16.0, "crypto": 25.0,
    "real_estate": 20.0, "self_improvement": 8.0, "business_entrepreneurship": 15.0,
    "cooking_recipes": 6.0, "gaming": 5.0, "beauty_skincare": 12.0,
    "travel": 10.0, "education_courses": 16.0, "software_saas": 22.0,
}


def rank_briefs_by_revenue(
    briefs: list[dict[str, Any]],
    niche: str = "general",
) -> list[dict[str, Any]]:
    """Sort a list of brief candidates by expected revenue, highest first."""
    cpm = NICHE_CPM_ESTIMATES.get(niche, 10.0)
    scored = []
    for b in briefs:
        ct = b.get("content_type", "SHORT_VIDEO")
        ct_mult = CONTENT_TYPE_REVENUE_MULTIPLIERS.get(ct, 1.0)
        rev = score_revenue_potential(
            offer_payout=b.get("offer_payout", 0),
            historical_cvr=b.get("historical_cvr", 0.02),
            estimated_impressions=b.get("estimated_impressions", 1000),
            monetization_density=b.get("monetization_density", 0.5),
            niche_cpm=cpm,
            content_type_multiplier=ct_mult,
        )
        scored.append({**b, "revenue_score": rev["expected_revenue"], "revenue_detail": rev})
    scored.sort(key=lambda x: x["revenue_score"], reverse=True)
    return scored


def should_prioritize_monetized(offer_payout: float, trend_score: float) -> bool:
    """Decide whether to prioritize a monetized brief over a pure-engagement trend brief."""
    if offer_payout >= 30 and trend_score < 0.6:
        return True
    if offer_payout >= 50:
        return True
    return False
