"""Repurposing worker — find long-form content and create short-form derivative briefs."""
from __future__ import annotations

import logging
import uuid

from workers.celery_app import app
from workers.base_task import TrackedTask

logger = logging.getLogger(__name__)

DERIVATIVE_PLATFORMS = ["tiktok", "instagram", "youtube"]


@app.task(base=TrackedTask, bind=True, name="workers.repurposing_worker.tasks.repurpose_content")
def repurpose_content(self) -> dict:
    """Find approved LONG_VIDEO ContentItems and create SHORT_VIDEO briefs on other platforms."""
    from sqlalchemy.orm import Session
    from sqlalchemy import select
    from packages.db.session import get_sync_engine
    from packages.db.models.content import ContentItem, ContentBrief
    from packages.db.enums import ContentType

    engine = get_sync_engine()
    items_found = 0
    briefs_created = 0

    with Session(engine) as session:
        try:
            candidates = session.execute(
                select(ContentItem).where(
                    ContentItem.content_type == ContentType.LONG_VIDEO,
                    ContentItem.status == "approved",
                )
            ).scalars().all()

            for item in candidates:
                items_found += 1
                existing_platform = (item.platform or "youtube").lower()

                for target_platform in DERIVATIVE_PLATFORMS:
                    if target_platform == existing_platform:
                        continue

                    already_exists = session.execute(
                        select(ContentBrief).where(
                            ContentBrief.brand_id == item.brand_id,
                            ContentBrief.target_platform == target_platform,
                            ContentBrief.title.contains(f"[repurpose:{item.id}]"),
                        )
                    ).scalars().first()

                    if already_exists:
                        continue

                    brief = ContentBrief(
                        brand_id=item.brand_id,
                        creator_account_id=item.creator_account_id,
                        offer_id=item.offer_id,
                        title=f"{item.title} [repurpose:{item.id}]",
                        content_type=ContentType.SHORT_VIDEO,
                        target_platform=target_platform,
                        hook=None,
                        angle=f"Short-form derivative of {item.title}",
                        key_points=[],
                        cta_strategy=None,
                        target_duration_seconds=60,
                        tone_guidance=None,
                        brief_metadata={
                            "source_content_item_id": str(item.id),
                            "repurpose_type": "long_to_short",
                            "source_platform": existing_platform,
                        },
                        status="draft",
                    )
                    session.add(brief)
                    briefs_created += 1

                item.status = "repurposed"
                logger.info(
                    "Content item %s marked repurposed, %d derivative briefs queued",
                    item.id, briefs_created,
                )

            session.commit()
        except Exception:
            logger.exception("Error during content repurposing")
            session.rollback()
            return {"status": "error", "message": "repurposing failed"}

    logger.info(
        "Repurposing complete: items_found=%d briefs_created=%d",
        items_found, briefs_created,
    )

    return {
        "status": "completed",
        "items_found": items_found,
        "briefs_created": briefs_created,
    }
