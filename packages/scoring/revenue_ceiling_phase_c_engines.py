"""Revenue Ceiling Phase C — recurring revenue, sponsor inventory, trust conversion,
monetization mix, paid promotion gate (pure functions, no I/O, no SQLAlchemy)."""
from __future__ import annotations

import math
from typing import Any

RC_PHASE_C = "revenue_ceiling_phase_c"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RECURRING_OFFER_TYPES = ["newsletter", "membership", "saas_tool", "coaching_retainer", "community"]

NICHE_RECURRING_AFFINITY: dict[str, float] = {
    "tech": 0.1, "technology": 0.1, "software": 0.1, "saas": 0.1,
    "finance": 0.1, "fintech": 0.1, "investing": 0.1, "trading": 0.1,
    "health": 0.1, "wellness": 0.1, "fitness": 0.1, "nutrition": 0.1,
}

NICHE_SPONSOR_CATEGORY: dict[str, str] = {
    "finance": "fintech", "fintech": "fintech", "investing": "fintech", "trading": "fintech",
    "health": "health_wellness", "wellness": "health_wellness",
    "fitness": "health_wellness", "nutrition": "health_wellness",
    "tech": "b2b_saas", "technology": "b2b_saas", "software": "b2b_saas", "saas": "b2b_saas",
    "ecommerce": "ecommerce", "shopping": "ecommerce", "retail": "ecommerce",
    "education": "edtech", "learning": "edtech", "course": "edtech",
    "gaming": "gaming", "esports": "gaming",
    "travel": "travel_lifestyle", "lifestyle": "travel_lifestyle",
    "beauty": "beauty_personal_care", "skincare": "beauty_personal_care", "makeup": "beauty_personal_care",
    "food": "food_beverage", "cooking": "food_beverage",
}

CONTENT_TYPE_BASE_RATES: dict[str, float] = {
    "long_form": 500.0,
    "short_form": 200.0,
    "podcast": 800.0,
    "article": 150.0,
}

CONTENT_TYPE_SPONSOR_BONUS: dict[str, float] = {
    "long_form": 0.10,
    "podcast": 0.15,
    "short_form": 0.0,
    "article": 0.0,
}

KNOWN_METHODS = [
    "affiliate", "sponsorship", "digital_product", "membership",
    "coaching", "ads", "email_list",
]

_METHOD_POTENTIAL_SCORES: dict[str, float] = {
    "affiliate": 0.65,
    "sponsorship": 0.72,
    "digital_product": 0.80,
    "membership": 0.78,
    "coaching": 0.85,
    "ads": 0.45,
    "email_list": 0.70,
}

_METHOD_RATIONALES: dict[str, str] = {
    "affiliate": "Low barrier; complements content with passive commissions",
    "sponsorship": "High CPM leverage; sponsor packages can 3–5x ad revenue",
    "digital_product": "High margin, one-time build; scales linearly with audience",
    "membership": "Predictable MRR; deepens community loyalty and LTV",
    "coaching": "Highest AOV; converts trust capital directly into revenue",
    "ads": "Passive income on existing content inventory; scales with impressions",
    "email_list": "Owned channel; highest long-term conversion leverage",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _h(s: str) -> int:
    """Deterministic hash bucket (0–999), stable across processes."""
    import hashlib
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16) % 1000


def _log_norm(value: float, scale: float = 6.0) -> float:
    """Log10-normalise a large integer to [0, 1].  1 000 000 → 1.0 at scale=6."""
    return min(1.0, math.log10(max(1.0, float(value))) / scale)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _niche_affinity(niche: str) -> float:
    """Return +0.10 bonus for high-recurring niches, else 0.0."""
    return NICHE_RECURRING_AFFINITY.get(niche.lower().strip(), 0.0)


def _sponsor_category(niche: str) -> str:
    return NICHE_SPONSOR_CATEGORY.get(niche.lower().strip(), "general")


# ---------------------------------------------------------------------------
# Recurring Revenue Engine
# ---------------------------------------------------------------------------

