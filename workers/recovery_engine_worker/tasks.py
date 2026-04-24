"""Recovery Engine workers."""
import logging

from celery import shared_task
from sqlalchemy import select

from packages.db.models.core import Organization
from packages.db.session import get_async_session_factory, run_async
from workers.base_task import TrackedTask

logger = logging.getLogger(__name__)

async def _run():
    from apps.api.services.recovery_engine_service import execute_pending_recovery_actions, recompute_recovery
    async with get_async_session_factory()() as db:
        orgs = list((await db.execute(select(Organization.id))).scalars().all())
    c = 0
    executed_total = 0
    for oid in orgs:
        try:
            async with get_async_session_factory()() as db:
                await recompute_recovery(db, oid)
                result = await execute_pending_recovery_actions(db, oid)
                executed_total += result.get("rollbacks", 0) + result.get("reroutes", 0) + result.get("throttles", 0)
                await db.commit(); c += 1
        except Exception: logger.exception("recovery engine failed %s", oid)
    return {"orgs": c, "actions_executed": executed_total}

@shared_task(name="workers.recovery_engine_worker.tasks.scan_recovery", base=TrackedTask)
def scan_recovery():
    result = run_async(_run())
    return {"status": "completed", **result}
