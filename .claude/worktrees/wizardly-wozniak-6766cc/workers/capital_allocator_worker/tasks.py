"""Capital Allocator workers — recompute allocations for all brands."""
import asyncio
import logging
from celery import shared_task
from sqlalchemy import select
from packages.db.session import async_session_factory
from workers.base_task import TrackedTask
from packages.db.models.core import Brand

logger = logging.getLogger(__name__)


async def _run():
    from apps.api.services.capital_allocator_service import recompute_allocation
    async with async_session_factory() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    count = 0
    for bid in brands:
        try:
            async with async_session_factory() as db:
                await recompute_allocation(db, bid)
                await db.commit()
                count += 1
        except Exception:
            logger.exception("capital allocator failed for brand %s", bid)
    return count


@shared_task(name="workers.capital_allocator_worker.tasks.recompute_capital_allocation", base=TrackedTask)
def recompute_capital_allocation():
    count = asyncio.run(_run())
    return {"status": "completed", "brands_processed": count}
