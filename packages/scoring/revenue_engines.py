"""Revenue ceiling engines: offer stacking, funnel scoring, owned audience,
productization, monetization density.

All functions are pure/deterministic — no DB access. Service layer handles persistence.
"""

from __future__ import annotations

from typing import Any, Optional

REVENUE_INTEL_SOURCE = "revenue_intel_engine"

MONETIZATION_LAYERS = [
    "ad_revenue", "affiliate", "sponsor", "lead_capture",
    "direct_product", "cross_sell", "upsell", "email_opt_in",
]


# ---------------------------------------------------------------------------
# 1. Offer Stack Optimizer
# ---------------------------------------------------------------------------

def optimize_offer_stack(
    content: dict,
    offers: list[dict],
    segment: Optional[dict],
) -> list[dict]:
    """Rank offer combinations (primary + secondary + downsell) for a content item."""
    if not offers:
        return []

    scored: list[dict] = []
    for primary in offers:
        primary_rev = float(primary.get("payout_amount", 0)) * float(primary.get("conversion_rate", 0.02))
        complementary = [o for o in offers if o.get("id") != primary.get("id")]

        secondary = None
        secondary_rev = 0.0
        for o in complementary:
            method = o.get("monetization_method", "")
            if method != primary.get("monetization_method", ""):
                rev = float(o.get("payout_amount", 0)) * float(o.get("conversion_rate", 0.02)) * 0.3
                if rev > secondary_rev:
                    secondary = o
                    secondary_rev = rev

        downsell = None
        downsell_rev = 0.0
        for o in complementary:
            if o.get("id") == (secondary or {}).get("id"):
                continue
            payout = float(o.get("payout_amount", 0))
            if payout < float(primary.get("payout_amount", 0)) * 0.5:
                rev = payout * float(o.get("conversion_rate", 0.02)) * 0.15
                if rev > downsell_rev:
                    downsell = o
                    downsell_rev = rev

        combined_rev = primary_rev + secondary_rev + downsell_rev
        aov_uplift = (secondary_rev + downsell_rev) / max(0.01, primary_rev) if primary_rev > 0 else 0
        stack_ids = [primary.get("id")]
        if secondary:
            stack_ids.append(secondary.get("id"))
        if downsell:
            stack_ids.append(downsell.get("id"))

        seg_fit = 1.0
        if segment:
            seg_tags = set(str(t).lower() for t in (segment.get("segment_criteria", {}).get("niche_focus", "").split() if isinstance(segment.get("segment_criteria"), dict) else []))
            offer_tags = set(str(t).lower() for t in (primary.get("audience_fit_tags") or []))
            if seg_tags and offer_tags:
                overlap = len(seg_tags & offer_tags)
                seg_fit = min(1.5, 1.0 + overlap * 0.15)

        scored.append({
            "content_id": content.get("id"),
            "content_title": content.get("title", ""),
            "primary_offer_id": primary.get("id"),
            "primary_offer_name": primary.get("name", ""),
            "secondary_offer_id": secondary.get("id") if secondary else None,
            "downsell_offer_id": downsell.get("id") if downsell else None,
            "offer_stack": stack_ids,
            "expected_revenue_per_impression": round(combined_rev * seg_fit / 1000, 4),
            "expected_aov_uplift_pct": round(aov_uplift * 100, 1),
            "combined_expected_revenue": round(combined_rev * seg_fit, 2),
            "segment_fit_multiplier": round(seg_fit, 2),
            "evidence": {
                "primary_expected": round(primary_rev, 2),
                "secondary_expected": round(secondary_rev, 2),
                "downsell_expected": round(downsell_rev, 2),
                "offers_considered": len(offers),
                "primary_method": primary.get("monetization_method"),
            },
            REVENUE_INTEL_SOURCE: True,
        })

    return sorted(scored, key=lambda x: -x["combined_expected_revenue"])


# ---------------------------------------------------------------------------
# 2. Post-Click Funnel Scorer
# ---------------------------------------------------------------------------

