"""Measured-Data Cascade: scheduled ingestion → offer learning → downstream recomputes.

Runs the full closed loop:
1. Performance metrics already ingested by analytics_worker (ingest_performance)
2. Offer economics updated from measured data (offer_learning_service)
3. Downstream intelligence recomputed with fresh data:
   - scale engine
   - expansion advisor
   - content form recommendations
   - gatekeeper
"""
from __future__ import annotations

import asyncio
import logging

from celery import shared_task
from sqlalchemy import select

from packages.db.session import async_session_factory
from packages.db.models.core import Brand

logger = logging.getLogger(__name__)


async def _cascade_for_brand(brand_id):
    """Run the full measured-data cascade for a single brand."""
    results = {}

    try:
        from apps.api.services.offer_learning_service import run_offer_learning
        async with async_session_factory() as db:
            r = await run_offer_learning(db, brand_id)
            await db.commit()
            results["offer_learning"] = r
    except Exception as e:
        logger.exception("cascade.offer_learning failed for %s", brand_id)
        results["offer_learning"] = {"error": str(e)}

    try:
        from apps.api.services.scale_service import recompute_scale_recommendations
        async with async_session_factory() as db:
            r = await recompute_scale_recommendations(db, brand_id)
            await db.commit()
            results["scale_engine"] = {"status": "completed"}
    except Exception as e:
        logger.exception("cascade.scale_engine failed for %s", brand_id)
        results["scale_engine"] = {"error": str(e)}

    try:
        from apps.api.services.expansion_advisor_service import recompute_advisory
        async with async_session_factory() as db:
            r = await recompute_advisory(db, brand_id)
            await db.commit()
            results["expansion_advisor"] = r
    except Exception as e:
        logger.exception("cascade.expansion_advisor failed for %s", brand_id)
        results["expansion_advisor"] = {"error": str(e)}

    try:
        from apps.api.services.content_form_service import recompute_recommendations
        async with async_session_factory() as db:
            r = await recompute_recommendations(db, brand_id)
            await db.commit()
            results["content_forms"] = r
    except Exception as e:
        logger.exception("cascade.content_forms failed for %s", brand_id)
        results["content_forms"] = {"error": str(e)}

    return results


async def _run_cascade():
    async with async_session_factory() as db:
        brand_ids = [r[0] for r in (await db.execute(select(Brand.id).where(Brand.is_active.is_(True)))).all()]

    all_results = {}
    for bid in brand_ids:
        try:
            all_results[str(bid)] = await _cascade_for_brand(bid)
        except Exception:
            logger.exception("cascade.brand_failed %s", bid)
            all_results[str(bid)] = {"error": "cascade failed"}

    return {"brands_processed": len(brand_ids), "results": all_results}


@shared_task(name="workers.publishing_worker.tasks.run_measured_data_cascade")
def run_measured_data_cascade():
    return asyncio.run(_run_cascade())
