"""Niche research worker — recompute niche scores with trend signals for all brands."""

from __future__ import annotations

import logging

from workers.base_task import TrackedTask
from workers.celery_app import app

logger = logging.getLogger(__name__)


@app.task(base=TrackedTask, bind=True, name="workers.niche_research_worker.tasks.recompute_niche_scores")
def recompute_niche_scores(self) -> dict:
    """Score niches across platforms for every active brand, incorporating trend signals."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from packages.db.models.core import Brand
    from packages.db.session import get_sync_engine
    from packages.scoring.niche_research_engine import rank_niches

    engine = get_sync_engine()
    brands_processed = 0
    total_niches_scored = 0

    with Session(engine) as session:
        brands = session.execute(select(Brand).where(Brand.is_active.is_(True))).scalars().all()

        for brand in brands:
            try:
                trend_signals: list[dict] = []
                if brand.brand_guidelines and isinstance(brand.brand_guidelines, dict):
                    trend_signals = brand.brand_guidelines.get("trend_signals", [])

                ranked = rank_niches(
                    platforms=["youtube", "tiktok", "instagram", "x", "linkedin"],
                    trend_signals=trend_signals,
                    top_n=15,
                )

                meta = dict(brand.brand_guidelines or {})
                meta["niche_scores"] = ranked
                meta["niche_scores_count"] = len(ranked)
                brand.brand_guidelines = meta
                total_niches_scored += len(ranked)
                brands_processed += 1

                logger.info(
                    "Niche scores computed for brand %s: top=%s score=%.4f",
                    brand.id,
                    ranked[0]["niche"] if ranked else "none",
                    ranked[0]["composite_score"] if ranked else 0,
                )
            except Exception:
                logger.exception("Error computing niche scores for brand %s", brand.id)

        session.commit()

    return {
        "status": "completed",
        "brands_processed": brands_processed,
        "total_niches_scored": total_niches_scored,
    }