def score_recurring_revenue(
    brand_niche: str,
    offers: list[dict],
    audience_size: int,
    avg_content_engagement_rate: float,
    existing_recurring_products: list[str],
) -> dict[str, Any]:
    """Score recurring revenue potential and recommend the best offer type.

    Returns:
        recurring_potential_score: float 0..1
        best_recurring_offer_type: str  (newsletter | membership | saas_tool | coaching_retainer | community)
        audience_fit: float 0..1
        churn_risk_proxy: float 0..1
        expected_monthly_value: float
        expected_annual_value: float
        confidence: float 0..1
        explanation: str
        RC_PHASE_C: True
    """
    # --- audience signal: log-normalised, 1 M audience → 1.0 ---
    audience_signal = _log_norm(audience_size, scale=6.0)

    # --- engagement signal: 5 % engagement → 1.0 ---
    engagement_signal = _clamp(avg_content_engagement_rate * 20.0)

    # --- niche affinity bonus (+0.10 for tech / finance / health) ---
    niche_bonus = _niche_affinity(brand_niche)

    # --- recurring potential score ---
    raw_potential = (
        0.40 * audience_signal
        + 0.40 * engagement_signal
        + 0.20 * _clamp(engagement_signal + niche_bonus)
    )
    recurring_potential_score = round(_clamp(raw_potential + niche_bonus), 3)

    # --- audience fit ---
    audience_fit = round(_clamp(0.50 * audience_signal + 0.50 * engagement_signal), 3)

    # --- churn risk proxy: inverse of engagement, capped 0.10..0.90 ---
    raw_churn = 1.0 - _clamp(avg_content_engagement_rate * 12.0)
    churn_risk_proxy = round(_clamp(raw_churn, 0.10, 0.90), 3)

    # --- best recurring offer type (exclude already-used types) ---
    existing = list(existing_recurring_products or [])
    available = [t for t in RECURRING_OFFER_TYPES if t not in existing]
    if not available:
        available = RECURRING_OFFER_TYPES[:]
    best_recurring_offer_type = available[_h(brand_niche.lower()) % len(available)]

    # --- average payout from live offers (default $9.97) ---
    payout_amounts = [
        float(o.get("payout_amount", 0) or 0)
        for o in (offers or [])
        if float(o.get("payout_amount", 0) or 0) > 0
    ]
    avg_payout = (sum(payout_amounts) / len(payout_amounts)) if payout_amounts else 9.97

    # --- expected values ---
    expected_monthly_value = round(
        recurring_potential_score * float(max(0, audience_size)) * 0.002 * avg_payout, 2
    )
    expected_annual_value = round(
        expected_monthly_value * 12.0 * (1.0 - churn_risk_proxy * 0.5), 2
    )

    # --- confidence ---
    data_richness = _clamp(len(offers) / 5.0) if offers else 0.10
    confidence = round(_clamp(0.40 + recurring_potential_score * 0.35 + data_richness * 0.25), 3)

    explanation = (
        f"Niche '{brand_niche}' — audience signal {audience_signal:.2f}, "
        f"engagement signal {engagement_signal:.2f}, niche bonus {niche_bonus:.2f}. "
        f"Best offer type '{best_recurring_offer_type}' selected from "
        f"{len(available)} available (excluding existing: {existing or ['none']}). "
        f"Avg payout ${avg_payout:.2f}; churn proxy {churn_risk_proxy:.2f}."
    )

    return {
        "recurring_potential_score": recurring_potential_score,
        "best_recurring_offer_type": best_recurring_offer_type,
        "audience_fit": audience_fit,
        "churn_risk_proxy": churn_risk_proxy,
        "expected_monthly_value": expected_monthly_value,
        "expected_annual_value": expected_annual_value,
        "confidence": confidence,
        "explanation": explanation,
        RC_PHASE_C: True,
    }


# ---------------------------------------------------------------------------
# Sponsor Inventory Engine
# ---------------------------------------------------------------------------

