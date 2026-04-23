"""Saturation, fatigue, and similarity penalty engine.

Evaluates whether a topic/niche is oversaturated for a brand or account.
Deterministic rules-based logic.
"""
from dataclasses import dataclass

FORMULA_VERSION = "v1"


@dataclass
class SaturationInput:
    total_posts_in_niche: int = 0
    posts_last_30d: int = 0
    posts_last_7d: int = 0
    unique_topics_covered: int = 0
    total_topics_available: int = 1
    avg_engagement_last_7d: float = 0.0
    avg_engagement_last_30d: float = 0.0
    similar_content_count: int = 0
    max_similarity_score: float = 0.0
    audience_overlap_pct: float = 0.0
    account_follower_growth_rate: float = 0.0


@dataclass
class SaturationResult:
    saturation_score: float
    fatigue_score: float
    originality_score: float
    topic_overlap_pct: float
    audience_overlap_pct: float
    recommended_action: str
    explanation: str
    formula_version: str = FORMULA_VERSION


def compute_saturation(inp: SaturationInput) -> SaturationResult:
    topic_overlap = min(inp.unique_topics_covered / max(inp.total_topics_available, 1), 1.0)

    posting_rate = inp.posts_last_7d / 7.0 if inp.posts_last_7d > 0 else 0.0
    rate_penalty = min(posting_rate / 3.0, 1.0)

    saturation_score = (
        0.30 * topic_overlap
        + 0.25 * rate_penalty
        + 0.25 * min(inp.audience_overlap_pct, 1.0)
        + 0.20 * min(inp.similar_content_count / 10.0, 1.0)
    )

    if inp.avg_engagement_last_30d > 0 and inp.avg_engagement_last_7d > 0:
        engagement_decline = 1.0 - (inp.avg_engagement_last_7d / inp.avg_engagement_last_30d)
        fatigue_score = max(0.0, min(engagement_decline, 1.0))
    else:
        fatigue_score = 0.0

    if inp.posts_last_30d > 10:
        fatigue_score = max(fatigue_score, 0.3)

    growth_decline_penalty = 0.0
    if inp.account_follower_growth_rate < 0:
        growth_decline_penalty = min(abs(inp.account_follower_growth_rate) * 10, 0.3)
    fatigue_score = min(fatigue_score + growth_decline_penalty, 1.0)

    originality_score = max(0.0, 1.0 - inp.max_similarity_score)

    if saturation_score > 0.7 or fatigue_score > 0.6:
        action = "suppress"
    elif saturation_score > 0.5 or fatigue_score > 0.4:
        action = "reduce"
    elif saturation_score > 0.3:
        action = "monitor"
    else:
        action = "maintain"

    explanation = (
        f"Saturation {saturation_score:.2f}, fatigue {fatigue_score:.2f}, "
        f"originality {originality_score:.2f}. "
        f"Topic overlap {topic_overlap:.0%}, posting rate {posting_rate:.1f}/day. "
        f"Action: {action}."
    )

    return SaturationResult(
        saturation_score=round(saturation_score, 4),
        fatigue_score=round(fatigue_score, 4),
        originality_score=round(originality_score, 4),
        topic_overlap_pct=round(topic_overlap, 4),
        audience_overlap_pct=round(min(inp.audience_overlap_pct, 1.0), 4),
        recommended_action=action,
        explanation=explanation,
    )
