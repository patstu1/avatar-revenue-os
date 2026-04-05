"""Deal Desk Engine — recommend deal strategy, pricing stance, and packaging."""
from __future__ import annotations

from typing import Any

DEAL_DESK = "deal_desk_engine"

STRATEGIES = [
    "custom_quote", "package_standard", "bundle_discount", "hold_price",
    "strategic_discount", "push_upsell", "nurture_sequence", "require_human_approval",
]

PRICING_STANCES = ["premium", "competitive", "penetration", "hold"]


def _score_deal_context(deal_context: dict[str, Any]) -> dict[str, float]:
    """Normalize deal signals to 0..1 scores."""
    deal_value = float(deal_context.get("deal_value", 0))
    lead_quality = float(deal_context.get("lead_quality", 0.5))
    urgency = float(deal_context.get("urgency", 0.5))
    competition = float(deal_context.get("competition_intensity", 0.5))

    value_score = 0.75 if deal_value > 0 else 0.0  # Any deal has value; scoring uses other signals
    return {
        "value_score": round(value_score, 3),
        "lead_quality": round(min(1.0, max(0.0, lead_quality)), 3),
        "urgency": round(min(1.0, max(0.0, urgency)), 3),
        "competition": round(min(1.0, max(0.0, competition)), 3),
    }


def _select_strategy(scores: dict[str, float], authority: float) -> str:
    value = scores["value_score"]
    quality = scores["lead_quality"]
    urgency = scores["urgency"]
    competition = scores["competition"]

    if value > 0.8 and quality > 0.7:
        return "custom_quote"
    if competition > 0.75 and urgency > 0.6:
        return "strategic_discount"
    if quality < 0.3:
        return "nurture_sequence"
    if value > 0.6 and authority > 0.7:
        return "hold_price"
    if value > 0.5:
        return "push_upsell"
    if quality > 0.6 and value > 0.3:
        return "bundle_discount"
    if value > 0.7 and quality < 0.5:
        return "require_human_approval"
    return "package_standard"


def _select_pricing_stance(
    strategy: str, competition: float, authority: float
) -> str:
    if strategy in ("custom_quote", "hold_price") and authority > 0.6:
        return "premium"
    if strategy == "strategic_discount" or competition > 0.7:
        return "competitive"
    if strategy == "nurture_sequence":
        return "penetration"
    return "hold"


def _build_packaging(
    strategy: str, deal_value: float, niche: str
) -> dict[str, Any]:
    """Construct packaging recommendation based on strategy."""
    if strategy == "custom_quote":
        return {
            "items": [
                {"name": f"Custom {niche} package", "type": "core"},
                {"name": "Priority onboarding", "type": "addon"},
                {"name": "Dedicated account manager", "type": "addon"},
            ],
            "terms": "net-30",
            "discount_pct": 0.0,
        }
    if strategy == "bundle_discount":
        return {
            "items": [
                {"name": f"{niche} starter bundle", "type": "core"},
                {"name": "Complementary analytics", "type": "addon"},
            ],
            "terms": "net-15",
            "discount_pct": 0.12,
        }
    if strategy == "strategic_discount":
        return {
            "items": [
                {"name": f"{niche} competitive pack", "type": "core"},
            ],
            "terms": "net-15",
            "discount_pct": 0.18,
        }
    if strategy == "push_upsell":
        return {
            "items": [
                {"name": f"{niche} base package", "type": "core"},
                {"name": "Premium upgrade", "type": "upsell"},
                {"name": "Annual commitment bonus", "type": "incentive"},
            ],
            "terms": "net-30",
            "discount_pct": 0.0,
        }
    return {
        "items": [{"name": f"{niche} standard package", "type": "core"}],
        "terms": "net-30",
        "discount_pct": 0.0,
    }


def recommend_deal_strategy(
    deal_context: dict[str, Any],
    brand_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Recommend deal strategy, pricing stance, and packaging.

    Parameters
    ----------
    deal_context:
        Dict with deal-level signals.
        Expected keys: deal_value, lead_quality (0-1), urgency (0-1),
        competition_intensity (0-1), niche, scope_type, scope_id.
    brand_metrics:
        Dict with brand-level authority and performance.
        Expected keys: brand_authority_score (0-1), avg_margin,
        avg_close_rate, niche.

    Returns
    -------
    dict with deal_strategy, pricing_stance, packaging_recommendation,
    expected_margin, expected_close_probability, confidence, explanation.
    """
    scores = _score_deal_context(deal_context)
    authority = float(brand_metrics.get("brand_authority_score", 0.5))
    avg_margin = float(brand_metrics.get("avg_margin", 0.35))
    avg_close = float(brand_metrics.get("avg_close_rate", 0.25))
    niche = deal_context.get("niche") or brand_metrics.get("niche", "general")
    deal_value = float(deal_context.get("deal_value", 0))

    strategy = _select_strategy(scores, authority)
    pricing_stance = _select_pricing_stance(strategy, scores["competition"], authority)
    packaging = _build_packaging(strategy, deal_value, niche)

    margin_adj = {
        "premium": 0.08, "competitive": -0.05,
        "penetration": -0.12, "hold": 0.0,
    }
    expected_margin = round(
        min(0.95, max(0.05, avg_margin + margin_adj.get(pricing_stance, 0.0))), 3
    )

    close_adj = {
        "custom_quote": 0.10, "strategic_discount": 0.12,
        "bundle_discount": 0.08, "push_upsell": 0.05,
        "hold_price": 0.0, "package_standard": 0.03,
        "nurture_sequence": -0.05, "require_human_approval": -0.03,
    }
    expected_close = round(
        min(0.95, max(0.05, avg_close + close_adj.get(strategy, 0.0))), 3
    )

    confidence = round(
        min(0.95, 0.40 + scores["lead_quality"] * 0.25 + authority * 0.15 + scores["value_score"] * 0.10),
        3,
    )

    explanation_parts = [
        f"Strategy: {strategy.replace('_', ' ')} based on deal value ${deal_value:,.0f}",
        f"lead quality {scores['lead_quality']:.2f}",
        f"authority {authority:.2f}",
        f"competition {scores['competition']:.2f}.",
        f"Pricing stance: {pricing_stance}.",
        f"Expected margin {expected_margin:.1%}, close probability {expected_close:.1%}.",
    ]

    return {
        "deal_strategy": strategy,
        "pricing_stance": pricing_stance,
        "packaging_recommendation": packaging,
        "expected_margin": expected_margin,
        "expected_close_probability": expected_close,
        "confidence": confidence,
        "explanation": " ".join(explanation_parts),
        DEAL_DESK: True,
    }
