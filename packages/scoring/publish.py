"""Publish readiness scoring engine.

PublishScore =
  0.15 * HookStrength + 0.15 * MonetizationFit + 0.14 * Originality +
  0.14 * Compliance + 0.10 * RetentionLikelihood + 0.08 * CTAClarity +
  0.08 * BrandConsistency + 0.06 * ThumbnailCTRPrediction + 0.10 * ExpectedProfitScore
"""

from dataclasses import dataclass

FORMULA_VERSION = "v1"

WEIGHTS = {
    "hook_strength": 0.15,
    "monetization_fit": 0.15,
    "originality": 0.14,
    "compliance": 0.14,
    "retention_likelihood": 0.10,
    "cta_clarity": 0.08,
    "brand_consistency": 0.08,
    "thumbnail_ctr_prediction": 0.06,
    "expected_profit_score": 0.10,
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


@dataclass
class PublishScoreInput:
    hook_strength: float = 0.0
    monetization_fit: float = 0.0
    originality: float = 0.0
    compliance: float = 0.0
    retention_likelihood: float = 0.0
    cta_clarity: float = 0.0
    brand_consistency: float = 0.0
    thumbnail_ctr_prediction: float = 0.0
    expected_profit_score: float = 0.0


@dataclass
class PublishScoreResult:
    composite_score: float
    weighted_components: dict[str, float]
    confidence: str
    publish_ready: bool
    blocking_issues: list[str]
    explanation: str
    formula_version: str = FORMULA_VERSION


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def compute_publish_score(inp: PublishScoreInput) -> PublishScoreResult:
    components = {k: _clamp(getattr(inp, k)) for k in WEIGHTS}
    weighted = {k: components[k] * WEIGHTS[k] for k in components}
    composite = sum(weighted.values())

    blockers = []
    if components["compliance"] < 0.5:
        blockers.append("Compliance score below threshold (missing disclosures or sponsor metadata)")
    if components["originality"] < 0.4:
        blockers.append("Low originality — force rewrite or guarded review path")

    signal_count = sum(1 for v in components.values() if v > 0.1)
    if signal_count >= 7 and composite > 0.6:
        confidence = "high"
    elif signal_count >= 4:
        confidence = "medium"
    elif signal_count >= 1:
        confidence = "low"
    else:
        confidence = "insufficient"

    publish_ready = len(blockers) == 0 and composite >= 0.5

    top = sorted(weighted.items(), key=lambda x: -x[1])[:3]
    explanation = f"Publish score {composite:.3f}. Top: {', '.join(f'{k}={v:.3f}' for k, v in top)}."
    if blockers:
        explanation += f" BLOCKED: {'; '.join(blockers)}."
    if not publish_ready and not blockers:
        explanation += " Score below publish threshold (0.5)."

    return PublishScoreResult(
        composite_score=round(composite, 4),
        weighted_components=weighted,
        confidence=confidence,
        publish_ready=publish_ready,
        blocking_issues=blockers,
        explanation=explanation,
    )
