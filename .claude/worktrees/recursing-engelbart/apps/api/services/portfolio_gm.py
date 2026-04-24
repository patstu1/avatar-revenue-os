"""Portfolio GM — cross-brand strategic brain for mass-scale operations.

The per-brand GM thinks about one brand at a time.
The Portfolio GM thinks across ALL brands simultaneously:
- Which brands deserve more resources?
- Which should be paused?
- How to allocate effort across the entire operation?
- What's the portfolio-level revenue ceiling?
- Where is the highest marginal return?
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand, Organization
from packages.db.models.offers import Offer
from packages.db.models.revenue_ledger import RevenueLedgerEntry

logger = structlog.get_logger()


async def get_portfolio_overview(db: AsyncSession, org_id: uuid.UUID) -> dict:
    """Cross-brand portfolio view: all brands ranked by performance."""
    now = datetime.now(timezone.utc)
    day_90 = now - timedelta(days=90)

    brands = (await db.execute(
        select(Brand).where(Brand.organization_id == org_id)
    )).scalars().all()

    brand_data = []
    for brand in brands:
        rev = (await db.execute(
            select(func.coalesce(func.sum(RevenueLedgerEntry.gross_amount), 0.0))
            .where(RevenueLedgerEntry.brand_id == brand.id, RevenueLedgerEntry.occurred_at >= day_90,
                   RevenueLedgerEntry.is_active.is_(True), RevenueLedgerEntry.is_refund.is_(False))
        )).scalar() or 0.0

        accounts = (await db.execute(
            select(func.count()).select_from(CreatorAccount)
            .where(CreatorAccount.brand_id == brand.id, CreatorAccount.is_active.is_(True))
        )).scalar() or 0

        followers = (await db.execute(
            select(func.coalesce(func.sum(CreatorAccount.follower_count), 0))
            .where(CreatorAccount.brand_id == brand.id, CreatorAccount.is_active.is_(True))
        )).scalar() or 0

        content = (await db.execute(
            select(func.count()).select_from(ContentItem)
            .where(ContentItem.brand_id == brand.id, ContentItem.status == "published")
        )).scalar() or 0

        offers = (await db.execute(
            select(func.count()).select_from(Offer)
            .where(Offer.brand_id == brand.id, Offer.is_active.is_(True))
        )).scalar() or 0

        rev_per_account = float(rev) / max(accounts, 1)
        rev_per_follower = float(rev) / max(int(followers), 1)

        brand_data.append({
            "brand_id": str(brand.id),
            "name": brand.name,
            "niche": brand.niche,
            "revenue_90d": float(rev),
            "accounts": accounts,
            "followers": int(followers),
            "published_content": content,
            "active_offers": offers,
            "rev_per_account": round(rev_per_account, 2),
            "rev_per_follower": round(rev_per_follower, 4),
        })

    brand_data.sort(key=lambda b: b["revenue_90d"], reverse=True)
    total_rev = sum(b["revenue_90d"] for b in brand_data)
    total_accounts = sum(b["accounts"] for b in brand_data)
    total_followers = sum(b["followers"] for b in brand_data)

    # Portfolio allocation: rank brands by marginal return
    for b in brand_data:
        share = b["revenue_90d"] / max(total_rev, 1)
        b["portfolio_share"] = round(share * 100, 1)
        b["allocation"] = "scale" if b["rev_per_account"] > total_rev / max(total_accounts, 1) else "maintain" if b["revenue_90d"] > 0 else "invest_or_pause"

    return {
        "org_id": str(org_id),
        "total_brands": len(brands),
        "total_revenue_90d": total_rev,
        "total_accounts": total_accounts,
        "total_followers": total_followers,
        "brands": brand_data,
        "top_performer": brand_data[0]["name"] if brand_data else None,
        "portfolio_directive": _portfolio_directive(brand_data, total_rev),
    }


async def compute_portfolio_allocation(db: AsyncSession, org_id: uuid.UUID) -> dict:
    """Deep portfolio allocator: computes % effort allocation per brand.

    Ranks by marginal return and outputs actual allocation percentages,
    not just scale/maintain labels.
    """
    overview = await get_portfolio_overview(db, org_id)
    brands = overview["brands"]
    total_rev = overview["total_revenue_90d"]

    if not brands:
        return {"allocations": [], "total_brands": 0}

    # Compute marginal return score per brand
    for b in brands:
        rev = b["revenue_90d"]
        accounts = max(b["accounts"], 1)
        followers = max(b["followers"], 1)

        # Marginal return: revenue efficiency × growth potential
        efficiency = rev / accounts  # Revenue per account
        yield_rate = rev / followers  # Revenue per follower
        content_velocity = b["published_content"] / max(accounts, 1)  # Content per account
        monetization_depth = 1.0 if b["active_offers"] > 0 and rev > 0 else 0.5 if b["active_offers"] > 0 else 0.2

        b["marginal_score"] = round(
            0.35 * min(1.0, efficiency / max(total_rev / max(len(brands), 1), 1)) +
            0.25 * min(1.0, yield_rate * 100) +
            0.20 * min(1.0, content_velocity / 5) +
            0.20 * monetization_depth,
            3
        )

    # Normalize to percentage allocation
    total_score = sum(b["marginal_score"] for b in brands) or 1
    allocations = []
    for b in brands:
        pct = round(b["marginal_score"] / total_score * 100, 1)
        allocations.append({
            "brand_id": b["brand_id"],
            "name": b["name"],
            "allocation_pct": pct,
            "marginal_score": b["marginal_score"],
            "revenue_90d": b["revenue_90d"],
            "accounts": b["accounts"],
            "directive": "scale_aggressively" if pct > 40 else "scale" if pct > 25 else "maintain" if pct > 10 else "reduce_or_pause",
        })

    allocations.sort(key=lambda a: a["allocation_pct"], reverse=True)

    return {
        "allocations": allocations,
        "total_brands": len(brands),
        "total_revenue_90d": total_rev,
        "concentration_risk": round(max(a["allocation_pct"] for a in allocations) / 100, 2) if allocations else 0,
    }


def _portfolio_directive(brands: list, total_rev: float) -> str:
    if not brands:
        return "No brands configured. Create your first brand to begin."
    scaling = [b for b in brands if b["allocation"] == "scale"]
    investing = [b for b in brands if b["allocation"] == "invest_or_pause"]
    if not scaling and total_rev == 0:
        return "No revenue yet across any brand. Focus on the highest-potential brand first."
    if scaling:
        return f"Scale: {', '.join(b['name'] for b in scaling[:3])}. These have the highest marginal return."
    return "All brands are maintaining. Look for the next scaling opportunity."
