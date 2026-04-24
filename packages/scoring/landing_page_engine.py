"""Landing Page Engine — generate, variant, score pages. Pure functions."""

from __future__ import annotations

from typing import Any

PAGE_TYPES = [
    "product",
    "review",
    "comparison",
    "advertorial",
    "presell",
    "optin",
    "lead_magnet",
    "quiz_funnel",
    "authority",
    "creator_revenue",
    "sponsor",
]

BLOCK_TYPES = ["hero", "proof", "objection", "cta", "disclosure", "media", "testimonial", "faq", "pricing", "guarantee"]


def generate_page(
    offer: dict[str, Any], audience: str = "", platform: str = "", page_type: str = "product"
) -> dict[str, Any]:
    name = offer.get("name", "Offer")
    method = offer.get("monetization_method", "affiliate")
    headline = _headline_for_type(page_type, name)
    sub = _subheadline_for_type(page_type, name, method)
    hook = _hook_angle(page_type, method)

    proof = [
        {"type": "testimonial", "text": f"Real results with {name}"},
        {"type": "data", "text": f"Proven conversion data for {name}"},
    ]
    objections = [{"objection": "price", "answer": f"See the ROI breakdown for {name}"}]
    ctas = [{"cta_type": "primary", "text": f"Get {name} Now", "url_param": "main_cta"}]
    disclosure = (
        [{"type": "affiliate_disclosure", "text": "This page contains affiliate links. We may earn a commission."}]
        if method == "affiliate"
        else []
    )

    return {
        "page_type": page_type,
        "headline": headline,
        "subheadline": sub,
        "hook_angle": hook,
        "proof_blocks": proof,
        "objection_blocks": objections,
        "cta_blocks": ctas,
        "disclosure_blocks": disclosure,
        "media_blocks": [],
        "tracking_params": {"source": platform, "medium": method},
        "status": "draft",
        "publish_status": "unpublished",
        "truth_label": "recommendation_only",
    }


def generate_variant(page: dict[str, Any], variant_idx: int = 1) -> dict[str, Any]:
    angles = ["urgency", "social_proof", "value_stack", "scarcity", "authority"]
    angle = angles[variant_idx % len(angles)]
    return {
        "variant_label": f"variant_{angle}_{variant_idx}",
        "headline": f"{angle.replace('_', ' ').title()} — {page.get('headline', '')}",
        "subheadline": page.get("subheadline"),
        "hook_angle": angle,
        "cta_blocks": page.get("cta_blocks", []),
        "is_control": variant_idx == 0,
    }


def score_page_quality(page: dict[str, Any], objection_count: int = 0, offer_cvr: float = 0) -> dict[str, Any]:
    has_headline = bool(page.get("headline"))
    has_proof = len(page.get("proof_blocks") or []) > 0
    has_cta = len(page.get("cta_blocks") or []) > 0
    has_disclosure = len(page.get("disclosure_blocks") or []) > 0
    has_objection_blocks = len(page.get("objection_blocks") or []) > 0

    trust = 0.3
    if has_disclosure:
        trust += 0.3
    if has_proof:
        trust += 0.2
    if has_objection_blocks:
        trust += 0.2

    conversion_fit = 0.3
    if has_cta:
        conversion_fit += 0.3
    if has_headline:
        conversion_fit += 0.2
    if offer_cvr > 0.03:
        conversion_fit += 0.2

    obj_cov = min(1.0, objection_count * 0.2) if has_objection_blocks else 0

    total = round(0.35 * trust + 0.40 * conversion_fit + 0.25 * obj_cov, 3)
    verdict = "pass" if total >= 0.5 else "warn" if total >= 0.3 else "fail"

    return {
        "total_score": total,
        "trust_score": round(trust, 3),
        "conversion_fit": round(conversion_fit, 3),
        "objection_coverage": round(obj_cov, 3),
        "verdict": verdict,
    }


def _headline_for_type(pt: str, name: str) -> str:
    m = {
        "product": f"The Complete Guide to {name}",
        "review": f"Honest {name} Review — Is It Worth It?",
        "comparison": f"{name} vs The Competition",
        "advertorial": f"How {name} Changed Everything",
        "presell": f"Before You Buy {name}, Read This",
        "optin": f"Get Free Access to {name}",
        "lead_magnet": f"Download the {name} Playbook",
        "quiz_funnel": f"Find Your Perfect {name} Match",
        "authority": f"The Definitive {name} Resource",
        "creator_revenue": f"Work With Us — {name}",
        "sponsor": f"Partner With {name}",
    }
    return m.get(pt, f"Discover {name}")


def _subheadline_for_type(pt: str, name: str, method: str) -> str:
    return f"See why {name} is the #1 choice for {method} in 2026"


def _hook_angle(pt: str, method: str) -> str:
    m = {
        "product": "value_demonstration",
        "review": "honest_assessment",
        "comparison": "side_by_side",
        "advertorial": "story_driven",
        "presell": "objection_preempt",
        "optin": "free_value",
        "lead_magnet": "lead_capture",
        "quiz_funnel": "personalization",
        "authority": "expertise",
        "creator_revenue": "partnership",
        "sponsor": "brand_fit",
    }
    return m.get(pt, "general")
