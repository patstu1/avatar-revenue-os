"""Content Routing workers — daily cost rollup."""
import logging

from celery import shared_task
from sqlalchemy import select

from packages.db.models.core import Brand
from packages.db.session import get_async_session_factory, run_async
from workers.base_task import TrackedTask

logger = logging.getLogger(__name__)


async def _run_all(coro_factory):
    async with get_async_session_factory()() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    for bid in brands:
        try:
            await coro_factory(bid)
        except Exception:
            logger.exception("content_routing task failed for brand %s", bid)


async def _daily_cost_rollup(bid):
    from apps.api.services.content_routing_service import recompute_cost_report
    async with get_async_session_factory()() as db:
        await recompute_cost_report(db, bid)
        await db.commit()


@shared_task(name="workers.content_routing_worker.tasks.daily_cost_rollup", base=TrackedTask)
def daily_cost_rollup():
    run_async(_run_all(_daily_cost_rollup))
    return "cost-rollup-done"
