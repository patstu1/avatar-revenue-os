"""Content Form Selection workers."""
import asyncio
import logging

from celery import shared_task
from sqlalchemy import select

from packages.db.session import async_session_factory
from workers.base_task import TrackedTask
from packages.db.models.core import Brand

logger = logging.getLogger(__name__)


async def _run_all(coro_factory):
    async with async_session_factory() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    for bid in brands:
        try:
            await coro_factory(bid)
        except Exception:
            logger.exception("content_form task failed for brand %s", bid)


async def _recompute_recs(bid):
    from apps.api.services.content_form_service import recompute_recommendations

    async with async_session_factory() as db:
        await recompute_recommendations(db, bid)
        await db.commit()


async def _recompute_mix(bid):
    from apps.api.services.content_form_service import recompute_mix

    async with async_session_factory() as db:
        await recompute_mix(db, bid)
        await db.commit()


async def _recompute_blockers(bid):
    from apps.api.services.content_form_service import recompute_blockers

    async with async_session_factory() as db:
        await recompute_blockers(db, bid)
        await db.commit()


@shared_task(name="workers.content_form_worker.tasks.recompute_content_forms", base=TrackedTask)
def recompute_content_forms():
    asyncio.run(_run_all(_recompute_recs))
    return "content-forms-done"


@shared_task(name="workers.content_form_worker.tasks.recompute_content_form_mix", base=TrackedTask)
def recompute_content_form_mix():
    asyncio.run(_run_all(_recompute_mix))
    return "content-form-mix-done"


@shared_task(name="workers.content_form_worker.tasks.recompute_content_form_blockers", base=TrackedTask)
def recompute_content_form_blockers():
    asyncio.run(_run_all(_recompute_blockers))
    return "content-form-blockers-done"
