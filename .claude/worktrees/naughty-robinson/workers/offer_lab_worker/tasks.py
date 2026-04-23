"""Offer Lab workers."""
import asyncio, logging
from celery import shared_task
from sqlalchemy import select
from packages.db.session import async_session_factory, run_async
from workers.base_task import TrackedTask
from packages.db.models.core import Brand
logger = logging.getLogger(__name__)

async def _run():
    from apps.api.services.offer_lab_service import recompute_offer_lab
    async with async_session_factory() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    c = 0
    for bid in brands:
        try:
            async with async_session_factory() as db:
                await recompute_offer_lab(db, bid); await db.commit(); c += 1
        except Exception: logger.exception("offer lab failed %s", bid)
    return c

@shared_task(name="workers.offer_lab_worker.tasks.recompute_offer_lab", base=TrackedTask)
def recompute_offer_lab_task():
    return {"status": "completed", "brands": run_async(_run())}
