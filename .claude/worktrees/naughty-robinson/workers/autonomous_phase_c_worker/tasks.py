"""Autonomous Phase C workers — funnel, paid operator, sponsor, retention, recovery."""
from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import select

from workers.celery_app import app
from workers.base_task import TrackedTask
from packages.db.session import async_session_factory, run_async
from packages.db.models.core import Brand
from apps.api.services import autonomous_phase_c_service as svc
from apps.api.services import autonomous_phase_c_lifecycle as lifecycle

logger = structlog.get_logger()


async def _all_brand_ids() -> list:
    async with async_session_factory() as db:
        rows = (await db.execute(select(Brand).where(Brand.is_active.is_(True)))).scalars().all()
        return [b.id for b in rows]


async def _run_per_brand(coro_factory):
    """Run async coroutine per brand with own session commit."""
    bids = await _all_brand_ids()
    total = 0
    errors = []
    for bid in bids:
        try:
            async with async_session_factory() as db:
                await coro_factory(db, bid)
                await db.commit()
                total += 1
        except Exception as exc:
            logger.exception("phase_c.worker.brand_error", brand_id=str(bid))
            errors.append({"brand_id": str(bid), "error": str(exc)})
    return total, errors


@app.task(base=TrackedTask, bind=True, name="workers.autonomous_phase_c_worker.tasks.run_funnel_execution")
def run_funnel_execution(self) -> dict:
    async def _go():
        return await _run_per_brand(svc.recompute_funnel_execution)

    n, err = run_async(_go())
    return {"status": "completed", "brands_processed": n, "errors": err}


@app.task(base=TrackedTask, bind=True, name="workers.autonomous_phase_c_worker.tasks.run_paid_operator")
def run_paid_operator(self) -> dict:
    async def _go():
        return await _run_per_brand(svc.recompute_paid_operator)

    n, err = run_async(_go())
    return {"status": "completed", "brands_processed": n, "errors": err}


@app.task(base=TrackedTask, bind=True, name="workers.autonomous_phase_c_worker.tasks.run_sponsor_autonomy")
def run_sponsor_autonomy(self) -> dict:
    async def _go():
        return await _run_per_brand(svc.recompute_sponsor_autonomy)

    n, err = run_async(_go())
    return {"status": "completed", "brands_processed": n, "errors": err}


@app.task(base=TrackedTask, bind=True, name="workers.autonomous_phase_c_worker.tasks.run_retention_autonomy")
def run_retention_autonomy(self) -> dict:
    async def _go():
        return await _run_per_brand(svc.recompute_retention_autonomy)

    n, err = run_async(_go())
    return {"status": "completed", "brands_processed": n, "errors": err}


@app.task(base=TrackedTask, bind=True, name="workers.autonomous_phase_c_worker.tasks.run_recovery_autonomy")
def run_recovery_autonomy(self) -> dict:
    async def _go():
        return await _run_per_brand(svc.recompute_recovery_autonomy)

    n, err = run_async(_go())
    return {"status": "completed", "brands_processed": n, "errors": err}


@app.task(base=TrackedTask, bind=True, name="workers.autonomous_phase_c_worker.tasks.execute_approved_actions")
def execute_approved_actions(self) -> dict:
    """Pick up all approved Phase C actions across brands and execute them."""
    async def _go():
        return await _run_per_brand(lifecycle.execute_approved_actions)

    n, err = run_async(_go())
    return {"status": "completed", "brands_processed": n, "errors": err}


@app.task(base=TrackedTask, bind=True, name="workers.autonomous_phase_c_worker.tasks.notify_operators")
def notify_operators(self) -> dict:
    """Collect operator_review items across brands and dispatch notifications."""
    async def _go():
        return await _run_per_brand(lifecycle.notify_operator_review_items)

    n, err = run_async(_go())
    return {"status": "completed", "brands_processed": n, "errors": err}
