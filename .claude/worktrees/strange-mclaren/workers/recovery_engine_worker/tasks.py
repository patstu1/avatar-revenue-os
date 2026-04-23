"""Recovery Engine workers."""
import asyncio, logging
from celery import shared_task
from sqlalchemy import select
from packages.db.session import async_session_factory
from workers.base_task import TrackedTask
from packages.db.models.core import Organization
logger = logging.getLogger(__name__)

async def _run():
    from apps.api.services.recovery_engine_service import recompute_recovery, execute_pending_recovery_actions
    async with async_session_factory() as db:
        orgs = list((await db.execute(select(Organization.id))).scalars().all())
    c = 0
    executed_total = 0
    for oid in orgs:
        try:
            async with async_session_factory() as db:
                await recompute_recovery(db, oid)
                result = await execute_pending_recovery_actions(db, oid)
                executed_total += result.get("rollbacks", 0) + result.get("reroutes", 0) + result.get("throttles", 0)
                await db.commit(); c += 1
        except Exception: logger.exception("recovery engine failed %s", oid)
    return {"orgs": c, "actions_executed": executed_total}

@shared_task(name="workers.recovery_engine_worker.tasks.scan_recovery", base=TrackedTask)
def scan_recovery():
    result = asyncio.run(_run())
    return {"status": "completed", **result}
