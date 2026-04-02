"""Revenue Ceiling Phase B — high-ticket, productization, revenue density, upsell (pure functions)."""
from __future__ import annotations

import hashlib
from typing import Any, Optional

RC_PHASE_B = "revenue_ceiling_phase_b"

HIGH_TICKET_KEYWORDS = ("coaching", "mastermind", "consult", "course", "program", "vip", "enterprise", "premium")
PRODUCT_TYPES = ("digital_course", "template_pack", "membership", "saas_tool", "community", "book_bundle")


def _h(s: str) -> int:
    """Deterministic hash bucket (0–999), stable across processes."""
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16) % 1000


def build_high_ticket_opportunity(
    opportunity_key: str,
    offer_name: str,
    niche: str,
    aov: float,
    payout: float,
    conversion_rate: float,
    content_title: Optional[str] = None,
    offer_id: Optional[str] = None,
    content_item_id: Optional[str] = None,
) -> dict[str, Any]:
    """Score high-ticket fit from offers + economics."""
    name_l = (offer_name or "").lower()
    ticket_signal = sum(1 for k in HIGH_TICKET_KEYWORDS if k in name_l) / max(1, len(HIGH_TICKET_KEYWORDS))
    value_signal = min(1.0, (aov + payout) / 5000.0) if (aov + payout) > 0 else 0.2
    conv_signal = min(1.0, conversion_rate * 25) if conversion_rate else 0.15
    eligibility = round(min(0.98, 0.25 + ticket_signal * 0.35 + value_signal * 0.25 + conv_signal * 0.15 + (_h(opportunity_key) % 50) / 500), 3)

    deal_value = round(max(aov, payout * 3, 500) * (1.0 + ticket_signal), 2)
    close_proxy = round(min(0.35, 0.02 + eligibility * 0.25 + conversion_rate * 0.5), 4)
    margin = 0.42 + ticket_signal * 0.15
    expected_profit = round(deal_value * close_proxy * margin, 2)
    conf = round(min(0.95, 0.4 + eligibility * 0.35 + value_signal * 0.2), 3)

    path = {
        "steps": [
            "Application or short discovery call",
            "Qualification + value framing",
            "Proposal / payment link",
            "Onboarding + delivery",
        ],
    }
    cta = f"Book a {niche or 'strategy'} call — limited spots this month"
    expl = (
        f"High-ticket fit from offer economics (AOV {aov:.0f}, payout {payout:.0f}) "
        f"and positioning signals in '{offer_name}'. "
        + (f"Content anchor: {content_title[:60]}…" if content_title else "")
    )

    return {
        "opportunity_key": opportunity_key,
        "source_offer_id": offer_id,
        "source_content_item_id": content_item_id,
        "eligibility_score": eligibility,
        "recommended_offer_path": path,
        "recommended_cta": cta,
        "expected_close_rate_proxy": close_proxy,
        "expected_deal_value": deal_value,
        "expected_profit": expected_profit,
        "confidence": conf,
        "explanation": expl,
        RC_PHASE_B: True,
    }


