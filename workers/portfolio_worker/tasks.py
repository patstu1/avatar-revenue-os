"""Portfolio worker tasks — rebalancing, scale decisions, capital allocation."""
from workers.base_task import TrackedTask
from workers.celery_app import app


@app.task(base=TrackedTask, bind=True, name="workers.portfolio_worker.tasks.rebalance_portfolios")
def rebalance_portfolios(self) -> dict:
    """Rebalance portfolio allocations using pattern memory cluster weights."""
    import logging

    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from packages.db.models.core import Brand
    from packages.db.models.pattern_memory import WinningPatternCluster
    from packages.db.models.portfolio import PortfolioAllocation
    from packages.db.session import get_sync_engine
    from packages.scoring.pattern_memory_engine import compute_pattern_allocation_weights

    logger = logging.getLogger(__name__)
    engine = get_sync_engine()
    with Session(engine) as session:
        count = session.execute(select(func.count()).select_from(PortfolioAllocation)).scalar() or 0

        brands = session.execute(select(Brand.id)).scalars().all()
        pattern_informed = 0
        for bid in brands:
            clusters = session.query(WinningPatternCluster).filter(
                WinningPatternCluster.brand_id == bid,
                WinningPatternCluster.is_active.is_(True),
            ).all()
            if not clusters:
                continue
            cluster_dicts = [{"cluster_type": c.cluster_type, "platform": c.platform, "cluster_name": c.cluster_name, "avg_win_score": float(c.avg_win_score), "pattern_count": c.pattern_count} for c in clusters]
            weights = compute_pattern_allocation_weights(cluster_dicts, 1000.0)
            logger.info("Brand %s: pattern allocation weights = %s", bid, [w["cluster_name"] + ":" + str(w["allocation_pct"]) for w in weights[:3]])
            pattern_informed += 1

        return {"status": "completed", "allocations_reviewed": count, "pattern_informed_brands": pattern_informed}


@app.task(base=TrackedTask, bind=True, name="workers.portfolio_worker.evaluate_scale")
def evaluate_scale(self, brand_id: str) -> dict:
    """Evaluate scale decisions: new account launch vs pushing existing winners."""
    import uuid as _uuid
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from packages.db.models.accounts import CreatorAccount
    from packages.db.models.core import Brand
    from packages.db.models.offers import Offer
    from packages.db.models.publishing import PerformanceMetric
    from packages.db.session import get_sync_engine
    from packages.scoring.saturation import SaturationInput, compute_saturation
    from packages.scoring.scale import (
        AccountScaleSnapshot,
        run_scale_engine,
    )

    engine = get_sync_engine()
    bid = _uuid.UUID(brand_id)

    with Session(engine) as session:
        brand = session.get(Brand, bid)
        if not brand:
            return {"status": "completed", "brand_id": brand_id, "recommendation": "brand_not_found"}

        accounts = session.execute(
            select(CreatorAccount).where(
                CreatorAccount.brand_id == bid,
                CreatorAccount.is_active.is_(True),
            )
        ).scalars().all()

        if not accounts:
            return {"status": "completed", "brand_id": brand_id, "recommendation": "no_active_accounts"}

        now = datetime.now(timezone.utc)
        cutoff_30d = now - timedelta(days=30)

        snapshots: list[AccountScaleSnapshot] = []
        total_impressions = 0

        for acct in accounts:
            metrics = session.execute(
                select(PerformanceMetric).where(
                    PerformanceMetric.creator_account_id == acct.id,
                    PerformanceMetric.measured_at >= cutoff_30d,
                )
            ).scalars().all()

            impressions = sum(m.impressions or 0 for m in metrics)
            sum(m.views or 0 for m in metrics)
            clicks = sum(m.clicks or 0 for m in metrics)
            revenue = sum(m.revenue or 0.0 for m in metrics)
            avg_eng = sum(m.engagement_rate or 0.0 for m in metrics) / max(len(metrics), 1)
            fg = sum(m.followers_gained or 0 for m in metrics)
            total_impressions += impressions

            ctr = clicks / max(impressions, 1)
            cvr = 0.02 if clicks > 0 else 0.0

            sat_result = compute_saturation(SaturationInput(
                avg_engagement_last_7d=avg_eng,
                avg_engagement_last_30d=avg_eng,
                posts_last_30d=len(metrics),
            ))

            snapshots.append(AccountScaleSnapshot(
                account_id=str(acct.id),
                platform=acct.platform.value if hasattr(acct.platform, "value") else str(acct.platform),
                username=acct.platform_username or str(acct.id)[:8],
                niche_focus=getattr(acct, "niche_focus", None),
                sub_niche_focus=getattr(acct, "sub_niche_focus", None),
                revenue=revenue,
                profit=revenue * 0.7,
                profit_per_post=revenue / max(len(metrics), 1),
                revenue_per_mille=(revenue / max(impressions, 1)) * 1000,
                ctr=ctr,
                conversion_rate=cvr,
                follower_growth_rate=fg / max(30, 1) / 1000.0,
                fatigue_score=sat_result.fatigue_score,
                saturation_score=sat_result.saturation_score,
                originality_drift_score=1.0 - sat_result.originality_score,
                diminishing_returns_score=sat_result.fatigue_score * 0.5,
                posting_capacity_per_day=3,
                account_health=acct.account_health.value if hasattr(acct.account_health, "value") else str(acct.account_health or "healthy"),
                offer_performance_score=0.5,
                scale_role=getattr(acct, "scale_role", None),
                impressions_rollup=impressions,
            ))

        offers_raw = session.execute(
            select(Offer).where(Offer.brand_id == bid, Offer.is_active.is_(True))
        ).scalars().all()
        offer_dicts = [
            {"epc": getattr(o, "epc", 0) or 0, "conversion_rate": getattr(o, "conversion_rate", 0) or 0}
            for o in offers_raw
        ]

        funnel_weak = any(s.ctr < 0.01 and s.impressions_rollup > 500 for s in snapshots)
        weak_offer_diversity = len(offer_dicts) < 2

        result = run_scale_engine(
            accounts=snapshots,
            offers=offer_dicts,
            total_impressions=total_impressions,
            brand_niche=getattr(brand, "niche_focus", None),
            funnel_weak=funnel_weak,
            weak_offer_diversity=weak_offer_diversity,
        )

    return {
        "status": "completed",
        "brand_id": brand_id,
        "recommendation": result.recommendation_key,
        "coarse_action": result.coarse_action,
        "scale_readiness_score": result.scale_readiness_score,
        "expansion_confidence": result.expansion_confidence,
        "cannibalization_risk": result.cannibalization_risk,
        "incremental_profit_new_account": result.incremental_profit_new_account,
        "incremental_profit_more_volume": result.incremental_profit_more_volume,
        "recommended_account_count": result.recommended_account_count,
        "explanation": result.explanation,
        "best_next_account": result.best_next_account,
    }
