"""Expansion Pack 2 Phase B — pricing, bundling, retention, reactivation engines.

Pure functions — no I/O, no SQLAlchemy. Each function returns a dict with
scored outputs plus an ``EP2B: True`` marker.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Any

EP2B = "expansion_pack2_phase_b"

# ─── helpers ────────────────────────────────────────────────────────────────

def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def _det_var(seed: str) -> float:
    """Deterministic float in [0, 1] from a string seed."""
    return int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16) % 1000 / 1000.0


# ═══════════════════════════════════════════════════════════════════════════
# 1. PRICING INTELLIGENCE ENGINE
# ═══════════════════════════════════════════════════════════════════════════

_PRICING_REC_TYPES = ("price_increase", "price_decrease", "anchor_reprice", "hold")


def recommend_pricing(
    offer_id: uuid.UUID,
    current_price: float,
    historical_sales_data: list[dict[str, Any]],
    market_data: list[dict[str, Any]],
    customer_segment_data: list[dict[str, Any]],
) -> dict[str, Any]:
    """Score an offer's current price and recommend an optimal price point.

    Evaluates price elasticity from historical volume changes, competitor
    positioning from market data, and willingness-to-pay from customer
    segments.  Returns a recommendation dict.
    """
    cp = max(current_price, 1.0)

    # --- elasticity signal (historical) ---
    if len(historical_sales_data) >= 2:
        sorted_hist = sorted(historical_sales_data, key=lambda d: d.get("date", ""))
        prices = [d.get("price", cp) for d in sorted_hist]
        qtys = [d.get("quantity_sold", 1) for d in sorted_hist]
        dp = (prices[-1] - prices[0]) / max(abs(prices[0]), 1.0)
        dq = (qtys[-1] - qtys[0]) / max(abs(qtys[0]), 1.0)
        elasticity_raw = abs(dq / dp) if abs(dp) > 0.001 else 0.5
    else:
        elasticity_raw = 0.5
    price_elasticity = round(_clamp(elasticity_raw, 0.05, 2.0), 3)

    # --- market signal ---
    comp_prices = [d.get("competitor_price", 0) for d in market_data if d.get("competitor_price")]
    avg_demand = sum(d.get("demand_level", 0.5) for d in market_data) / max(1, len(market_data))
    avg_comp = sum(comp_prices) / max(1, len(comp_prices)) if comp_prices else cp
    market_ratio = avg_comp / cp if cp > 0 else 1.0

    # --- customer willingness-to-pay signal ---
    wtps = [d.get("willingness_to_pay", cp) for d in customer_segment_data if d.get("willingness_to_pay")]
    sensitivities = [d.get("price_sensitivity", 0.5) for d in customer_segment_data]
    avg_wtp = sum(wtps) / max(1, len(wtps)) if wtps else cp
    avg_sens = sum(sensitivities) / max(1, len(sensitivities)) if sensitivities else 0.5

    # --- composite recommended price ---
    market_pull = cp * (0.40 * market_ratio + 0.30 * (avg_wtp / cp) + 0.30 * (1.0 + avg_demand * 0.20))
    sensitivity_dampener = 1.0 - avg_sens * 0.30
    raw_price = market_pull * sensitivity_dampener
    recommended_price = round(max(1.0, raw_price), 2)

    # --- recommendation type ---
    delta_pct = (recommended_price - cp) / cp
    if delta_pct > 0.05:
        rec_type = "price_increase"
    elif delta_pct < -0.05:
        rec_type = "price_decrease"
    elif abs(delta_pct) <= 0.05 and comp_prices:
        rec_type = "anchor_reprice"
    else:
        rec_type = "hold"

    # --- revenue impact (monthly proxy) ---
    volume_proxy = sum(d.get("quantity_sold", 10) for d in historical_sales_data[-3:]) / max(1, min(3, len(historical_sales_data)))
    estimated_revenue_impact = round((recommended_price - cp) * volume_proxy, 2)

    # --- confidence ---
    data_depth = _clamp(len(historical_sales_data) / 12.0, 0.0, 0.30)
    market_depth = _clamp(len(market_data) / 5.0, 0.0, 0.25)
    seg_depth = _clamp(len(customer_segment_data) / 4.0, 0.0, 0.20)
    confidence = round(_clamp(0.25 + data_depth + market_depth + seg_depth), 3)

    explanation = (
        f"{'Increase' if rec_type == 'price_increase' else 'Decrease' if rec_type == 'price_decrease' else 'Hold'} "
        f"from ${cp:.2f} to ${recommended_price:.2f} "
        f"(elasticity {price_elasticity:.2f}, market avg ${avg_comp:.2f}, "
        f"WTP ${avg_wtp:.2f}, sensitivity {avg_sens:.2f}). "
        f"Est. monthly impact ${estimated_revenue_impact:+.2f}."
    )

    return {
        "offer_id": str(offer_id),
        "recommendation_type": rec_type,
        "current_price": cp,
        "recommended_price": recommended_price,
        "price_elasticity": price_elasticity,
        "estimated_revenue_impact": estimated_revenue_impact,
        "confidence": confidence,
        "explanation": explanation,
        EP2B: True,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 2. PACKAGING & BUNDLING ENGINE
# ═══════════════════════════════════════════════════════════════════════════

_BUNDLE_STRATEGIES = ("value_stack", "gateway_premium", "complementary", "discount_only")


def recommend_bundles(
    available_offers: list[dict[str, Any]],
    customer_purchase_history: list[dict[str, Any]],
    market_trends: list[dict[str, Any]],
    brand_name: str = "",
    niche: str = "",
) -> list[dict[str, Any]]:
    """Generate 1–4 bundle recommendations from the offer catalog.

    Evaluates co-purchase frequency, price-tier pairing, complementary
    features, and market trend alignment.  Returns a list of bundle dicts.
    """
    if not available_offers:
        return [{
            "bundle_name": "No Bundle Recommended",
            "offer_ids": [],
            "bundle_strategy": "none",
            "recommended_bundle_price": 0.0,
            "savings_pct": 0.0,
            "estimated_upsell_rate": 0.0,
            "estimated_revenue_impact": 0.0,
            "confidence": 0.0,
            "explanation": "No offers available to bundle.",
            EP2B: True,
        }]

    bundles: list[dict[str, Any]] = []
    seen_combos: set[str] = set()

    sorted_offers = sorted(available_offers, key=lambda x: x.get("price", 0), reverse=True)

    # --- co-purchase frequency map ---
    copurchase: dict[str, set[str]] = {}
    for hist in customer_purchase_history:
        ids = hist.get("purchased_offer_ids", [])
        for oid in ids:
            copurchase.setdefault(oid, set()).update(i for i in ids if i != oid)

    def _add_bundle(name: str, offer_ids: list[str], strategy: str, discount: float):
        combo_key = "|".join(sorted(offer_ids))
        if combo_key in seen_combos or len(offer_ids) < 2:
            return
        seen_combos.add(combo_key)
        prices = [o.get("price", 0) for o in available_offers if o.get("id") in offer_ids]
        total = sum(prices) if prices else 0.0
        bundle_price = round(total * (1.0 - discount), 2)
        savings = round(discount * 100, 1)
        volume_est = max(10, int(50 * discount * len(offer_ids)))
        upsell_rate = round(_clamp(0.05 + discount * 0.30 + len(offer_ids) * 0.03), 3)
        rev_impact = round(bundle_price * volume_est * upsell_rate, 2)
        conf = round(_clamp(0.40 + len(offer_ids) * 0.08 + min(0.20, len(customer_purchase_history) * 0.02)), 3)
        names = [o.get("name", "?") for o in available_offers if o.get("id") in offer_ids]
        explanation = (
            f"{strategy.replace('_', ' ').title()} bundle: {' + '.join(names)} "
            f"at ${bundle_price:.2f} ({savings}% off). Est. upsell rate {upsell_rate:.1%}."
        )
        bundles.append({
            "bundle_name": name,
            "offer_ids": offer_ids,
            "bundle_strategy": strategy,
            "recommended_bundle_price": bundle_price,
            "savings_pct": savings,
            "estimated_upsell_rate": upsell_rate,
            "estimated_revenue_impact": rev_impact,
            "confidence": conf,
            "explanation": explanation,
            EP2B: True,
        })

    # Strategy 1: value_stack — top 2-3 offers, 20% off
    if len(sorted_offers) >= 2:
        top = sorted_offers[:min(3, len(sorted_offers))]
        _add_bundle(
            f"{brand_name or 'Premium'} Value Stack",
            [o["id"] for o in top],
            "value_stack",
            0.20,
        )

    # Strategy 2: gateway_premium — cheapest + most expensive, 15% off
    if len(sorted_offers) >= 2:
        cheapest = sorted_offers[-1]
        priciest = sorted_offers[0]
        if cheapest["id"] != priciest["id"]:
            _add_bundle(
                f"Gateway to {priciest.get('name', 'Premium')}",
                [cheapest["id"], priciest["id"]],
                "gateway_premium",
                0.15,
            )

    # Strategy 3: complementary — co-purchased pairs
    for oid, partners in copurchase.items():
        for pid in list(partners)[:1]:
            if oid in [o["id"] for o in available_offers] and pid in [o["id"] for o in available_offers]:
                o1_name = next((o.get("name", "A") for o in available_offers if o["id"] == oid), "A")
                o2_name = next((o.get("name", "B") for o in available_offers if o["id"] == pid), "B")
                _add_bundle(
                    f"{o1_name} + {o2_name} Combo",
                    [oid, pid],
                    "complementary",
                    0.18,
                )
        if len(bundles) >= 4:
            break

    # Strategy 4: discount_only fallback (2 cheapest, 25% off)
    if len(bundles) < 2 and len(sorted_offers) >= 2:
        bottom2 = sorted_offers[-2:]
        _add_bundle(
            f"{niche.title() if niche else 'Starter'} Essentials",
            [o["id"] for o in bottom2],
            "discount_only",
            0.25,
        )

    return bundles[:4] if bundles else [{
        "bundle_name": "No Bundle Recommended",
        "offer_ids": [],
        "bundle_strategy": "none",
        "recommended_bundle_price": 0.0,
        "savings_pct": 0.0,
        "estimated_upsell_rate": 0.0,
        "estimated_revenue_impact": 0.0,
        "confidence": 0.0,
        "explanation": "Not enough offers to build a bundle.",
        EP2B: True,
    }]


# Keep backward-compatible single-bundle API used by existing service layer
def recommend_bundle(
    available_offers: list[dict[str, Any]],
    customer_purchase_history: list[dict[str, Any]],
    market_trends: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return the top bundle recommendation (backward-compatible wrapper)."""
    results = recommend_bundles(available_offers, customer_purchase_history, market_trends)
    return results[0]


