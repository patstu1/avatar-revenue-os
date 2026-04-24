"""Revenue bottleneck classifier.

Classifies the primary bottleneck for an entity (account, topic, offer, funnel)
across 14 categories. Deterministic, rules-based, explainable.
"""

from dataclasses import dataclass
from enum import Enum

FORMULA_VERSION = "v1"


class BottleneckCategory(str, Enum):
    WEAK_OPPORTUNITY_SELECTION = "weak_opportunity_selection"
    WEAK_HOOK_RETENTION = "weak_hook_retention"
    WEAK_CTR = "weak_ctr"
    WEAK_OFFER_FIT = "weak_offer_fit"
    WEAK_LANDING_PAGE = "weak_landing_page"
    WEAK_CONVERSION = "weak_conversion"
    WEAK_AOV = "weak_aov"
    WEAK_LTV = "weak_ltv"
    WEAK_SCALE_CAPACITY = "weak_scale_capacity"
    AUDIENCE_FATIGUE = "audience_fatigue"
    CONTENT_SIMILARITY = "content_similarity"
    PLATFORM_MISMATCH = "platform_mismatch"
    TRUST_DEFICIT = "trust_deficit"
    MONETIZATION_MISMATCH = "monetization_mismatch"


@dataclass
class BottleneckInput:
    impressions: int = 0
    views: int = 0
    clicks: int = 0
    conversions: int = 0
    revenue: float = 0.0
    ctr: float = 0.0
    conversion_rate: float = 0.0
    avg_watch_pct: float = 0.0
    engagement_rate: float = 0.0
    aov: float = 0.0
    offer_fit_score: float = 0.0
    opportunity_score: float = 0.0
    fatigue_score: float = 0.0
    similarity_score: float = 0.0
    follower_growth_rate: float = 0.0
    posting_capacity_used_pct: float = 0.0
    platform_match_score: float = 0.0
    trust_score: float = 0.0
    ltv_estimate: float = 0.0


@dataclass
class BottleneckResult:
    primary_bottleneck: str
    all_bottlenecks: list[dict]
    severity: str
    explanation: str
    recommended_actions: list[str]
    formula_version: str = FORMULA_VERSION


