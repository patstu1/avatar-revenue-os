"""Buffer Distribution Layer — Celery tasks for publish submission and status sync."""
from __future__ import annotations

import uuid

import structlog
from celery import shared_task

from packages.db.session import get_async_session_factory, run_async
from workers.base_task import BaseTask

logger = structlog.get_logger()


async def _all_brand_ids(db) -> list[uuid.UUID]:
    from sqlalchemy import select

    from packages.db.models.core import Brand
    rows = (await db.execute(select(Brand.id).where(Brand.is_active.is_(True)))).all()
    return [r[0] for r in rows]


async def _submit_pending_jobs():
    """Submit all pending Buffer publish jobs to Buffer."""
    from sqlalchemy import select

    from apps.api.services import buffer_distribution_service as svc
    from packages.db.models.buffer_distribution import BufferPublishJob

    async with get_async_session_factory()() as db:
        brand_ids = await _all_brand_ids(db)

    for bid in brand_ids:
        try:
            async with get_async_session_factory()() as db:
                jobs_q = await db.execute(
                    select(BufferPublishJob)
                    .where(
                        BufferPublishJob.brand_id == bid,
                        BufferPublishJob.status == "pending",
                        BufferPublishJob.is_active.is_(True),
                    )
                    .limit(20)
                )
                jobs = jobs_q.scalars().all()
                submitted = 0
                for job in jobs:
                    try:
                        await svc.submit_job_to_buffer(db, job.id)
                        submitted += 1
                    except Exception:
                        logger.exception("buffer.submit_failed", job_id=str(job.id))
                await db.commit()
                if submitted:
                    logger.info("buffer.batch_submit_done", brand_id=str(bid), submitted=submitted)
        except Exception:
            logger.exception("buffer.submit_batch_failed", brand_id=str(bid))


async def _sync_buffer_statuses():
    """Sync Buffer post statuses + ingest real external links from Buffer GraphQL API.

    Two-step:
      1. Run per-brand status sync (legacy compatibility)
      2. Run per-org sync_published_posts_from_buffer to ingest external platform URLs
         into publish_jobs and content_items
    """
    from sqlalchemy import select

    from apps.api.services import buffer_distribution_service as svc
    from packages.db.models.core import Organization

    async with get_async_session_factory()() as db:
        brand_ids = await _all_brand_ids(db)
        org_ids_q = await db.execute(
            select(Organization.id).where(Organization.is_active.is_(True))
        )
        org_ids = [r[0] for r in org_ids_q.all()]

    # Step 1: per-brand status sync (legacy)
    for bid in brand_ids:
        try:
            async with get_async_session_factory()() as db:
                result = await svc.run_status_sync(db, bid)
                await db.commit()
                logger.info("buffer.status_sync_done", brand_id=str(bid), **result)
        except Exception:
            logger.exception("buffer.status_sync_failed", brand_id=str(bid))

    # Step 2: per-org Buffer post ingestion (real URLs)
    for oid in org_ids:
        try:
            async with get_async_session_factory()() as db:
                result = await svc.sync_published_posts_from_buffer(db, oid)
                await db.commit()
                logger.info("buffer.post_ingest_done", org_id=str(oid), **result)
        except Exception:
            logger.exception("buffer.post_ingest_failed", org_id=str(oid))


@shared_task(base=BaseTask, name="workers.buffer_worker.tasks.submit_pending_jobs")
def submit_pending_jobs():
    run_async(_submit_pending_jobs())


@shared_task(base=BaseTask, name="workers.buffer_worker.tasks.sync_buffer_statuses")
def sync_buffer_statuses():
    run_async(_sync_buffer_statuses())
