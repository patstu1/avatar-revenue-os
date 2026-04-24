"""Landing Page workers."""
import logging

from celery import shared_task
from sqlalchemy import select

from packages.db.models.core import Brand
from packages.db.session import get_async_session_factory, run_async
from workers.base_task import TrackedTask

logger = logging.getLogger(__name__)

async def _run():
    from apps.api.services.landing_page_service import recompute_landing_pages
    async with get_async_session_factory()() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    c = 0
    for bid in brands:
        try:
            async with get_async_session_factory()() as db:
                await recompute_landing_pages(db, bid); await db.commit(); c += 1
        except Exception: logger.exception("lp worker failed %s", bid)
    return c

@shared_task(name="workers.landing_page_worker.tasks.recompute_landing_pages", base=TrackedTask)
def recompute_landing_pages_task():
    return {"status": "completed", "brands": run_async(_run())}