def score_sponsor_inventory_item(
    content_item_id: str,
    content_title: str,
    niche: str,
    impressions: int,
    engagement_rate: float,
    audience_size: int,
    content_type: str,
) -> dict[str, Any]:
    """Score a single content item as a sponsor inventory unit.

    Returns:
        content_item_id: str
        sponsor_fit_score: float 0..1
        estimated_package_price: float
        sponsor_category: str
        confidence: float 0..1
        explanation: str
        RC_PHASE_C: True
    """
    # --- impressions signal: log-normalised, 1 M → 1.0 ---
    impressions_signal = _log_norm(impressions, scale=6.0)

    # --- engagement signal: 5 % → 1.0 ---
    engagement_signal = _clamp(engagement_rate * 20.0)

    # --- content type sponsor bonus ---
    type_bonus = CONTENT_TYPE_SPONSOR_BONUS.get(content_type, 0.0)

    # --- sponsor fit score ---
    raw_fit = 0.45 * impressions_signal + 0.40 * engagement_signal + type_bonus
    sponsor_fit_score = round(_clamp(raw_fit), 3)

    # --- impressions tier multiplier ---
    if impressions >= 500_000:
        tier_mult = 3.0
    elif impressions >= 100_000:
        tier_mult = 2.0
    elif impressions >= 50_000:
        tier_mult = 1.5
    elif impressions >= 10_000:
        tier_mult = 1.0
    else:
        tier_mult = 0.5

    # --- engagement multiplier: 10 % engagement → 2.0x ---
    eng_mult = 1.0 + _clamp(engagement_rate * 10.0)

    # --- estimated package price ---
    base_rate = CONTENT_TYPE_BASE_RATES.get(content_type, 200.0)
    estimated_package_price = round(base_rate * tier_mult * eng_mult, 2)

    # --- sponsor category ---
    sponsor_category = _sponsor_category(niche)

    # --- confidence ---
    confidence = round(
        _clamp(0.35 + sponsor_fit_score * 0.45 + 0.20 * _clamp(impressions / 100_000.0)), 3
    )

    explanation = (
        f"Content '{content_title[:60]}' ({content_type}) — "
        f"impressions signal {impressions_signal:.2f}, engagement signal {engagement_signal:.2f}, "
        f"type bonus {type_bonus:.2f}. Tier mult {tier_mult:.1f}x, eng mult {eng_mult:.2f}x. "
        f"Estimated package: ${estimated_package_price:,.2f} (category: {sponsor_category})."
    )

    return {
        "content_item_id": content_item_id,
        "sponsor_fit_score": sponsor_fit_score,
        "estimated_package_price": estimated_package_price,
        "sponsor_category": sponsor_category,
        "confidence": confidence,
        "explanation": explanation,
        RC_PHASE_C: True,
    }


def _build_deliverables(niche: str, inventory: list[dict]) -> list[str]:
    """Build a realistic deliverables list from inventory content types."""
    deliverables: list[str] = []
    seen: set[str] = set()
    type_labels: dict[str, str] = {
        "long_form": f"1x long-form {niche} video with integrated sponsor segment",
        "short_form": f"2x short-form {niche} clips with sponsor mention",
        "podcast": "1x podcast episode with host-read sponsor spot",
        "article": f"1x sponsored {niche} article with editorial mention",
    }
    for item in inventory[:5]:
        ctype = item.get("content_type", "")
        if ctype and ctype not in seen:
            seen.add(ctype)
            deliverables.append(
                type_labels.get(ctype, f"1x {ctype} content placement for {niche}")
            )
    if not deliverables:
        deliverables = [
            f"3x branded content pieces in the {niche} niche",
            "Dedicated newsletter sponsor feature",
            "Social media amplification across active channels",
        ]
    deliverables.append("Post-campaign analytics report with performance summary")
    return deliverables


