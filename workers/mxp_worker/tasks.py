"""Maximum-strength pack recurring recomputes (11 modules)."""
import logging

from sqlalchemy import select

from apps.api.services import (
    audience_state_service,
    capacity_service,
    contribution_service,
    creative_memory_service,
    deal_desk_service,
    experiment_decision_service,
    kill_ledger_service,
    market_timing_service,
    offer_lifecycle_service,
    recovery_service,
    reputation_service,
)
from packages.db.models.core import Brand
from packages.db.session import get_async_session_factory, run_async
from workers.base_task import TrackedTask
from workers.celery_app import app

logger = logging.getLogger(__name__)


def _run_async(coro):
    return run_async(coro)


# ---------------------------------------------------------------------------
# 1. Experiment Decisions
# ---------------------------------------------------------------------------
@app.task(base=TrackedTask, bind=True, name="workers.mxp_worker.tasks.recompute_all_experiment_decisions")
def recompute_all_experiment_decisions(self) -> dict:
    async def _run():
        total = {"brands": 0, "errors": []}
        async with get_async_session_factory()() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with get_async_session_factory()() as db:
                    await experiment_decision_service.recompute_experiment_decisions(db, bid)
                    await db.commit()
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_experiment_decisions %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


# ---------------------------------------------------------------------------
# 2. Contribution & Attribution
# ---------------------------------------------------------------------------
@app.task(base=TrackedTask, bind=True, name="workers.mxp_worker.tasks.recompute_all_contribution_reports")
def recompute_all_contribution_reports(self) -> dict:
    async def _run():
        total = {"brands": 0, "errors": []}
        async with get_async_session_factory()() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with get_async_session_factory()() as db:
                    await contribution_service.recompute_contribution_reports(db, bid)
                    await db.commit()
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_contribution_reports %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


# ---------------------------------------------------------------------------
# 3. Capacity Orchestrator
# ---------------------------------------------------------------------------
@app.task(base=TrackedTask, bind=True, name="workers.mxp_worker.tasks.recompute_all_capacity")
def recompute_all_capacity(self) -> dict:
    async def _run():
        total = {"brands": 0, "errors": []}
        async with get_async_session_factory()() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with get_async_session_factory()() as db:
                    await capacity_service.recompute_capacity(db, bid)
                    await db.commit()
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_capacity %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


# ---------------------------------------------------------------------------
# 4. Offer Lifecycle
# ---------------------------------------------------------------------------
@app.task(base=TrackedTask, bind=True, name="workers.mxp_worker.tasks.recompute_all_offer_lifecycle")
def recompute_all_offer_lifecycle(self) -> dict:
    async def _run():
        total = {"brands": 0, "errors": []}
        async with get_async_session_factory()() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with get_async_session_factory()() as db:
                    await offer_lifecycle_service.recompute_offer_lifecycle(db, bid)
                    await db.commit()
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_offer_lifecycle %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


# ---------------------------------------------------------------------------
# 5. Creative Memory
# ---------------------------------------------------------------------------
@app.task(base=TrackedTask, bind=True, name="workers.mxp_worker.tasks.recompute_all_creative_memory")
def recompute_all_creative_memory(self) -> dict:
    async def _run():
        total = {"brands": 0, "errors": []}
        async with get_async_session_factory()() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with get_async_session_factory()() as db:
                    await creative_memory_service.recompute_creative_memory(db, bid)
                    await db.commit()
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_creative_memory %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


# ---------------------------------------------------------------------------
# 6. Recovery Engine
# ---------------------------------------------------------------------------
@app.task(base=TrackedTask, bind=True, name="workers.mxp_worker.tasks.recompute_all_recovery_incidents")
def recompute_all_recovery_incidents(self) -> dict:
    async def _run():
        total = {"brands": 0, "errors": []}
        async with get_async_session_factory()() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with get_async_session_factory()() as db:
                    await recovery_service.recompute_recovery_incidents(db, bid)
                    await db.commit()
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_recovery_incidents %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


# ---------------------------------------------------------------------------
# 7. Deal Desk
# ---------------------------------------------------------------------------
@app.task(base=TrackedTask, bind=True, name="workers.mxp_worker.tasks.recompute_all_deal_desk")
def recompute_all_deal_desk(self) -> dict:
    async def _run():
        total = {"brands": 0, "errors": []}
        async with get_async_session_factory()() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with get_async_session_factory()() as db:
                    await deal_desk_service.recompute_deal_desk(db, bid)
                    await db.commit()
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_deal_desk %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


# ---------------------------------------------------------------------------
# 8. Audience State
# ---------------------------------------------------------------------------
@app.task(base=TrackedTask, bind=True, name="workers.mxp_worker.tasks.recompute_all_audience_states")
def recompute_all_audience_states(self) -> dict:
    async def _run():
        total = {"brands": 0, "errors": []}
        async with get_async_session_factory()() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with get_async_session_factory()() as db:
                    await audience_state_service.recompute_audience_states(db, bid)
                    await db.commit()
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_audience_states %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


# ---------------------------------------------------------------------------
# 9. Reputation Monitor
# ---------------------------------------------------------------------------
@app.task(base=TrackedTask, bind=True, name="workers.mxp_worker.tasks.recompute_all_reputation")
def recompute_all_reputation(self) -> dict:
    async def _run():
        total = {"brands": 0, "errors": []}
        async with get_async_session_factory()() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with get_async_session_factory()() as db:
                    await reputation_service.recompute_reputation(db, bid)
                    await db.commit()
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_reputation %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


# ---------------------------------------------------------------------------
# 10. Market Timing
# ---------------------------------------------------------------------------
@app.task(base=TrackedTask, bind=True, name="workers.mxp_worker.tasks.recompute_all_market_timing")
def recompute_all_market_timing(self) -> dict:
    async def _run():
        total = {"brands": 0, "errors": []}
        async with get_async_session_factory()() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with get_async_session_factory()() as db:
                    await market_timing_service.recompute_market_timing(db, bid)
                    await db.commit()
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_market_timing %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


# ---------------------------------------------------------------------------
# 11. Kill Ledger
# ---------------------------------------------------------------------------
@app.task(base=TrackedTask, bind=True, name="workers.mxp_worker.tasks.recompute_all_kill_ledger")
def recompute_all_kill_ledger(self) -> dict:
    async def _run():
        total = {"brands": 0, "errors": []}
        async with get_async_session_factory()() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with get_async_session_factory()() as db:
                    await kill_ledger_service.recompute_kill_ledger_full(db, bid)
                    await db.commit()
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_kill_ledger %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())
