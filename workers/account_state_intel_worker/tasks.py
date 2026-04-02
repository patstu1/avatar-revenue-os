"""Account-State Intelligence workers — recompute states for all brands."""
import asyncio
import logging
from celery import shared_task
from sqlalchemy import select
from packages.db.session import async_session_factory
from packages.db.models.core import Brand

logger = logging.getLogger(__name__)


async def _run():
    from apps.api.services.account_state_intel_service import recompute_account_states
    async with async_session_factory() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    count = 0
    for bid in brands:
        try:
            async with async_session_factory() as db:
                await recompute_account_states(db, bid)
                await db.commit()
                count += 1
        except Exception:
            logger.exception("account state intel failed for brand %s", bid)
    return count


@shared_task(name="workers.account_state_intel_worker.tasks.recompute_account_state_intel")
def recompute_account_state_intel():
    count = asyncio.run(_run())
    return {"status": "completed", "brands_processed": count}