# ═══════════════════════════════════════════════════════════════════════════
# 3. RETENTION & REACTIVATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════

_RETENTION_STRATEGIES = (
    "personalized_offer", "engagement_campaign", "loyalty_reward",
    "feedback_survey", "vip_upgrade", "win_back_discount",
)

_REACTIVATION_TYPES = (
    "email_series", "discount_offer", "content_drip",
    "social_retarget", "personal_outreach", "limited_time_access",
)


def recommend_retention(
    customer_id: uuid.UUID,
    customer_behavior_data: list[dict[str, Any]],
    churn_risk_score: float,
    available_retention_offers: list[dict[str, Any]],
) -> dict[str, Any]:
    """Score churn risk for a customer segment and recommend retention actions.

    Evaluates activity recency, purchase frequency, churn risk score, and
    available retention offers to produce a prioritised recommendation.
    """
    churn = _clamp(churn_risk_score)

    # --- segment classification ---
    if churn >= 0.75:
        segment = "critical_churn_risk"
    elif churn >= 0.50:
        segment = "high_churn_risk"
    elif churn >= 0.25:
        segment = "moderate_churn_risk"
    else:
        segment = "low_churn_risk"

    # --- activity recency signal ---
    recency_scores = []
    for bd in customer_behavior_data:
        level = bd.get("activity_level", "low")
        recency_scores.append({"high": 0.1, "medium": 0.3, "low": 0.6}.get(level, 0.5))
    avg_recency_risk = sum(recency_scores) / max(1, len(recency_scores)) if recency_scores else 0.5

    # --- choose strategy ---
    if churn >= 0.75:
        if available_retention_offers:
            rec_type = "win_back_discount"
            action = {
                "offer_id": str(available_retention_offers[0].get("offer_id", "")),
                "discount": available_retention_offers[0].get("discount", 0.15),
                "urgency": "immediate",
            }
        else:
            rec_type = "personal_outreach"
            action = {"channel": "email", "urgency": "immediate"}
    elif churn >= 0.50:
        rec_type = "personalized_offer"
        action = {
            "offer_id": str(available_retention_offers[0].get("offer_id", "")) if available_retention_offers else "",
            "urgency": "48h",
        }
    elif churn >= 0.25:
        rec_type = "engagement_campaign"
        action = {"campaign_type": "content_drip", "duration_days": 14}
    else:
        rec_type = "loyalty_reward"
        action = {"reward_type": "early_access", "duration_days": 30}

    # --- estimated lift ---
    base_lift = {
        "win_back_discount": 0.18, "personal_outreach": 0.12,
        "personalized_offer": 0.15, "engagement_campaign": 0.10,
        "loyalty_reward": 0.08, "vip_upgrade": 0.12,
        "feedback_survey": 0.05,
    }.get(rec_type, 0.08)
    offer_bonus = 0.05 if available_retention_offers else 0.0
    estimated_lift = round(_clamp(base_lift + offer_bonus + (1.0 - avg_recency_risk) * 0.05, 0.0, 0.50), 3)

    # --- confidence ---
    data_signal = _clamp(len(customer_behavior_data) / 10.0, 0.0, 0.25)
    offer_signal = _clamp(len(available_retention_offers) / 3.0, 0.0, 0.15)
    confidence = round(_clamp(0.35 + data_signal + offer_signal + (1.0 - churn) * 0.15), 3)

    explanation = (
        f"Segment: {segment} (churn score {churn:.2f}, recency risk {avg_recency_risk:.2f}). "
        f"Recommend {rec_type} with estimated {estimated_lift:.1%} retention lift."
    )

    return {
        "customer_segment": segment,
        "recommendation_type": rec_type,
        "action_details": action,
        "estimated_retention_lift": estimated_lift,
        "confidence": confidence,
        "explanation": explanation,
        EP2B: True,
    }


