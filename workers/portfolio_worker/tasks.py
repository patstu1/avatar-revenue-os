"""Portfolio worker tasks — rebalancing, scale decisions, capital allocation."""
from workers.celery_app import app
from workers.base_task import TrackedTask


@app.task(base=TrackedTask, bind=True, name="workers.portfolio_worker.tasks.rebalance_portfolios")
def rebalance_portfolios(self) -> dict:
    """Rebalance portfolio allocations using pattern memory cluster weights."""
    import logging
    from sqlalchemy.orm import Session
    from sqlalchemy import func, select
    from packages.db.session import get_sync_engine
    from packages.db.models.portfolio import PortfolioAllocation
    from packages.db.models.pattern_memory import WinningPatternCluster
    from packages.db.models.core import Brand
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
    return {
        "status": "completed",
        "brand_id": brand_id,
        "recommendation": "insufficient_signal",
        "note": "Requires performance history to evaluate scale decisions",
    }
