"""Deal Desk service — strategy recommendations per scope (offer, sponsor, lead)."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.audience_state import AudienceStateReport
from packages.db.models.contribution import ContributionReport
from packages.db.models.core import Brand
from packages.db.models.deal_desk import DealDeskEvent, DealDeskRecommendation
from packages.db.models.market_timing import MarketTimingReport
from packages.db.models.offers import AudienceSegment, Offer, SponsorProfile
from packages.db.models.publishing import PerformanceMetric
from packages.scoring.deal_desk_engine import DEAL_DESK, recommend_deal_strategy


def _strip_meta(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k != DEAL_DESK}


# ---------------------------------------------------------------------------
# Recompute
# ---------------------------------------------------------------------------


async def recompute_deal_desk(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    # Delete active recommendations (events are FK-linked, delete first)
    await db.execute(delete(DealDeskEvent).where(DealDeskEvent.brand_id == brand_id))
    await db.execute(
        delete(DealDeskRecommendation).where(
            DealDeskRecommendation.brand_id == brand_id,
            DealDeskRecommendation.is_active.is_(True),
        )
    )

    # Brand-level metrics
    aud_scalar = (
        await db.execute(
            select(func.coalesce(func.sum(CreatorAccount.follower_count), 0)).where(
                CreatorAccount.brand_id == brand_id
            )
        )
    ).scalar()
    audience_size = int(aud_scalar or 0)

    avg_eng = (
        await db.execute(
            select(func.coalesce(func.avg(PerformanceMetric.engagement_rate), 0.04)).where(
                PerformanceMetric.brand_id == brand_id
            )
        )
    ).scalar()
    avg_engagement = float(avg_eng or 0.04)

    total_rev = (
        await db.execute(
            select(func.coalesce(func.sum(PerformanceMetric.revenue), 0.0)).where(
                PerformanceMetric.brand_id == brand_id
            )
        )
    ).scalar()
    avg_monthly_revenue = float(total_rev or 0.0) / 12.0

    avg_margin = 0.35
    avg_close_rate = 0.25
    brand_authority = min(1.0, audience_size / 100_000 * 0.5 + avg_engagement * 5)

    aud_states = list(
        (
            await db.execute(
                select(AudienceStateReport).where(
                    AudienceStateReport.brand_id == brand_id,
                    AudienceStateReport.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    if aud_states:
        avg_state = sum(float(s.state_score or 0.0) for s in aud_states) / len(aud_states)
        audience_lead_modifier = 0.82 + 0.28 * min(1.0, max(0.0, avg_state))
    else:
        audience_lead_modifier = 1.0

    mt_row = (
        await db.execute(
            select(MarketTimingReport)
            .where(
                MarketTimingReport.brand_id == brand_id,
                MarketTimingReport.is_active.is_(True),
            )
            .order_by(MarketTimingReport.updated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if mt_row:
        ts = float(mt_row.timing_score or 0.0)
        urgency_modifier = 0.72 + 0.36 * min(1.0, max(0.0, ts))
    else:
        urgency_modifier = 1.0

    contrib_rows = list(
        (
            await db.execute(
                select(ContributionReport).where(
                    ContributionReport.brand_id == brand_id,
                    ContributionReport.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    contrib_by_scope: dict[tuple[str, str], float] = {}
    for cr in contrib_rows:
        sid = str(cr.scope_id) if cr.scope_id else ""
        key = (cr.scope_type, sid)
        cs = min(1.0, max(0.0, float(cr.contribution_score or 0.0)))
        if key not in contrib_by_scope or cs > contrib_by_scope[key]:
            contrib_by_scope[key] = cs

    brand_metrics: dict[str, Any] = {
        "brand_authority_score": round(brand_authority, 3),
        "avg_margin": avg_margin,
        "avg_close_rate": avg_close_rate,
        "niche": brand.niche or "general",
        "cross_module_influence": {
            "audience_state_lead_modifier": round(audience_lead_modifier, 4),
            "market_timing_urgency_modifier": round(urgency_modifier, 4),
            "audience_state_rows": len(aud_states),
            "market_timing_report": bool(mt_row),
            "contribution_reports_loaded": len(contrib_rows),
            "contribution_scope_keys": len(contrib_by_scope),
        },
    }

    # Gather deal scopes: offers, sponsors, audience segments
    offers = list(
        (
            await db.execute(
                select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    sponsors = list(
        (
            await db.execute(
                select(SponsorProfile).where(
                    SponsorProfile.brand_id == brand_id, SponsorProfile.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    segments = list(
        (
            await db.execute(
                select(AudienceSegment).where(
                    AudienceSegment.brand_id == brand_id, AudienceSegment.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )

    deal_contexts: list[dict[str, Any]] = []

    for o in offers:
        deal_contexts.append({
            "scope_type": "offer",
            "scope_id": str(o.id),
            "deal_value": float(o.average_order_value or 0) * 10,
            "lead_quality": min(1.0, float(o.conversion_rate or 0) * 10),
            "urgency": 0.5,
            "competition_intensity": 0.4,
            "niche": brand.niche or "general",
        })

    for sp in sponsors:
        budget_mid = (float(sp.budget_range_min or 0) + float(sp.budget_range_max or 0)) / 2
        deal_contexts.append({
            "scope_type": "sponsor",
            "scope_id": str(sp.id),
            "deal_value": budget_mid,
            "lead_quality": 0.6,
            "urgency": 0.5,
            "competition_intensity": 0.5,
            "niche": brand.niche or "general",
        })

    for seg in segments:
        deal_contexts.append({
            "scope_type": "audience_segment",
            "scope_id": str(seg.id),
            "deal_value": float(seg.avg_ltv or 0) * float(seg.estimated_size or 0) * 0.01,
            "lead_quality": min(1.0, float(seg.conversion_rate or 0) * 10),
            "urgency": 0.4,
            "competition_intensity": 0.3,
            "niche": brand.niche or "general",
        })

    if not deal_contexts:
        deal_contexts.append({
            "scope_type": "brand",
            "scope_id": str(brand_id),
            "deal_value": avg_monthly_revenue,
            "lead_quality": 0.5,
            "urgency": 0.5,
            "competition_intensity": 0.5,
            "niche": brand.niche or "general",
        })

    count = 0
    for ctx in deal_contexts:
        ctx_adj = dict(ctx)
        ctx_adj["lead_quality"] = min(1.0, float(ctx_adj.get("lead_quality", 0.5)) * audience_lead_modifier)
        ctx_adj["urgency"] = min(1.0, float(ctx_adj.get("urgency", 0.5)) * urgency_modifier)
        ck = (ctx["scope_type"], ctx["scope_id"])
        contrib_score = contrib_by_scope.get(ck)
        contrib_applied = False
        if contrib_score is not None:
            lq = float(ctx_adj.get("lead_quality", 0.5))
            ctx_adj["lead_quality"] = min(1.0, 0.62 * lq + 0.38 * contrib_score)
            contrib_applied = True
        result = recommend_deal_strategy(ctx_adj, brand_metrics)
        r = _strip_meta(result)

        scope_id_val: uuid.UUID | None = None
        try:
            scope_id_val = uuid.UUID(ctx["scope_id"])
        except (ValueError, KeyError):
            pass

        db.add(
            DealDeskRecommendation(
                brand_id=brand_id,
                scope_type=ctx["scope_type"],
                scope_id=scope_id_val,
                deal_strategy=r["deal_strategy"],
                pricing_stance=r["pricing_stance"],
                packaging_recommendation_json=r.get("packaging_recommendation", {}),
                expected_margin=float(r["expected_margin"]),
                expected_close_probability=float(r["expected_close_probability"]),
                confidence_score=float(r["confidence"]),
                explanation_json={
                    "explanation": r.get("explanation", ""),
                    "decision_summary": {
                        "deal_strategy": r["deal_strategy"],
                        "pricing_stance": r["pricing_stance"],
                    },
                    "cross_module_influence": brand_metrics.get("cross_module_influence"),
                    "adjusted_inputs": {
                        "lead_quality": ctx_adj.get("lead_quality"),
                        "urgency": ctx_adj.get("urgency"),
                        "contribution_score_applied": contrib_score if contrib_applied else None,
                    },
                },
            )
        )
        count += 1

    await db.flush()

    rec_rows = list(
        (
            await db.execute(
                select(DealDeskRecommendation)
                .where(
                    DealDeskRecommendation.brand_id == brand_id,
                    DealDeskRecommendation.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    for rec in rec_rows:
        db.add(
            DealDeskEvent(
                brand_id=brand_id,
                recommendation_id=rec.id,
                event_type="recommendation_generated",
                result_json={
                    "deal_strategy": rec.deal_strategy,
                    "confidence_score": rec.confidence_score,
                },
            )
        )
    await db.flush()
    return {"deal_desk_recommendations": count, "deal_desk_events": len(rec_rows)}


# ---------------------------------------------------------------------------
# Dict helpers
# ---------------------------------------------------------------------------


def _rec_dict(x: DealDeskRecommendation) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "scope_type": x.scope_type,
        "scope_id": str(x.scope_id) if x.scope_id else None,
        "deal_strategy": x.deal_strategy,
        "pricing_stance": x.pricing_stance,
        "packaging_recommendation_json": x.packaging_recommendation_json,
        "expected_margin": x.expected_margin,
        "expected_close_probability": x.expected_close_probability,
        "confidence_score": x.confidence_score,
        "explanation_json": x.explanation_json,
        "is_active": x.is_active,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


# ---------------------------------------------------------------------------
# Getter
# ---------------------------------------------------------------------------


async def get_deal_desk_recommendations(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(DealDeskRecommendation)
                .where(
                    DealDeskRecommendation.brand_id == brand_id,
                    DealDeskRecommendation.is_active.is_(True),
                )
                .order_by(DealDeskRecommendation.confidence_score.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_rec_dict(r) for r in rows]
