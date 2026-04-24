"""Digital Twin workers."""

import logging

from celery import shared_task
from sqlalchemy import select

from packages.db.models.core import Brand
from packages.db.session import get_async_session_factory, run_async
from workers.base_task import TrackedTask

logger = logging.getLogger(__name__)


async def _run():
    from apps.api.services.digital_twin_service import run_simulation

    async with get_async_session_factory()() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    c = 0
    for bid in brands:
        try:
            async with get_async_session_factory()() as db:
                await run_simulation(db, bid)
                await db.commit()
                c += 1
        except Exception:
            logger.exception("digital twin failed %s", bid)
    return c


@shared_task(name="workers.digital_twin_worker.tasks.run_simulations", base=TrackedTask)
def run_simulations():
    return {"status": "completed", "brands": run_async(_run())}
