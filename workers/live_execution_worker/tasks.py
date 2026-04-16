"""Celery tasks for Live Execution Closure Phase 1."""
from __future__ import annotations

import asyncio
import uuid

from celery import shared_task
from sqlalchemy import select

from workers.base_task import TrackedTask

from packages.db.session import AsyncSessionLocal, run_async


async def _sync_analytics(brand_id: uuid.UUID) -> None:
    from apps.api.services.live_execution_service import recompute_analytics
    async with AsyncSessionLocal() as db:
        await recompute_analytics(db, brand_id)
        await db.commit()


async def _sync_experiment_truth(brand_id: uuid.UUID) -> None:
    from apps.api.services.live_execution_service import recompute_experiment_truth
    async with AsyncSessionLocal() as db:
        await recompute_experiment_truth(db, brand_id)
        await db.commit()


async def _run_crm_sync(brand_id: uuid.UUID) -> None:
    from apps.api.services.live_execution_service import run_crm_sync
    async with AsyncSessionLocal() as db:
        await run_crm_sync(db, brand_id)
        await db.commit()


async def _execute_emails(brand_id: uuid.UUID) -> None:
    from apps.api.services.live_execution_service import execute_pending_emails
    async with AsyncSessionLocal() as db:
        await execute_pending_emails(db, brand_id)
        await db.commit()


async def _execute_sms(brand_id: uuid.UUID) -> None:
    from apps.api.services.live_execution_service import execute_pending_sms
    async with AsyncSessionLocal() as db:
        await execute_pending_sms(db, brand_id)
        await db.commit()


async def _recompute_blockers(brand_id: uuid.UUID) -> None:
    from apps.api.services.live_execution_service import recompute_messaging_blockers
    async with AsyncSessionLocal() as db:
        await recompute_messaging_blockers(db, brand_id)
        await db.commit()


async def _run_all_brands(coro_factory):
    from packages.db.models.core import Brand
    async with AsyncSessionLocal() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    for bid in brands:
        await coro_factory(bid)


@shared_task(name="workers.live_execution_worker.tasks.sync_analytics", base=TrackedTask)
def sync_analytics() -> str:
    run_async(_run_all_brands(_sync_analytics))
    return "analytics-sync-done"


@shared_task(name="workers.live_execution_worker.tasks.sync_experiment_truth", base=TrackedTask)
def sync_experiment_truth() -> str:
    run_async(_run_all_brands(_sync_experiment_truth))
    return "experiment-truth-sync-done"


@shared_task(name="workers.live_execution_worker.tasks.run_crm_sync", base=TrackedTask)
def run_crm_sync() -> str:
    run_async(_run_all_brands(_run_crm_sync))
    return "crm-sync-done"


@shared_task(name="workers.live_execution_worker.tasks.execute_emails", base=TrackedTask)
def execute_emails() -> str:
    run_async(_run_all_brands(_execute_emails))
    return "email-execution-done"


@shared_task(name="workers.live_execution_worker.tasks.execute_sms", base=TrackedTask)
def execute_sms() -> str:
    run_async(_run_all_brands(_execute_sms))
    return "sms-execution-done"


@shared_task(name="workers.live_execution_worker.tasks.recompute_messaging_blockers", base=TrackedTask)
def recompute_messaging_blockers() -> str:
    run_async(_run_all_brands(_recompute_blockers))
    return "messaging-blockers-done"
