"""Offer fit scoring engine.

Evaluates how well a specific offer matches a specific topic candidate
for a specific brand's audience. Deterministic, rules-based.
"""
from __future__ import annotations

from dataclasses import dataclass

FORMULA_VERSION = "v1"


@dataclass
class OfferFitInput:
    topic_keywords: list[str]
    offer_audience_tags: list[str]
    offer_epc: float = 0.0
    offer_conversion_rate: float = 0.0
    offer_payout: float = 0.0
    brand_niche: str = ""
    offer_niche_relevance: float = 0.5
    topic_buyer_intent: float = 0.0
    platform: str = ""
    offer_platform_restrictions: list[str] | None = None


@dataclass
class OfferFitResult:
    fit_score: float
    audience_alignment: float
    intent_match: float
    friction_score: float
    repeatability_score: float
    revenue_potential: float
    confidence: str
    explanation: str
    formula_version: str = FORMULA_VERSION


def _keyword_overlap(topic_kw: list[str], offer_tags: list[str]) -> float:
    if not topic_kw or not offer_tags:
        return 0.0
    t_set = {k.lower().strip() for k in topic_kw}
    o_set = {k.lower().strip() for k in offer_tags}
    if not t_set or not o_set:
        return 0.0
    overlap = len(t_set & o_set)
    return min(overlap / max(len(o_set), 1), 1.0)


def compute_offer_fit(inp: OfferFitInput) -> OfferFitResult:
    audience_alignment = _keyword_overlap(inp.topic_keywords, inp.offer_audience_tags)
    audience_alignment = max(audience_alignment, inp.offer_niche_relevance * 0.5)
    audience_alignment = min(audience_alignment, 1.0)

    intent_match = min(inp.topic_buyer_intent, 1.0)

    if inp.offer_platform_restrictions and inp.platform:
        if inp.platform.lower() not in [p.lower() for p in inp.offer_platform_restrictions]:
            friction_score = 0.8
        else:
            friction_score = 0.1
    else:
        friction_score = 0.2

    repeatability_score = 0.5
    if inp.offer_conversion_rate > 0.05:
        repeatability_score += 0.2
    if inp.offer_epc > 2.0:
        repeatability_score += 0.15
    if inp.offer_payout > 30:
        repeatability_score += 0.15
    repeatability_score = min(repeatability_score, 1.0)

    rev_potential = 0.0
    if inp.offer_epc > 0:
        rev_potential += min(inp.offer_epc / 5.0, 0.4)
    if inp.offer_payout > 0:
        rev_potential += min(inp.offer_payout / 100.0, 0.3)
    if inp.offer_conversion_rate > 0:
        rev_potential += min(inp.offer_conversion_rate / 0.10, 0.3)
    revenue_potential = min(rev_potential, 1.0)

    fit_score = (
        0.25 * audience_alignment
        + 0.20 * intent_match
        + 0.15 * (1.0 - friction_score)
        + 0.15 * repeatability_score
        + 0.25 * revenue_potential
    )

    signal_count = sum(1 for v in [audience_alignment, intent_match, revenue_potential] if v > 0.1)
    if signal_count >= 3 and fit_score > 0.5:
        confidence = "high"
    elif signal_count >= 2:
        confidence = "medium"
    elif signal_count >= 1:
        confidence = "low"
    else:
        confidence = "insufficient"

    explanation = (
        f"Fit score {fit_score:.3f}: audience_alignment={audience_alignment:.2f}, "
        f"intent_match={intent_match:.2f}, friction={friction_score:.2f}, "
        f"repeatability={repeatability_score:.2f}, revenue_potential={revenue_potential:.2f}."
    )

    return OfferFitResult(
        fit_score=round(fit_score, 4),
        audience_alignment=round(audience_alignment, 4),
        intent_match=round(intent_match, 4),
        friction_score=round(friction_score, 4),
        repeatability_score=round(repeatability_score, 4),
        revenue_potential=round(revenue_potential, 4),
        confidence=confidence,
        explanation=explanation,
    )
