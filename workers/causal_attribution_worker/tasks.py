"""Causal Attribution workers."""
import asyncio, logging
from celery import shared_task
from sqlalchemy import select
from packages.db.session import async_session_factory
from packages.db.models.core import Brand
logger = logging.getLogger(__name__)

async def _run():
    from apps.api.services.causal_attribution_service import recompute_attribution
    async with async_session_factory() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    c = 0
    for bid in brands:
        try:
            async with async_session_factory() as db:
                await recompute_attribution(db, bid); await db.commit(); c += 1
        except Exception: logger.exception("causal attribution failed %s", bid)
    return c

@shared_task(name="workers.causal_attribution_worker.tasks.recompute_causal_attribution")
def recompute_causal_attribution():
    return {"status": "completed", "brands": asyncio.run(_run())}
