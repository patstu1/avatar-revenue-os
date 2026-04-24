"""Opportunity-Cost Ranking workers — rank actions for all brands."""

import logging

from celery import shared_task
from sqlalchemy import select

from packages.db.models.core import Brand
from packages.db.session import get_async_session_factory, run_async
from workers.base_task import TrackedTask

logger = logging.getLogger(__name__)


async def _run():
    from apps.api.services.opportunity_cost_service import recompute_ranking

    async with get_async_session_factory()() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    count = 0
    for bid in brands:
        try:
            async with get_async_session_factory()() as db:
                await recompute_ranking(db, bid)
                await db.commit()
                count += 1
        except Exception:
            logger.exception("opportunity cost ranking failed for brand %s", bid)
    return count


@shared_task(name="workers.opportunity_cost_worker.tasks.recompute_opportunity_cost", base=TrackedTask)
def recompute_opportunity_cost():
    count = run_async(_run())
    return {"status": "completed", "brands_processed": count}