def generate_high_ticket_rows(
    niche: str,
    offers: list[dict[str, Any]],
    content_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not offers:
        return out
    for i, o in enumerate(offers[:10]):
        if not content_items:
            key = f"ht|offer:{o.get('id', i)}"
            out.append(build_high_ticket_opportunity(
                key, o.get("name", "Offer"), niche,
                float(o.get("average_order_value", 0) or 0),
                float(o.get("payout_amount", 0) or 0),
                float(o.get("conversion_rate", 0) or 0),
                offer_id=str(o.get("id")),
            ))
            continue
        for j, ci in enumerate(content_items[:15]):
            key = f"ht|offer:{o.get('id', i)}|content:{ci.get('id', j)}"
            out.append(build_high_ticket_opportunity(
                key, o.get("name", "Offer"), niche,
                float(o.get("average_order_value", 0) or 0),
                float(o.get("payout_amount", 0) or 0),
                float(o.get("conversion_rate", 0) or 0),
                content_title=ci.get("title", ""),
                offer_id=str(o.get("id")),
                content_item_id=str(ci.get("id")),
            ))
    return out


def build_product_opportunity(
    opportunity_key: str,
    niche: str,
    audience_hint: str,
    idx: int,
) -> dict[str, Any]:
    ptype = PRODUCT_TYPES[idx % len(PRODUCT_TYPES)]
    prices = [(47, 97), (97, 297), (297, 997), (29, 79), (19, 49), (9, 29)]
    lo, hi = prices[idx % len(prices)]
    launch = round(800 + _h(opportunity_key) * 40 + 50 * idx, 2)
    recurring = round(launch * 0.18, 2) if ptype in ("membership", "saas_tool", "community") else None
    complexity = ["low", "medium", "high"][(idx + _h(niche)) % 3]
    conf = round(min(0.92, 0.45 + (idx % 5) * 0.08 + _h(opportunity_key) / 800), 3)

    product_name = f"{niche.title()} {ptype.replace('_', ' ')} — pack {idx + 1}"
    expl = (
        f"Derived from niche '{niche}' and audience '{audience_hint}'. "
        f"Type {ptype} balances build cost vs recurring upside."
    )

    return {
        "opportunity_key": opportunity_key,
        "product_recommendation": product_name,
        "product_type": ptype,
        "target_audience": audience_hint or f"{niche} creators ready to implement",
        "price_range_min": float(lo),
        "price_range_max": float(hi),
        "expected_launch_value": launch,
        "expected_recurring_value": recurring,
        "build_complexity": complexity,
        "confidence": conf,
        "explanation": expl,
        RC_PHASE_B: True,
    }


def generate_product_opportunities(niche: str, target_audience: Optional[str], brand_voice: str = "") -> list[dict[str, Any]]:
    aud = target_audience or f"{niche} operators"
    return [build_product_opportunity(f"prod|{niche}|{i}", niche, aud, i) for i in range(6)]


def compute_revenue_density_row(
    content_item_id: str,
    title: str,
    total_revenue: float,
    total_impressions: int,
    total_cost: float,
    audience_members: int,
    monetization_density_score_existing: float,
) -> dict[str, Any]:
    """Per-item density metrics from aggregates."""
    imp = max(1, total_impressions)
    aud = max(1, audience_members)
    rev_item = round(total_revenue, 4)
    rpm = round((total_revenue / imp) * 1000.0, 4)
    profit = total_revenue - total_cost
    profit_p1k = round((profit / imp) * 1000.0, 4)
    profit_per_member = round(profit / aud, 6)

    depth = round(min(1.0, 0.15 + (_h(content_item_id) % 60) / 100 + monetization_density_score_existing * 0.5), 3)
    repeat = round(min(1.0, 0.2 + (total_revenue / max(1.0, total_cost + 1)) * 0.1 + depth * 0.25), 3)
    ceiling = round(min(1.0, 0.25 + depth * 0.35 + repeat * 0.25 + min(0.3, rpm / 100)), 3)

    rec = "Scale winners: duplicate format + add order bump" if rpm > 15 else "Improve CTA-to-offer match + add retargeting capture"
    if ceiling > 0.72:
        rec = "Near ceiling on this asset — test new channel or premium offer"

    return {
        "content_item_id": content_item_id,
        "revenue_per_content_item": rev_item,
        "revenue_per_1k_impressions": rpm,
        "profit_per_1k_impressions": profit_p1k,
        "profit_per_audience_member": profit_per_member,
        "monetization_depth_score": depth,
        "repeat_monetization_score": repeat,
        "ceiling_score": ceiling,
        "recommendation": rec,
        RC_PHASE_B: True,
    }


def build_upsell_recommendation(
    opportunity_key: str,
    anchor_offer: dict[str, Any],
    next_offer: dict[str, Any],
    platform_hint: str,
) -> dict[str, Any]:
    """Pairwise upsell from two offers."""
    a_epc = float(anchor_offer.get("epc", 0) or 0)
    n_epc = float(next_offer.get("epc", 0) or 0)
    take = round(min(0.45, 0.08 + (n_epc / max(50.0, a_epc + 1)) * 0.12 + (_h(opportunity_key) % 40) / 400), 4)
    incremental = round(max(n_epc, float(next_offer.get("payout_amount", 0) or 0)) * take, 2)
    timing = ["after_first_conversion", "day_3_email", "post-checkout", "webinar_close"][_h(opportunity_key) % 4]
    channel = platform_hint or ["email", "youtube_description", "sms", "in_app"][_h(opportunity_key) % 4]
    seq = {"steps": ["order_bump", "core_upsell", "continuity"]}

    return {
        "opportunity_key": opportunity_key,
        "anchor_offer_id": str(anchor_offer.get("id")),
        "anchor_content_item_id": None,
        "best_next_offer": {
            "offer_id": str(next_offer.get("id")),
            "name": next_offer.get("name", "Next offer"),
            "monetization_method": str(next_offer.get("monetization_method", "")),
        },
        "best_timing": timing,
        "best_channel": channel,
        "expected_take_rate": take,
        "expected_incremental_value": incremental,
        "best_upsell_sequencing": seq,
        "confidence": round(min(0.94, 0.5 + take * 1.2), 3),
        "explanation": f"Upsell from {anchor_offer.get('name')} → {next_offer.get('name')} (EPC lift {n_epc:.2f}).",
        RC_PHASE_B: True,
    }


def generate_upsell_rows(offers: list[dict[str, Any]], platform: str = "youtube") -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if len(offers) < 2:
        return out
    sorted_o = sorted(offers, key=lambda x: float(x.get("priority", 0) or 0), reverse=True)
    for i in range(min(len(sorted_o) - 1, 8)):
        a, b = sorted_o[i], sorted_o[i + 1]
        key = f"upsell|{a.get('id')}|{b.get('id')}"
        row = build_upsell_recommendation(key, a, b, platform)
        out.append(row)
    return out
