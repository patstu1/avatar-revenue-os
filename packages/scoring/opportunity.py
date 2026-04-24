"""Opportunity scoring engine.

Formula (v1):
  OpportunityScore =
    0.22 * BuyerIntent + 0.10 * TrendVelocity + 0.08 * TrendAcceleration +
    0.10 * ContentGap + 0.12 * HistoricalWinRate + 0.12 * OfferFit +
    0.18 * ExpectedProfitScore + 0.08 * PlatformSuitability
  + SeasonalBoost + BrandFitBoost
  - AudienceFatiguePenalty - SimilarityPenalty - SaturationPenalty - RiskPenalty

All component scores normalized to [0, 1]. Penalties in [0, 0.3].
"""
from dataclasses import dataclass

FORMULA_VERSION = "v1"

WEIGHTS = {
    "buyer_intent": 0.22,
    "trend_velocity": 0.10,
    "trend_acceleration": 0.08,
    "content_gap": 0.10,
    "historical_win_rate": 0.12,
    "offer_fit": 0.12,
    "expected_profit_score": 0.18,
    "platform_suitability": 0.08,
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"


@dataclass
class OpportunityInput:
    buyer_intent: float = 0.0
    trend_velocity: float = 0.0
    trend_acceleration: float = 0.0
    content_gap: float = 0.0
    historical_win_rate: float = 0.0
    offer_fit: float = 0.0
    expected_profit_score: float = 0.0
    platform_suitability: float = 0.0

    seasonal_boost: float = 0.0
    brand_fit_boost: float = 0.0

    audience_fatigue_penalty: float = 0.0
    similarity_penalty: float = 0.0
    saturation_penalty: float = 0.0
    risk_penalty: float = 0.0


@dataclass
class OpportunityResult:
    composite_score: float
    weighted_components: dict[str, float]
    boosts: dict[str, float]
    penalties: dict[str, float]
    raw_base: float
    confidence: str
    explanation: str
    formula_version: str = FORMULA_VERSION


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def compute_opportunity_score(inp: OpportunityInput) -> OpportunityResult:
    components = {
        "buyer_intent": _clamp(inp.buyer_intent),
        "trend_velocity": _clamp(inp.trend_velocity),
        "trend_acceleration": _clamp(inp.trend_acceleration),
        "content_gap": _clamp(inp.content_gap),
        "historical_win_rate": _clamp(inp.historical_win_rate),
        "offer_fit": _clamp(inp.offer_fit),
        "expected_profit_score": _clamp(inp.expected_profit_score),
        "platform_suitability": _clamp(inp.platform_suitability),
    }

    weighted = {k: components[k] * WEIGHTS[k] for k in components}
    base = sum(weighted.values())

    boosts = {
        "seasonal_boost": _clamp(inp.seasonal_boost, 0.0, 0.15),
        "brand_fit_boost": _clamp(inp.brand_fit_boost, 0.0, 0.10),
    }

    penalties = {
        "audience_fatigue_penalty": _clamp(inp.audience_fatigue_penalty, 0.0, 0.30),
        "similarity_penalty": _clamp(inp.similarity_penalty, 0.0, 0.30),
        "saturation_penalty": _clamp(inp.saturation_penalty, 0.0, 0.30),
        "risk_penalty": _clamp(inp.risk_penalty, 0.0, 0.20),
    }

    total_boosts = sum(boosts.values())
    total_penalties = sum(penalties.values())
    composite = _clamp(base + total_boosts - total_penalties)

    signal_count = sum(1 for v in components.values() if v > 0.1)
    if signal_count >= 6 and composite > 0.6:
        confidence = "high"
    elif signal_count >= 3 and composite > 0.3:
        confidence = "medium"
    elif signal_count >= 1:
        confidence = "low"
    else:
        confidence = "insufficient"

    top_drivers = sorted(weighted.items(), key=lambda x: -x[1])[:3]
    drivers_text = ", ".join(f"{k}={v:.3f}" for k, v in top_drivers)
    penalty_text = ", ".join(f"{k}={v:.3f}" for k, v in penalties.items() if v > 0)

    explanation = f"Score {composite:.3f} (base={base:.3f}). Top drivers: {drivers_text}."
    if penalty_text:
        explanation += f" Penalties: {penalty_text}."
    if confidence == "insufficient":
        explanation += " Insufficient signal — classify as monitor."

    return OpportunityResult(
        composite_score=composite,
        weighted_components=weighted,
        boosts=boosts,
        penalties=penalties,
        raw_base=base,
        confidence=confidence,
        explanation=explanation,
    )
