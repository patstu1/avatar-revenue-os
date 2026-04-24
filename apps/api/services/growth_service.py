"""Phase 6: audience segments, LTV, leaks, expansion, paid candidates, trust — persist + query.

Architecture: sync_phase6_brand() is the WRITE path (called by POST recompute only).
All get_* functions are READ-ONLY — they return persisted data without mutations.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services import analytics_service as asvc
from packages.db.enums import (
    ActorType,
    ConfidenceLevel,
    DecisionMode,
    DecisionType,
    JobStatus,
    RecommendedAction,
)
from packages.db.models.accounts import AccountPortfolio, CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.decisions import ExpansionDecision
from packages.db.models.offers import AudienceSegment, LtvModel, Offer
from packages.db.models.portfolio import (
    GeoLanguageExpansionRecommendation,
    PaidAmplificationJob,
    RevenueLeakReport,
    TrustSignalReport,
)
from packages.db.models.publishing import AttributionEvent, PerformanceMetric
from packages.scoring.growth_intel import (
    PHASE6_SOURCE,
    ContentPerfRollup,
    cluster_segments_rules,
    detect_leaks,
    estimate_ltv_rules,
    geo_language_expansion_rules,
    paid_amplification_candidates,
    plan_cross_platform_derivatives,
    trust_score_for_account,
)
from packages.scoring.winner import ContentPerformance

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _uuid_or_none(s: str | None) -> uuid.UUID | None:
    if not s:
        return None
    try:
        return uuid.UUID(str(s))
    except ValueError:
        return None


async def _content_performance_rollups(db: AsyncSession, brand_id: uuid.UUID) -> list[ContentPerfRollup]:
    items = (await db.execute(select(ContentItem).where(ContentItem.brand_id == brand_id).limit(200))).scalars().all()
    out: list[ContentPerfRollup] = []
    for item in items:
        row = (
            await db.execute(
                select(
                    func.coalesce(func.sum(PerformanceMetric.impressions), 0),
                    func.coalesce(func.sum(PerformanceMetric.clicks), 0),
                    func.coalesce(func.sum(PerformanceMetric.views), 0),
                    func.coalesce(func.sum(PerformanceMetric.revenue), 0.0),
                    func.coalesce(func.avg(PerformanceMetric.ctr), 0.0),
                    func.coalesce(func.avg(PerformanceMetric.engagement_rate), 0.0),
                    func.coalesce(func.avg(PerformanceMetric.avg_watch_pct), 0.0),
                ).where(PerformanceMetric.content_item_id == item.id)
            )
        ).one()
        imps, clicks, views, rev, avg_ctr, avg_er, avg_watch = (
            int(row[0]),
            int(row[1]),
            int(row[2]),
            float(row[3]),
            float(row[4]),
            float(row[5]),
            float(row[6]),
        )
        conv = (
            await db.execute(
                select(func.count())
                .select_from(AttributionEvent)
                .where(AttributionEvent.content_item_id == item.id, AttributionEvent.event_type != "click")
            )
        ).scalar() or 0
        cvr = (conv / clicks) if clicks > 0 else 0.0
        ctr = (clicks / imps) if imps > 0 else round(avg_ctr, 4)
        rpm = (rev / imps * 1000) if imps > 0 else 0.0
        profit = rev - float(item.total_cost or 0)
        out.append(
            ContentPerfRollup(
                content_id=str(item.id),
                title=item.title,
                brand_id=str(brand_id),
                creator_account_id=str(item.creator_account_id) if item.creator_account_id else None,
                platform=(item.platform or "unknown").lower(),
                offer_id=str(item.offer_id) if item.offer_id else None,
                impressions=imps,
                clicks=clicks,
                views=views,
                revenue=rev,
                profit=profit,
                cost=float(item.total_cost or 0),
                ctr=ctr,
                rpm=rpm,
                engagement_rate=avg_er,
                avg_watch_pct=avg_watch,
                conversions=int(conv),
                conversion_rate=cvr,
            )
        )
    return out


async def _account_perf_map(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, dict]:
    accounts = (await db.execute(select(CreatorAccount).where(CreatorAccount.brand_id == brand_id))).scalars().all()
    m: dict[str, dict] = {}
    for acct in accounts:
        row = (
            await db.execute(
                select(
                    func.coalesce(func.sum(PerformanceMetric.impressions), 0),
                    func.coalesce(func.sum(PerformanceMetric.revenue), 0.0),
                ).where(PerformanceMetric.creator_account_id == acct.id)
            )
        ).one()
        m[str(acct.id)] = {
            "impressions": int(row[0]),
            "revenue": float(acct.total_revenue or row[1] or 0),
            "profit": float(acct.total_profit or 0),
        }
    return m


def _accounts_as_dicts(accounts: list) -> list[dict]:
    return [
        {
            "id": str(a.id),
            "platform": a.platform.value if hasattr(a.platform, "value") else str(a.platform),
            "geography": a.geography,
            "language": a.language,
            "niche_focus": a.niche_focus,
            "follower_count": a.follower_count,
            "is_active": a.is_active,
            "account_health": a.account_health.value if hasattr(a.account_health, "value") else str(a.account_health),
            "posting_capacity_per_day": a.posting_capacity_per_day,
            "originality_drift_score": float(a.originality_drift_score or 0),
            "fatigue_score": float(a.fatigue_score or 0),
            "follower_growth_rate": float(a.follower_growth_rate or 0),
        }
        for a in accounts
    ]


# ---------------------------------------------------------------------------
# Serializers (single source of truth for dict shapes)
# ---------------------------------------------------------------------------


def _serialize_leak(r: RevenueLeakReport) -> dict:
    return {
        "id": str(r.id),
        "leak_type": r.leak_type,
        "affected_entity_type": r.affected_entity_type,
        "affected_entity_id": str(r.affected_entity_id) if r.affected_entity_id else None,
        "estimated_leaked_revenue": r.estimated_leaked_revenue,
        "estimated_recoverable": r.estimated_recoverable,
        "root_cause": r.root_cause,
        "recommended_fix": r.recommended_fix,
        "severity": r.severity,
        "details": r.details,
    }


def _serialize_geo(g: GeoLanguageExpansionRecommendation) -> dict:
    return {
        "id": str(g.id),
        "target_geography": g.target_geography,
        "target_language": g.target_language,
        "target_platform": g.target_platform,
        "estimated_audience_size": g.estimated_audience_size,
        "estimated_revenue_potential": g.estimated_revenue_potential,
        "entry_cost_estimate": g.entry_cost_estimate,
        "rationale": g.rationale,
        "confidence": g.confidence.value if hasattr(g.confidence, "value") else str(g.confidence),
    }


def _serialize_paid_job(j: PaidAmplificationJob) -> dict:
    return {
        "id": str(j.id),
        "content_item_id": str(j.content_item_id),
        "platform": j.platform,
        "budget": j.budget,
        "spent": j.spent,
        "status": j.status.value if hasattr(j.status, "value") else str(j.status),
        "roi": j.roi,
        "explanation": j.explanation,
        "is_candidate": j.is_candidate,
    }


def _serialize_trust(t: TrustSignalReport) -> dict:
    return {
        "id": str(t.id),
        "creator_account_id": str(t.creator_account_id) if t.creator_account_id else None,
        "trust_score": t.trust_score,
        "components": t.components,
        "recommendations": t.recommendations or [],
        "evidence": t.evidence or {},
        "confidence_label": t.confidence_label,
    }


# ---------------------------------------------------------------------------
# WRITE PATH — recompute (called by POST endpoint only)
# ---------------------------------------------------------------------------


async def recompute_growth_intel(
    db: AsyncSession,
    brand_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Recompute and persist all Phase 6 artifacts for a brand. Idempotent: cleans
    prior Phase 6-owned rows before inserting fresh ones."""
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    accounts = list(
        (await db.execute(select(CreatorAccount).where(CreatorAccount.brand_id == brand_id))).scalars().all()
    )
    acc_dicts = _accounts_as_dicts(accounts)
    perf_by_ac = await _account_perf_map(db, brand_id)
    rollups = await _content_performance_rollups(db, brand_id)
    offers = list(
        (await db.execute(select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True)))).scalars().all()
    )
    offer_by_id = {
        str(o.id): {
            "id": str(o.id),
            "epc": o.epc,
            "conversion_rate": o.conversion_rate,
            "payout_amount": o.payout_amount,
            "average_order_value": o.average_order_value,
            "recurring_commission": o.recurring_commission,
            "priority": o.priority,
        }
        for o in offers
    }
    follower_growth_by_ac = {str(a.id): float(a.follower_growth_rate or 0) for a in accounts}

    funnel = await asvc.get_funnel_data(db, brand_id)
    f_imps = int(funnel.get("impressions") or 0)
    f_clicks = int(funnel.get("total_clicks") or 0)
    f_conv = sum(
        (funnel.get("funnel_stages") or {}).get(et, {}).get("count", 0)
        for et in ("purchase", "lead", "opt_in", "affiliate_conversion")
    )

    # —— Clean prior Phase 6 rows ——
    await db.execute(
        text("DELETE FROM audience_segments WHERE brand_id = :bid AND (segment_criteria->>'phase6_auto') = 'true'"),
        {"bid": str(brand_id)},
    )
    await db.execute(
        text("DELETE FROM ltv_models WHERE brand_id = :bid AND (parameters->>'phase6_auto') = 'true'"),
        {"bid": str(brand_id)},
    )
    await db.execute(
        delete(RevenueLeakReport).where(
            RevenueLeakReport.brand_id == brand_id,
            RevenueLeakReport.details.contains({PHASE6_SOURCE: True}),
        )
    )
    await db.execute(
        delete(GeoLanguageExpansionRecommendation).where(
            GeoLanguageExpansionRecommendation.brand_id == brand_id,
            GeoLanguageExpansionRecommendation.rationale.like("[phase6 auto]%"),
        )
    )
    await db.execute(delete(TrustSignalReport).where(TrustSignalReport.brand_id == brand_id))
    await db.execute(
        delete(PaidAmplificationJob).where(
            PaidAmplificationJob.brand_id == brand_id,
            PaidAmplificationJob.is_candidate.is_(True),
        )
    )
    await db.execute(
        delete(ExpansionDecision).where(
            ExpansionDecision.brand_id == brand_id,
            ExpansionDecision.expansion_type == "cross_platform_and_geo",
        )
    )

    # —— Segments ——
    seg_payloads = cluster_segments_rules(acc_dicts, perf_by_ac)
    for sp in seg_payloads:
        db.add(
            AudienceSegment(
                brand_id=brand_id,
                name=sp["name"][:255],
                description=sp.get("description"),
                segment_criteria=sp["segment_criteria"],
                estimated_size=int(sp["estimated_size"]),
                revenue_contribution=float(sp["revenue_contribution"]),
                conversion_rate=float(sp["conversion_rate"]),
                avg_ltv=float(sp.get("avg_ltv") or 0),
                platforms=sp.get("platforms") or [],
                is_active=True,
            )
        )

    # —— LTV (per active offer × distinct platform) ——
    plats = list(
        {(a.platform.value if hasattr(a.platform, "value") else str(a.platform)).lower() for a in accounts}
    ) or ["youtube"]
    ref = accounts[0] if accounts else None
    geo_d = (ref.geography or "US") if ref else "US"
    lang_d = (ref.language or "en") if ref else "en"
    seg_n = ((ref.niche_focus or "core")[:80]) if ref else "core"
    ltv_count = 0
    for o in offers:
        offer_d = offer_by_id[str(o.id)]
        for plat in plats:
            row = estimate_ltv_rules(
                offer_d, plat, geo_d, lang_d, seg_n, seg_n, "organic", float(o.conversion_rate or 0.02)
            )
            db.add(
                LtvModel(
                    brand_id=brand_id,
                    segment_name=row["segment_name"][:255],
                    model_type=row["model_type"],
                    parameters=row["parameters"],
                    estimated_ltv_30d=row["estimated_ltv_30d"],
                    estimated_ltv_90d=row["estimated_ltv_90d"],
                    estimated_ltv_365d=row["estimated_ltv_365d"],
                    confidence=float(row["confidence"]),
                    sample_size=int(row["sample_size"]),
                    last_trained_at=datetime.now(timezone.utc).date().isoformat(),
                    is_active=True,
                )
            )
            ltv_count += 1

    # —— Leaks ——
    leaks = detect_leaks(rollups, f_imps, f_clicks, f_conv, offer_by_id, follower_growth_by_ac)
    for lk in leaks:
        db.add(
            RevenueLeakReport(
                brand_id=brand_id,
                leak_type=lk["leak_type"],
                affected_entity_type=lk["entity_type"],
                affected_entity_id=_uuid_or_none(str(lk.get("entity_id")) if lk.get("entity_id") else None),
                estimated_leaked_revenue=float(lk["estimated_leaked_revenue"]),
                estimated_recoverable=float(lk["estimated_recoverable"]),
                root_cause=lk.get("root_cause"),
                recommended_fix=lk.get("recommended_fix"),
                severity=lk.get("severity", "medium"),
                details=lk.get("details") or {},
                is_resolved=False,
            )
        )

    # —— Geo / language ——
    geo_rows = geo_language_expansion_rules(acc_dicts, brand.niche)
    for gr in geo_rows:
        db.add(
            GeoLanguageExpansionRecommendation(
                brand_id=brand_id,
                target_geography=gr["target_geography"],
                target_language=gr["target_language"],
                target_platform=gr.get("target_platform"),
                estimated_audience_size=int(gr["estimated_audience_size"]),
                estimated_revenue_potential=float(gr["estimated_revenue_potential"]),
                competition_level=gr.get("competition_level"),
                entry_cost_estimate=float(gr["entry_cost_estimate"]),
                confidence=ConfidenceLevel.MEDIUM,
                rationale="[phase6 auto] " + gr["rationale"],
                is_actioned=False,
            )
        )

    # —— Cross-platform derivatives + expansion decision ——
    cp_items = [
        ContentPerformance(
            content_id=r.content_id,
            title=r.title,
            impressions=r.impressions,
            revenue=r.revenue,
            profit=r.profit,
            rpm=r.rpm,
            ctr=r.ctr,
            engagement_rate=r.engagement_rate,
            conversion_rate=r.conversion_rate,
            platform=r.platform,
            account_id=r.creator_account_id or "",
        )
        for r in rollups
    ]
    plats_l = {(a.platform.value if hasattr(a.platform, "value") else str(a.platform)).lower() for a in accounts}
    cross_plans = plan_cross_platform_derivatives(cp_items, plats_l)

    # Revenue bottleneck classifier (same engine as analytics / scale) informs expansion framing.
    bottleneck_rows = await asvc.classify_bottlenecks(db, brand_id)
    sev_rank = {"critical": 3, "warning": 2, "info": 1, "ok": 0}
    worst_bn = None
    if bottleneck_rows:
        worst_bn = max(bottleneck_rows, key=lambda b: sev_rank.get(str(b.get("severity") or "ok"), 0))
    bn_tail = ""
    if worst_bn:
        bn_tail = (
            f" Dominant bottleneck signal: {worst_bn.get('primary_bottleneck')} "
            f"({worst_bn.get('severity')}) on {worst_bn.get('platform')} @{worst_bn.get('username')}."
        )

    db.add(
        ExpansionDecision(
            brand_id=brand_id,
            decision_type=DecisionType.EXPANSION,
            decision_mode=DecisionMode.GUARDED_AUTO,
            actor_type=ActorType.HUMAN if user_id else ActorType.SYSTEM,
            actor_id=user_id,
            expansion_type="cross_platform_and_geo",
            input_snapshot={
                "cross_platform_plans": cross_plans[:30],
                "geo_rows": geo_rows,
                "revenue_bottlenecks_by_account": bottleneck_rows[:50],
            },
            formulas_used={
                "engines": [
                    "growth_intel.plan_cross_platform_derivatives",
                    "geo_language_expansion_rules",
                    "analytics_service.classify_bottlenecks",
                    "packages.scoring.bottleneck.classify_bottleneck",
                ],
            },
            score_components={
                "worst_bottleneck": {
                    "account_id": worst_bn.get("account_id") if worst_bn else None,
                    "primary_bottleneck": worst_bn.get("primary_bottleneck") if worst_bn else None,
                    "severity": worst_bn.get("severity") if worst_bn else None,
                },
            },
            composite_score=min(100.0, float(len(cross_plans)) * 5.0),
            confidence=ConfidenceLevel.MEDIUM,
            recommended_action=RecommendedAction.EXPERIMENT,
            explanation=(
                f"Phase 6 expansion snapshot: {len(geo_rows)} geo/lang rows, {len(cross_plans)} derivative links."
                f"{bn_tail}"
            ),
            estimated_revenue=sum(float(g["estimated_revenue_potential"]) for g in geo_rows),
            estimated_cost=sum(float(g["entry_cost_estimate"]) for g in geo_rows),
        )
    )

    # —— Paid amplification (winners only) ——
    existing_paid: set[str] = set()
    for row in (
        await db.execute(select(PaidAmplificationJob.content_item_id).where(PaidAmplificationJob.brand_id == brand_id))
    ).all():
        existing_paid.add(str(row[0]))
    candidates = paid_amplification_candidates(cp_items, existing_paid)
    for c in candidates:
        cid = uuid.UUID(c["content_item_id"])
        acct_id = None
        for r in rollups:
            if r.content_id == c["content_item_id"]:
                acct_id = _uuid_or_none(r.creator_account_id)
                break
        db.add(
            PaidAmplificationJob(
                brand_id=brand_id,
                content_item_id=cid,
                creator_account_id=acct_id,
                platform=c.get("platform", "youtube"),
                budget=float(c["suggested_budget"]),
                target_audience_config={"phase6_candidate": True, "win_score": c.get("win_score")},
                status=JobStatus.PENDING,
                explanation=c.get("explanation"),
                is_candidate=True,
            )
        )

    # —— Trust ——
    eng_by_ac: dict[str, dict] = {}
    for r in rollups:
        aid = r.creator_account_id or ""
        if aid not in eng_by_ac:
            eng_by_ac[aid] = {"engagement_rate": 0.0, "n": 0}
        eng_by_ac[aid]["engagement_rate"] += r.engagement_rate
        eng_by_ac[aid]["n"] += 1
    for v in eng_by_ac.values():
        if v["n"]:
            v["engagement_rate"] /= v["n"]
    for a in accounts:
        tr = trust_score_for_account(
            _accounts_as_dicts([a])[0],
            eng_by_ac.get(str(a.id), {"engagement_rate": 0.0}),
        )
        conf = "high" if tr["trust_score"] >= 72 else ("medium" if tr["trust_score"] >= 48 else "low")
        db.add(
            TrustSignalReport(
                brand_id=brand_id,
                creator_account_id=a.id,
                trust_score=tr["trust_score"],
                components=tr["components"],
                recommendations=tr["recommendations"],
                evidence=tr["evidence"],
                confidence_label=conf,
            )
        )

    # —— Portfolio expansion inputs ——
    port = (
        (
            await db.execute(
                select(AccountPortfolio)
                .where(AccountPortfolio.brand_id == brand_id, AccountPortfolio.is_active.is_(True))
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    if port:
        cfg = dict(port.allocation_config or {})
        cfg["phase6_expansion_inputs"] = {
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "cross_platform_derivatives": cross_plans[:20],
            "geo_language_targets": [{"geo": g["target_geography"], "lang": g["target_language"]} for g in geo_rows],
            "leak_count": len(leaks),
        }
        port.allocation_config = cfg

    await db.flush()
    return {
        "segments": len(seg_payloads),
        "ltv_rows": ltv_count,
        "leaks": len(leaks),
        "geo_expansion": len(geo_rows),
        "paid_candidates": len(candidates),
        "trust_reports": len(accounts),
        "cross_platform_plans": len(cross_plans),
    }


# ---------------------------------------------------------------------------
# READ PATH — all functions below are side-effect free
# ---------------------------------------------------------------------------


async def get_audience_segments(db: AsyncSession, brand_id: uuid.UUID) -> list[AudienceSegment]:
    q = await db.execute(
        select(AudienceSegment).where(AudienceSegment.brand_id == brand_id, AudienceSegment.is_active.is_(True))
    )
    return list(q.scalars().all())


async def get_ltv_models(db: AsyncSession, brand_id: uuid.UUID) -> list[LtvModel]:
    q = await db.execute(select(LtvModel).where(LtvModel.brand_id == brand_id, LtvModel.is_active.is_(True)).limit(200))
    return list(q.scalars().all())


async def get_leak_reports_dashboard(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    funnel = await asvc.get_funnel_data(db, brand_id)
    rows = (
        (
            await db.execute(
                select(RevenueLeakReport)
                .where(RevenueLeakReport.brand_id == brand_id, RevenueLeakReport.is_resolved.is_(False))
                .order_by(RevenueLeakReport.estimated_leaked_revenue.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    leak_list = [_serialize_leak(r) for r in rows]
    return {
        "brand_id": str(brand_id),
        "funnel": funnel,
        "leaks": leak_list,
        "summary": {
            "open_leaks": len(leak_list),
            "total_leaked_est": round(sum(l["estimated_leaked_revenue"] for l in leak_list), 2),
        },
    }


async def get_expansion_bundle(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    geo = (
        (
            await db.execute(
                select(GeoLanguageExpansionRecommendation)
                .where(GeoLanguageExpansionRecommendation.brand_id == brand_id)
                .order_by(GeoLanguageExpansionRecommendation.estimated_revenue_potential.desc())
            )
        )
        .scalars()
        .all()
    )
    ex_dec = (
        (
            await db.execute(
                select(ExpansionDecision)
                .where(ExpansionDecision.brand_id == brand_id)
                .order_by(ExpansionDecision.decided_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    cross = (ex_dec.input_snapshot or {}).get("cross_platform_plans", []) if ex_dec else []
    return {
        "geo_language_recommendations": [_serialize_geo(g) for g in geo],
        "cross_platform_flow_plans": cross,
        "latest_expansion_decision_id": str(ex_dec.id) if ex_dec else None,
    }


async def get_paid_amplification_bundle(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    jobs = (
        (
            await db.execute(
                select(PaidAmplificationJob)
                .where(PaidAmplificationJob.brand_id == brand_id)
                .order_by(PaidAmplificationJob.created_at.desc())
                .limit(80)
            )
        )
        .scalars()
        .all()
    )
    return {
        "jobs": [_serialize_paid_job(j) for j in jobs],
        "note": "Candidates are system-generated for winner-gated content only (is_candidate=true).",
    }


async def get_trust_signals_bundle(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    rows = (
        (
            await db.execute(
                select(TrustSignalReport)
                .where(TrustSignalReport.brand_id == brand_id)
                .order_by(TrustSignalReport.trust_score.desc())
            )
        )
        .scalars()
        .all()
    )
    return {"reports": [_serialize_trust(t) for t in rows]}


async def get_growth_intel_dashboard(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    """Bundled read of all Phase 6 slices. Side-effect free."""
    segs = await get_audience_segments(db, brand_id)
    ltv = await get_ltv_models(db, brand_id)
    leaks = await get_leak_reports_dashboard(db, brand_id)
    expansion = await get_expansion_bundle(db, brand_id)
    paid = await get_paid_amplification_bundle(db, brand_id)
    trust = await get_trust_signals_bundle(db, brand_id)
    return {
        "brand_id": str(brand_id),
        "audience_segments": segs,
        "ltv_models": ltv,
        "leaks": leaks,
        "expansion": expansion,
        "paid_amplification": paid,
        "trust_signals": trust,
    }
