"""Failure-Family Suppression workers."""
import asyncio, logging
from celery import shared_task
from sqlalchemy import select
from packages.db.session import async_session_factory
from packages.db.models.core import Brand

logger = logging.getLogger(__name__)

async def _run():
    from apps.api.services.failure_family_service import recompute_failure_families, run_decay_check
    async with async_session_factory() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    count = 0
    for bid in brands:
        try:
            async with async_session_factory() as db:
                await recompute_failure_families(db, bid)
                await run_decay_check(db, bid)
                await db.commit()
                count += 1
        except Exception:
            logger.exception("failure family suppression failed for brand %s", bid)
    return count

@shared_task(name="workers.failure_family_worker.tasks.recompute_failure_families")
def recompute_failure_families_task():
    count = asyncio.run(_run())
    return {"status": "completed", "brands_processed": count}