def score_funnel_paths(
    paths: list[dict],
    brand_avg_conversion_rate: float,
) -> list[dict]:
    """Score each content→offer→landing conversion path.

    Each path dict: content_id, offer_id, stages (dict of stage_name → count),
    total_clicks, total_conversions, revenue.
    """
    results: list[dict] = []
    for p in paths:
        stages = p.get("stages", {})
        clicks = int(p.get("total_clicks", 0))
        conversions = int(p.get("total_conversions", 0))
        revenue = float(p.get("revenue", 0))
        cvr = conversions / clicks if clicks > 0 else 0.0

        drop_stage = None
        worst_drop = 0.0
        ordered_stages = ["click", "opt_in", "lead", "booked_call", "purchase"]
        prev_count = clicks
        for stage in ordered_stages:
            count = stages.get(stage, 0)
            if prev_count > 0 and count < prev_count:
                drop_rate = 1.0 - (count / prev_count)
                if drop_rate > worst_drop:
                    worst_drop = drop_rate
                    drop_stage = stage
            if count > 0:
                prev_count = count

        efficiency = cvr / max(0.001, brand_avg_conversion_rate)
        recoverable = 0.0
        fix = "No action needed."
        if efficiency < 0.5 and clicks >= 20:
            target_cvr = brand_avg_conversion_rate * 0.75
            recoverable = (target_cvr - cvr) * clicks * float(p.get("avg_event_value", 10.0))
            fix = f"Path underperforming by {(1 - efficiency) * 100:.0f}% vs brand avg."
            if drop_stage:
                fix += f" Worst drop at '{drop_stage}' stage ({worst_drop * 100:.0f}% loss)."

        results.append({
            "content_id": p.get("content_id"),
            "offer_id": p.get("offer_id"),
            "total_clicks": clicks,
            "total_conversions": conversions,
            "conversion_rate": round(cvr, 4),
            "efficiency_vs_brand_avg": round(efficiency, 2),
            "drop_off_stage": drop_stage,
            "drop_off_rate": round(worst_drop, 2),
            "expected_recoverable_revenue": round(max(0, recoverable), 2),
            "recommended_fix": fix,
            "evidence": {
                "stages": stages,
                "brand_avg_cvr": round(brand_avg_conversion_rate, 4),
                "revenue_on_path": round(revenue, 2),
            },
            REVENUE_INTEL_SOURCE: True,
        })

    return sorted(results, key=lambda x: -x["expected_recoverable_revenue"])


# ---------------------------------------------------------------------------
# 3. Owned Audience Value Engine
# ---------------------------------------------------------------------------

def estimate_owned_audience_value(
    opt_in_count: int,
    subscriber_count: int,
    membership_count: int,
    avg_revenue_per_subscriber: float,
    repeat_purchase_rate: float,
    offers: list[dict],
) -> dict:
    """Estimate value of owned audience channels."""
    best_payout = max((float(o.get("payout_amount", 0)) for o in offers), default=10.0)
    email_value_per = best_payout * 0.05 * max(0.01, repeat_purchase_rate)
    subscriber_value_per = avg_revenue_per_subscriber * 12
    membership_value_per = max(
        avg_revenue_per_subscriber * 1.5,
        best_payout * 0.1,
    )

    total_email = round(opt_in_count * email_value_per, 2)
    total_subscriber = round(subscriber_count * subscriber_value_per, 2)
    total_membership = round(membership_count * membership_value_per, 2)
    total = total_email + total_subscriber + total_membership

    actions: list[dict] = []
    if opt_in_count < max(total_subscribers * 2, 1):  # Relative to current subscriber base
        actions.append({
            "channel": "email",
            "action": "Add lead magnet to top 5 performing content pieces.",
            "expected_uplift": round(best_payout * 0.02 * 500, 2),
        })
    if repeat_purchase_rate < 0.1:
        actions.append({
            "channel": "email",
            "action": "Build post-purchase email sequence targeting repeat conversions.",
            "expected_uplift": round(total_email * 0.3, 2),
        })
    if membership_count == 0 and subscriber_count >= 1000:
        actions.append({
            "channel": "membership",
            "action": "Launch paid membership tier for top-engaged subscribers.",
            "expected_uplift": round(subscriber_count * 0.02 * membership_value_per, 2),
        })

    return {
        "channels": {
            "email": {"size": opt_in_count, "value_per_contact": round(email_value_per, 2), "total_value": total_email},
            "subscribers": {"size": subscriber_count, "value_per_contact": round(subscriber_value_per, 2), "total_value": total_subscriber},
            "membership": {"size": membership_count, "value_per_contact": round(membership_value_per, 2), "total_value": total_membership},
        },
        "total_owned_audience_value": round(total, 2),
        "recommended_actions": actions,
        "evidence": {
            "repeat_purchase_rate": repeat_purchase_rate,
            "avg_revenue_per_subscriber": avg_revenue_per_subscriber,
            "best_offer_payout": best_payout,
        },
        REVENUE_INTEL_SOURCE: True,
    }


# ---------------------------------------------------------------------------
# 4. Productization Recommender
# ---------------------------------------------------------------------------

