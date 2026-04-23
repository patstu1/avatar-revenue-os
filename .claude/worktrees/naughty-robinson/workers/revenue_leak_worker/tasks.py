"""Revenue Leak Detector workers."""
import asyncio, logging
from celery import shared_task
from sqlalchemy import select
from packages.db.session import async_session_factory, run_async
from workers.base_task import TrackedTask
from packages.db.models.core import Brand
logger = logging.getLogger(__name__)

async def _run():
    from apps.api.services.revenue_leak_service import recompute_leaks
    async with async_session_factory() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    c = 0
    for bid in brands:
        try:
            async with async_session_factory() as db:
                await recompute_leaks(db, bid); await db.commit(); c += 1
        except Exception: logger.exception("revenue leak failed %s", bid)
    return c

@shared_task(name="workers.revenue_leak_worker.tasks.recompute_revenue_leaks", base=TrackedTask)
def recompute_revenue_leaks():
    return {"status": "completed", "brands": run_async(_run())}
