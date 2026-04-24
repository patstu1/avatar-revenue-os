"""Landing Page Service — generate, score, persist, list."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.landing_pages import LandingPage, LandingPageBlock, LandingPageQualityReport, LandingPageVariant
from packages.db.models.objection_mining import ObjectionCluster
from packages.db.models.offers import Offer
from packages.scoring.landing_page_engine import generate_page, generate_variant, score_page_quality


async def recompute_landing_pages(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    offers = list((await db.execute(select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True)))).scalars().all())
    await db.execute(delete(LandingPageQualityReport).where(LandingPageQualityReport.brand_id == brand_id))
    await db.execute(delete(LandingPageBlock).where(LandingPageBlock.page_id.in_(select(LandingPage.id).where(LandingPage.brand_id == brand_id))))
    await db.execute(delete(LandingPageVariant).where(LandingPageVariant.page_id.in_(select(LandingPage.id).where(LandingPage.brand_id == brand_id))))
    await db.execute(delete(LandingPage).where(LandingPage.brand_id == brand_id))

    obj_count = (await db.execute(select(ObjectionCluster).where(ObjectionCluster.brand_id == brand_id, ObjectionCluster.is_active.is_(True)))).scalars().all()
    objection_n = len(obj_count)

    pages_created = 0
    for offer in offers:
        for pt in ("product", "review", "presell"):
            offer_dict = {"name": offer.name, "monetization_method": offer.monetization_method, "epc": float(offer.epc or 0), "conversion_rate": float(offer.conversion_rate or 0)}
            spec = generate_page(offer_dict, page_type=pt)
            page = LandingPage(brand_id=brand_id, offer_id=offer.id, **{k: v for k, v in spec.items() if k not in ("status", "publish_status", "truth_label") or True})
            db.add(page)
            await db.flush()

            for i in range(2):
                vs = generate_variant(spec, i)
                db.add(LandingPageVariant(page_id=page.id, **vs))

            quality = score_page_quality(spec, objection_n, float(offer.conversion_rate or 0))
            db.add(LandingPageQualityReport(page_id=page.id, brand_id=brand_id, **quality))
            pages_created += 1

    await db.flush()
    return {"rows_processed": pages_created, "status": "completed"}


async def list_pages(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(LandingPage).where(LandingPage.brand_id == brand_id, LandingPage.is_active.is_(True)).order_by(LandingPage.created_at.desc()))).scalars().all())

async def list_variants(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(LandingPageVariant).join(LandingPage).where(LandingPage.brand_id == brand_id, LandingPageVariant.is_active.is_(True)))).scalars().all())

async def list_quality(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(LandingPageQualityReport).where(LandingPageQualityReport.brand_id == brand_id, LandingPageQualityReport.is_active.is_(True)))).scalars().all())

async def get_best_page_for_offer(db: AsyncSession, brand_id: uuid.UUID, offer_id: uuid.UUID) -> dict[str, Any]:
    page = (await db.execute(select(LandingPage).where(LandingPage.brand_id == brand_id, LandingPage.offer_id == offer_id, LandingPage.is_active.is_(True)).order_by(LandingPage.created_at.desc()).limit(1))).scalar_one_or_none()
    if not page:
        return {"page_id": None, "truth_label": "no_page"}
    return {"page_id": str(page.id), "page_type": page.page_type, "headline": page.headline, "destination_url": page.destination_url, "truth_label": page.truth_label, "publish_status": page.publish_status}


PUBLISH_ADAPTERS = {
    "manual": "_publish_manual",
    "vercel": "_publish_vercel",
    "netlify": "_publish_netlify",
    "s3_static": "_publish_s3",
}


async def publish_page(db: AsyncSession, page_id: uuid.UUID, publish_method: str = "manual", destination_url: str = "") -> dict[str, Any]:
    """Publish a landing page — transition truth label from recommendation_only to published."""
    from packages.db.models.landing_pages import LandingPagePublishRecord

    page = (await db.execute(select(LandingPage).where(LandingPage.id == page_id))).scalar_one_or_none()
    if not page:
        return {"success": False, "reason": "Page not found"}

    quality = (await db.execute(select(LandingPageQualityReport).where(LandingPageQualityReport.page_id == page_id, LandingPageQualityReport.is_active.is_(True)).order_by(LandingPageQualityReport.created_at.desc()).limit(1))).scalar_one_or_none()
    if quality and quality.verdict == "fail":
        return {"success": False, "reason": f"Quality gate failed (score={quality.total_score:.2f})"}

    if publish_method == "manual" and not destination_url:
        return {"success": False, "reason": "Manual publish requires a destination_url"}

    page.destination_url = destination_url or page.destination_url
    page.publish_status = "published"
    page.truth_label = "published"
    page.status = "published"

    db.add(LandingPagePublishRecord(
        page_id=page.id, brand_id=page.brand_id,
        published_url=page.destination_url,
        publish_method=publish_method,
        truth_label="published",
    ))

    await db.flush()
    return {"success": True, "page_id": str(page.id), "destination_url": page.destination_url, "truth_label": "published", "publish_method": publish_method}
