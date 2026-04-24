"""Revenue ceiling service: offer stacking, funnel scoring, owned audience,
productization, monetization density.

Architecture: recompute_revenue_intel() is the WRITE path (POST only).
All get_* functions are READ-ONLY.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.enums import (
    ActorType,
    ConfidenceLevel,
    DecisionMode,
    DecisionType,
    RecommendedAction,
)
from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.decisions import MonetizationDecision
from packages.db.models.learning import CommentCashSignal
from packages.db.models.offers import AudienceSegment, Offer
from packages.db.models.portfolio import MonetizationRecommendation
from packages.db.models.publishing import AttributionEvent, PerformanceMetric
from packages.scoring.revenue_engines import (
    estimate_owned_audience_value,
    optimize_offer_stack,
    recommend_productization,
    score_funnel_paths,
    score_monetization_density,
)
from packages.scoring.winner import ContentPerformance, detect_winners

# ---------------------------------------------------------------------------
# WRITE PATH
# ---------------------------------------------------------------------------

async def recompute_revenue_intel(
    db: AsyncSession,
    brand_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Recompute and persist all revenue ceiling artifacts. Idempotent."""
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    accounts = list((await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )).scalars().all())
    offers = list((await db.execute(
        select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
    )).scalars().all())
    offer_dicts = [{
        "id": str(o.id), "name": o.name, "epc": o.epc,
        "conversion_rate": o.conversion_rate, "payout_amount": o.payout_amount,
        "average_order_value": o.average_order_value,
        "monetization_method": o.monetization_method.value if hasattr(o.monetization_method, "value") else str(o.monetization_method),
        "audience_fit_tags": o.audience_fit_tags or [],
        "recurring_commission": o.recurring_commission,
    } for o in offers]

    content_items = list((await db.execute(
        select(ContentItem).where(ContentItem.brand_id == brand_id).limit(200)
    )).scalars().all())

    segments = list((await db.execute(
        select(AudienceSegment).where(AudienceSegment.brand_id == brand_id, AudienceSegment.is_active.is_(True))
    )).scalars().all())
    seg_dicts = [{"name": s.name, "estimated_size": s.estimated_size, "segment_criteria": s.segment_criteria} for s in segments]

    total_rev = sum(float(a.total_revenue or 0) for a in accounts)
    subscriber_count = sum(a.follower_count for a in accounts)

    # Clean prior revenue intel rows
    await db.execute(delete(MonetizationRecommendation).where(MonetizationRecommendation.brand_id == brand_id))
    await db.execute(delete(MonetizationDecision).where(
        MonetizationDecision.brand_id == brand_id,
        MonetizationDecision.decision_mode == DecisionMode.GUARDED_AUTO,
    ))

    # Build content rollups for density + stacking
    content_rollups: list[dict] = []
    for ci in content_items:
        row = (await db.execute(select(
            func.coalesce(func.sum(PerformanceMetric.impressions), 0),
            func.coalesce(func.sum(PerformanceMetric.revenue), 0.0),
            func.coalesce(func.sum(PerformanceMetric.clicks), 0),
            func.coalesce(func.avg(PerformanceMetric.ctr), 0.0),
            func.coalesce(func.avg(PerformanceMetric.engagement_rate), 0.0),
        ).where(PerformanceMetric.content_item_id == ci.id))).one()
        imps, rev, clicks, ctr, er = int(row[0]), float(row[1]), int(row[2]), float(row[3]), float(row[4])
        profit = rev - float(ci.total_cost or 0)
        rpm = (rev / imps * 1000) if imps > 0 else 0.0

        attr_events = list((await db.execute(
            select(AttributionEvent.event_type, func.count())
            .where(AttributionEvent.content_item_id == ci.id)
            .group_by(AttributionEvent.event_type)
        )).all())
        event_types = {str(r[0]): int(r[1]) for r in attr_events}

        content_rollups.append({
            "id": str(ci.id), "title": ci.title, "platform": ci.platform or "youtube",
            "offer_id": str(ci.offer_id) if ci.offer_id else None,
            "monetization_method": ci.monetization_method,
            "impressions": imps, "revenue": rev, "profit": profit, "clicks": clicks,
            "rpm": rpm, "ctr": ctr, "engagement_rate": er,
            "event_types": event_types,
        })

    # --- 1. Offer Stack Optimizer ---
    stack_count = 0
    first_seg = seg_dicts[0] if seg_dicts else None
    for cr in content_rollups:
        stacks = optimize_offer_stack(cr, offer_dicts, first_seg)
        if stacks:
            best = stacks[0]
            ci_obj = await db.get(ContentItem, uuid.UUID(cr["id"]))
            if ci_obj:
                ci_obj.offer_stack = best["offer_stack"]

            db.add(MonetizationRecommendation(
                brand_id=brand_id, content_item_id=uuid.UUID(cr["id"]),
                recommendation_type="offer_stack",
                title=f"Stack: {best['primary_offer_name']} + {len(best['offer_stack']) - 1} more",
                description=f"AOV uplift {best['expected_aov_uplift_pct']}%. Combined rev/1k imps: ${best['expected_revenue_per_impression']}",
                expected_revenue_uplift=best["combined_expected_revenue"],
                expected_cost=0.0, confidence=min(0.9, best["segment_fit_multiplier"] * 0.6),
                evidence=best["evidence"],
            ))
            db.add(MonetizationDecision(
                brand_id=brand_id, decision_type=DecisionType.MONETIZATION,
                decision_mode=DecisionMode.GUARDED_AUTO,
                actor_type=ActorType.HUMAN if user_id else ActorType.SYSTEM,
                actor_id=user_id,
                content_item_id=uuid.UUID(cr["id"]),
                offer_id=uuid.UUID(best["primary_offer_id"]) if best.get("primary_offer_id") else None,
                direct_revenue_estimate=best["combined_expected_revenue"],
                conversion_rate_estimate=float(offer_dicts[0].get("conversion_rate", 0.02)) if offer_dicts else 0.02,
                audience_fit_score=best["segment_fit_multiplier"],
                ltv_estimate=best["combined_expected_revenue"] * 3,
                input_snapshot={"offer_stack": best["offer_stack"], "evidence": best["evidence"]},
                composite_score=min(100.0, best["combined_expected_revenue"] * 2),
                confidence=ConfidenceLevel.MEDIUM,
                recommended_action=RecommendedAction.SCALE if best["combined_expected_revenue"] > 5 else RecommendedAction.EXPERIMENT,
                explanation=f"Offer stack for '{cr['title'][:60]}': {len(best['offer_stack'])} offers, AOV uplift {best['expected_aov_uplift_pct']}%.",
            ))
            stack_count += 1

    # --- 2. Funnel Path Scoring ---
    paths: list[dict] = []
    for cr in content_rollups:
        if cr["clicks"] < 5:
            continue
        total_conv = sum(v for k, v in cr["event_types"].items() if k != "click")
        avg_val_row = (await db.execute(select(
            func.coalesce(func.avg(AttributionEvent.event_value), 10.0)
        ).where(AttributionEvent.brand_id == brand_id, AttributionEvent.event_type != "click"))).scalar() or 10.0
        paths.append({
            "content_id": cr["id"], "offer_id": cr["offer_id"],
            "stages": cr["event_types"], "total_clicks": cr["clicks"],
            "total_conversions": total_conv, "revenue": cr["revenue"],
            "avg_event_value": float(avg_val_row),
        })

    brand_avg_cvr = 0.02
    if paths:
        total_clicks = sum(p["total_clicks"] for p in paths)
        total_conv = sum(p["total_conversions"] for p in paths)
        if total_clicks > 0:
            brand_avg_cvr = total_conv / total_clicks

    funnel_results = score_funnel_paths(paths, brand_avg_cvr)
    funnel_fix_count = 0
    for fr in funnel_results:
        if fr["expected_recoverable_revenue"] > 0:
            db.add(MonetizationRecommendation(
                brand_id=brand_id,
                content_item_id=uuid.UUID(fr["content_id"]) if fr.get("content_id") else None,
                recommendation_type="funnel_fix",
                title=f"Fix funnel: drop at '{fr['drop_off_stage'] or 'unknown'}' stage",
                description=fr["recommended_fix"],
                expected_revenue_uplift=fr["expected_recoverable_revenue"],
                expected_cost=0.0, confidence=min(0.8, fr["efficiency_vs_brand_avg"]),
                evidence=fr["evidence"],
            ))
            funnel_fix_count += 1

    # --- 3. Owned Audience Value ---
    opt_in_count = (await db.execute(select(func.count()).select_from(AttributionEvent).where(
        AttributionEvent.brand_id == brand_id, AttributionEvent.event_type == "opt_in"
    ))).scalar() or 0
    membership_count = (await db.execute(select(func.count()).select_from(AttributionEvent).where(
        AttributionEvent.brand_id == brand_id, AttributionEvent.event_type.in_(["purchase", "affiliate_conversion"])
    ))).scalar() or 0
    repeat_count = max(0, membership_count - len(set(
        str(r[0]) for r in (await db.execute(select(AttributionEvent.tracking_id).where(
            AttributionEvent.brand_id == brand_id, AttributionEvent.event_type == "purchase"
        ).distinct())).all()
    )))
    repeat_rate = repeat_count / max(1, membership_count)
    avg_rev_per_sub = total_rev / max(1, subscriber_count) if subscriber_count > 0 else 0.0

    owned = estimate_owned_audience_value(
        opt_in_count, subscriber_count, membership_count,
        avg_rev_per_sub, repeat_rate, offer_dicts,
    )
    for action in owned.get("recommended_actions", []):
        db.add(MonetizationRecommendation(
            brand_id=brand_id, recommendation_type="owned_audience",
            title=action["action"][:500],
            description=f"Channel: {action['channel']}",
            expected_revenue_uplift=action["expected_uplift"],
            expected_cost=0.0, confidence=0.6,
            evidence=owned["evidence"],
        ))

    # --- 4. Productization ---
    cp_items = [ContentPerformance(
        content_id=cr["id"], title=cr["title"], impressions=cr["impressions"],
        revenue=cr["revenue"], profit=cr["profit"], rpm=cr["rpm"],
        ctr=cr["ctr"], engagement_rate=cr["engagement_rate"],
        platform=cr["platform"], account_id="",
    ) for cr in content_rollups]
    winner_signals = detect_winners(cp_items)
    winner_dicts = [{"title": w.title, "win_score": w.win_score, "content_id": w.content_id} for w in winner_signals if w.is_winner]

    purchase_signal_count = (await db.execute(select(func.count()).select_from(CommentCashSignal).where(
        CommentCashSignal.brand_id == brand_id, CommentCashSignal.signal_type == "purchase_intent_cluster"
    ))).scalar() or 0

    prod_recs = recommend_productization(winner_dicts, seg_dicts, offer_dicts, purchase_signal_count, total_rev, subscriber_count)
    for pr in prod_recs:
        db.add(MonetizationRecommendation(
            brand_id=brand_id, recommendation_type="productization",
            title=pr["title"][:500], description=f"Type: {pr['product_type']}, price: ${pr['price_point']:.0f}",
            expected_revenue_uplift=pr["expected_revenue"],
            expected_cost=pr["expected_cost"], confidence=pr["confidence"],
            evidence=pr["evidence"],
        ))

    # --- 5. Monetization Density ---
    density_count = 0
    for cr in content_rollups:
        et = cr["event_types"]
        mm = (cr.get("monetization_method") or "").lower()
        density = score_monetization_density(
            content_id=cr["id"], content_title=cr["title"],
            has_ad_revenue="adsense" in mm or cr["revenue"] > 0,
            has_affiliate="affiliate" in mm,
            has_sponsor="sponsor" in mm,
            has_lead_capture=et.get("opt_in", 0) > 0 or et.get("lead", 0) > 0,
            has_direct_product="product" in mm or "course" in mm,
            has_cross_sell=len(cr.get("event_types", {})) > 3,
            has_upsell=False,
            has_email_opt_in=et.get("opt_in", 0) > 0,
            revenue=cr["revenue"], impressions=cr["impressions"],
        )
        ci_obj = await db.get(ContentItem, uuid.UUID(cr["id"]))
        if ci_obj:
            ci_obj.monetization_density_score = density["density_score"]

        if density["recommended_additions"]:
            db.add(MonetizationRecommendation(
                brand_id=brand_id, content_item_id=uuid.UUID(cr["id"]),
                recommendation_type="density_improvement",
                title=f"Add layers: {', '.join(a['layer'] for a in density['recommended_additions'][:2])}",
                description=density["recommended_additions"][0]["recommendation"],
                expected_revenue_uplift=sum(a["expected_revenue_uplift_pct"] for a in density["recommended_additions"]) * cr["revenue"] / 100 if cr["revenue"] > 0 else 0,
                expected_cost=0.0, confidence=0.65,
                evidence=density["evidence"],
            ))
            density_count += 1

    await db.flush()
    return {
        "offer_stacks": stack_count,
        "funnel_fixes": funnel_fix_count,
        "owned_audience_actions": len(owned.get("recommended_actions", [])),
        "productization_recs": len(prod_recs),
        "density_improvements": density_count,
        "monetization_decisions": stack_count,
        "owned_audience_value": owned["total_owned_audience_value"],
    }


