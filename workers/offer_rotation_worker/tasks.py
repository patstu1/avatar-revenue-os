"""Offer rotation worker — detect fatigued offers, auto-swap to best alternative, track trends."""

from __future__ import annotations

import logging

from workers.base_task import TrackedTask
from workers.celery_app import app

logger = logging.getLogger(__name__)

FATIGUE_CONVERSION_THRESHOLD = 0.015
FATIGUE_EPC_THRESHOLD = 0.10
CVR_DECLINE_PCT = 0.30


@app.task(base=TrackedTask, bind=True, name="workers.offer_rotation_worker.tasks.rotate_offers")
def rotate_offers(self) -> dict:
    """Detect fatigued offers and auto-swap to the best available alternative."""
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from packages.db.enums import MonetizationMethod
    from packages.db.models.content import ContentBrief
    from packages.db.models.core import Brand
    from packages.db.models.offers import Offer
    from packages.db.session import get_sync_engine
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
                offers = (
                    session.execute(
                        select(Offer).where(
                            Offer.brand_id == brand.id,
                            Offer.is_active.is_(True),
                        )
                    )
                    .scalars()
                    .all()
                )

                active_offers = [o for o in offers if o.monetization_method == MonetizationMethod.AFFILIATE]

                for offer in active_offers:
                    is_fatigued = False
                    reason = ""

                    if offer.conversion_rate < FATIGUE_CONVERSION_THRESHOLD and offer.epc < FATIGUE_EPC_THRESHOLD:
                        is_fatigued = True
                        reason = f"Low performance: CVR={offer.conversion_rate:.4f}, EPC={offer.epc:.2f}"

                    brief_count = (
                        session.execute(
                            select(func.count())
                            .select_from(ContentBrief)
                            .where(
                                ContentBrief.offer_id == offer.id,
                                ContentBrief.status.in_(
                                    ["draft", "ready", "script_generated", "approved", "published"]
                                ),
                            )
                        ).scalar()
                        or 0
                    )
                    if brief_count > 20 and offer.conversion_rate < 0.02:
                        is_fatigued = True
                        reason = f"Overused ({brief_count} briefs) with low CVR={offer.conversion_rate:.4f}"

                    if is_fatigued:
                        logger.warning("OFFER FATIGUED: %s (%s) — %s", offer.name, offer.id, reason)

                        niche_products = get_all_products_for_niche(niche)
                        replacement = None
                        for p in niche_products:
                            existing = session.execute(
                                select(Offer).where(
                                    Offer.brand_id == brand.id, Offer.name == p["name"], Offer.is_active.is_(True)
                                )
                            ).scalar_one_or_none()
                            if not existing and p.get("payout", 0) > offer.payout_amount * 0.5:
                                replacement = p
                                break

                        if replacement:
                            new_offer = Offer(
                                brand_id=brand.id,
                                name=replacement["name"],
                                monetization_method="affiliate",
                                payout_amount=replacement.get("payout", 0),
                                epc=replacement.get("payout", 0) * 0.02,
                                conversion_rate=0.02,
                            )
                            session.add(new_offer)
                            session.flush()

                            pending_briefs = (
                                session.execute(
                                    select(ContentBrief).where(
                                        ContentBrief.offer_id == offer.id,
                                        ContentBrief.status.in_(["draft", "ready"]),
                                    )
                                )
                                .scalars()
                                .all()
                            )
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