def score_sponsor_package(
    brand_niche: str,
    total_audience: int,
    avg_monthly_impressions: int,
    avg_engagement_rate: float,
    available_inventory: list[dict],
) -> dict[str, Any]:
    """Aggregate sponsor inventory into a recommended sponsor package.

    Returns:
        recommended_package: dict  {name, deliverables, duration_weeks, exclusivity}
        sponsor_fit_score: float
        estimated_package_price: float
        sponsor_category: str
        confidence: float
        explanation: str
        RC_PHASE_C: True
    """
    n_inventory = len(available_inventory)

    # --- aggregate signals from inventory ---
    if available_inventory:
        avg_fit = sum(i.get("sponsor_fit_score", 0.0) for i in available_inventory) / n_inventory
        total_item_price = sum(i.get("estimated_package_price", 0.0) for i in available_inventory)
        categories = [i.get("sponsor_category", "general") for i in available_inventory]
        sponsor_category = max(set(categories), key=categories.count)
    else:
        avg_fit = 0.30
        total_item_price = 0.0
        sponsor_category = _sponsor_category(brand_niche)

    # --- brand-level signals ---
    audience_signal = _log_norm(total_audience, scale=6.0)
    impressions_signal = _log_norm(avg_monthly_impressions, scale=6.0)
    engagement_signal = _clamp(avg_engagement_rate * 20.0)

    sponsor_fit_score = round(
        _clamp(
            0.35 * avg_fit
            + 0.30 * audience_signal
            + 0.20 * impressions_signal
            + 0.15 * engagement_signal
        ),
        3,
    )

    # --- package price: item sum or CPM floor, boosted by fit ---
    cpm_floor = float(avg_monthly_impressions) * 0.005  # $5 CPM floor
    base_price = max(total_item_price, cpm_floor)
    estimated_package_price = round(base_price * (1.0 + sponsor_fit_score * 0.50), 2)

    # --- recommended package structure ---
    duration_weeks = 4 if n_inventory <= 3 else (8 if n_inventory <= 8 else 12)
    exclusivity = sponsor_fit_score > 0.65
    deliverables = _build_deliverables(brand_niche, available_inventory)
    pkg_name = (
        f"{brand_niche.title()} × {sponsor_category.replace('_', ' ').title()} Sponsor Package"
    )
    recommended_package = {
        "name": pkg_name,
        "deliverables": deliverables,
        "duration_weeks": duration_weeks,
        "exclusivity": exclusivity,
    }

    # --- confidence ---
    confidence = round(
        _clamp(0.40 + sponsor_fit_score * 0.35 + min(0.25, n_inventory / 20.0)), 3
    )

    explanation = (
        f"Brand '{brand_niche}' — {n_inventory} inventory items, avg item fit {avg_fit:.2f}. "
        f"Audience {total_audience:,}, monthly impressions {avg_monthly_impressions:,}. "
        f"Package: {duration_weeks}w, exclusivity={exclusivity}, "
        f"category='{sponsor_category}'. "
        f"Price: ${estimated_package_price:,.2f}."
    )

    return {
        "recommended_package": recommended_package,
        "sponsor_fit_score": sponsor_fit_score,
        "estimated_package_price": estimated_package_price,
        "sponsor_category": sponsor_category,
        "confidence": confidence,
        "explanation": explanation,
        RC_PHASE_C: True,
    }


# ---------------------------------------------------------------------------
# Trust Conversion Engine
# ---------------------------------------------------------------------------