def recommend_reactivation_campaign(
    lapsed_customer_segment: list[dict[str, Any]],
    historical_campaign_performance: list[dict[str, Any]],
    available_campaign_types: list[str],
) -> dict[str, Any]:
    """Design a reactivation campaign for a lapsed customer segment.

    Evaluates lapse duration, historical campaign effectiveness, and
    available campaign channels to recommend an optimal reactivation play.
    """
    # --- target segment ---
    target_segment = (
        lapsed_customer_segment[0]["segment_name"]
        if lapsed_customer_segment
        else "lapsed_customers"
    )

    # --- lapse duration signal ---
    lapse_days = []
    for seg in lapsed_customer_segment:
        lapse_days.append(seg.get("last_activity_days_ago", 90))
    avg_lapse = sum(lapse_days) / max(1, len(lapse_days)) if lapse_days else 90

    # --- best historical campaign type ---
    best_type = None
    best_rate = 0.0
    for perf in historical_campaign_performance:
        rate = perf.get("reactivation_rate", 0)
        if rate > best_rate and perf.get("campaign_type") in available_campaign_types:
            best_rate = rate
            best_type = perf["campaign_type"]

    if best_type:
        campaign_type = best_type
    elif available_campaign_types:
        campaign_type = available_campaign_types[0]
    else:
        campaign_type = "email_series"

    # --- reactivation rate estimate ---
    base_rate = {
        "email_series": 0.05, "discount_offer": 0.08,
        "content_drip": 0.04, "social_retarget": 0.06,
        "personal_outreach": 0.10, "limited_time_access": 0.07,
    }.get(campaign_type, 0.05)
    lapse_penalty = _clamp(avg_lapse / 365.0, 0.0, 0.50) * 0.5
    hist_bonus = min(best_rate * 0.30, 0.05) if best_rate > 0 else 0.0
    estimated_rate = round(_clamp(base_rate - lapse_penalty + hist_bonus, 0.01, 0.30), 3)

    # --- revenue impact ---
    segment_size = sum(seg.get("segment_size", 100) for seg in lapsed_customer_segment) if lapsed_customer_segment else 100
    avg_aov = 75.0
    estimated_revenue = round(segment_size * estimated_rate * avg_aov, 2)

    # --- confidence ---
    hist_depth = _clamp(len(historical_campaign_performance) / 5.0, 0.0, 0.25)
    seg_depth = _clamp(len(lapsed_customer_segment) / 3.0, 0.0, 0.20)
    confidence = round(_clamp(0.35 + hist_depth + seg_depth + min(0.15, best_rate * 2.0)), 3)

    # --- campaign dates ---
    duration = 30 if avg_lapse < 120 else 45
    start_dt = datetime.utcnow()
    end_dt = start_dt + timedelta(days=duration)

    explanation = (
        f"{campaign_type.replace('_', ' ').title()} campaign targeting {target_segment} "
        f"(avg lapse {avg_lapse:.0f}d, segment ~{segment_size}). "
        f"Est. reactivation {estimated_rate:.1%}, revenue ${estimated_revenue:,.0f}."
    )

    return {
        "campaign_name": f"{target_segment.replace('_', ' ').title()} {campaign_type.replace('_', ' ').title()}",
        "target_segment": target_segment,
        "campaign_type": campaign_type,
        "start_date": start_dt.isoformat(),
        "end_date": end_dt.isoformat(),
        "estimated_reactivation_rate": estimated_rate,
        "estimated_revenue_impact": estimated_revenue,
        "confidence": confidence,
        "explanation": explanation,
        EP2B: True,
    }