def classify_bottleneck(inp: BottleneckInput) -> BottleneckResult:
    scores: list[tuple[str, float, str]] = []

    # Check each bottleneck dimension (higher score = worse bottleneck)
    if inp.opportunity_score < 0.3 and inp.impressions > 0:
        scores.append(
            (
                "weak_opportunity_selection",
                0.9 - inp.opportunity_score,
                "Low opportunity scores — topic selection needs improvement",
            )
        )

    if inp.avg_watch_pct < 0.3 and inp.views > 0:
        scores.append(
            (
                "weak_hook_retention",
                0.8 - inp.avg_watch_pct,
                f"Avg watch {inp.avg_watch_pct:.0%} — hook/retention is weak",
            )
        )

    if inp.ctr < 0.02 and inp.impressions > 0:
        scores.append(("weak_ctr", 0.8 - min(inp.ctr * 20, 0.8), f"CTR {inp.ctr:.2%} below 2% threshold"))

    if inp.offer_fit_score < 0.4:
        scores.append(
            (
                "weak_offer_fit",
                0.7 - inp.offer_fit_score,
                f"Offer fit {inp.offer_fit_score:.2f} — offer doesn't match audience",
            )
        )

    if inp.clicks > 10 and inp.conversions == 0:
        scores.append(("weak_landing_page", 0.8, f"{inp.clicks} clicks, 0 conversions — landing page likely failing"))

    if inp.conversion_rate < 0.01 and inp.clicks > 20:
        scores.append(
            (
                "weak_conversion",
                0.8 - min(inp.conversion_rate * 50, 0.5),
                f"Conversion rate {inp.conversion_rate:.2%} — funnel is leaking",
            )
        )

    if inp.aov < 15 and inp.conversions > 0:
        scores.append(("weak_aov", 0.6 - min(inp.aov / 50, 0.5), f"AOV ${inp.aov:.2f} — consider higher-value offers"))

    if inp.ltv_estimate < 20 and inp.conversions > 5:
        scores.append(
            (
                "weak_ltv",
                0.6 - min(inp.ltv_estimate / 100, 0.5),
                f"LTV ${inp.ltv_estimate:.2f} — no repeat revenue path",
            )
        )

    if inp.posting_capacity_used_pct > 0.9:
        scores.append(
            (
                "weak_scale_capacity",
                inp.posting_capacity_used_pct - 0.5,
                f"Using {inp.posting_capacity_used_pct:.0%} of posting capacity — at limit",
            )
        )

    if inp.fatigue_score > 0.5:
        scores.append(
            (
                "audience_fatigue",
                inp.fatigue_score,
                f"Fatigue score {inp.fatigue_score:.2f} — audience is tiring of this content",
            )
        )

    if inp.similarity_score > 0.7:
        scores.append(
            (
                "content_similarity",
                inp.similarity_score - 0.3,
                f"Similarity {inp.similarity_score:.2f} — content too repetitive",
            )
        )

    if inp.platform_match_score < 0.4:
        scores.append(
            (
                "platform_mismatch",
                0.7 - inp.platform_match_score,
                f"Platform match {inp.platform_match_score:.2f} — wrong platform for this content",
            )
        )

    if inp.trust_score < 0.4 and inp.impressions > 0:
        scores.append(
            ("trust_deficit", 0.7 - inp.trust_score, f"Trust score {inp.trust_score:.2f} — audience trust low")
        )

    if inp.offer_fit_score > 0.5 and inp.conversion_rate > 0.02 and inp.revenue == 0 and inp.impressions > 0:
        scores.append(
            ("monetization_mismatch", 0.5, "Good fit and conversion but low revenue — monetization method may be wrong")
        )

    if not scores:
        if inp.impressions < 100:
            scores.append(("weak_opportunity_selection", 0.3, "Insufficient data — need more content published"))
        else:
            scores.append(
                ("weak_opportunity_selection", 0.1, "No clear bottleneck detected — system performing acceptably")
            )

    scores.sort(key=lambda x: -x[1])
    primary = scores[0]

    severity = "critical" if primary[1] > 0.6 else "warning" if primary[1] > 0.3 else "info"

    action_map = {
        "weak_opportunity_selection": ["Improve topic research", "Expand signal sources"],
        "weak_hook_retention": ["Test stronger hooks", "Shorten intro", "A/B test openings"],
        "weak_ctr": ["Improve thumbnails", "Test titles", "Optimize posting times"],
        "weak_offer_fit": ["Switch offer", "Test different monetization methods"],
        "weak_landing_page": ["Audit landing page", "Test different CTAs"],
        "weak_conversion": ["Simplify funnel", "Add social proof", "Test pricing"],
        "weak_aov": ["Bundle offers", "Upsell higher-tier products"],
        "weak_ltv": ["Add email capture", "Create follow-up sequence"],
        "weak_scale_capacity": ["Add accounts", "Increase posting frequency"],
        "audience_fatigue": ["Rotate topics", "Pause and diversify"],
        "content_similarity": ["Create unique angles", "Vary format"],
        "platform_mismatch": ["Test different platforms", "Adapt content format"],
        "trust_deficit": ["Share more results", "Add testimonials"],
        "monetization_mismatch": ["Test different offer types", "Try direct products"],
    }

    return BottleneckResult(
        primary_bottleneck=primary[0],
        all_bottlenecks=[{"category": s[0], "score": round(s[1], 3), "detail": s[2]} for s in scores],
        severity=severity,
        explanation=primary[2],
        recommended_actions=action_map.get(primary[0], ["Investigate manually"]),
    )