def score_trust_conversion(
    brand_niche: str,
    has_testimonials: bool,
    has_case_studies: bool,
    has_social_proof_count: int,
    has_media_features: bool,
    has_certifications: bool,
    content_item_count: int,
    avg_quality_score: float,
    offer_conversion_rate: float,
) -> dict[str, Any]:
    """Compute trust deficit and recommended proof blocks for conversion uplift.

    Returns:
        trust_deficit_score: float 0..1  (higher = bigger deficit)
        recommended_proof_blocks: list[dict]  each: {type, priority, action}
        missing_trust_elements: list[str]
        expected_uplift: float  (fractional, e.g. 0.08 = +8 % conversion lift)
        confidence: float 0..1
        explanation: str
        RC_PHASE_C: True
    """
    # --- trust deficit: start at 1.0, subtract for each present element ---
    deficit = 1.0
    if has_testimonials:
        deficit -= 0.15
    if has_case_studies:
        deficit -= 0.20
    if has_social_proof_count >= 5:
        deficit -= 0.10
    if has_media_features:
        deficit -= 0.10
    if has_certifications:
        deficit -= 0.10
    trust_deficit_score = round(max(0.05, deficit), 3)

    # --- missing trust elements ---
    missing_trust_elements: list[str] = []
    if not has_testimonials:
        missing_trust_elements.append("testimonials")
    if not has_case_studies:
        missing_trust_elements.append("case_studies")
    if has_social_proof_count < 5:
        missing_trust_elements.append("social_proof_volume")
    if not has_media_features:
        missing_trust_elements.append("media_features")
    if not has_certifications:
        missing_trust_elements.append("certifications")

    # --- recommended proof blocks (priority ordered) ---
    _proof_map: dict[str, tuple[int, str]] = {
        "testimonials": (
            1,
            "Collect 5–10 customer testimonials (video preferred); place above the fold on offer pages",
        ),
        "case_studies": (
            2,
            "Build 2–3 before/after case studies with measurable outcomes from your strongest customers",
        ),
        "social_proof_volume": (
            3,
            f"Reach 5+ public social proof items (reviews, shares, UGC); "
            f"currently have {has_social_proof_count}",
        ),
        "media_features": (
            4,
            "Pitch 2–3 niche podcasts or publications for a feature, interview, or quote mention",
        ),
        "certifications": (
            5,
            "Add relevant credential badges or platform certifications near the primary CTA",
        ),
    }
    recommended_proof_blocks: list[dict[str, Any]] = []
    for element in missing_trust_elements:
        priority, action = _proof_map.get(element, (9, f"Add {element} to credibility stack"))
        recommended_proof_blocks.append({"type": element, "priority": priority, "action": action})
    recommended_proof_blocks.sort(key=lambda x: x["priority"])

    # --- expected uplift: deficit * 0.25 ---
    expected_uplift = round(trust_deficit_score * 0.25, 4)

    # --- confidence ---
    data_quality = _clamp(avg_quality_score) * 0.30 + min(0.30, content_item_count / 50.0)
    cvr_signal = _clamp(offer_conversion_rate * 20.0) * 0.20
    confidence = round(
        _clamp(0.35 + data_quality + cvr_signal + 0.15 * (1.0 - trust_deficit_score)), 3
    )

    explanation = (
        f"Trust deficit {trust_deficit_score:.2f} for '{brand_niche}'. "
        f"Missing elements: {missing_trust_elements or ['none — stack complete']}. "
        f"Expected conversion uplift if all gaps addressed: +{expected_uplift * 100:.1f}%. "
        f"Quality score {avg_quality_score:.2f}, {content_item_count} content items, "
        f"current CVR {offer_conversion_rate:.2%}."
    )

    return {
        "trust_deficit_score": trust_deficit_score,
        "recommended_proof_blocks": recommended_proof_blocks,
        "missing_trust_elements": missing_trust_elements,
        "expected_uplift": expected_uplift,
        "confidence": confidence,
        "explanation": explanation,
        RC_PHASE_C: True,
    }


# ---------------------------------------------------------------------------
# Monetization Mix Engine
# ---------------------------------------------------------------------------

