"""Offer rotation worker — detect fatigued offers, auto-swap to best alternative, track trends."""
from __future__ import annotations

import logging
import uuid

from workers.celery_app import app
from workers.base_task import TrackedTask

logger = logging.getLogger(__name__)

FATIGUE_CONVERSION_THRESHOLD = 0.015
FATIGUE_EPC_THRESHOLD = 0.10
CVR_DECLINE_PCT = 0.30


@app.task(base=TrackedTask, bind=True, name="workers.offer_rotation_worker.tasks.rotate_offers")
def rotate_offers(self) -> dict:
    """Detect fatigued offers and auto-swap to the best available alternative."""
    from sqlalchemy.orm import Session
    from sqlalchemy import select, func
    from packages.db.session import get_sync_engine
    from packages.db.models.core import Brand
    from packages.db.models.offers import Offer
    from packages.db.models.content import ContentBrief
    from packages.db.enums import MonetizationMethod
    from packages.scoring.affiliate_link_engine import get_all_products_for_niche

    engine = get_sync_engine()
    brands_checked = 0
    offers_rotated = 0
    offers_deactivated = 0

    with Session(engine) as session:
        brands = session.execute(select(Brand).where(Brand.is_active.is_(True))).scalars().all()

        for brand in brands:
            try:
                niche = brand.niche or "general"
                offers = session.execute(
                    select(Offer).where(
                        Offer.brand_id == brand.id,
                        Offer.is_active.is_(True),
                    )
                ).scalars().all()

                active_offers = [o for o in offers if o.monetization_method == MonetizationMethod.AFFILIATE]

                for offer in active_offers:
                    is_fatigued = False
                    reason = ""

                    if offer.conversion_rate < FATIGUE_CONVERSION_THRESHOLD and offer.epc < FATIGUE_EPC_THRESHOLD:
                        is_fatigued = True
                        reason = f"Low performance: CVR={offer.conversion_rate:.4f}, EPC={offer.epc:.2f}"

                    brief_count = session.execute(
                        select(func.count()).select_from(ContentBrief).where(
                            ContentBrief.offer_id == offer.id,
                            ContentBrief.status.in_(["draft", "ready", "script_generated", "approved", "published"]),
                        )
                    ).scalar() or 0
                    if brief_count > 20 and offer.conversion_rate < 0.02:
                        is_fatigued = True
                        reason = f"Overused ({brief_count} briefs) with low CVR={offer.conversion_rate:.4f}"

                    if is_fatigued:
                        logger.warning("OFFER FATIGUED: %s (%s) — %s", offer.name, offer.id, reason)

                        niche_products = get_all_products_for_niche(niche)
                        replacement = None
                        for p in niche_products:
                            existing = session.execute(
                                select(Offer).where(Offer.brand_id == brand.id, Offer.name == p["name"], Offer.is_active.is_(True))
                            ).scalar_one_or_none()
                            if not existing and p.get("payout", 0) > offer.payout_amount * 0.5:
                                replacement = p
                                break

                        if replacement:
                            new_offer = Offer(
                                brand_id=brand.id, name=replacement["name"],
                                monetization_method="affiliate",
                                payout_amount=replacement.get("payout", 0),
                                epc=replacement.get("payout", 0) * 0.02,
                                conversion_rate=0.02,
                            )
                            session.add(new_offer)
                            session.flush()

                            pending_briefs = session.execute(
                                select(ContentBrief).where(
                                    ContentBrief.offer_id == offer.id,
                                    ContentBrief.status.in_(["draft", "ready"]),
                                )
                            ).scalars().all()
                            for brief in pending_briefs:
                                brief.offer_id = new_offer.id

                            offer.is_active = False
                            offers_rotated += 1
                            logger.info("ROTATED: %s -> %s (brand: %s)", offer.name, replacement["name"], brand.name)
                        else:
                            offer.is_active = False
                            offers_deactivated += 1
                            logger.info("DEACTIVATED (no replacement): %s (brand: %s)", offer.name, brand.name)

                brands_checked += 1
            except Exception:
                logger.exception("Error rotating offers for brand %s", brand.id)

        session.commit()

    return {
        "status": "completed",
        "brands_checked": brands_checked,
        "offers_rotated": offers_rotated,
        "offers_deactivated": offers_deactivated,
    }


# ── Performance-Based Weight Auto-Adjustment ─────────────────────────

# Weight bounds to prevent runaway oscillation
MIN_WEIGHT = 0.1
MAX_WEIGHT = 5.0
WEIGHT_ADJUST_RATE = 0.15  # 15% adjustment per cycle max


