"""Brand Governance workers."""
import asyncio, logging
from celery import shared_task
from sqlalchemy import select
from packages.db.session import async_session_factory
from packages.db.models.core import Brand
logger = logging.getLogger(__name__)

async def _run():
    from apps.api.services.brand_governance_service import recompute_governance
    async with async_session_factory() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    c = 0
    for bid in brands:
        try:
            async with async_session_factory() as db:
                await recompute_governance(db, bid); await db.commit(); c += 1
        except Exception: logger.exception("brand governance failed %s", bid)
    return c

@shared_task(name="workers.brand_governance_worker.tasks.recompute_brand_governance")
def recompute_brand_governance():
    return {"status": "completed", "brands": asyncio.run(_run())}
