"""Offer fit scoring engine — ProofHook Revenue-Ops formula.

Evaluates how well a specific package offer matches a specific lead or
inbound signal set. Deterministic, rules-based, no audience metrics.

DOCTRINE — Revenue-Ops formula:
    ProofHook sells packaged creative services to brands. Fit is determined
    by lead intent, package routing efficiency, commercial friction, repeat
    potential, and revenue ceiling — NOT by audience_alignment (which was
    a creator-economy metric for content monetization).

    The weighting is:
        0.30 * intent_match        — does the lead signal a real package need?
        0.25 * package_routing     — does this package match the best-fit slug?
        0.20 * (1 - friction)      — how easy is it to close without calls / custom scoping?
        0.15 * repeatability       — does this generate upsell / repeat revenue?
        0.10 * revenue_potential   — what's the absolute revenue ceiling?

    Notes on the legacy fields:
      • OfferFitInput still accepts `offer_audience_tags` and `brand_niche`
        for backward compatibility with existing callers, but they are
        NOT used in the scoring. The audience_alignment field in the
        output is always 0.0 and exists only so older code that unpacks
        it doesn't crash.
      • `topic_keywords` is reinterpreted as "lead signal keywords" — the
        signals extracted from the inbound message via package_recommender.
"""
from __future__ import annotations

from dataclasses import dataclass

FORMULA_VERSION = "v2-revenue-ops"


@dataclass
class OfferFitInput:
    # Lead signals (from package_recommender or classifier)
    topic_keywords: list[str]          # reinterpreted as "lead signal keywords"
    offer_audience_tags: list[str]     # LEGACY — kept for call-site compat, unused
    offer_epc: float = 0.0             # LEGACY — unused
    offer_conversion_rate: float = 0.0 # LEGACY — unused
    offer_payout: float = 0.0          # LEGACY — unused
    brand_niche: str = ""              # LEGACY — unused
    offer_niche_relevance: float = 0.5 # LEGACY — unused
    topic_buyer_intent: float = 0.0    # real input: lead intent score

    # Revenue-Ops inputs (new)
    package_slug: str = ""             # the candidate package
    recommended_slug: str = ""         # what package_recommender picked
    package_price: float = 0.0         # absolute revenue ceiling
    is_recurring: bool = False         # monthly vs one-time
    is_retainer: bool = False          # full retainer path
    requires_call_to_close: bool = False  # friction signal
    requires_custom_scoping: bool = False  # friction signal

    # Legacy platform fields (unused in scoring, kept for back-compat)
    platform: str = ""
    offer_platform_restrictions: list[str] | None = None


@dataclass
class OfferFitResult:
    fit_score: float
    audience_alignment: float          # ALWAYS 0.0 under new formula
    intent_match: float
    friction_score: float
    repeatability_score: float
    revenue_potential: float
    package_routing_match: float       # NEW: does this match the recommender?
    confidence: str
    explanation: str
    formula_version: str = FORMULA_VERSION


def compute_offer_fit(inp: OfferFitInput) -> OfferFitResult:
    """Compute package fit score using the Revenue-Ops formula.

    Scoring weights:
        0.30 intent_match
        0.25 package_routing_match
        0.20 (1 - friction_score)
        0.15 repeatability_score
        0.10 revenue_potential
        0.00 audience_alignment   (removed from formula, always 0.0)
    """
    # ── Intent match — how strong is the buyer-intent signal? ─────────────
    intent_match = min(max(inp.topic_buyer_intent, 0.0), 1.0)

    # ── Package routing match — does this offer align with the recommender's pick? ─
    if inp.package_slug and inp.recommended_slug:
        package_routing_match = 1.0 if inp.package_slug == inp.recommended_slug else 0.3
    elif inp.package_slug:
        package_routing_match = 0.6  # no recommender input, neutral fit
    else:
        package_routing_match = 0.4

    # ── Friction — anything that requires a call / custom scoping is high friction ─
    friction = 0.1  # baseline (no friction)
    if inp.requires_call_to_close:
        friction += 0.4
    if inp.requires_custom_scoping:
        friction += 0.4
    friction = min(friction, 1.0)

    # ── Repeatability — recurring / retainer packages repeat revenue ──────
    if inp.is_retainer:
        repeatability_score = 1.0
    elif inp.is_recurring:
        repeatability_score = 0.85
    else:
        repeatability_score = 0.40  # one-time packages still generate upsells

    # ── Revenue potential — scaled against a $10k/mo ceiling ──────────────
    if inp.package_price > 0:
        revenue_potential = min(inp.package_price / 10000.0, 1.0)
    else:
        revenue_potential = 0.2  # unknown price defaults to low

    # ── Final fit score — Revenue-Ops weighted sum, NO audience weight ────
    fit_score = (
        0.30 * intent_match
        + 0.25 * package_routing_match
        + 0.20 * (1.0 - friction)
        + 0.15 * repeatability_score
        + 0.10 * revenue_potential
    )

    # Confidence: number of non-trivial signals
    signal_count = sum(
        1 for v in [intent_match, package_routing_match, repeatability_score, revenue_potential]
        if v > 0.3
    )
    if signal_count >= 3 and fit_score > 0.55:
        confidence = "high"
    elif signal_count >= 2:
        confidence = "medium"
    elif signal_count >= 1:
        confidence = "low"
    else:
        confidence = "insufficient"

    explanation = (
        f"Fit {fit_score:.3f} [v2-revenue-ops]: intent={intent_match:.2f}, "
        f"package_routing={package_routing_match:.2f}, friction={friction:.2f}, "
        f"repeatability={repeatability_score:.2f}, revenue_potential={revenue_potential:.2f}. "
        f"audience_alignment is removed from the formula (weight=0)."
    )

    return OfferFitResult(
        fit_score=round(fit_score, 4),
        audience_alignment=0.0,  # always zero — removed from formula
        intent_match=round(intent_match, 4),
        friction_score=round(friction, 4),
        repeatability_score=round(repeatability_score, 4),
        revenue_potential=round(revenue_potential, 4),
        package_routing_match=round(package_routing_match, 4),
        confidence=confidence,
        explanation=explanation,
    )
