"""Revenue ceiling endpoints: offer stacks, funnel paths, owned audience,
productization, monetization density.

POST recompute writes. All GETs are read-only.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.revenue_intel import MonetizationRecRow, RevenueIntelDashboardResponse
from apps.api.services import revenue_service as rsvc
from apps.api.services.audit_service import log_action
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, user, db: DBSession) -> Brand:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")
    return brand


@router.post("/{brand_id}/revenue-intel/recompute")
async def recompute_revenue_intel(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await rsvc.recompute_revenue_intel(db, brand_id, user_id=current_user.id)
    await log_action(db, "revenue_intel.recomputed", organization_id=current_user.organization_id, brand_id=brand_id, user_id=current_user.id, actor_type="human", entity_type="revenue_intel", details=result)
    return result


@router.get("/{brand_id}/offer-stacks", response_model=list[MonetizationRecRow])
async def list_offer_stacks(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rsvc.get_offer_stacks(db, brand_id)


@router.get("/{brand_id}/funnel-paths", response_model=list[MonetizationRecRow])
async def list_funnel_paths(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rsvc.get_funnel_paths(db, brand_id)


@router.get("/{brand_id}/owned-audience-value", response_model=list[MonetizationRecRow])
async def list_owned_audience(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rsvc.get_owned_audience_value(db, brand_id)


@router.get("/{brand_id}/productization", response_model=list[MonetizationRecRow])
async def list_productization(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rsvc.get_productization(db, brand_id)


@router.get("/{brand_id}/monetization-density", response_model=list[MonetizationRecRow])
async def list_density(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rsvc.get_monetization_density(db, brand_id)


# ── Post-Level Revenue Attribution ─────────────────────────────────


@router.get("/{brand_id}/post-revenue-attribution")
async def get_post_revenue_attribution(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    limit: int = 50,
):
    """Return per-post revenue attribution: post → content item → offer → revenue.

    Joins PublishJob + ContentItem + Offer + RevenueLedgerEntry + PerformanceMetric
    to show the operator exactly which published posts generated which revenue.
    """
    await _require_brand(brand_id, current_user, db)

    from packages.db.models.publishing import PublishJob, PerformanceMetric
    from packages.db.models.content import ContentItem
    from packages.db.models.offers import Offer
    from packages.db.models.revenue_ledger import RevenueLedgerEntry
    from packages.db.enums import JobStatus
    from sqlalchemy import func, desc

    # Get published posts with their content items and offers
    jobs = (await db.execute(
        select(PublishJob).where(
            PublishJob.brand_id == brand_id,
            PublishJob.status == JobStatus.COMPLETED,
        ).order_by(desc(PublishJob.published_at)).limit(limit)
    )).scalars().all()

    results = []
    for job in jobs:
        ci = (await db.execute(
            select(ContentItem).where(ContentItem.id == job.content_item_id)
        )).scalar_one_or_none() if job.content_item_id else None

        offer = None
        if ci and ci.offer_id:
            offer = (await db.execute(
                select(Offer).where(Offer.id == ci.offer_id)
            )).scalar_one_or_none()

        # Get revenue attributed to this content item
        revenue_total = 0.0
        revenue_entries = []
        if job.content_item_id:
            ledger_rows = (await db.execute(
                select(RevenueLedgerEntry).where(
                    RevenueLedgerEntry.content_item_id == job.content_item_id,
                    RevenueLedgerEntry.is_active.is_(True),
                )
            )).scalars().all()
            for entry in ledger_rows:
                revenue_total += entry.net_amount or entry.gross_amount or 0
                revenue_entries.append({
                    "source": entry.revenue_source_type,
                    "gross": float(entry.gross_amount or 0),
                    "net": float(entry.net_amount or 0),
                    "state": entry.payment_state,
                })

        # Get performance metrics
        metrics_summary = {}
        if job.content_item_id:
            metrics = (await db.execute(
                select(PerformanceMetric).where(
                    PerformanceMetric.content_item_id == job.content_item_id,
                ).order_by(desc(PerformanceMetric.measured_at)).limit(1)
            )).scalar_one_or_none()
            if metrics:
                metrics_summary = {
                    "views": metrics.views,
                    "likes": metrics.likes,
                    "comments": metrics.comments,
                    "shares": metrics.shares,
                    "engagement_rate": round(metrics.engagement_rate, 4),
                    "revenue_from_platform": float(metrics.revenue or 0),
                }

        platform_val = job.platform.value if hasattr(job.platform, "value") else str(job.platform)

        results.append({
            "publish_job_id": str(job.id),
            "content_item_id": str(job.content_item_id) if job.content_item_id else None,
            "platform": platform_val,
            "platform_post_id": job.platform_post_id,
            "platform_post_url": job.platform_post_url,
            "published_at": job.published_at.isoformat() if job.published_at else None,
            "content_title": ci.title if ci and hasattr(ci, 'title') else None,
            "offer_name": offer.name if offer else None,
            "offer_id": str(offer.id) if offer else None,
            "monetization_method": offer.monetization_method if offer else None,
            "total_revenue": round(revenue_total, 2),
            "revenue_entries": revenue_entries,
            "performance": metrics_summary,
        })

    total_attributed = sum(r["total_revenue"] for r in results)
    posts_with_revenue = sum(1 for r in results if r["total_revenue"] > 0)

    return {
        "brand_id": str(brand_id),
        "posts_analyzed": len(results),
        "posts_with_revenue": posts_with_revenue,
        "total_attributed_revenue": round(total_attributed, 2),
        "posts": results,
    }
