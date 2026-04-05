"""Sponsor Pipeline Service — actively manages the sponsor acquisition funnel.

Transforms from "tracks sponsor deals passively" to "scores sponsor fit,
manages pipeline stages, generates outreach prep, creates follow-up actions."
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_action, emit_event
from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.offers import Offer, SponsorOpportunity, SponsorProfile
from packages.db.models.publishing import PerformanceMetric
from packages.db.models.revenue_ledger import RevenueLedgerEntry

logger = structlog.get_logger()

DEAL_STAGES = ["prospect", "outreach", "negotiation", "proposal", "active", "delivering", "completed", "lost"]


async def get_sponsor_pipeline(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    """Full sponsor pipeline view: deals by stage, revenue, fit scores."""
    # Deals by stage
    stage_q = await db.execute(
        select(SponsorOpportunity.status, func.count(), func.sum(SponsorOpportunity.deal_value))
        .where(SponsorOpportunity.brand_id == brand_id)
        .group_by(SponsorOpportunity.status)
    )
    by_stage = {str(r[0]): {"count": r[1], "value": float(r[2] or 0)} for r in stage_q.all()}

    total_pipeline = sum(d["value"] for d in by_stage.values())
    active_deals = sum(d["count"] for s, d in by_stage.items() if s in ("negotiation", "proposal", "active", "delivering"))

    # Sponsor profiles
    sponsors = (await db.execute(
        select(SponsorProfile).where(SponsorProfile.brand_id == brand_id, SponsorProfile.is_active.is_(True))
    )).scalars().all()

    # Revenue from sponsors
    sponsor_rev = (await db.execute(
        select(func.coalesce(func.sum(RevenueLedgerEntry.gross_amount), 0.0))
        .where(RevenueLedgerEntry.brand_id == brand_id,
               RevenueLedgerEntry.revenue_source_type == "sponsor_payment",
               RevenueLedgerEntry.is_active.is_(True))
    )).scalar() or 0.0

    # Stalled deals (no update in 14+ days)
    stalled = (await db.execute(
        select(SponsorOpportunity)
        .where(SponsorOpportunity.brand_id == brand_id,
               SponsorOpportunity.status.in_(["prospect", "outreach", "negotiation"]),
               SponsorOpportunity.updated_at < datetime.now(timezone.utc) - timedelta(days=14))
    )).scalars().all()

    return {
        "by_stage": by_stage,
        "total_pipeline_value": total_pipeline,
        "active_deals": active_deals,
        "sponsor_count": len(sponsors),
        "total_sponsor_revenue": float(sponsor_rev),
        "stalled_deals": [{"id": str(d.id), "title": d.title, "status": d.status,
                            "deal_value": float(d.deal_value or 0)} for d in stalled],
        "stalled_count": len(stalled),
    }


async def score_sponsor_fit(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    """Score each creator account for sponsor readiness."""
    accounts = (await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )).scalars().all()

    results = []
    for acct in accounts:
        followers = getattr(acct, 'follower_count', 0) or 0
        engagement = getattr(acct, 'engagement_rate', 0) or getattr(acct, 'ctr', 0) or 0
        platform = acct.platform.value if hasattr(acct.platform, 'value') else str(acct.platform)

        # Sponsor readiness score
        audience_score = min(1.0, followers / 50000)
        engagement_score = min(1.0, engagement * 15)
        platform_fit = 0.8 if platform in ("youtube", "instagram", "tiktok") else 0.5 if platform in ("linkedin", "x") else 0.3

        content_count = (await db.execute(
            select(func.count()).select_from(ContentItem).where(
                ContentItem.brand_id == brand_id, ContentItem.creator_account_id == acct.id
            )
        )).scalar() or 0
        content_score = min(1.0, content_count / 20)

        sponsor_score = (
            0.30 * audience_score +
            0.25 * engagement_score +
            0.25 * platform_fit +
            0.20 * content_score
        )

        readiness = "sponsor_ready" if sponsor_score > 0.6 else "growing" if sponsor_score > 0.3 else "not_ready"

        results.append({
            "account_id": str(acct.id),
            "platform": platform,
            "followers": followers,
            "sponsor_score": round(sponsor_score, 3),
            "readiness": readiness,
            "audience_score": round(audience_score, 3),
            "engagement_score": round(engagement_score, 3),
            "content_count": content_count,
        })

    results.sort(key=lambda x: x["sponsor_score"], reverse=True)
    return results


async def generate_outreach_brief(
    db: AsyncSession, brand_id: uuid.UUID, sponsor_id: uuid.UUID,
) -> dict:
    """Generate an outreach preparation brief for a sponsor."""
    sponsor = (await db.execute(
        select(SponsorProfile).where(SponsorProfile.id == sponsor_id)
    )).scalar_one_or_none()
    if not sponsor:
        return {"error": "Sponsor not found"}

    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()

    # Get top-performing content for the pitch
    top_content = (await db.execute(
        select(ContentItem.title, PerformanceMetric.impressions, PerformanceMetric.engagement_rate)
        .outerjoin(PerformanceMetric, PerformanceMetric.content_item_id == ContentItem.id)
        .where(ContentItem.brand_id == brand_id)
        .order_by(PerformanceMetric.impressions.desc().nullslast())
        .limit(5)
    )).all()

    total_followers = (await db.execute(
        select(func.sum(CreatorAccount.follower_count)).where(
            CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True)
        )
    )).scalar() or 0

    return {
        "sponsor_name": sponsor.sponsor_name,
        "industry": sponsor.industry,
        "budget_range": f"${sponsor.budget_range_min or 0:,.0f} - ${sponsor.budget_range_max or 0:,.0f}",
        "brand_name": brand.name if brand else "Unknown",
        "brand_niche": brand.niche if brand else "General",
        "total_audience": int(total_followers),
        "top_content": [{"title": r[0], "impressions": int(r[1] or 0)} for r in top_content],
        "suggested_deal_types": ["sponsored_video", "product_placement", "dedicated_review", "series_sponsorship"],
        "suggested_price_range": f"${int(total_followers * 0.02):,} - ${int(total_followers * 0.05):,}",
    }


async def surface_sponsor_actions(
    db: AsyncSession, org_id: uuid.UUID, brand_id: uuid.UUID,
) -> list[dict]:
    """Create operator actions for sponsor pipeline management."""
    pipeline = await get_sponsor_pipeline(db, brand_id)
    fit_scores = await score_sponsor_fit(db, brand_id)
    created = []

    # Stalled deals → follow-up actions
    for deal in pipeline.get("stalled_deals", [])[:3]:
        a = await emit_action(
            db, org_id=org_id, action_type="follow_up_sponsor",
            title=f"Stalled deal: {deal['title'][:50]} (${deal['deal_value']:,.0f})",
            description=f"Deal in '{deal['status']}' stage with no update in 14+ days.",
            category="monetization", priority="high",
            brand_id=brand_id, source_module="sponsor_pipeline",
            entity_type="sponsor_opportunity", entity_id=uuid.UUID(deal["id"]),
        )
        created.append({"type": "stalled_deal", "action_id": str(a.id)})

    # Sponsor-ready accounts without active deals
    ready = [f for f in fit_scores if f["readiness"] == "sponsor_ready"]
    if ready and pipeline.get("active_deals", 0) == 0:
        a = await emit_action(
            db, org_id=org_id, action_type="escalate_sponsor_opportunity",
            title=f"{len(ready)} accounts are sponsor-ready — no active deals",
            description=f"Top account: {ready[0]['platform']} ({ready[0]['followers']:,} followers, score {ready[0]['sponsor_score']:.0%})",
            category="monetization", priority="high",
            brand_id=brand_id, source_module="sponsor_pipeline",
        )
        created.append({"type": "sponsor_ready", "action_id": str(a.id)})

    return created
