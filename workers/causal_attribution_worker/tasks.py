"""Causal Attribution workers.

Two entry points:
  1. recompute_causal_attribution: sweep all brands (6-hour scheduled safety net)
  2. attribute_revenue_for_content_item: per-item fast path (event-driven, triggered
     by analytics ingestion ~5-6 min after publish)
"""
import asyncio
import logging
import uuid

from celery import shared_task
from sqlalchemy import select

from packages.db.session import async_session_factory
from workers.base_task import TrackedTask
from packages.db.models.core import Brand

logger = logging.getLogger(__name__)


async def _run():
    from apps.api.services.causal_attribution_service import recompute_attribution
    async with async_session_factory() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    c = 0
    for bid in brands:
        try:
            async with async_session_factory() as db:
                await recompute_attribution(db, bid)
                await db.commit()
                c += 1
        except Exception:
            logger.exception("causal attribution failed %s", bid)
    return c


@shared_task(name="workers.causal_attribution_worker.tasks.recompute_causal_attribution", base=TrackedTask)
def recompute_causal_attribution():
    """Sweep all brands — 6-hour safety net."""
    return {"status": "completed", "brands": asyncio.run(_run())}


@shared_task(name="workers.causal_attribution_worker.tasks.attribute_revenue_for_content_item", base=TrackedTask)
def attribute_revenue_for_content_item(content_item_id: str):
    """Per-item fast path: attribute revenue for a single content item.

    Called ~6 min after publish (5 min delay to metrics, 1 min delay to here).
    Runs the attribution service scoped to the brand of the content item.
    This is the fast path — the 6-hour sweep handles anything this misses.
    """
    return asyncio.run(_attribute_single_item(content_item_id))


async def _attribute_single_item(content_item_id_str: str):
    from apps.api.services.causal_attribution_service import recompute_attribution
    from packages.db.models.content import ContentItem

    cid = uuid.UUID(content_item_id_str)

    async with async_session_factory() as db:
        item = (await db.execute(
            select(ContentItem).where(ContentItem.id == cid)
        )).scalar_one_or_none()
        if not item:
            return {"skipped": True, "reason": "content_item_not_found"}

        brand_id = item.brand_id

    try:
        async with async_session_factory() as db:
            await recompute_attribution(db, brand_id)
            await db.commit()
        return {"status": "completed", "brand_id": str(brand_id), "content_item_id": content_item_id_str}
    except Exception as e:
        logger.exception("per_item_attribution_failed content_id=%s", content_item_id_str)
        return {"status": "failed", "error": str(e)[:200]}
