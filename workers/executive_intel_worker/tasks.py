"""Executive Intelligence workers."""
import asyncio, logging
from celery import shared_task
from sqlalchemy import select
from packages.db.session import async_session_factory
from workers.base_task import TrackedTask
from packages.db.models.core import Organization
logger = logging.getLogger(__name__)

async def _run():
    from apps.api.services.executive_intel_service import recompute_executive_intel
    async with async_session_factory() as db:
        orgs = list((await db.execute(select(Organization.id))).scalars().all())
    c = 0
    for oid in orgs:
        try:
            async with async_session_factory() as db:
                await recompute_executive_intel(db, oid); await db.commit(); c += 1
        except Exception: logger.exception("executive intel failed %s", oid)
    return c

@shared_task(name="workers.executive_intel_worker.tasks.recompute_executive_intel", base=TrackedTask)
def recompute_executive_intel_task():
    return {"status": "completed", "orgs": asyncio.run(_run())}
