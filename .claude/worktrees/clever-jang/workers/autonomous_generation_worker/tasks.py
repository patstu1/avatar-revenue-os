"""Autonomous Content Generation Worker.

Runs on schedule. Finds briefs in 'draft' or 'ready' status, generates real AI content,
scores through quality governor, and auto-approves passing content for publishing.
"""
import asyncio
import logging
import uuid

from sqlalchemy import select, func

from workers.celery_app import app
from workers.base_task import TrackedTask
from packages.db.session import async_session_factory
from packages.db.models.content import ContentBrief
from packages.db.models.core import Brand

logger = logging.getLogger(__name__)


async def _process_pending_briefs():
    """Find all pending briefs and run the full autonomous pipeline."""
    from apps.api.services.content_generation_service import full_pipeline

    async with async_session_factory() as db:
        briefs = list((await db.execute(
            select(ContentBrief).where(
                ContentBrief.status.in_(["draft", "ready", "pending_generation"]),
            ).order_by(ContentBrief.created_at.asc()).limit(20)
        )).scalars().all())

    results = {"processed": 0, "approved": 0, "failed": 0, "quality_blocked": 0}

    for brief in briefs:
        try:
            async with async_session_factory() as db:
                result = await full_pipeline(db, brief.id)
                await db.commit()

                if result.get("success"):
                    results["processed"] += 1
                    if result.get("approved"):
                        results["approved"] += 1
                    else:
                        results["quality_blocked"] += 1
                else:
                    results["failed"] += 1
                    logger.warning("generation failed for brief %s: %s", brief.id, result.get("error"))
        except Exception:
            results["failed"] += 1
            logger.exception("autonomous generation failed for brief %s", brief.id)

    return results


async def _cleanup_stuck_briefs():
    """Reset briefs stuck in 'generating' for over 30 minutes back to 'draft'."""
    from datetime import datetime, timezone, timedelta
    async with async_session_factory() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        stuck = list((await db.execute(
            select(ContentBrief).where(
                ContentBrief.status == "generating",
                ContentBrief.updated_at < cutoff,
            )
        )).scalars().all())
        for brief in stuck:
            brief.status = "draft"
            logger.warning("Reset stuck brief %s from 'generating' back to 'draft'", brief.id)
        await db.commit()
        return len(stuck)


@app.task(base=TrackedTask, bind=True, name="workers.autonomous_generation_worker.tasks.process_pending_briefs")
def process_pending_briefs(self):
    """Celery task with auto-retry: process all pending content briefs through AI generation."""
    asyncio.run(_cleanup_stuck_briefs())
    return asyncio.run(_process_pending_briefs())
