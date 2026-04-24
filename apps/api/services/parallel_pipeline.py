"""Parallel Content Pipeline — processes multiple briefs concurrently.

Replaces sequential one-brief-at-a-time processing with fan-out:
- Accept N briefs
- Generate scripts in parallel (up to concurrency limit)
- Track all jobs
- Return aggregated results

This is the mass-scale content velocity engine.
"""

from __future__ import annotations

import asyncio
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.content import ContentBrief

logger = structlog.get_logger()

MAX_CONCURRENT = 10  # Max parallel generation tasks


async def generate_batch(
    db: AsyncSession,
    brand_id: uuid.UUID,
    *,
    brief_ids: list[uuid.UUID] | None = None,
    max_concurrent: int = MAX_CONCURRENT,
) -> dict:
    """Generate scripts for multiple briefs in parallel.

    If brief_ids is None, processes all draft briefs for the brand.
    """
    if brief_ids:
        briefs_q = await db.execute(
            select(ContentBrief).where(
                ContentBrief.id.in_(brief_ids),
                ContentBrief.brand_id == brand_id,
            )
        )
    else:
        briefs_q = await db.execute(
            select(ContentBrief)
            .where(
                ContentBrief.brand_id == brand_id,
                ContentBrief.status == "draft",
            )
            .limit(max_concurrent)
        )

    briefs = briefs_q.scalars().all()

    if not briefs:
        return {"processed": 0, "message": "No draft briefs to process"}

    # Process in parallel chunks
    results = []
    for i in range(0, len(briefs), max_concurrent):
        chunk = briefs[i : i + max_concurrent]
        chunk_results = await asyncio.gather(
            *[_generate_single(db, brief) for brief in chunk],
            return_exceptions=True,
        )
        for brief, result in zip(chunk, chunk_results):
            if isinstance(result, Exception):
                results.append(
                    {
                        "brief_id": str(brief.id),
                        "title": brief.title[:60],
                        "status": "failed",
                        "error": str(result)[:200],
                    }
                )
            else:
                results.append(result)

    succeeded = len([r for r in results if r.get("status") == "generated"])
    failed = len([r for r in results if r.get("status") == "failed"])

    return {
        "processed": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "max_concurrent": max_concurrent,
        "results": results,
    }


async def _generate_single(db: AsyncSession, brief: ContentBrief) -> dict:
    """Generate a single script. Called in parallel by generate_batch."""
    try:
        from apps.api.services.content_lifecycle import generate_script_with_events

        script = await generate_script_with_events(db, brief.id)
        return {
            "brief_id": str(brief.id),
            "title": brief.title[:60],
            "status": "generated",
            "script_id": str(script.id),
            "word_count": script.word_count,
            "model": script.generation_model,
        }
    except Exception as e:
        return {
            "brief_id": str(brief.id),
            "title": brief.title[:60],
            "status": "failed",
            "error": str(e)[:200],
        }


async def publish_batch(
    db: AsyncSession,
    brand_id: uuid.UUID,
    *,
    content_ids: list[uuid.UUID],
    creator_account_id: uuid.UUID,
    platform: str,
    max_concurrent: int = MAX_CONCURRENT,
) -> dict:
    """Publish multiple content items in parallel."""

    results = []
    for i in range(0, len(content_ids), max_concurrent):
        chunk = content_ids[i : i + max_concurrent]
        chunk_results = await asyncio.gather(
            *[_publish_single(db, cid, creator_account_id, platform) for cid in chunk],
            return_exceptions=True,
        )
        for cid, result in zip(chunk, chunk_results):
            if isinstance(result, Exception):
                results.append({"content_id": str(cid), "status": "failed", "error": str(result)[:200]})
            else:
                results.append(result)

    return {
        "processed": len(results),
        "succeeded": len([r for r in results if r.get("status") != "failed"]),
        "failed": len([r for r in results if r.get("status") == "failed"]),
        "results": results,
    }


async def _publish_single(db, content_id, creator_account_id, platform) -> dict:
    try:
        from apps.api.services.content_lifecycle import publish_with_events

        result = await publish_with_events(db, content_id, creator_account_id, platform)
        return {"content_id": str(content_id), "status": "publishing", "job_id": str(result["job"].id)}
    except Exception as e:
        return {"content_id": str(content_id), "status": "failed", "error": str(e)[:200]}
