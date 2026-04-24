"""Expansion Pack 2 Phase A — lead qualification, closer actions, owned offer recommendations."""

from __future__ import annotations

import uuid
from collections import Counter
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.expansion_pack2_phase_a import (
    CloserAction,
    LeadOpportunity,
    LeadQualificationReport,
    OwnedOfferRecommendation,
)
from packages.db.models.learning import CommentCluster
from packages.db.models.offers import AudienceSegment, Offer
from packages.db.models.publishing import PerformanceMetric
from packages.db.models.revenue_ceiling_phase_a import FunnelLeakFix
from packages.scoring.expansion_pack2_phase_a_engines import (
    EP2A,
    detect_offer_opportunities,
    generate_closer_actions,
    score_lead,
)


def _strip_meta(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k != EP2A}


# ---------------------------------------------------------------------------
# Recompute functions
# ---------------------------------------------------------------------------


async def recompute_lead_qualification(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    # Active offers → scoring parameters
    offers = list(
        (await db.execute(select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True)))).scalars().all()
    )
    existing_offer_count = len(offers)
    avg_offer_aov = (
        sum(float(o.average_order_value or 0) for o in offers) / existing_offer_count if existing_offer_count else 0.0
    )
    avg_offer_cvr = (
        sum(float(o.conversion_rate or 0) for o in offers) / existing_offer_count if existing_offer_count else 0.0
    )

    # Audience size from creator accounts
    aud_scalar = (
        await db.execute(
            select(func.coalesce(func.sum(CreatorAccount.follower_count), 0)).where(CreatorAccount.brand_id == brand_id)
        )
    ).scalar()
    audience_size = int(aud_scalar or 0)

    # Average content engagement rate
    eng_scalar = (
        await db.execute(
            select(func.coalesce(func.avg(PerformanceMetric.engagement_rate), 0.04)).where(
                PerformanceMetric.brand_id == brand_id
            )
        )
    ).scalar()
    avg_engagement = float(eng_scalar or 0.04)

    # Comment clusters (limit 50) — each cluster is treated as a lead signal
    clusters = list(
        (await db.execute(select(CommentCluster).where(CommentCluster.brand_id == brand_id).limit(50))).scalars().all()
    )

    # Build (lead_source, message_text) pairs from clusters or synthetics
    # Note: CommentCluster has no representative_text field; cluster_label is the message proxy.
    lead_inputs: list[tuple[str, str]] = []
    if clusters:
        for cluster in clusters:
            msg = (cluster.cluster_label or "general inquiry")[:1000]
            lead_inputs.append(("comment", msg))
    else:
        niche_label = brand.niche or "this"
        for src in ["dm", "call_booked", "email"]:
            lead_inputs.append((src, f"Interested in {niche_label} solutions — {src}"))

    # Delete old rows in FK-safe order: CloserAction → LeadOpportunity → LeadQualificationReport
    await db.execute(delete(CloserAction).where(CloserAction.brand_id == brand_id))
    await db.execute(delete(LeadOpportunity).where(LeadOpportunity.brand_id == brand_id))
    await db.execute(delete(LeadQualificationReport).where(LeadQualificationReport.brand_id == brand_id))

    # Score each lead, insert rows
    channel_counter: Counter[str] = Counter()
    action_counter: Counter[str] = Counter()
    hot = warm = cold = 0
    total_composite = 0.0
    total_expected_value = 0.0

    for lead_source, message_text in lead_inputs:
        result = score_lead(
            lead_source=lead_source,
            niche=brand.niche or "general",
            message_text=message_text,
            audience_size=audience_size,
            avg_offer_aov=avg_offer_aov,
            avg_offer_cvr=avg_offer_cvr,
            content_engagement_rate=avg_engagement,
            existing_offer_count=existing_offer_count,
        )
        r = _strip_meta(result)

        tier = r["qualification_tier"]
        if tier == "hot":
            hot += 1
        elif tier == "warm":
            warm += 1
        else:
            cold += 1

        total_composite += float(r["composite_score"])
        total_expected_value += float(r["expected_value"])
        channel_counter[r.get("channel_preference", "email")] += 1
        action_counter[r.get("recommended_action", "low_priority_follow_up")] += 1

        # Insert LeadOpportunity — lo.id is set Python-side via default=uuid.uuid4
        lo = LeadOpportunity(
            brand_id=brand_id,
            lead_source=lead_source,
            message_text=message_text[:2000] if message_text else None,
            urgency_score=float(r["urgency_score"]),
            budget_proxy_score=float(r["budget_proxy_score"]),
            sophistication_score=float(r["sophistication_score"]),
            offer_fit_score=float(r["offer_fit_score"]),
            trust_readiness_score=float(r["trust_readiness_score"]),
            composite_score=float(r["composite_score"]),
            qualification_tier=tier,
            recommended_action=r.get("recommended_action", ""),
            expected_value=float(r["expected_value"]),
            likelihood_to_close=float(r["likelihood_to_close"]),
            channel_preference=r.get("channel_preference", "email"),
            confidence=float(r["confidence"]),
            explanation=r.get("explanation"),
        )
        db.add(lo)

        # Generate and insert closer actions linked to lo.id (Python-side UUID — no flush needed)
        actions = generate_closer_actions(
            qualification_tier=tier,
            lead_source=lead_source,
            niche=brand.niche or "general",
            composite_score=float(r["composite_score"]),
            urgency_score=float(r["urgency_score"]),
            budget_proxy_score=float(r["budget_proxy_score"]),
            trust_readiness_score=float(r["trust_readiness_score"]),
            avg_offer_aov=avg_offer_aov,
            brand_name=brand.name,
        )
        for act in actions:
            a = _strip_meta(act)
            db.add(
                CloserAction(
                    brand_id=brand_id,
                    lead_opportunity_id=lo.id,
                    action_type=a.get("action_type", "follow_up"),
                    priority=int(a.get("priority", 1)),
                    channel=a.get("channel", "email"),
                    subject_or_opener=str(a.get("subject_or_opener", ""))[:500],
                    timing=str(a.get("timing", ""))[:255],
                    rationale=a.get("rationale"),
                    expected_outcome=a.get("expected_outcome"),
                )
            )

    # Aggregate stats for the qualification report
    n = len(lead_inputs)
    avg_composite = total_composite / n if n else 0.0
    avg_expected_value = total_expected_value / n if n else 0.0
    top_channel = channel_counter.most_common(1)[0][0] if channel_counter else "email"
    top_action = action_counter.most_common(1)[0][0] if action_counter else "low_priority_follow_up"

    # Insert new LeadQualificationReport
    db.add(
        LeadQualificationReport(
            brand_id=brand_id,
            total_leads_scored=n,
            hot_leads=hot,
            warm_leads=warm,
            cold_leads=cold,
            avg_composite_score=round(avg_composite, 4),
            avg_expected_value=round(avg_expected_value, 2),
            top_channel=top_channel,
            top_recommended_action=top_action,
            signal_summary={
                "channel_breakdown": dict(channel_counter),
                "action_breakdown": dict(action_counter),
            },
            confidence=min(1.0, round(0.40 + (n / 20.0) * 0.60, 4)),
            explanation=(
                f"Scored {n} lead signal(s) for brand '{brand.name}': "
                f"{hot} hot, {warm} warm, {cold} cold. "
                f"Avg composite {avg_composite:.3f}; "
                f"avg expected value ${avg_expected_value:,.2f}."
            ),
        )
    )

    await db.flush()
    return {"leads_scored": n, "hot": hot, "warm": warm, "cold": cold}


