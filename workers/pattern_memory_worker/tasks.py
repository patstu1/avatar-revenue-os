"""Pattern Memory workers — extraction, scoring, clustering, decay, reuse."""
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
            logger.exception("pattern_memory task failed for brand %s", bid)


async def _recompute_all(bid):
    from apps.api.services.pattern_memory_service import (
        recompute_clusters,
        recompute_decay,
        recompute_patterns,
        recompute_reuse,
    )

    async with get_async_session_factory()() as db:
        await recompute_patterns(db, bid)
        await recompute_clusters(db, bid)
        await recompute_decay(db, bid)
        await recompute_reuse(db, bid)
        await db.commit()


@shared_task(name="workers.pattern_memory_worker.tasks.recompute_pattern_memory", base=TrackedTask)
def recompute_pattern_memory():
    run_async(_run_all(_recompute_all))
    return "pattern-memory-done"
