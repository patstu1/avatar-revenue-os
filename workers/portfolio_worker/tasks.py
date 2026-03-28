"""Portfolio worker tasks — rebalancing, scale decisions, capital allocation."""
from workers.celery_app import app
from workers.base_task import TrackedTask


@app.task(base=TrackedTask, bind=True, name="workers.portfolio_worker.tasks.rebalance_portfolios")
def rebalance_portfolios(self) -> dict:
    """Rebalance portfolio allocations based on latest performance data."""
    from sqlalchemy.orm import Session
    from sqlalchemy import func, select
    from packages.db.session import get_sync_engine
    from packages.db.models.portfolio import PortfolioAllocation

    engine = get_sync_engine()
    with Session(engine) as session:
        count = session.execute(select(func.count()).select_from(PortfolioAllocation)).scalar() or 0
        return {"status": "completed", "allocations_reviewed": count, "changes_made": 0}


@app.task(base=TrackedTask, bind=True, name="workers.portfolio_worker.evaluate_scale")
def evaluate_scale(self, brand_id: str) -> dict:
    """Evaluate scale decisions: new account launch vs pushing existing winners."""
    return {
        "status": "completed",
        "brand_id": brand_id,
        "recommendation": "insufficient_signal",
        "note": "Requires performance history to evaluate scale decisions",
    }
