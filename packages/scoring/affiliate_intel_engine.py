"""Elite Affiliate Intelligence Engine — rank, detect leaks, select best. Pure functions."""

from __future__ import annotations

from typing import Any


def rank_offer(offer: dict[str, Any]) -> float:
    """Score an affiliate offer on 0-1 scale."""
    epc = min(1.0, float(offer.get("epc", 0) or 0) / 5.0)
    cvr = min(1.0, float(offer.get("conversion_rate", 0) or 0) * 20)
    commission = min(1.0, float(offer.get("commission_rate", 0) or 0) / 50)
    refund_risk = max(0, 1.0 - float(offer.get("refund_rate", 0) or 0) * 5)
    trust = float(offer.get("trust_score", 0.5) or 0.5)
    content_fit = float(offer.get("content_fit_score", 0.5) or 0.5)
    platform_fit = float(offer.get("platform_fit_score", 0.5) or 0.5)
    audience_fit = float(offer.get("audience_fit_score", 0.5) or 0.5)

    score = (
        0.25 * epc
        + 0.15 * cvr
        + 0.10 * commission
        + 0.10 * refund_risk
        + 0.10 * trust
        + 0.10 * content_fit
        + 0.10 * platform_fit
        + 0.10 * audience_fit
    )
    return round(min(1.0, max(0.0, score)), 4)


def rank_offers(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank a list of offers by composite score."""
    scored = []
    for o in offers:
        s = rank_offer(o)
        scored.append({**o, "rank_score": s})
    return sorted(scored, key=lambda x: -x["rank_score"])


def select_best_offer(
    offers: list[dict[str, Any]], platform: str = "", content_form: str = ""
) -> dict[str, Any] | None:
    """Pick the single best offer for given context."""
    ranked = rank_offers(offers)
    if platform:
        platform_match = [o for o in ranked if o.get("platform_fit_score", 0) >= 0.5]
        if platform_match:
            return platform_match[0]
    return ranked[0] if ranked else None


def build_affiliate_link(
    offer: dict[str, Any], content_item_id: str = "", campaign_id: str = "", platform: str = ""
) -> dict[str, Any]:
    """Build a full affiliate link with UTM params."""
    base = offer.get("affiliate_url") or offer.get("destination_url") or ""
    sep = "&" if "?" in base else "?"
    utm = f"utm_source={platform}&utm_medium=affiliate&utm_campaign={campaign_id[:8] if campaign_id else 'direct'}&utm_content={content_item_id[:8] if content_item_id else 'generic'}"
    full = f"{base}{sep}{utm}" if base else ""
    return {
        "full_url": full,
        "utm_params": {"source": platform, "medium": "affiliate", "campaign": campaign_id, "content": content_item_id},
        "disclosure_applied": False,
    }


def detect_leaks(offers: list[dict[str, Any]], links: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect affiliate revenue leaks."""
    leaks = []
    for link in links:
        clicks = int(link.get("click_count", 0) or 0)
        conversions = int(link.get("conversion_count", 0) or 0)
        if clicks > 50 and conversions == 0:
            leaks.append(
                {
                    "leak_type": "high_clicks_zero_conversions",
                    "severity": "critical",
                    "revenue_loss_estimate": clicks * 0.5,
                    "recommendation": "Check landing page, offer status, and tracking integrity",
                    "link_id": link.get("id"),
                    "offer_id": link.get("offer_id"),
                }
            )
        elif clicks > 20 and conversions > 0 and (conversions / clicks) < 0.005:
            leaks.append(
                {
                    "leak_type": "very_low_conversion",
                    "severity": "high",
                    "revenue_loss_estimate": clicks * 0.3,
                    "recommendation": "Test different landing page or offer angle",
                    "link_id": link.get("id"),
                    "offer_id": link.get("offer_id"),
                }
            )

    for offer in offers:
        if offer.get("is_active") and offer.get("blocker_state"):
            leaks.append(
                {
                    "leak_type": "blocked_offer_still_active",
                    "severity": "high",
                    "revenue_loss_estimate": 10,
                    "recommendation": "Deactivate or fix blocker",
                    "offer_id": offer.get("id"),
                }
            )
        if float(offer.get("refund_rate", 0) or 0) > 0.15:
            leaks.append(
                {
                    "leak_type": "high_refund_rate",
                    "severity": "medium",
                    "revenue_loss_estimate": float(offer.get("epc", 0) or 0) * 20,
                    "recommendation": "Switch to lower-refund merchant or product",
                    "offer_id": offer.get("id"),
                }
            )

    return sorted(leaks, key=lambda l: {"critical": 0, "high": 1, "medium": 2}.get(l["severity"], 3))


def detect_blockers(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect affiliate blockers."""
    blockers = []
    for o in offers:
        if not o.get("affiliate_url") and not o.get("destination_url"):
            blockers.append(
                {
                    "offer_id": o.get("id"),
                    "blocker_type": "no_destination_url",
                    "description": f"Offer '{o.get('product_name', '')}' has no affiliate or destination URL",
                    "severity": "critical",
                }
            )
        if float(o.get("epc", 0) or 0) == 0 and float(o.get("commission_rate", 0) or 0) == 0:
            blockers.append(
                {
                    "offer_id": o.get("id"),
                    "blocker_type": "no_commission_data",
                    "description": f"Offer '{o.get('product_name', '')}' has no EPC or commission rate",
                    "severity": "high",
                }
            )
    return blockers