def score_monetization_mix(
    brand_niche: str,
    revenue_by_method: dict[str, float],
    total_revenue: float,
    audience_size: int,
    active_offer_types: list[str],
) -> dict[str, Any]:
    """Analyse monetization concentration and recommend diversification.

    Returns:
        current_revenue_mix: dict  (method -> pct of total)
        dependency_risk: float 0..1  (HHI-style concentration; 1.0 = fully concentrated)
        underused_monetization_paths: list[dict]  each: {path, potential_score, rationale}
        next_best_mix: dict  (method -> recommended_pct)
        expected_margin_uplift: float
        expected_ltv_uplift: float
        confidence: float 0..1
        explanation: str
        RC_PHASE_C: True
    """
    # --- normalise total ---
    total = total_revenue if total_revenue > 0 else max(sum(revenue_by_method.values()), 1.0)

    # --- current revenue mix ---
    current_revenue_mix: dict[str, float] = {
        method: round(amt / total, 4)
        for method, amt in revenue_by_method.items()
        if amt > 0
    }

    # --- HHI-style dependency risk: sum of (pct_i^2) ---
    dependency_risk = (
        round(sum(pct ** 2 for pct in current_revenue_mix.values()), 4)
        if current_revenue_mix
        else 1.0
    )

    # --- underused monetization paths ---
    active_set = set(active_offer_types or [])
    audience_boost = _clamp(0.10 * _log_norm(audience_size))
    underused_monetization_paths: list[dict[str, Any]] = []
    for method in KNOWN_METHODS:
        if method not in active_set:
            base_potential = _METHOD_POTENTIAL_SCORES.get(method, 0.50)
            adjusted_potential = round(_clamp(base_potential + audience_boost), 3)
            underused_monetization_paths.append({
                "path": method,
                "potential_score": adjusted_potential,
                "rationale": _METHOD_RATIONALES.get(method, f"Add {method} to diversify revenue"),
            })
    underused_monetization_paths.sort(key=lambda x: x["potential_score"], reverse=True)

    # --- next best mix: redistribute so no single method > 40 % ---
    all_methods = list(
        dict.fromkeys(
            list(active_offer_types or [])
            + [u["path"] for u in underused_monetization_paths[:3]]
        )
    )
    n = max(1, len(all_methods))
    base_share = 1.0 / n

    raw_mix: dict[str, float] = {}
    for m in all_methods:
        current_pct = current_revenue_mix.get(m, 0.0)
        raw_mix[m] = min(0.40, max(base_share, current_pct))

    mix_total = sum(raw_mix.values())
    next_best_mix: dict[str, float] = (
        {m: round(v / mix_total, 4) for m, v in raw_mix.items()}
        if mix_total > 0
        else {m: round(1.0 / n, 4) for m in all_methods}
    )

    # --- expected uplifts ---
    diversification_factor = 1.0 - dependency_risk
    expected_margin_uplift = round(_clamp(diversification_factor * 0.18), 4)
    expected_ltv_uplift = round(
        _clamp(diversification_factor * 0.25 + len(underused_monetization_paths) * 0.02), 4
    )

    # --- confidence ---
    data_richness = _clamp(len(revenue_by_method) / 5.0) if revenue_by_method else 0.10
    confidence = round(
        _clamp(
            0.40
            + data_richness * 0.30
            + 0.20 * (1.0 - dependency_risk)
            + 0.10 * _log_norm(audience_size)
        ),
        3,
    )

    explanation = (
        f"'{brand_niche}' monetization: {len(active_offer_types)} active method(s), "
        f"HHI dependency_risk {dependency_risk:.2f} "
        f"({'high' if dependency_risk > 0.6 else 'medium' if dependency_risk > 0.3 else 'low'} concentration). "
        f"{len(underused_monetization_paths)} underused paths identified. "
        f"Redistributing to cap each method at 40 % reduces concentration risk. "
        f"Expected margin uplift +{expected_margin_uplift * 100:.1f}%, "
        f"LTV uplift +{expected_ltv_uplift * 100:.1f}%."
    )

    return {
        "current_revenue_mix": current_revenue_mix,
        "dependency_risk": dependency_risk,
        "underused_monetization_paths": underused_monetization_paths,
        "next_best_mix": next_best_mix,
        "expected_margin_uplift": expected_margin_uplift,
        "expected_ltv_uplift": expected_ltv_uplift,
        "confidence": confidence,
        "explanation": explanation,
        RC_PHASE_C: True,
    }


# ---------------------------------------------------------------------------
# Paid Promotion Gate Engine
# ---------------------------------------------------------------------------