def recommend_productization(
    winners: list[dict],
    segments: list[dict],
    offers: list[dict],
    comment_purchase_signals: int,
    total_revenue: float,
    subscriber_count: int,
) -> list[dict]:
    """Recommend courses/memberships/products from proven content."""
    recs: list[dict] = []
    existing_methods = {o.get("monetization_method") for o in offers}

    if "course" not in existing_methods and len(winners) >= 2:
        best_winner = winners[0]
        price_est = max(47.0, min(297.0, total_revenue * 0.05))
        seg_size = sum(s.get("estimated_size", 0) for s in segments) or 5000
        addressable = int(seg_size * 0.02)
        recs.append({
            "product_type": "course",
            "title": f"Course: {best_winner.get('title', 'Proven topic')[:80]}",
            "price_point": round(price_est, 0),
            "expected_revenue": round(price_est * addressable * 0.3, 2),
            "expected_cost": 2000.0,
            "confidence": min(0.85, 0.4 + len(winners) * 0.05 + comment_purchase_signals * 0.02),
            "addressable_segment_size": addressable,
            "break_even_units": max(1, int(2000.0 / price_est)),
            "evidence": {
                "winner_count": len(winners),
                "top_winner_title": best_winner.get("title"),
                "comment_purchase_signals": comment_purchase_signals,
            },
            REVENUE_INTEL_SOURCE: True,
        })

    if "membership" not in existing_methods and subscriber_count >= 500:
        monthly = max(9.0, min(49.0, total_revenue * 0.002))
        recs.append({
            "product_type": "membership",
            "title": "Premium Membership Community",
            "price_point": round(monthly, 0),
            "expected_revenue": round(monthly * subscriber_count * 0.03 * 12, 2),
            "expected_cost": 500.0,
            "confidence": min(0.8, 0.35 + subscriber_count * 0.0001),
            "addressable_segment_size": int(subscriber_count * 0.03),
            "break_even_units": max(1, int(500.0 / monthly)),
            "evidence": {"subscriber_count": subscriber_count},
            REVENUE_INTEL_SOURCE: True,
        })

    if "lead_gen" not in existing_methods and total_revenue >= 1000:
        recs.append({
            "product_type": "lead_magnet",
            "title": "Free guide / checklist lead magnet",
            "price_point": 0.0,
            "expected_revenue": round(total_revenue * 0.08, 2),
            "expected_cost": 200.0,
            "confidence": 0.7,
            "addressable_segment_size": sum(s.get("estimated_size", 0) for s in segments) or 5000,
            "break_even_units": 0,
            "evidence": {"total_revenue": total_revenue, "purpose": "list building for upsell"},
            REVENUE_INTEL_SOURCE: True,
        })

    if "consulting" not in existing_methods and total_revenue >= 5000 and len(winners) >= 3:
        recs.append({
            "product_type": "consulting",
            "title": "1-on-1 consulting or coaching offer",
            "price_point": max(197.0, total_revenue * 0.01),
            "expected_revenue": round(max(197.0, total_revenue * 0.01) * 4, 2),
            "expected_cost": 100.0,
            "confidence": min(0.75, 0.3 + len(winners) * 0.05),
            "addressable_segment_size": max(10, subscriber_count // 100),
            "break_even_units": 1,
            "evidence": {"winner_authority_signal": len(winners), "revenue_proof": total_revenue},
            REVENUE_INTEL_SOURCE: True,
        })

    return sorted(recs, key=lambda r: -(r["expected_revenue"] - r["expected_cost"]))


# ---------------------------------------------------------------------------
# 5. Monetization Density Scorer
# ---------------------------------------------------------------------------

def score_monetization_density(
    content_id: str,
    content_title: str,
    has_ad_revenue: bool,
    has_affiliate: bool,
    has_sponsor: bool,
    has_lead_capture: bool,
    has_direct_product: bool,
    has_cross_sell: bool,
    has_upsell: bool,
    has_email_opt_in: bool,
    revenue: float,
    impressions: int,
) -> dict:
    """Score how many revenue layers a content item activates (0-100)."""
    layers = {
        "ad_revenue": has_ad_revenue,
        "affiliate": has_affiliate,
        "sponsor": has_sponsor,
        "lead_capture": has_lead_capture,
        "direct_product": has_direct_product,
        "cross_sell": has_cross_sell,
        "upsell": has_upsell,
        "email_opt_in": has_email_opt_in,
    }
    active = [k for k, v in layers.items() if v]
    missing = [k for k, v in layers.items() if not v]
    density = round(len(active) / len(MONETIZATION_LAYERS) * 100, 1)

    rpm = (revenue / impressions * 1000) if impressions > 0 else 0.0
    revenue_efficiency = min(1.0, rpm / 15.0)
    weighted_score = round(density * 0.7 + revenue_efficiency * 100 * 0.3, 1)

    additions: list[dict] = []
    priority_missing = [
        ("email_opt_in", "Add email capture CTA — builds owned audience for repeat monetization.", 0.05),
        ("affiliate", "Attach affiliate link — passive monetization layer.", 0.03),
        ("lead_capture", "Add lead magnet — converts viewers to contactable leads.", 0.04),
        ("upsell", "Add upsell path from primary offer — increases AOV.", 0.06),
        ("cross_sell", "Add related offer cross-sell — captures adjacent intent.", 0.04),
    ]
    for layer, reason, uplift_pct in priority_missing:
        if layer in missing:
            additions.append({
                "layer": layer,
                "recommendation": reason,
                "expected_revenue_uplift_pct": round(uplift_pct * 100, 1),
            })

    return {
        "content_id": content_id,
        "content_title": content_title,
        "density_score": weighted_score,
        "layer_count": len(active),
        "active_layers": active,
        "missing_layers": missing,
        "recommended_additions": additions[:3],
        "evidence": {
            "rpm": round(rpm, 2),
            "revenue": round(revenue, 2),
            "impressions": impressions,
            "revenue_efficiency": round(revenue_efficiency, 2),
        },
        REVENUE_INTEL_SOURCE: True,
    }
