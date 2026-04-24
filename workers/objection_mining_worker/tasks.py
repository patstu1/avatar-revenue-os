"""Objection Mining workers — extract objections for all brands."""
import logging

from celery import shared_task
from sqlalchemy import select

from packages.db.models.core import Brand
from packages.db.session import get_async_session_factory, run_async
from workers.base_task import TrackedTask

logger = logging.getLogger(__name__)

async def _run():
    from apps.api.services.objection_mining_service import recompute_objections
    async with get_async_session_factory()() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    count = 0
    for bid in brands:
        try:
            async with get_async_session_factory()() as db:
                await recompute_objections(db, bid)
                await db.commit()
                count += 1
        except Exception:
            logger.exception("objection mining failed for brand %s", bid)
    return count

@shared_task(name="workers.objection_mining_worker.tasks.recompute_objection_mining", base=TrackedTask)
def recompute_objection_mining():
    count = run_async(_run())
    return {"status": "completed", "brands_processed": count}
