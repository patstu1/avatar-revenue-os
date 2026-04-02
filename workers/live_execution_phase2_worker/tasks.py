"""Live Execution Phase 2 + Buffer Expansion workers."""
from __future__ import annotations

import asyncio
import logging
import uuid

from celery import shared_task
from sqlalchemy import select

from packages.db.models.core import Brand
from packages.db.session import async_session_factory

logger = logging.getLogger(__name__)


async def _run_all_brands(coro_factory):
    async with async_session_factory() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    for bid in brands:
        try:
            await coro_factory(bid)
        except Exception:
            logger.exception("live_execution_phase2 task failed for brand %s", bid)


async def _do_recompute_event_ingestions(brand_id: uuid.UUID) -> None:
    from apps.api.services.live_execution_phase2_service import recompute_event_ingestions

    async with async_session_factory() as db:
        await recompute_event_ingestions(db, brand_id)
        await db.commit()


async def _do_process_sequence_triggers(brand_id: uuid.UUID) -> None:
    from apps.api.services.live_execution_phase2_service import (
        process_sequence_triggers as run_process_sequence_triggers,
    )

    async with async_session_factory() as db:
        await run_process_sequence_triggers(db, brand_id)
        await db.commit()


async def _do_run_payment_sync(brand_id: uuid.UUID) -> None:
    from apps.api.services.live_execution_phase2_service import run_payment_sync

    async with async_session_factory() as db:
        await run_payment_sync(db, brand_id, provider="stripe")
        await db.commit()


async def _do_run_analytics_sync(brand_id: uuid.UUID) -> None:
    from apps.api.services.live_execution_phase2_service import run_analytics_sync

    async with async_session_factory() as db:
        await run_analytics_sync(db, brand_id, source="buffer")
        await db.commit()


async def _do_run_ad_import(brand_id: uuid.UUID) -> None:
    from apps.api.services.live_execution_phase2_service import run_ad_import

    async with async_session_factory() as db:
        await run_ad_import(db, brand_id, platform="meta_ads")
        await db.commit()


async def _do_recompute_buffer_execution_truth(brand_id: uuid.UUID) -> None:
    from apps.api.services.live_execution_phase2_service import recompute_buffer_execution_truth

    async with async_session_factory() as db:
        await recompute_buffer_execution_truth(db, brand_id)
        await db.commit()


async def _do_detect_stale_buffer_jobs(brand_id: uuid.UUID) -> None:
    from apps.api.services.live_execution_phase2_service import recompute_buffer_execution_truth

    async with async_session_factory() as db:
        await recompute_buffer_execution_truth(db, brand_id)
        await db.commit()


async def _do_recompute_buffer_capabilities(brand_id: uuid.UUID) -> None:
    from apps.api.services.live_execution_phase2_service import recompute_buffer_capabilities

    async with async_session_factory() as db:
        await recompute_buffer_capabilities(db, brand_id)
        await db.commit()


@shared_task(name="workers.live_execution_phase2_worker.tasks.process_webhook_events")
def process_webhook_events():
    asyncio.run(_run_all_brands(_do_recompute_event_ingestions))
    return "done"


@shared_task(name="workers.live_execution_phase2_worker.tasks.process_sequence_triggers")
def process_sequence_triggers():
    asyncio.run(_run_all_brands(_do_process_sequence_triggers))
    return "done"


@shared_task(name="workers.live_execution_phase2_worker.tasks.run_payment_connector_sync")
def run_payment_connector_sync():
    asyncio.run(_run_all_brands(_do_run_payment_sync))
    return "done"


@shared_task(name="workers.live_execution_phase2_worker.tasks.run_analytics_auto_pull")
def run_analytics_auto_pull():
    asyncio.run(_run_all_brands(_do_run_analytics_sync))
    return "done"


@shared_task(name="workers.live_execution_phase2_worker.tasks.run_ad_reporting_import")
def run_ad_reporting_import():
    asyncio.run(_run_all_brands(_do_run_ad_import))
    return "done"


@shared_task(name="workers.live_execution_phase2_worker.tasks.recompute_buffer_execution_truth")
def recompute_buffer_execution_truth():
    asyncio.run(_run_all_brands(_do_recompute_buffer_execution_truth))
    return "done"


@shared_task(name="workers.live_execution_phase2_worker.tasks.detect_stale_buffer_jobs")
def detect_stale_buffer_jobs():
    asyncio.run(_run_all_brands(_do_detect_stale_buffer_jobs))
    return "done"


@shared_task(name="workers.live_execution_phase2_worker.tasks.recompute_buffer_capabilities")
def recompute_buffer_capabilities():
    asyncio.run(_run_all_brands(_do_recompute_buffer_capabilities))
    return "done"
