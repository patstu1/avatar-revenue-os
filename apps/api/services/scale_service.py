"""Phase 5: scale recommendations, portfolio allocations, command center."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services import analytics_service as asvc
from packages.db.enums import (
    ActorType,
    ConfidenceLevel,
    DecisionMode,
    DecisionType,
    HealthStatus,
    RecommendedAction,
)
from packages.db.models.accounts import AccountPortfolio, CreatorAccount
from packages.db.models.core import Brand
from packages.db.models.decisions import AllocationDecision, ScaleDecision
from packages.db.models.offers import Offer
from packages.db.models.portfolio import PortfolioAllocation, ScaleRecommendation
from packages.db.models.publishing import PerformanceMetric
from packages.scoring.scale import (
    EXPANSION_BEATS_EXISTING_RATIO,
    NEW_ACCOUNT_OVERHEAD_USD,
    RK_REDUCE_WEAK,
    VOLUME_LIFT_FACTOR,
    AccountScaleSnapshot,
    compute_offer_performance_score,
    run_scale_engine,
)


def _action_from_coarse(coarse: str) -> RecommendedAction:
    m = {
        "scale": RecommendedAction.SCALE,
        "maintain": RecommendedAction.MAINTAIN,
        "reduce": RecommendedAction.REDUCE,
        "suppress": RecommendedAction.SUPPRESS,
        "monitor": RecommendedAction.MONITOR,
        "experiment": RecommendedAction.EXPERIMENT,
    }
    return m.get((coarse or "monitor").lower(), RecommendedAction.MONITOR)


def _confidence_from_engine(exp_conf: float, readiness: float) -> ConfidenceLevel:
    s = (exp_conf * 0.5 + (readiness / 100) * 0.5)
    if s >= 0.72:
        return ConfidenceLevel.HIGH
    if s >= 0.45:
        return ConfidenceLevel.MEDIUM
    if s >= 0.25:
        return ConfidenceLevel.LOW
    return ConfidenceLevel.INSUFFICIENT


async def sync_account_metrics_from_performance(db: AsyncSession, brand_id: uuid.UUID) -> int:
    """Roll PerformanceMetric into CreatorAccount scale fields (best-effort)."""
    accounts = (
        (await db.execute(select(CreatorAccount).where(CreatorAccount.brand_id == brand_id))).scalars().all()
    )
    updated = 0
    for acct in accounts:
        row = (
            await db.execute(
                select(
                    func.coalesce(func.sum(PerformanceMetric.impressions), 0),
                    func.coalesce(func.sum(PerformanceMetric.clicks), 0),
                    func.coalesce(func.sum(PerformanceMetric.revenue), 0.0),
                    func.coalesce(func.sum(PerformanceMetric.followers_gained), 0),
                    func.coalesce(func.avg(PerformanceMetric.ctr), 0.0),
                ).where(PerformanceMetric.creator_account_id == acct.id)
            )
        ).one()
        imps, clicks, rev, f_gain, avg_ctr = int(row[0]), int(row[1]), float(row[2]), int(row[3]), float(row[4])
        if imps > 0:
            acct.ctr = round(clicks / imps, 4) if clicks else acct.ctr
            acct.revenue_per_mille = round((rev / imps) * 1000, 2)
        elif avg_ctr > 0:
            acct.ctr = round(avg_ctr, 4)
        if imps > 500 and acct.follower_count > 0:
            acct.follower_growth_rate = round(min(0.2, f_gain / max(1, acct.follower_count)), 4)

        meta = dict(acct.cannibalization_risk or {})
        meta["last_impressions_rollup"] = imps
        acct.cannibalization_risk = meta
        updated += 1
    await db.flush()
    return updated


async def _build_snapshots(db: AsyncSession, brand_id: uuid.UUID) -> tuple[list[AccountScaleSnapshot], int, dict]:
    accounts = (
        (
            await db.execute(
                select(CreatorAccount).where(
                    CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    offers_rows = (
        (await db.execute(select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True)))).scalars().all()
    )
    offers = [{"epc": o.epc, "conversion_rate": o.conversion_rate, "priority": o.priority} for o in offers_rows]

    total_impressions = (
        await db.execute(
            select(func.coalesce(func.sum(PerformanceMetric.impressions), 0)).where(
                PerformanceMetric.brand_id == brand_id
            )
        )
    ).scalar() or 0

    imp_q = await db.execute(
        select(PerformanceMetric.creator_account_id, func.coalesce(func.sum(PerformanceMetric.impressions), 0))
        .where(PerformanceMetric.brand_id == brand_id)
        .group_by(PerformanceMetric.creator_account_id)
    )
    imp_map = {str(row[0]): int(row[1]) for row in imp_q.all()}

    offer_pf = compute_offer_performance_score(offers)
    snapshots: list[AccountScaleSnapshot] = []
    for acct in accounts:
        imps_ac = imp_map.get(str(acct.id), int((acct.cannibalization_risk or {}).get("last_impressions_rollup") or 0))
        snapshots.append(
            AccountScaleSnapshot(
                account_id=str(acct.id),
                platform=acct.platform.value if hasattr(acct.platform, "value") else str(acct.platform),
                username=acct.platform_username,
                niche_focus=acct.niche_focus,
                sub_niche_focus=acct.sub_niche_focus,
                revenue=float(acct.total_revenue or 0),
                profit=float(acct.total_profit or 0),
                profit_per_post=float(acct.profit_per_post or 0),
                revenue_per_mille=float(acct.revenue_per_mille or 0),
                ctr=float(acct.ctr or 0),
                conversion_rate=float(acct.conversion_rate or 0),
                follower_growth_rate=float(acct.follower_growth_rate or 0),
                fatigue_score=float(acct.fatigue_score or 0),
                saturation_score=float(acct.saturation_score or 0),
                originality_drift_score=float(acct.originality_drift_score or 0),
                diminishing_returns_score=float(acct.diminishing_returns_score or 0),
                posting_capacity_per_day=int(acct.posting_capacity_per_day or 1),
                account_health=acct.account_health.value if hasattr(acct.account_health, "value") else str(acct.account_health),
                offer_performance_score=offer_pf,
                scale_role=acct.scale_role,
                impressions_rollup=imps_ac,
            )
        )
    return snapshots, int(total_impressions), {"offers": offers, "offer_performance_score": offer_pf}


async def _funnel_weak(db: AsyncSession, brand_id: uuid.UUID) -> bool:
    funnel = await asvc.get_funnel_data(db, brand_id)
    imps = funnel.get("impressions") or 0
    clicks = funnel.get("total_clicks") or 0
    stages = funnel.get("funnel_stages") or {}
    purchases = (stages.get("purchase") or {}).get("count") or 0
    if imps > 2000 and clicks > 0:
        ctr = clicks / imps
        if ctr < 0.008:
            return True
    if clicks > 50 and purchases == 0:
        return True
    return False


def _weak_offer_diversity(offers: list[dict]) -> bool:
    if len(offers) < 2:
        return True
    strong = sum(1 for o in offers if float(o.get("epc") or 0) >= 1.0 and float(o.get("conversion_rate") or 0) >= 0.02)
    return strong < 1


async def recompute_scale_recommendations(
    db: AsyncSession,
    brand_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    sync_metrics: bool = True,
) -> list[ScaleRecommendation]:
    if sync_metrics:
        await sync_account_metrics_from_performance(db, brand_id)
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("brand not found")

    snaps, total_impressions, ctx = await _build_snapshots(db, brand_id)
    funnel_w = await _funnel_weak(db, brand_id)
    weak_offers = _weak_offer_diversity(ctx["offers"])

    engine = run_scale_engine(
        snaps,
        ctx["offers"],
        total_impressions,
        brand.niche,
        funnel_w,
        weak_offers,
    )

    await db.execute(delete(ScaleRecommendation).where(ScaleRecommendation.brand_id == brand_id))
    await db.flush()

    conf = _confidence_from_engine(engine.expansion_confidence, engine.scale_readiness_score)
    primary_coarse = _action_from_coarse(engine.coarse_action)

    flagship_id = None
    for s in snaps:
        if (s.scale_role or "").lower() == "flagship":
            flagship_id = uuid.UUID(s.account_id)
            break

    primary = ScaleRecommendation(
        brand_id=brand_id,
        creator_account_id=flagship_id,
        recommended_action=primary_coarse,
        recommendation_key=engine.recommendation_key,
        incremental_profit_new_account=engine.incremental_profit_new_account,
        incremental_profit_existing_push=engine.incremental_profit_more_volume,
        comparison_ratio=engine.score_components.get("comparison_ratio", 0.0),
        scale_readiness_score=engine.scale_readiness_score,
        cannibalization_risk_score=engine.cannibalization_risk,
        audience_segment_separation=engine.audience_segment_separation,
        expansion_confidence=engine.expansion_confidence,
        recommended_account_count=engine.recommended_account_count,
        weekly_action_plan={"days": engine.weekly_action_plan},
        best_next_account=engine.best_next_account,
        score_components=engine.score_components,
        penalties=engine.penalties,
        confidence=conf,
        explanation=engine.explanation,
    )
    db.add(primary)

    if RK_REDUCE_WEAK in engine.secondary_keys:
        weak_snaps = [s for s in snaps if s.profit_per_post < 2 and s.impressions_rollup > 300][:3]
        for ws in weak_snaps:
            db.add(
                ScaleRecommendation(
                    brand_id=brand_id,
                    creator_account_id=uuid.UUID(ws.account_id),
                    recommended_action=RecommendedAction.REDUCE,
                    recommendation_key=RK_REDUCE_WEAK,
                    incremental_profit_new_account=0.0,
                    incremental_profit_existing_push=0.0,
                    comparison_ratio=0.0,
                    scale_readiness_score=engine.scale_readiness_score,
                    cannibalization_risk_score=engine.cannibalization_risk,
                    audience_segment_separation=engine.audience_segment_separation,
                    expansion_confidence=engine.expansion_confidence,
                    recommended_account_count=engine.recommended_account_count,
                    weekly_action_plan={},
                    best_next_account={},
                    score_components={"secondary": True},
                    penalties={},
                    confidence=ConfidenceLevel.MEDIUM,
                    explanation="Weak profit_per_post relative to impressions on this account.",
                )
            )

    decision = ScaleDecision(
        brand_id=brand_id,
        decision_type=DecisionType.SCALE,
        decision_mode=DecisionMode.GUARDED_AUTO,
        actor_type=ActorType.HUMAN if user_id else ActorType.SYSTEM,
        actor_id=user_id,
        creator_account_id=flagship_id,
        incremental_profit_new=engine.incremental_profit_new_account,
        incremental_profit_existing=engine.incremental_profit_more_volume,
        comparison_ratio=engine.score_components.get("comparison_ratio", 0.0),
        input_snapshot={"recommendation_key": engine.recommendation_key, "account_count": len(snaps)},
        formulas_used={"engine": "packages.scoring.scale.run_scale_engine"},
        score_components=engine.score_components,
        penalties=engine.penalties,
        composite_score=engine.scale_readiness_score,
        confidence=conf,
        recommended_action=primary_coarse,
        explanation=engine.explanation,
    )
    db.add(decision)

    await persist_account_scale_roles(db, brand_id, snaps)
    await db.flush()
    return await get_scale_recommendations(db, brand_id)


async def persist_account_scale_roles(db: AsyncSession, brand_id: uuid.UUID, snaps: list[AccountScaleSnapshot]) -> None:
    for s in snaps:
        if not s.scale_role:
            continue
        acct = (
            await db.execute(select(CreatorAccount).where(CreatorAccount.id == uuid.UUID(s.account_id)))
        ).scalar_one_or_none()
        if acct and acct.brand_id == brand_id:
            acct.scale_role = s.scale_role
    await db.flush()


async def recompute_portfolio_allocations(db: AsyncSession, brand_id: uuid.UUID) -> tuple[list[PortfolioAllocation], uuid.UUID]:
    portfolio = (
        await db.execute(
            select(AccountPortfolio).where(AccountPortfolio.brand_id == brand_id, AccountPortfolio.is_active.is_(True)).limit(1)
        )
    ).scalar_one_or_none()
    if not portfolio:
        portfolio = AccountPortfolio(
            brand_id=brand_id,
            name="Default portfolio",
            description="Auto-created for allocation recompute",
            strategy="profit_weighted",
            total_accounts=0,
            is_active=True,
        )
        db.add(portfolio)
        await db.flush()

    accounts = (
        (await db.execute(select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))))
        .scalars()
        .all()
    )
    portfolio.total_accounts = len(accounts)
    portfolio.total_revenue = sum(float(a.total_revenue or 0) for a in accounts)
    portfolio.total_profit = sum(float(a.total_profit or 0) for a in accounts)

    weights: list[float] = []
    for a in accounts:
        h = 1.0 if a.account_health == HealthStatus.HEALTHY else 0.55
        w = max(0.05, float(a.total_profit or 0) + 1.0) * (1.0 - min(1.0, float(a.diminishing_returns_score or 0))) * h
        weights.append(w)
    s_weights = sum(weights) or 1.0

    await db.execute(delete(PortfolioAllocation).where(PortfolioAllocation.portfolio_id == portfolio.id))
    await db.flush()

    allocations: list[PortfolioAllocation] = []
    for a, w in zip(accounts, weights):
        pct = round(100.0 * w / s_weights, 2)
        cap = max(1, int(round(a.posting_capacity_per_day * (pct / 100.0) * 5)))
        row = PortfolioAllocation(
            portfolio_id=portfolio.id,
            creator_account_id=a.id,
            brand_id=brand_id,
            allocation_pct=pct,
            budget_allocated=0.0,
            posting_capacity_allocated=cap,
            expected_roi=round(float(a.profit_per_post or 0) * 0.1, 2),
            actual_roi=round(float(a.total_profit or 0) / max(1.0, float(a.total_revenue or 1)), 2),
            rationale=f"Profit × (1 − diminishing returns) × health — scaled to {pct}%",
            confidence=ConfidenceLevel.MEDIUM,
            is_active=True,
        )
        db.add(row)
        allocations.append(row)

    alloc_snap = {"items": [{"account_id": str(row.creator_account_id), "pct": row.allocation_pct} for row in allocations]}
    db.add(
        AllocationDecision(
            brand_id=brand_id,
            decision_type=DecisionType.ALLOCATION,
            decision_mode=DecisionMode.GUARDED_AUTO,
            actor_type=ActorType.SYSTEM,
            portfolio_id=portfolio.id,
            allocation_snapshot=alloc_snap,
            rebalance_actions=[{"portfolio_id": str(portfolio.id), "rows": len(allocations)}],
            composite_score=min(100.0, portfolio.total_profit / max(1, len(accounts))),
            confidence=ConfidenceLevel.MEDIUM,
            recommended_action=RecommendedAction.MAINTAIN,
            explanation="Posting capacity and notional budget weights aligned to profit and diminishing returns.",
        )
    )

    await db.flush()
    for row in allocations:
        await db.refresh(row)
    return allocations, portfolio.id


async def get_scale_recommendations(db: AsyncSession, brand_id: uuid.UUID) -> list[ScaleRecommendation]:
    """Primary portfolio recommendations first; per-account reduce/weak rows after."""
    priority = case(
        (ScaleRecommendation.recommendation_key == RK_REDUCE_WEAK, 1),
        else_=0,
    )
    return list(
        (
            await db.execute(
                select(ScaleRecommendation)
                .where(ScaleRecommendation.brand_id == brand_id)
                .order_by(priority.asc(), ScaleRecommendation.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def get_portfolio_allocations(db: AsyncSession, brand_id: uuid.UUID) -> list[PortfolioAllocation]:
    q = await db.execute(
        select(PortfolioAllocation)
        .where(PortfolioAllocation.brand_id == brand_id, PortfolioAllocation.is_active.is_(True))
        .order_by(PortfolioAllocation.allocation_pct.desc())
    )
    return list(q.scalars().all())


async def build_scale_command_center(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("brand not found")

    snaps, total_impressions, _ = await _build_snapshots(db, brand_id)
    recs = await get_scale_recommendations(db, brand_id)
    allocations = await get_portfolio_allocations(db, brand_id)
    leaks = await asvc.preview_revenue_leaks(db, brand_id)
    blockers = await asvc.classify_bottlenecks(db, brand_id)
    offers_dict = await _load_offers_dict(db, brand_id)
    offer_avg = _ctx_offer_avg(offers_dict)
    funnel_weak_flag = await _funnel_weak(db, brand_id)

    accounts_payload = []
    for acct in (
        (
            await db.execute(
                select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    ):
        accounts_payload.append(
            {
                "id": str(acct.id),
                "username": acct.platform_username,
                "platform": acct.platform.value if hasattr(acct.platform, "value") else str(acct.platform),
                "niche_focus": acct.niche_focus,
                "sub_niche_focus": acct.sub_niche_focus,
                "scale_role": acct.scale_role,
                "revenue": float(acct.total_revenue or 0),
                "profit": float(acct.total_profit or 0),
                "profit_per_post": float(acct.profit_per_post or 0),
                "revenue_per_mille": float(acct.revenue_per_mille or 0),
                "ctr": float(acct.ctr or 0),
                "conversion_rate": float(acct.conversion_rate or 0),
                "follower_growth_rate": float(acct.follower_growth_rate or 0),
                "content_fatigue": float(acct.fatigue_score or 0),
                "niche_saturation": float(acct.saturation_score or 0),
                "account_health": acct.account_health.value if hasattr(acct.account_health, "value") else str(acct.account_health),
                "originality_drift": float(acct.originality_drift_score or 0),
                "posting_capacity_per_day": acct.posting_capacity_per_day,
                "diminishing_returns": float(acct.diminishing_returns_score or 0),
                "offer_performance_proxy": offer_avg,
            }
        )

    primary_rec = next((r for r in recs if r.recommendation_key != RK_REDUCE_WEAK), recs[0] if recs else None)
    best_next = (primary_rec.best_next_account if primary_rec else {}) or {}
    weekly = (
        (primary_rec.weekly_action_plan or {}).get("days", []) if primary_rec and primary_rec.weekly_action_plan else []
    )

    totals = {
        "total_revenue": round(sum(a["revenue"] for a in accounts_payload), 2),
        "total_profit": round(sum(a["profit"] for a in accounts_payload), 2),
        "active_accounts": len(accounts_payload),
    }
    inc_new = float(primary_rec.incremental_profit_new_account) if primary_rec else 0.0
    inc_vol = float(primary_rec.incremental_profit_existing_push) if primary_rec else 0.0
    ratio = float(primary_rec.comparison_ratio) if primary_rec else 0.0
    tradeoff_winner = (
        "new_account"
        if inc_new > inc_vol * EXPANSION_BEATS_EXISTING_RATIO
        else ("more_volume" if inc_vol >= inc_new else "tie")
    )
    incremental_tradeoff = {
        "incremental_profit_new_account": inc_new,
        "incremental_profit_more_volume_on_existing": inc_vol,
        "comparison_ratio_new_vs_volume": ratio,
        "expansion_beats_existing_threshold": EXPANSION_BEATS_EXISTING_RATIO,
        "interpretation": (
            f"New-account incremental ${inc_new:.2f} vs volume push ${inc_vol:.2f} "
            f"(ratio {ratio:.3f}; expansion favored if new > volume × {EXPANSION_BEATS_EXISTING_RATIO})."
        ),
        "tradeoff_winner_hint": tradeoff_winner,
        "primary_recommendation_id": str(primary_rec.id) if primary_rec else None,
    }
    audit = {
        "engine_module": "packages.scoring.scale.run_scale_engine",
        "formula_constants": {
            "new_account_overhead_usd": NEW_ACCOUNT_OVERHEAD_USD,
            "volume_lift_factor": VOLUME_LIFT_FACTOR,
            "expansion_beats_existing_ratio": EXPANSION_BEATS_EXISTING_RATIO,
        },
        "funnel_weak_gate_current": funnel_weak_flag,
        "offer_diversity_weak_current": _weak_offer_diversity(offers_dict),
    }

    warnings = []
    for acct in accounts_payload:
        if acct["niche_saturation"] > 0.65:
            warnings.append(
                {
                    "type": "saturation",
                    "account": acct["username"],
                    "detail": "Niche saturation elevated — reduce angle overlap before cloning.",
                }
            )
        if acct["content_fatigue"] > 0.6:
            warnings.append(
                {
                    "type": "fatigue",
                    "account": acct["username"],
                    "detail": "Content fatigue rising — rotate hooks and templates.",
                }
            )
    if primary_rec and primary_rec.cannibalization_risk_score > 0.5:
        warnings.append(
            {
                "type": "cannibalization",
                "account": "portfolio",
                "detail": f"Cannibalization risk {primary_rec.cannibalization_risk_score:.2f} — separate niche or platform.",
            }
        )

    platform_alloc = {}
    for row in allocations:
        acct = (
            await db.execute(select(CreatorAccount).where(CreatorAccount.id == row.creator_account_id))
        ).scalar_one_or_none()
        if not acct:
            continue
        pl = acct.platform.value if hasattr(acct.platform, "value") else str(acct.platform)
        platform_alloc.setdefault(pl, {"pct": 0.0, "accounts": []})
        platform_alloc[pl]["pct"] += float(row.allocation_pct)
        platform_alloc[pl]["accounts"].append(acct.platform_username)

    niche_view = {
        "clusters": [
            {
                "label": a["username"],
                "niche_focus": a.get("niche_focus"),
                "platform": a.get("platform"),
                "profit": a["profit"],
            }
            for a in sorted(accounts_payload, key=lambda x: -x["profit"])
        ],
        "expansion_readiness": primary_rec.scale_readiness_score if primary_rec else 0.0,
        "segment_separation": primary_rec.audience_segment_separation if primary_rec else 0.0,
    }

    return {
        "brand_id": str(brand_id),
        "brand_name": brand.name,
        "portfolio_overview": {
            "accounts": accounts_payload,
            "totals": totals,
            "total_impressions_rollups": total_impressions,
            "recommended_structure": "1 flagship + 1 experimental minimum",
        },
        "ai_recommendations": [_serialize_rec(r) for r in recs[:12]],
        "best_next_account": best_next,
        "recommended_account_count": primary_rec.recommended_account_count if primary_rec else 2,
        "incremental_tradeoff": incremental_tradeoff,
        "audit": audit,
        "platform_allocation": platform_alloc,
        "niche_expansion": niche_view,
        "revenue_leak_alerts": leaks[:20],
        "growth_blockers": blockers[:20],
        "saturation_cannibalization_warnings": warnings,
        "weekly_action_plan": weekly,
        "computed_at": str(primary_rec.created_at) if primary_rec else None,
    }


async def _load_offers_dict(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    offers_rows = (
        (await db.execute(select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True)))).scalars().all()
    )
    return [{"epc": o.epc, "conversion_rate": o.conversion_rate} for o in offers_rows]


def _ctx_offer_avg(offers: list[dict]) -> float:
    if not offers:
        return 0.0
    return round(sum(float(o.get("conversion_rate") or 0) for o in offers) / len(offers), 4)


def _serialize_rec(r: ScaleRecommendation) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "recommendation_key": r.recommendation_key,
        "recommended_action": r.recommended_action.value if hasattr(r.recommended_action, "value") else str(r.recommended_action),
        "creator_account_id": str(r.creator_account_id) if r.creator_account_id else None,
        "incremental_profit_new_account": r.incremental_profit_new_account,
        "incremental_profit_existing_push": r.incremental_profit_existing_push,
        "comparison_ratio": r.comparison_ratio,
        "scale_readiness_score": r.scale_readiness_score,
        "cannibalization_risk_score": r.cannibalization_risk_score,
        "audience_segment_separation": r.audience_segment_separation,
        "expansion_confidence": r.expansion_confidence,
        "recommended_account_count": r.recommended_account_count,
        "best_next_account": r.best_next_account or {},
        "weekly_action_plan": r.weekly_action_plan or {},
        "score_components": r.score_components or {},
        "penalties": r.penalties or {},
        "confidence": r.confidence.value if hasattr(r.confidence, "value") else str(r.confidence),
        "explanation": r.explanation,
        "is_actioned": r.is_actioned,
    }
