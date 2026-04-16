"""Celery tasks for Creator Revenue Avenues (all phases)."""
from __future__ import annotations

import asyncio
import logging
import uuid

from celery import shared_task
from sqlalchemy import select

from packages.db.session import async_session_factory, run_async
from workers.base_task import TrackedTask

logger = logging.getLogger(__name__)


async def _run_all_brands(coro_factory):
    from packages.db.models.core import Brand
    async with async_session_factory() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    for bid in brands:
        try:
            await coro_factory(bid)
        except Exception:
            logger.exception("creator_revenue task failed for brand %s", bid)


async def _recompute_opps(brand_id: uuid.UUID) -> None:
    from apps.api.services.creator_revenue_service import recompute_opportunities
    async with async_session_factory() as db:
        await recompute_opportunities(db, brand_id)
        await db.commit()


async def _recompute_ugc(brand_id: uuid.UUID) -> None:
    from apps.api.services.creator_revenue_service import recompute_ugc_services
    async with async_session_factory() as db:
        await recompute_ugc_services(db, brand_id)
        await db.commit()


async def _recompute_consulting(brand_id: uuid.UUID) -> None:
    from apps.api.services.creator_revenue_service import recompute_service_consulting
    async with async_session_factory() as db:
        await recompute_service_consulting(db, brand_id)
        await db.commit()


async def _recompute_premium(brand_id: uuid.UUID) -> None:
    from apps.api.services.creator_revenue_service import recompute_premium_access
    async with async_session_factory() as db:
        await recompute_premium_access(db, brand_id)
        await db.commit()


async def _recompute_licensing(brand_id: uuid.UUID) -> None:
    from apps.api.services.creator_revenue_service import recompute_licensing
    async with async_session_factory() as db:
        await recompute_licensing(db, brand_id)
        await db.commit()


async def _recompute_syndication(brand_id: uuid.UUID) -> None:
    from apps.api.services.creator_revenue_service import recompute_syndication
    async with async_session_factory() as db:
        await recompute_syndication(db, brand_id)
        await db.commit()


async def _recompute_data_products(brand_id: uuid.UUID) -> None:
    from apps.api.services.creator_revenue_service import recompute_data_products
    async with async_session_factory() as db:
        await recompute_data_products(db, brand_id)
        await db.commit()


async def _recompute_merch(brand_id: uuid.UUID) -> None:
    from apps.api.services.creator_revenue_service import recompute_merch
    async with async_session_factory() as db:
        await recompute_merch(db, brand_id)
        await db.commit()


async def _recompute_live_events(brand_id: uuid.UUID) -> None:
    from apps.api.services.creator_revenue_service import recompute_live_events
    async with async_session_factory() as db:
        await recompute_live_events(db, brand_id)
        await db.commit()


async def _recompute_affiliate_program(brand_id: uuid.UUID) -> None:
    from apps.api.services.creator_revenue_service import recompute_owned_affiliate_program
    async with async_session_factory() as db:
        await recompute_owned_affiliate_program(db, brand_id)
        await db.commit()


async def _recompute_hub(brand_id: uuid.UUID) -> None:
    from apps.api.services.creator_revenue_service import recompute_hub
    async with async_session_factory() as db:
        await recompute_hub(db, brand_id)
        await db.commit()


async def _recompute_blockers(brand_id: uuid.UUID) -> None:
    from apps.api.services.creator_revenue_service import recompute_blockers
    async with async_session_factory() as db:
        await recompute_blockers(db, brand_id)
        await db.commit()


@shared_task(name="workers.creator_revenue_worker.tasks.recompute_creator_revenue", base=TrackedTask)
def recompute_creator_revenue() -> str:
    run_async(_run_all_brands(_recompute_opps))
    return "creator-revenue-opps-done"


@shared_task(name="workers.creator_revenue_worker.tasks.recompute_ugc_services", base=TrackedTask)
def recompute_ugc_services() -> str:
    run_async(_run_all_brands(_recompute_ugc))
    return "ugc-services-done"


@shared_task(name="workers.creator_revenue_worker.tasks.recompute_service_consulting", base=TrackedTask)
def recompute_service_consulting() -> str:
    run_async(_run_all_brands(_recompute_consulting))
    return "service-consulting-done"


@shared_task(name="workers.creator_revenue_worker.tasks.recompute_premium_access", base=TrackedTask)
def recompute_premium_access() -> str:
    run_async(_run_all_brands(_recompute_premium))
    return "premium-access-done"


@shared_task(name="workers.creator_revenue_worker.tasks.recompute_licensing", base=TrackedTask)
def recompute_licensing_task() -> str:
    run_async(_run_all_brands(_recompute_licensing))
    return "licensing-done"


@shared_task(name="workers.creator_revenue_worker.tasks.recompute_syndication", base=TrackedTask)
def recompute_syndication_task() -> str:
    run_async(_run_all_brands(_recompute_syndication))
    return "syndication-done"


@shared_task(name="workers.creator_revenue_worker.tasks.recompute_data_products", base=TrackedTask)
def recompute_data_products_task() -> str:
    run_async(_run_all_brands(_recompute_data_products))
    return "data-products-done"


@shared_task(name="workers.creator_revenue_worker.tasks.recompute_merch", base=TrackedTask)
def recompute_merch_task() -> str:
    run_async(_run_all_brands(_recompute_merch))
    return "merch-done"


@shared_task(name="workers.creator_revenue_worker.tasks.recompute_live_events", base=TrackedTask)
def recompute_live_events_task() -> str:
    run_async(_run_all_brands(_recompute_live_events))
    return "live-events-done"


@shared_task(name="workers.creator_revenue_worker.tasks.recompute_affiliate_program", base=TrackedTask)
def recompute_affiliate_program_task() -> str:
    run_async(_run_all_brands(_recompute_affiliate_program))
    return "affiliate-program-done"


@shared_task(name="workers.creator_revenue_worker.tasks.recompute_creator_revenue_hub", base=TrackedTask)
def recompute_creator_revenue_hub() -> str:
    run_async(_run_all_brands(_recompute_hub))
    return "creator-revenue-hub-done"


@shared_task(name="workers.creator_revenue_worker.tasks.recompute_creator_revenue_blockers", base=TrackedTask)
def recompute_creator_revenue_blockers() -> str:
    run_async(_run_all_brands(_recompute_blockers))
    return "creator-revenue-blockers-done"
