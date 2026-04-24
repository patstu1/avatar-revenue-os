"""Live Execution Phase 2 + Buffer Expansion workers."""

from __future__ import annotations

import logging
import uuid

from celery import shared_task
from sqlalchemy import select

from packages.db.models.core import Brand
from packages.db.session import get_async_session_factory, run_async
from workers.base_task import TrackedTask

logger = logging.getLogger(__name__)


async def _run_all_brands(coro_factory):
    async with get_async_session_factory()() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    for bid in brands:
        try:
            await coro_factory(bid)
        except Exception:
            logger.exception("live_execution_phase2 task failed for brand %s", bid)


async def _do_recompute_event_ingestions(brand_id: uuid.UUID) -> None:
    from apps.api.services.live_execution_phase2_service import recompute_event_ingestions

    async with get_async_session_factory()() as db:
        await recompute_event_ingestions(db, brand_id)
        await db.commit()


async def _do_process_sequence_triggers(brand_id: uuid.UUID) -> None:
    from apps.api.services.live_execution_phase2_service import (
        process_sequence_triggers as run_process_sequence_triggers,
    )

    async with get_async_session_factory()() as db:
        await run_process_sequence_triggers(db, brand_id)
        await db.commit()


async def _do_run_payment_sync(brand_id: uuid.UUID) -> None:
    from apps.api.services.live_execution_phase2_service import run_payment_sync

    async with get_async_session_factory()() as db:
        await run_payment_sync(db, brand_id, provider="stripe")
        await db.commit()


async def _do_run_analytics_sync(brand_id: uuid.UUID) -> None:
    from apps.api.services.live_execution_phase2_service import run_analytics_sync

    async with get_async_session_factory()() as db:
        await run_analytics_sync(db, brand_id, source="buffer")
        await db.commit()


async def _do_run_ad_import(brand_id: uuid.UUID) -> None:
    from apps.api.services.live_execution_phase2_service import run_ad_import

    async with get_async_session_factory()() as db:
        await run_ad_import(db, brand_id, platform="meta_ads")
        await db.commit()


async def _do_recompute_buffer_execution_truth(brand_id: uuid.UUID) -> None:
    from apps.api.services.live_execution_phase2_service import recompute_buffer_execution_truth

    async with get_async_session_factory()() as db:
        await recompute_buffer_execution_truth(db, brand_id)
        await db.commit()


async def _do_detect_stale_buffer_jobs(brand_id: uuid.UUID) -> None:
    from datetime import datetime, timezone

    from sqlalchemy import select

    from packages.db.models.buffer_distribution import BufferPublishJob
    from packages.scoring.live_execution_phase2_engine import detect_stale_jobs

    async with get_async_session_factory()() as db:
        q = select(BufferPublishJob).where(
            BufferPublishJob.brand_id == brand_id,
            BufferPublishJob.is_active.is_(True),
            BufferPublishJob.status.in_(["pending", "processing", "queued", "submitted"]),
        )
        jobs = list((await db.execute(q)).scalars().all())
        now = datetime.now(timezone.utc)
        for job in jobs:
            hours = 0.0
            if job.created_at:
                dt = job.created_at if job.created_at.tzinfo else job.created_at.replace(tzinfo=timezone.utc)
                hours = (now - dt).total_seconds() / 3600.0
            result = detect_stale_jobs(hours, job.status or "unknown")
            if result["is_stale"]:
                job.status = "stale"
        await db.commit()


async def _do_recompute_buffer_capabilities(brand_id: uuid.UUID) -> None:
    from apps.api.services.live_execution_phase2_service import recompute_buffer_capabilities

    async with get_async_session_factory()() as db:
        await recompute_buffer_capabilities(db, brand_id)
        await db.commit()


@shared_task(name="workers.live_execution_phase2_worker.tasks.process_webhook_events", base=TrackedTask)
def process_webhook_events():
    run_async(_run_all_brands(_do_recompute_event_ingestions))
    return "done"


@shared_task(name="workers.live_execution_phase2_worker.tasks.process_sequence_triggers", base=TrackedTask)
def process_sequence_triggers():
    run_async(_run_all_brands(_do_process_sequence_triggers))
    return "done"


@shared_task(name="workers.live_execution_phase2_worker.tasks.run_payment_connector_sync", base=TrackedTask)
def run_payment_connector_sync():
    run_async(_run_all_brands(_do_run_payment_sync))
    return "done"


@shared_task(name="workers.live_execution_phase2_worker.tasks.run_analytics_auto_pull", base=TrackedTask)
def run_analytics_auto_pull():
    run_async(_run_all_brands(_do_run_analytics_sync))
    return "done"


@shared_task(name="workers.live_execution_phase2_worker.tasks.run_ad_reporting_import", base=TrackedTask)
def run_ad_reporting_import():
    run_async(_run_all_brands(_do_run_ad_import))
    return "done"


@shared_task(name="workers.live_execution_phase2_worker.tasks.recompute_buffer_execution_truth", base=TrackedTask)
def recompute_buffer_execution_truth():
    run_async(_run_all_brands(_do_recompute_buffer_execution_truth))
    return "done"


@shared_task(name="workers.live_execution_phase2_worker.tasks.detect_stale_buffer_jobs", base=TrackedTask)
def detect_stale_buffer_jobs():
    run_async(_run_all_brands(_do_detect_stale_buffer_jobs))
    return "done"


@shared_task(name="workers.live_execution_phase2_worker.tasks.recompute_buffer_capabilities", base=TrackedTask)
def recompute_buffer_capabilities():
    run_async(_run_all_brands(_do_recompute_buffer_capabilities))
    return "done"
