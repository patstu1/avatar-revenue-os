"""Phase 6 growth intelligence: segments, LTV, leaks, expansion, paid, trust, cross-platform."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from packages.scoring.winner import ContentPerformance, detect_winners

PHASE6_SOURCE = "phase6_engine"


@dataclass
class ContentPerfRollup:
    content_id: str
    title: str
    brand_id: str
    creator_account_id: Optional[str]
    platform: str
    offer_id: Optional[str]
    impressions: int = 0
    clicks: int = 0
    views: int = 0
    revenue: float = 0.0
    profit: float = 0.0
    cost: float = 0.0
    ctr: float = 0.0
    rpm: float = 0.0
    engagement_rate: float = 0.0
    avg_watch_pct: float = 0.0
    conversions: int = 0
    conversion_rate: float = 0.0


def cluster_segments_rules(
    accounts: list[dict],
    perf_by_account: dict[str, dict],
) -> list[dict]:
    """Rules-based clusters: platform × geography × language × niche_focus."""
    clusters: dict[str, dict] = {}
    for a in accounts:
        if not a.get("is_active", True):
            continue
        plat = (a.get("platform") or "unknown").lower()
        geo = (a.get("geography") or "global").lower()
        lang = (a.get("language") or "en").lower()
        niche = (a.get("niche_focus") or "general").lower()[:80]
        key = f"{plat}|{geo}|{lang}|{niche}"
        if key not in clusters:
            clusters[key] = {
                "name": f"{plat.upper()} · {geo} · {lang} · {niche[:40]}",
                "criteria": {
                    "phase6_auto": True,
                    "platform": plat,
                    "geography": geo,
                    "language": lang,
                    "niche_focus": niche,
                },
                "account_ids": [],
                "revenue": 0.0,
                "profit": 0.0,
                "impressions": 0,
            }
        clusters[key]["account_ids"].append(str(a["id"]))
        pb = perf_by_account.get(str(a["id"]), {})
        clusters[key]["revenue"] += float(pb.get("revenue", 0))
        clusters[key]["profit"] += float(pb.get("profit", 0))
        clusters[key]["impressions"] += int(pb.get("impressions", 0))

    out = []
    for c in clusters.values():
        n_ac = max(1, len(c["account_ids"]))
        follower_sum = 0
        for aid in c["account_ids"]:
            for x in accounts:
                if str(x["id"]) == aid:
                    follower_sum += int(x.get("follower_count") or 0)
                    break
        est_size = follower_sum or n_ac * 1000
        impressions = max(1, c["impressions"])
        revenue = c["revenue"]
        cvr = round(min(1.0, revenue / max(1.0, est_size * 0.01)), 4) if est_size > 0 else 0.02
        avg_ltv = round(revenue / n_ac, 2) if n_ac > 0 and revenue > 0 else 0.0
        out.append(
            {
                "name": c["name"],
                "description": "Rules cluster: platform + geo + language + niche",
                "segment_criteria": c["criteria"],
                "estimated_size": est_size,
                "revenue_contribution": round(revenue, 2),
                "conversion_rate": cvr,
                "avg_ltv": avg_ltv,
                "platforms": list({c["criteria"]["platform"]}),
            }
        )
    return out


def estimate_ltv_rules(
    offer: dict,
    platform: str,
    geography: str,
    language: str,
    topic_label: str,
    segment_name: str,
    attribution_source: str,
    base_conversion: float,
) -> dict:
    """Heuristic LTV from offer economics × dimensional multipliers (not ML)."""
    aov = float(offer.get("average_order_value") or 0) or float(offer.get("payout_amount") or 0)
    payout = float(offer.get("payout_amount") or 0)
    cr = max(0.001, float(offer.get("conversion_rate") or base_conversion or 0.02))
    repeat_est = 1.15 if offer.get("recurring_commission") else 1.05
    geo_mult = 1.1 if (geography or "").upper() in ("US", "UK", "CA", "AU") else 0.85
    plat_mult = {
        "youtube": 1.05, "tiktok": 0.95, "instagram": 1.0,
        "twitter": 0.85, "reddit": 0.80, "linkedin": 1.10, "facebook": 0.90,
    }.get(platform.lower(), 1.0)
    lang_mult = 1.0 if (language or "en").lower() == "en" else 0.9

    ltv_30 = payout * cr * repeat_est * geo_mult * plat_mult * lang_mult * 0.25
    ltv_90 = ltv_30 * 2.8
    ltv_365 = ltv_30 * 9.0 + aov * cr * 3.0 * geo_mult

    return {
        "segment_name": f"{segment_name}|{platform}|{geography}|{language}",
        "model_type": "rules_based_phase6",
        "parameters": {
            "phase6_auto": True,
            "dimensions": {
                "platform": platform,
                "geography": geography,
                "language": language,
                "topic": topic_label,
                "offer_id": offer.get("id"),
                "segment": segment_name,
                "attribution_source": attribution_source,
            },
        },
        "estimated_ltv_30d": round(ltv_30, 2),
        "estimated_ltv_90d": round(ltv_90, 2),
        "estimated_ltv_365d": round(ltv_365, 2),
        "confidence": min(0.95, 0.35 + cr * 5),
        "sample_size": int(offer.get("priority") or 0) + 100,
    }


def detect_leaks(
    items: list[ContentPerfRollup],
    funnel_impressions: int,
    funnel_clicks: int,
    funnel_conversions: int,
    offer_by_id: dict[str, dict],
    account_follower_growth: dict[str, float],
) -> list[dict]:
    """Rule-based leak detection for dashboard + persistence."""
    leaks: list[dict] = []
    funnel_ctr = funnel_clicks / funnel_impressions if funnel_impressions > 0 else 0.0
    for it in items:
        oid = it.offer_id
        offer = offer_by_id.get(str(oid)) if oid else None
        epc_potential = float(offer.get("epc", 0)) * 0.5 if offer else 5.0

        if it.impressions >= 3000 and it.ctr < 0.006:
            leaks.append(
                {
                    "leak_type": "high_views_low_clicks",
                    "entity_type": "content_item",
                    "entity_id": it.content_id,
                    "estimated_leaked_revenue": round(it.impressions * 0.001 * max(epc_potential, 1.0), 2),
                    "estimated_recoverable": round(it.impressions * 0.002 * max(epc_potential, 1.0), 2),
                    "root_cause": "CTR below threshold despite reach",
                    "recommended_fix": "Test hooks, thumbnails, first-frame; verify CTA clarity",
                    "severity": "high" if it.ctr < 0.003 else "medium",
                    "details": {"ctr": it.ctr, "impressions": it.impressions, PHASE6_SOURCE: True},
                }
            )

        if it.clicks >= 200 and it.conversion_rate < 0.008:
            epfc = max(epc_potential, 1.0)
            leaks.append(
                {
                    "leak_type": "high_clicks_low_conversions",
                    "entity_type": "content_item",
                    "entity_id": it.content_id,
                    "estimated_leaked_revenue": round(it.clicks * epfc * 0.15, 2),
                    "estimated_recoverable": round(it.clicks * epfc * 0.08, 2),
                    "root_cause": "Traffic not converting — landing or offer mismatch",
                    "recommended_fix": "Align offer to intent; shorten funnel; A/B LP",
                    "severity": "high",
                    "details": {"clicks": it.clicks, "cvr": it.conversion_rate, PHASE6_SOURCE: True},
                }
            )

        if it.engagement_rate >= 0.045 and it.rpm < max(2.0, epc_potential * 0.15):
            leaks.append(
                {
                    "leak_type": "strong_content_weak_offer_fit",
                    "entity_type": "content_item",
                    "entity_id": it.content_id,
                    "estimated_leaked_revenue": round(it.impressions * 0.002 * max(epc_potential, 1.0), 2),
                    "estimated_recoverable": round(it.impressions * 0.0015 * max(epc_potential, 1.0), 2),
                    "root_cause": "Engagement strong but monetization weak vs offer potential",
                    "recommended_fix": "Swap or bundle offer; tighten bridge page",
                    "severity": "medium",
                    "details": {"rpm": it.rpm, "engagement": it.engagement_rate, PHASE6_SOURCE: True},
                }
            )

        if it.avg_watch_pct >= 0.4 and it.rpm < 3.0 and it.impressions >= 1500:
            leaks.append(
                {
                    "leak_type": "good_retention_poor_monetization",
                    "entity_type": "content_item",
                    "entity_id": it.content_id,
                    "estimated_leaked_revenue": round(it.views * 0.0003 * max(epc_potential, 1.0), 2),
                    "estimated_recoverable": round(it.views * 0.0002 * max(epc_potential, 1.0), 2),
                    "root_cause": "Watch/retention signal solid but RPM weak",
                    "recommended_fix": "Strengthen mid-roll CTA and offer bridge; test higher-intent offer",
                    "severity": "medium",
                    "details": {"avg_watch_pct": it.avg_watch_pct, "rpm": it.rpm, PHASE6_SOURCE: True},
                }
            )

        if it.cost > 20 and it.revenue > 0 and it.profit < 0 and it.cost > it.revenue * 0.4:
            leaks.append(
                {
                    "leak_type": "high_cost_low_return",
                    "entity_type": "content_item",
                    "entity_id": it.content_id,
                    "estimated_leaked_revenue": round(abs(it.profit), 2),
                    "estimated_recoverable": round(min(it.cost * 0.35, abs(it.profit)), 2),
                    "root_cause": "Production cost outpaces return on this asset",
                    "recommended_fix": "Reduce variant cost; template winning format; pause low-ROI experiments",
                    "severity": "high",
                    "details": {"cost": it.cost, "revenue": it.revenue, "profit": it.profit, PHASE6_SOURCE: True},
                }
            )

        aid = it.creator_account_id or ""
        fg = account_follower_growth.get(aid, 0.0)
        if fg >= 0.02 and it.ctr < 0.01 and it.impressions >= 2000:
            leaks.append(
                {
                    "leak_type": "strong_audience_weak_funnel",
                    "entity_type": "creator_account",
                    "entity_id": aid or None,
                    "estimated_leaked_revenue": round(it.impressions * 0.001 * max(epc_potential, 1.0), 2),
                    "estimated_recoverable": round(it.impressions * 0.0015 * max(epc_potential, 1.0), 2),
                    "root_cause": "Audience growth present but click-through underperforming",
                    "recommended_fix": "Fix above-fold CTA; audit link in bio / pinned funnel",
                    "severity": "medium",
                    "details": {"follower_growth_rate": fg, "ctr": it.ctr, PHASE6_SOURCE: True},
                }
            )

    if funnel_impressions >= 5000 and funnel_ctr < 0.008 and funnel_conversions < max(3, funnel_clicks // 80):
        leaks.append(
            {
                "leak_type": "strong_audience_weak_funnel",
                "entity_type": "brand_funnel",
                "entity_id": None,
                "estimated_leaked_revenue": round(funnel_impressions * 0.0005 * 10.0, 2),
                "estimated_recoverable": round(funnel_impressions * 0.0003 * 10.0, 2),
                "root_cause": "Brand-level funnel CTR/conversion softness",
                "recommended_fix": "Unified UTM hygiene; reduce friction on first click goal",
                "severity": "high",
                "details": {
                    "funnel_ctr": funnel_ctr,
                    "funnel_clicks": funnel_clicks,
                    "conversions": funnel_conversions,
                    PHASE6_SOURCE: True,
                },
            }
        )

    return leaks


def plan_cross_platform_derivatives(
    items: list[ContentPerformance],
    platforms_present: set[str],
) -> list[dict]:
    """Derivative targets for proven winners only (cross-platform flow)."""
    win_by_id = {s.content_id: s for s in detect_winners(items, list(platforms_present)) if s.is_winner}
    all_plat = {"youtube", "tiktok", "instagram", "twitter", "reddit", "linkedin", "facebook"}
    plans = []
    for w in items:
        sig = win_by_id.get(w.content_id)
        if not sig or not w.platform:
            continue
        for p in all_plat:
            if p == w.platform.lower():
                continue
            if p not in platforms_present:
                prio = min(100.0, w.rpm / 2.0 + sig.win_score * 20.0)
                plans.append(
                    {
                        "source_content_id": w.content_id,
                        "source_platform": w.platform,
                        "target_platform": p,
                        "title": w.title,
                        "rationale": f"Winner ({w.platform}) → adapt format for {p}",
                        "priority": round(prio, 2),
                        "win_score": round(sig.win_score, 3),
                    }
                )
    return plans[:40]


def geo_language_expansion_rules(
    accounts: list[dict],
    brand_niche: Optional[str],
) -> list[dict]:
    """Geo/language expansion rows for persistence."""
    geos = {((a.get("geography") or "US") or "").upper() for a in accounts}
    langs = {(a.get("language") or "en").lower() for a in accounts}
    plat_set = {(a.get("platform") or "").lower() for a in accounts}
    recs: list[dict] = []
    if "US" in geos and len(geos) < 2:
        recs.append(
            {
                "target_geography": "EU-5",
                "target_language": "en",
                "target_platform": next(iter(plat_set - {""}) or {"youtube"}),
                "estimated_audience_size": 250_000,
                "estimated_revenue_potential": 4800.0,
                "competition_level": "medium",
                "entry_cost_estimate": 400.0,
                "rationale": "Diversify beyond single geography to reduce concentration risk",
            }
        )
    if "en" in langs and len(langs) < 2:
        recs.append(
            {
                "target_geography": "LATAM",
                "target_language": "es",
                "target_platform": "youtube",
                "estimated_audience_size": 400_000,
                "estimated_revenue_potential": 3200.0,
                "competition_level": "medium",
                "entry_cost_estimate": 350.0,
                "rationale": f"Language expansion from core ({brand_niche or 'brand'}) angle",
            }
        )
    if "tiktok" in plat_set and "youtube" not in plat_set:
        recs.append(
            {
                "target_geography": (list(geos)[0] if geos else "US"),
                "target_language": "en",
                "target_platform": "youtube",
                "estimated_audience_size": 180_000,
                "estimated_revenue_potential": 5100.0,
                "competition_level": "high",
                "entry_cost_estimate": 520.0,
                "rationale": "Long-form evergreen on YouTube complements short-form TikTok",
            }
        )
    return recs


def paid_amplification_candidates(
    items: list[ContentPerformance],
    existing_content_ids: set[str],
    min_win_score: float = 0.5,
) -> list[dict]:
    """Only proven winners qualify for paid boost candidates."""
    signals = detect_winners(items, [])
    out = []
    for s in signals:
        if not s.is_winner or s.win_score < min_win_score:
            continue
        if s.content_id in existing_content_ids:
            continue
        budget = 150.0 + min(850.0, s.win_score * 400.0)
        out.append(
            {
                "content_item_id": s.content_id,
                "platform": next((it.platform for it in items if it.content_id == s.content_id), "youtube"),
                "suggested_budget": round(budget, 2),
                "win_score": round(s.win_score, 3),
                "explanation": s.explanation + " | Paid only after winner threshold met.",
                "is_candidate": True,
            }
        )
    return out


def trust_score_for_account(account: dict, rollup: dict[str, Any]) -> dict[str, Any]:
    """Trust & authority heuristic (0–100) with component breakdown."""
    health = (account.get("account_health") or "healthy").lower()
    health_pts = {"healthy": 25, "warning": 18, "degraded": 12, "critical": 5, "suspended": 0}.get(health, 15)
    consistency = min(25, 10 + min(15, (account.get("posting_capacity_per_day") or 1) * 2))
    originality = max(0, 20 - float(account.get("originality_drift_score") or 0) * 15)
    fatigue = max(0, 15 - float(account.get("fatigue_score") or 0) * 10)
    engagement_signal = min(15, float(rollup.get("engagement_rate", 0)) * 120)

    total = min(100.0, health_pts + consistency + originality + fatigue + engagement_signal)
    recs = []
    if health_pts < 18:
        recs.append("Stabilize account health before scaling authority plays.")
    if float(account.get("originality_drift_score") or 0) > 0.45:
        recs.append("Refresh creative templates to protect perceived authenticity.")
    if float(rollup.get("engagement_rate", 0)) < 0.02:
        recs.append("Lift comment/reply cadence and community prompts.")

    return {
        "trust_score": round(total, 2),
        "components": {
            "health": round(health_pts, 2),
            "consistency_posting": round(consistency, 2),
            "originality": round(originality, 2),
            "fatigue_inverse": round(fatigue, 2),
            "engagement_quality": round(engagement_signal, 2),
        },
        "recommendations": recs,
        "evidence": {
            "platform": account.get("platform"),
            "follower_count": account.get("follower_count"),
        },
    }
