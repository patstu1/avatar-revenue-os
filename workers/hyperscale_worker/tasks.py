"""Hyper-Scale Execution workers."""
import asyncio, logging
from celery import shared_task
from sqlalchemy import select
from packages.db.session import async_session_factory, run_async
from workers.base_task import TrackedTask
from packages.db.models.core import Organization
logger = logging.getLogger(__name__)

async def _run():
    from apps.api.services.hyperscale_service import recompute_capacity
    async with async_session_factory() as db:
        orgs = list((await db.execute(select(Organization.id))).scalars().all())
    c = 0
    for oid in orgs:
        try:
            async with async_session_factory() as db:
                await recompute_capacity(db, oid); await db.commit(); c += 1
        except Exception: logger.exception("hyperscale failed %s", oid)
    return c

@shared_task(name="workers.hyperscale_worker.tasks.recompute_scale_capacity", base=TrackedTask)
def recompute_scale_capacity():
    return {"status": "completed", "orgs": run_async(_run())}
