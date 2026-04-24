"""Offer Lab Engine — generate, score, rank, test, learn, revise. Pure functions."""
from __future__ import annotations

from typing import Any

OFFER_TYPES = ["affiliate", "lead_gen", "product", "service", "subscription", "premium_access", "consulting", "course", "download", "event"]
VARIANT_TYPES = ["budget", "premium", "convenience", "authority", "comparison", "problem_relief", "identity", "recurring_value"]
ANGLES = ["value_demo", "social_proof", "scarcity", "authority", "comparison", "problem_solution", "identity", "convenience", "risk_reversal"]


def generate_offer(source: dict[str, Any], brand: dict[str, Any]) -> dict[str, Any]:
    name = source.get("name", "Offer")
    method = source.get("monetization_method", "affiliate")
    price = float(source.get("payout_amount", 0) or source.get("price_point", 0) or 0)
    epc = float(source.get("epc", 0) or 0)
    cvr = float(source.get("conversion_rate", 0) or 0)
    niche = brand.get("niche", "general")

    return {
        "offer_name": name,
        "offer_type": method,
        "audience_segment": f"{niche} audience",
        "problem_solved": f"Helps {niche} audience with {name}",
        "value_promise": f"Get results with {name}",
        "primary_angle": "value_demo",
        "trust_requirement": "medium",
        "risk_level": "low" if cvr > 0.03 else "medium",
        "price_point": price,
        "margin_estimate": price * 0.3,
        "monetization_method": method,
        "platform_fit": 0.5,
        "funnel_stage_fit": "middle",
        "expected_upside": epc * 100,
        "expected_cost": price * 0.1,
        "confidence": min(1.0, 0.3 + cvr * 10),
        "status": "draft",
        "truth_label": "recommendation_only",
    }


def generate_variants(offer: dict[str, Any]) -> list[dict[str, Any]]:
    variants = []
    name = offer.get("offer_name", "Offer")
    price = float(offer.get("price_point", 0))
    for i, vt in enumerate(VARIANT_TYPES):
        angle = ANGLES[i % len(ANGLES)]
        vp = price * (0.7 if vt == "budget" else 1.5 if vt == "premium" else 1.0)
        variants.append({
            "variant_type": vt,
            "variant_name": f"{name} — {vt.replace('_', ' ').title()}",
            "angle": angle,
            "price_point": round(vp, 2),
            "value_promise": f"{vt.replace('_', ' ').title()} version of {name}",
            "is_control": i == 0,
        })
    return variants


def generate_pricing_test(offer: dict[str, Any]) -> dict[str, Any]:
    price = float(offer.get("price_point", 0))
    return {"test_price": round(price * 0.8, 2), "control_price": round(price, 2)}


def generate_positioning_test(offer: dict[str, Any]) -> dict[str, Any]:
    primary = offer.get("primary_angle", "value_demo")
    alt = "social_proof" if primary != "social_proof" else "authority"
    return {"test_angle": alt, "control_angle": primary}


def generate_bundles(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(offers) < 2:
        return []
    bundles = []
    for i in range(0, len(offers) - 1, 2):
        a, b = offers[i], offers[i + 1]
        combined = float(a.get("price_point", 0)) + float(b.get("price_point", 0))
        bundles.append({
            "bundle_name": f"{a.get('offer_name', '')} + {b.get('offer_name', '')} Bundle",
            "offer_ids": [str(a.get("id", "")), str(b.get("id", ""))],
            "combined_price": round(combined * 0.85, 2),
            "savings_pct": 15.0,
            "expected_uplift": 0.2,
        })
    return bundles


def generate_upsells(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sorted_offers = sorted(offers, key=lambda o: float(o.get("price_point", 0)))
    upsells = []
    for i in range(len(sorted_offers) - 1):
        upsells.append({
            "primary_offer_id": str(sorted_offers[i].get("id", "")),
            "upsell_offer_id": str(sorted_offers[i + 1].get("id", "")),
            "upsell_type": "upsell",
            "expected_take_rate": 0.15,
        })
    return upsells


def score_offer(offer: dict[str, Any]) -> float:
    epc = min(1.0, float(offer.get("expected_upside", 0)) / 100)
    confidence = float(offer.get("confidence", 0.5))
    platform = float(offer.get("platform_fit", 0.5))
    margin = min(1.0, float(offer.get("margin_estimate", 0)) / 50)
    trust_map = {"low": 1.0, "medium": 0.7, "high": 0.4}
    trust_penalty = trust_map.get(offer.get("trust_requirement", "medium"), 0.7)

    return round(0.30 * epc + 0.20 * confidence + 0.15 * platform + 0.15 * margin + 0.20 * trust_penalty, 4)


def detect_offer_issues(offer: dict[str, Any]) -> list[dict[str, Any]]:
    issues = []
    if float(offer.get("expected_upside", 0)) == 0:
        issues.append({"blocker_type": "no_expected_upside", "description": "Offer has no expected upside — not validated", "recommendation": "Add EPC or conversion data", "severity": "high"})
    if float(offer.get("price_point", 0)) == 0:
        issues.append({"blocker_type": "no_price_point", "description": "No price point set", "recommendation": "Set price point for margin calculation", "severity": "medium"})
    if float(offer.get("confidence", 0)) < 0.3:
        issues.append({"blocker_type": "low_confidence", "description": f"Confidence {offer.get('confidence', 0):.0%} is too low", "recommendation": "Run pricing/positioning tests to build confidence", "severity": "medium"})
    if offer.get("trust_requirement") == "high" and float(offer.get("platform_fit", 0)) < 0.4:
        issues.append({"blocker_type": "trust_platform_mismatch", "description": "High trust offer on low-fit platform", "recommendation": "Move to authority platform or add proof", "severity": "high"})
    return issues


def recommend_revision(offer: dict[str, Any], issues: list[dict]) -> list[str]:
    recs = []
    for issue in issues:
        bt = issue.get("blocker_type", "")
        if bt == "no_expected_upside":
            recs.append("revise_pricing")
        elif bt == "low_confidence":
            recs.append("run_test")
        elif bt == "trust_platform_mismatch":
            recs.append("add_proof")
    if not issues:
        score = score_offer(offer)
        if score < 0.3:
            recs.append("suppress_offer")
        elif score < 0.5:
            recs.append("change_positioning")
    return recs if recs else ["keep_current"]
