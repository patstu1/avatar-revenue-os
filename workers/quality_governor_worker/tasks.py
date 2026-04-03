"""Quality Governor workers — score pending content for all brands."""
import asyncio
import logging
from celery import shared_task
from sqlalchemy import select
from packages.db.session import async_session_factory
from workers.base_task import TrackedTask
from packages.db.models.core import Brand

logger = logging.getLogger(__name__)


async def _run():
    from apps.api.services.quality_governor_service import recompute_brand_quality
    async with async_session_factory() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    count = 0
    for bid in brands:
        try:
            async with async_session_factory() as db:
                await recompute_brand_quality(db, bid)
                await db.commit()
                count += 1
        except Exception:
            logger.exception("quality governor failed for brand %s", bid)
    return count


@shared_task(name="workers.quality_governor_worker.tasks.recompute_quality_governor", base=TrackedTask)
def recompute_quality_governor():
    count = asyncio.run(_run())
    return {"status": "completed", "brands_processed": count}