# ---------------------------------------------------------------------------
# READ PATH (all side-effect free)
# ---------------------------------------------------------------------------

async def get_offer_stacks(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    rows = list((await db.execute(
        select(MonetizationRecommendation).where(
            MonetizationRecommendation.brand_id == brand_id,
            MonetizationRecommendation.recommendation_type == "offer_stack",
        ).order_by(MonetizationRecommendation.expected_revenue_uplift.desc())
    )).scalars().all())
    return [_serialize_rec(r) for r in rows]


async def get_funnel_paths(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    rows = list((await db.execute(
        select(MonetizationRecommendation).where(
            MonetizationRecommendation.brand_id == brand_id,
            MonetizationRecommendation.recommendation_type == "funnel_fix",
        ).order_by(MonetizationRecommendation.expected_revenue_uplift.desc())
    )).scalars().all())
    return [_serialize_rec(r) for r in rows]


async def get_owned_audience_value(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    rows = list((await db.execute(
        select(MonetizationRecommendation).where(
            MonetizationRecommendation.brand_id == brand_id,
            MonetizationRecommendation.recommendation_type == "owned_audience",
        ).order_by(MonetizationRecommendation.expected_revenue_uplift.desc())
    )).scalars().all())
    return [_serialize_rec(r) for r in rows]


async def get_productization(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    rows = list((await db.execute(
        select(MonetizationRecommendation).where(
            MonetizationRecommendation.brand_id == brand_id,
            MonetizationRecommendation.recommendation_type == "productization",
        ).order_by(MonetizationRecommendation.expected_revenue_uplift.desc())
    )).scalars().all())
    return [_serialize_rec(r) for r in rows]


async def get_monetization_density(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    rows = list((await db.execute(
        select(MonetizationRecommendation).where(
            MonetizationRecommendation.brand_id == brand_id,
            MonetizationRecommendation.recommendation_type == "density_improvement",
        ).order_by(MonetizationRecommendation.expected_revenue_uplift.desc())
    )).scalars().all())
    return [_serialize_rec(r) for r in rows]


async def get_revenue_intel_dashboard(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    """Bundled read of all revenue intel slices. Side-effect free."""
    return {
        "brand_id": str(brand_id),
        "offer_stacks": await get_offer_stacks(db, brand_id),
        "funnel_paths": await get_funnel_paths(db, brand_id),
        "owned_audience": await get_owned_audience_value(db, brand_id),
        "productization": await get_productization(db, brand_id),
        "density_improvements": await get_monetization_density(db, brand_id),
    }


def _serialize_rec(r: MonetizationRecommendation) -> dict:
    return {
        "id": str(r.id),
        "content_item_id": str(r.content_item_id) if r.content_item_id else None,
        "recommendation_type": r.recommendation_type,
        "title": r.title,
        "description": r.description,
        "expected_revenue_uplift": r.expected_revenue_uplift,
        "expected_cost": r.expected_cost,
        "confidence": r.confidence,
        "evidence": r.evidence,
        "is_actioned": r.is_actioned,
    }