async def recompute_owned_offer_recommendations(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    # Active offers → existing_offer_types
    offers = list(
        (await db.execute(select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True)))).scalars().all()
    )
    existing_offer_types = list({getattr(o.monetization_method, "value", str(o.monetization_method)) for o in offers})

    # ContentItem rows (limit 100)
    items = list(
        (await db.execute(select(ContentItem).where(ContentItem.brand_id == brand_id).limit(100))).scalars().all()
    )

    # PerformanceMetric aggregates per content item
    agg_rows = (
        await db.execute(
            select(
                PerformanceMetric.content_item_id,
                func.coalesce(func.sum(PerformanceMetric.impressions), 0).label("imp"),
                func.coalesce(func.avg(PerformanceMetric.engagement_rate), 0.04).label("eng"),
                func.coalesce(func.sum(PerformanceMetric.revenue), 0.0).label("rev"),
            )
            .where(PerformanceMetric.brand_id == brand_id)
            .group_by(PerformanceMetric.content_item_id)
        )
    ).all()
    perf_map: dict[uuid.UUID, tuple[int, float, float]] = {
        row[0]: (int(row[1]), float(row[2]), float(row[3])) for row in agg_rows
    }

    content_engagement_signals: list[dict[str, Any]] = []
    for ci in items:
        imp, eng, rev = perf_map.get(ci.id, (0, 0.04, 0.0))
        content_engagement_signals.append(
            {
                "content_id": str(ci.id),
                "title": ci.title or "",
                "impressions": imp,
                "engagement_rate": eng,
                "revenue": rev,
            }
        )

    # AudienceSegment rows
    segs = list(
        (
            await db.execute(
                select(AudienceSegment).where(
                    AudienceSegment.brand_id == brand_id,
                    AudienceSegment.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    audience_segments: list[dict[str, Any]] = [
        {
            "name": s.name,
            "description": s.description or "",
            "estimated_size": s.estimated_size,
            "avg_ltv": s.avg_ltv,
            "conversion_rate": s.conversion_rate,
        }
        for s in segs
    ]

    # CommentCluster → top_comment_themes (limit 20)
    clusters = list(
        (await db.execute(select(CommentCluster).where(CommentCluster.brand_id == brand_id).limit(20))).scalars().all()
    )
    top_comment_themes = [c.cluster_label for c in clusters if c.cluster_label]

    # FunnelLeakFix → top_objections (suspected_cause strings, limit 10)
    leak_scalars = list(
        (
            await db.execute(
                select(FunnelLeakFix.suspected_cause)
                .where(
                    FunnelLeakFix.brand_id == brand_id,
                    FunnelLeakFix.is_active.is_(True),
                )
                .limit(10)
            )
        )
        .scalars()
        .all()
    )
    top_objections = [t for t in leak_scalars if t]

    # avg_monthly_revenue — total PerformanceMetric revenue / 12 as monthly proxy
    rev_scalar = (
        await db.execute(
            select(func.coalesce(func.sum(PerformanceMetric.revenue), 0.0)).where(
                PerformanceMetric.brand_id == brand_id
            )
        )
    ).scalar()
    avg_monthly_revenue = float(rev_scalar or 0.0) / 12.0

    # total_audience_size
    aud_scalar = (
        await db.execute(
            select(func.coalesce(func.sum(CreatorAccount.follower_count), 0)).where(CreatorAccount.brand_id == brand_id)
        )
    ).scalar()
    total_audience_size = int(aud_scalar or 0)

    # Detect opportunities via scoring engine
    opportunities = detect_offer_opportunities(
        niche=brand.niche or "general",
        brand_name=brand.name,
        top_comment_themes=top_comment_themes,
        top_objections=top_objections,
        content_engagement_signals=content_engagement_signals,
        audience_segments=audience_segments,
        existing_offer_types=existing_offer_types,
        total_audience_size=total_audience_size,
        avg_monthly_revenue=avg_monthly_revenue,
    )

    # Delete old rows and insert fresh ones
    await db.execute(delete(OwnedOfferRecommendation).where(OwnedOfferRecommendation.brand_id == brand_id))

    for opp in opportunities:
        r = _strip_meta(opp)
        db.add(
            OwnedOfferRecommendation(
                brand_id=brand_id,
                opportunity_key=r["opportunity_key"][:255],
                signal_type=r["signal_type"],
                detected_signal=r.get("detected_signal"),
                recommended_offer_type=r.get("recommended_offer_type", ""),
                offer_name_suggestion=str(r.get("offer_name_suggestion", ""))[:500],
                price_point_min=float(r.get("price_point_min", 0.0)),
                price_point_max=float(r.get("price_point_max", 0.0)),
                estimated_demand_score=float(r.get("estimated_demand_score", 0.0)),
                estimated_first_month_revenue=float(r.get("estimated_first_month_revenue", 0.0)),
                audience_fit=r.get("audience_fit"),
                confidence=float(r.get("confidence", 0.0)),
                explanation=r.get("explanation"),
                build_priority=r.get("build_priority", "medium"),
            )
        )

    await db.flush()
    return {"owned_offer_rows": len(opportunities)}


# ---------------------------------------------------------------------------
# Dict helpers (model → plain dict)
# ---------------------------------------------------------------------------


def _lo_dict(x: LeadOpportunity) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "lead_source": x.lead_source,
        "message_text": x.message_text,
        "urgency_score": x.urgency_score,
        "budget_proxy_score": x.budget_proxy_score,
        "sophistication_score": x.sophistication_score,
        "offer_fit_score": x.offer_fit_score,
        "trust_readiness_score": x.trust_readiness_score,
        "composite_score": x.composite_score,
        "qualification_tier": x.qualification_tier,
        "recommended_action": x.recommended_action,
        "expected_value": x.expected_value,
        "likelihood_to_close": x.likelihood_to_close,
        "channel_preference": x.channel_preference,
        "confidence": x.confidence,
        "explanation": x.explanation,
    }


def _ca_dict(x: CloserAction) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "lead_opportunity_id": str(x.lead_opportunity_id) if x.lead_opportunity_id else None,
        "action_type": x.action_type,
        "priority": x.priority,
        "channel": x.channel,
        "subject_or_opener": x.subject_or_opener,
        "timing": x.timing,
        "rationale": x.rationale,
        "expected_outcome": x.expected_outcome,
        "is_completed": x.is_completed,
    }


def _lqr_dict(x: LeadQualificationReport) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "total_leads_scored": x.total_leads_scored,
        "hot_leads": x.hot_leads,
        "warm_leads": x.warm_leads,
        "cold_leads": x.cold_leads,
        "avg_composite_score": x.avg_composite_score,
        "avg_expected_value": x.avg_expected_value,
        "top_channel": x.top_channel,
        "top_recommended_action": x.top_recommended_action,
        "signal_summary": x.signal_summary,
        "confidence": x.confidence,
        "explanation": x.explanation,
    }


def _oor_dict(x: OwnedOfferRecommendation) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "opportunity_key": x.opportunity_key,
        "signal_type": x.signal_type,
        "detected_signal": x.detected_signal,
        "recommended_offer_type": x.recommended_offer_type,
        "offer_name_suggestion": x.offer_name_suggestion,
        "price_point_min": x.price_point_min,
        "price_point_max": x.price_point_max,
        "estimated_demand_score": x.estimated_demand_score,
        "estimated_first_month_revenue": x.estimated_first_month_revenue,
        "audience_fit": x.audience_fit,
        "confidence": x.confidence,
        "explanation": x.explanation,
        "build_priority": x.build_priority,
    }


# ---------------------------------------------------------------------------
# Getter functions
# ---------------------------------------------------------------------------


async def get_lead_opportunities(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(LeadOpportunity)
                .where(
                    LeadOpportunity.brand_id == brand_id,
                    LeadOpportunity.is_active.is_(True),
                )
                .order_by(LeadOpportunity.composite_score.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    return [_lo_dict(r) for r in rows]


async def get_closer_actions(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(CloserAction)
                .where(
                    CloserAction.brand_id == brand_id,
                    CloserAction.is_active.is_(True),
                )
                .order_by(CloserAction.priority.asc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    return [_ca_dict(r) for r in rows]


async def get_lead_qualification_report(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(LeadQualificationReport)
                .where(LeadQualificationReport.brand_id == brand_id)
                .order_by(LeadQualificationReport.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_lqr_dict(r) for r in rows]


async def get_owned_offer_recommendations(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(OwnedOfferRecommendation)
                .where(
                    OwnedOfferRecommendation.brand_id == brand_id,
                    OwnedOfferRecommendation.is_active.is_(True),
                )
                .order_by(OwnedOfferRecommendation.estimated_demand_score.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_oor_dict(r) for r in rows]
