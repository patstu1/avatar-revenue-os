"""Portfolio GM — cross-brand Revenue-Ops scoring for ProofHook.

The per-brand GM thinks about one brand at a time.
The Portfolio GM thinks across ALL brands simultaneously:
- Which brands are generating package revenue?
- Which packages are routing efficiently?
- Where is the Revenue-Ops funnel leaking?
- What's the portfolio-level package-revenue ceiling?

Scoring is package-efficiency-driven, NOT audience-driven. Followers,
engagement, posting cadence, and impressions are NOT inputs because
ProofHook sells creative services packages to brands — none of that
matters for revenue. The inputs that matter are:
    • package_revenue_90d      → did packages actually sell?
    • packages_sold            → how many checkouts completed?
    • active_packages          → how deep is the catalog?
    • avg_package_value        → what's the ceiling per lead?
    • upsell_rate              → do delivered packages generate repeat revenue?
    • delivery_throughput      → is production bottlenecked?
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
    """Cross-brand Revenue-Ops portfolio view: brands ranked by package efficiency.

    Package efficiency = package_revenue_90d per active package. This is
    the Revenue-Ops replacement for "rev per follower" (audience metric).
    Brands with higher package revenue per active package are scaling the
    funnel efficiently; brands with low efficiency have a routing or
    conversion problem in the package recommender or checkout flow.
    """
    now = datetime.now(timezone.utc)
    day_90 = now - timedelta(days=90)

    brands = (await db.execute(
        select(Brand).where(Brand.organization_id == org_id)
    )).scalars().all()

    brand_data = []
    for brand in brands:
        package_revenue = (await db.execute(
            select(func.coalesce(func.sum(RevenueLedgerEntry.gross_amount), 0.0))
            .where(RevenueLedgerEntry.brand_id == brand.id, RevenueLedgerEntry.occurred_at >= day_90,
                   RevenueLedgerEntry.is_active.is_(True), RevenueLedgerEntry.is_refund.is_(False))
        )).scalar() or 0.0

        # Package-revenue events (checkout completions in the 90d window)
        packages_sold = (await db.execute(
            select(func.count()).select_from(RevenueLedgerEntry)
            .where(RevenueLedgerEntry.brand_id == brand.id, RevenueLedgerEntry.occurred_at >= day_90,
                   RevenueLedgerEntry.is_active.is_(True), RevenueLedgerEntry.is_refund.is_(False))
        )).scalar() or 0

        # Kept for legacy back-compat fields but NOT used in scoring
        inboxes = (await db.execute(
            select(func.count()).select_from(CreatorAccount)
            .where(CreatorAccount.brand_id == brand.id, CreatorAccount.is_active.is_(True))
        )).scalar() or 0

        delivered_content = (await db.execute(
            select(func.count()).select_from(ContentItem)
            .where(ContentItem.brand_id == brand.id, ContentItem.status == "published")
        )).scalar() or 0

        active_packages = (await db.execute(
            select(func.count()).select_from(Offer)
            .where(Offer.brand_id == brand.id, Offer.is_active.is_(True))
        )).scalar() or 0

        # Package efficiency = revenue per active package in catalog.
        # Higher = the catalog is routing leads into packages that convert.
        package_efficiency = float(package_revenue) / max(int(active_packages), 1)
        # Average package value = revenue per closed package
        avg_package_value = float(package_revenue) / max(int(packages_sold), 1) if packages_sold else 0.0

        brand_data.append({
            "brand_id": str(brand.id),
            "name": brand.name,
            # niche is retained for legacy UI compat but plays ZERO role in
            # scoring or allocation. Do not use it for decisions.
            "niche": brand.niche,
            "package_revenue_90d": float(package_revenue),
            "packages_sold_90d": int(packages_sold),
            "avg_package_value": round(avg_package_value, 2),
            "active_packages": int(active_packages),
            "package_efficiency": round(package_efficiency, 2),
            "delivery_throughput_90d": int(delivered_content),  # production queue depth
            "active_inboxes": int(inboxes),
            # Back-compat aliases (legacy callers still read these keys)
            "revenue_90d": float(package_revenue),
            "accounts": int(inboxes),
            "published_content": int(delivered_content),
            "active_offers": int(active_packages),
        })

    brand_data.sort(key=lambda b: b["package_revenue_90d"], reverse=True)
    total_rev = sum(b["package_revenue_90d"] for b in brand_data)
    total_packages_sold = sum(b["packages_sold_90d"] for b in brand_data)
    total_active_packages = sum(b["active_packages"] for b in brand_data)
    total_inboxes = sum(b["active_inboxes"] for b in brand_data)

    # Portfolio allocation: rank brands by package efficiency, not audience.
    # "scale" = package_efficiency is above portfolio average AND brand is
    # actually generating revenue. "maintain" = revenue exists but below
    # average efficiency. "invest_or_pause" = no package revenue yet.
    avg_efficiency = total_rev / max(total_active_packages, 1)
    for b in brand_data:
        share = b["package_revenue_90d"] / max(total_rev, 1)
        b["portfolio_share"] = round(share * 100, 1)
        if b["package_revenue_90d"] > 0 and b["package_efficiency"] >= avg_efficiency:
            b["allocation"] = "scale"
        elif b["package_revenue_90d"] > 0:
            b["allocation"] = "maintain"
        else:
            b["allocation"] = "invest_or_pause"

    return {
        "org_id": str(org_id),
        "total_brands": len(brands),
        "total_revenue_90d": total_rev,           # back-compat alias
        "total_package_revenue_90d": total_rev,
        "total_packages_sold_90d": total_packages_sold,
        "total_active_packages": total_active_packages,
        "total_accounts": total_inboxes,           # back-compat alias
        "total_inboxes": total_inboxes,
        "portfolio_avg_package_efficiency": round(avg_efficiency, 2),
        "brands": brand_data,
        "top_performer": brand_data[0]["name"] if brand_data else None,
        "portfolio_directive": _portfolio_directive(brand_data, total_rev),
    }


async def compute_portfolio_allocation(db: AsyncSession, org_id: uuid.UUID) -> dict:
    """Deep portfolio allocator: computes % effort allocation per brand.

    Ranks by PACKAGE-EFFICIENCY marginal return. Follower counts and
    audience metrics are NOT inputs — ProofHook Revenue-Ops ignores them
    entirely. Inputs are:
        • package_revenue_90d    (absolute revenue generated)
        • package_efficiency     (revenue per active package in catalog)
        • packages_sold_90d      (checkout completions)
        • catalog_depth          (active packages — routing surface area)
    """
    overview = await get_portfolio_overview(db, org_id)
    brands = overview["brands"]
    total_rev = overview["total_package_revenue_90d"]
    avg_efficiency = overview["portfolio_avg_package_efficiency"] or 1.0

    if not brands:
        return {"allocations": [], "total_brands": 0}

    # Compute package-efficiency marginal score per brand
    for b in brands:
        rev = b["package_revenue_90d"]
        packages_sold = max(b["packages_sold_90d"], 1)
        active_packages = max(b["active_packages"], 1)

        # Four inputs, no audience metrics:
        #   1. relative package efficiency vs portfolio average (0-1)
        #   2. absolute package revenue scaled to portfolio total (0-1)
        #   3. throughput — packages sold vs portfolio average (0-1)
        #   4. catalog depth — how routable the brand is (0-1)
        rel_efficiency = min(1.0, b["package_efficiency"] / max(avg_efficiency, 1))
        rev_share = min(1.0, rev / max(total_rev, 1))
        avg_packages_sold = sum(x["packages_sold_90d"] for x in brands) / len(brands)
        throughput_score = min(1.0, b["packages_sold_90d"] / max(avg_packages_sold, 1))
        catalog_depth = min(1.0, active_packages / 6)  # 6 packages = full catalog

        b["marginal_score"] = round(
            0.40 * rel_efficiency
            + 0.30 * rev_share
            + 0.20 * throughput_score
            + 0.10 * catalog_depth,
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
            "package_revenue_90d": b["package_revenue_90d"],
            "packages_sold_90d": b["packages_sold_90d"],
            "active_packages": b["active_packages"],
            "package_efficiency": b["package_efficiency"],
            # Back-compat aliases
            "revenue_90d": b["package_revenue_90d"],
            "accounts": b["active_inboxes"],
            "directive": "scale_aggressively" if pct > 40 else "scale" if pct > 25 else "maintain" if pct > 10 else "reduce_or_pause",
        })

    allocations.sort(key=lambda a: a["allocation_pct"], reverse=True)

    return {
        "allocations": allocations,
        "total_brands": len(brands),
        "total_revenue_90d": total_rev,
        "total_package_revenue_90d": total_rev,
        "portfolio_avg_package_efficiency": avg_efficiency,
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