@app.task(base=TrackedTask, bind=True, name="workers.offer_rotation_worker.tasks.adjust_offer_weights")
def adjust_offer_weights(self) -> dict:
    """Adjust Offer.rotation_weight based on real performance data.

    Reads PerformanceMetric (engagement, CTR) and RevenueLedgerEntry (conversions)
    to promote high-performing offers and suppress underperformers.
    Safe bounds prevent oscillation.
    """
    from sqlalchemy.orm import Session
    from sqlalchemy import select, func
    from packages.db.session import get_sync_engine
    from packages.db.models.core import Brand
    from packages.db.models.offers import Offer
    from packages.db.models.publishing import PerformanceMetric, PublishJob
    from packages.db.enums import JobStatus
    from datetime import datetime, timedelta, timezone

    engine = get_sync_engine()
    adjusted_up = 0
    adjusted_down = 0
    unchanged = 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=14)

    with Session(engine) as session:
        brands = session.execute(select(Brand).where(Brand.is_active.is_(True))).scalars().all()

        for brand in brands:
            try:
                offers = session.execute(
                    select(Offer).where(Offer.brand_id == brand.id, Offer.is_active.is_(True))
                ).scalars().all()

                if len(offers) < 2:
                    continue  # Need at least 2 offers for relative comparison

                # Compute per-offer performance scores
                offer_scores: dict[uuid.UUID, float] = {}
                for offer in offers:
                    # Get content items linked to this offer that were published recently
                    jobs = session.execute(
                        select(PublishJob).where(
                            PublishJob.brand_id == brand.id,
                            PublishJob.status == JobStatus.COMPLETED,
                            PublishJob.published_at >= cutoff,
                        )
                    ).scalars().all()

                    # Filter to jobs for content items linked to this offer
                    from packages.db.models.content import ContentItem
                    content_with_offer = session.execute(
                        select(ContentItem.id).where(
                            ContentItem.brand_id == brand.id,
                            ContentItem.offer_id == offer.id,
                        )
                    ).scalars().all()
                    offer_content_ids = set(content_with_offer)

                    relevant_jobs = [j for j in jobs if j.content_item_id in offer_content_ids]
                    if not relevant_jobs:
                        offer_scores[offer.id] = 0.0
                        continue

                    # Get performance metrics for these content items
                    content_ids = [j.content_item_id for j in relevant_jobs]
                    metrics = session.execute(
                        select(PerformanceMetric).where(
                            PerformanceMetric.content_item_id.in_(content_ids),
                            PerformanceMetric.measured_at >= cutoff,
                        )
                    ).scalars().all()

                    if not metrics:
                        offer_scores[offer.id] = 0.0
                        continue

                    # Score: weighted combination of engagement + CTR + revenue
                    total_views = sum(m.views for m in metrics)
                    total_engagement = sum(m.likes + m.comments + m.shares for m in metrics)
                    total_revenue = sum(m.revenue for m in metrics)
                    avg_engagement_rate = (total_engagement / total_views) if total_views > 0 else 0

                    # Composite score
                    score = (
                        avg_engagement_rate * 0.3 +
                        (total_revenue / max(len(relevant_jobs), 1)) * 0.5 +
                        (total_views / max(len(relevant_jobs), 1)) / 10000 * 0.2
                    )
                    offer_scores[offer.id] = score

                # Adjust weights relative to mean performance
                scores = [s for s in offer_scores.values() if s > 0]
                if not scores:
                    continue
                mean_score = sum(scores) / len(scores)
                if mean_score <= 0:
                    continue

                for offer in offers:
                    score = offer_scores.get(offer.id, 0)
                    if score <= 0:
                        unchanged += 1
                        continue

                    current_weight = offer.rotation_weight or 1.0

                    if score > mean_score * 1.2:
                        # Winner: increase weight (capped)
                        new_weight = min(MAX_WEIGHT, current_weight * (1 + WEIGHT_ADJUST_RATE))
                        offer.rotation_weight = round(new_weight, 3)
                        adjusted_up += 1
                        logger.info("offer_weight.promoted",
                                    offer=offer.name, old=current_weight, new=new_weight,
                                    score=round(score, 4), mean=round(mean_score, 4))
                    elif score < mean_score * 0.6:
                        # Loser: decrease weight (floored)
                        new_weight = max(MIN_WEIGHT, current_weight * (1 - WEIGHT_ADJUST_RATE))
                        offer.rotation_weight = round(new_weight, 3)
                        adjusted_down += 1
                        logger.info("offer_weight.suppressed",
                                    offer=offer.name, old=current_weight, new=new_weight,
                                    score=round(score, 4), mean=round(mean_score, 4))
                    else:
                        unchanged += 1

            except Exception:
                logger.exception("Error adjusting weights for brand %s", brand.id)

        session.commit()

    return {
        "status": "completed",
        "promoted": adjusted_up,
        "suppressed": adjusted_down,
        "unchanged": unchanged,
    }