def evaluate_paid_promotion_candidate(
    content_item_id: str,
    content_title: str,
    organic_impressions: int,
    organic_engagement_rate: float,
    organic_revenue: float,
    organic_roi: float,
    content_age_days: int,
    winner_threshold_impressions: int = 5000,
    winner_threshold_engagement: float = 0.04,
    winner_threshold_roi: float = 1.5,
) -> dict[str, Any]:
    """Strict organic-winner gate — all signals must pass before approving paid spend.

    Returns:
        content_item_id: str
        organic_winner_evidence: dict  (all signals with pass/fail per criterion)
        is_eligible: bool   (True ONLY when ALL organic evidence is strong)
        gate_reason: str    (brief reason for eligibility or ineligibility)
        confidence: float 0..1
        RC_PHASE_C: True
    """
    # --- evaluate each gate criterion ---
    impressions_pass = organic_impressions >= winner_threshold_impressions
    engagement_pass = organic_engagement_rate >= winner_threshold_engagement
    roi_pass = organic_roi >= winner_threshold_roi
    age_pass = content_age_days >= 14
    revenue_pass = organic_revenue > 0

    # roi OR age satisfies the "proven over time" criterion
    roi_or_age_pass = roi_pass or age_pass

    organic_winner_evidence: dict[str, Any] = {
        "organic_impressions": organic_impressions,
        "impressions_threshold": winner_threshold_impressions,
        "impressions_pass": impressions_pass,
        "organic_engagement_rate": organic_engagement_rate,
        "engagement_threshold": winner_threshold_engagement,
        "engagement_pass": engagement_pass,
        "organic_revenue": organic_revenue,
        "revenue_pass": revenue_pass,
        "organic_roi": organic_roi,
        "roi_threshold": winner_threshold_roi,
        "roi_pass": roi_pass,
        "content_age_days": content_age_days,
        "age_pass_14d": age_pass,
        "roi_or_age_pass": roi_or_age_pass,
    }

    # --- strict gate: ALL criteria must pass ---
    is_eligible = bool(
        impressions_pass
        and engagement_pass
        and roi_or_age_pass
        and revenue_pass
    )

    # --- gate reason ---
    if is_eligible:
        qualifier = (
            f"ROI {organic_roi:.2f}x (≥{winner_threshold_roi:.2f}x)"
            if roi_pass
            else f"age {content_age_days}d (≥14d)"
        )
        gate_reason = (
            f"Eligible — all organic signals pass: "
            f"{organic_impressions:,} impressions (≥{winner_threshold_impressions:,}), "
            f"{organic_engagement_rate:.2%} engagement (≥{winner_threshold_engagement:.2%}), "
            f"${organic_revenue:.2f} organic revenue, "
            f"{qualifier}."
        )
    else:
        failed: list[str] = []
        if not impressions_pass:
            failed.append(
                f"impressions {organic_impressions:,} < {winner_threshold_impressions:,}"
            )
        if not engagement_pass:
            failed.append(
                f"engagement {organic_engagement_rate:.2%} < {winner_threshold_engagement:.2%}"
            )
        if not roi_or_age_pass:
            failed.append(
                f"ROI {organic_roi:.2f}x < {winner_threshold_roi:.2f}x "
                f"AND age {content_age_days}d < 14d"
            )
        if not revenue_pass:
            failed.append("organic_revenue = $0 (no proven monetization on this asset)")
        gate_reason = "Not eligible — failed: " + "; ".join(failed)

    # --- confidence: rises with each passing gate criterion ---
    pass_count = sum([impressions_pass, engagement_pass, roi_or_age_pass, revenue_pass])
    confidence = round(_clamp(0.20 + pass_count * 0.20), 3)

    return {
        "content_item_id": content_item_id,
        "organic_winner_evidence": organic_winner_evidence,
        "is_eligible": is_eligible,
        "gate_reason": gate_reason,
        "confidence": confidence,
        RC_PHASE_C: True,
    }
