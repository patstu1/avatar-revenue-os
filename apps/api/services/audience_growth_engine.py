"""Audience Growth Engine — actively discovers and recommends expansion opportunities.

This engine transforms the system from "operates on pre-supplied inputs" to
"identifies where the next revenue audience exists and recommends how to reach it."

Capabilities:
- Identify high-fit audience pockets from existing performance data
- Score adjacent niches by revenue potential
- Rank expansion opportunities by expected uplift
- Recommend content/offer routing for new audience segments
- Surface platform-specific growth actions
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_action
from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.discovery import NicheCluster, TrendSignal
from packages.db.models.publishing import PerformanceMetric
from packages.db.models.revenue_ledger import RevenueLedgerEntry

logger = structlog.get_logger()


async def discover_audience_expansion_opportunities(
    db: AsyncSession,
    brand_id: uuid.UUID,
) -> dict:
    """Identify where the next revenue audience exists and how to reach it."""
    now = datetime.now(timezone.utc)
    day_90 = now - timedelta(days=90)

    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    niche = brand.niche if brand else "general"

    # Current platforms with performance data
    platform_perf = {}
    perf_q = await db.execute(
        select(
            PerformanceMetric.platform,
            func.sum(PerformanceMetric.impressions),
            func.sum(PerformanceMetric.revenue),
            func.count(),
        )
        .where(PerformanceMetric.brand_id == brand_id, PerformanceMetric.created_at >= day_90)
        .group_by(PerformanceMetric.platform)
    )
    for row in perf_q.all():
        if row[0]:
            platform_perf[str(row[0])] = {
                "impressions": int(row[1] or 0),
                "revenue": float(row[2] or 0),
                "count": row[3],
            }

    # Current accounts by platform
    accounts = (
        (
            await db.execute(
                select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    active_platforms = set()
    for a in accounts:
        p = a.platform.value if hasattr(a.platform, "value") else str(a.platform) if a.platform else None
        if p:
            active_platforms.add(p)

    # Ledger revenue by source for audience quality assessment
    rev_q = await db.execute(
        select(RevenueLedgerEntry.revenue_source_type, func.sum(RevenueLedgerEntry.gross_amount))
        .where(
            RevenueLedgerEntry.brand_id == brand_id,
            RevenueLedgerEntry.occurred_at >= day_90,
            RevenueLedgerEntry.is_active.is_(True),
            RevenueLedgerEntry.is_refund.is_(False),
        )
        .group_by(RevenueLedgerEntry.revenue_source_type)
    )
    revenue_by_source = {str(r[0]): float(r[1] or 0) for r in rev_q.all()}
    total_revenue = sum(revenue_by_source.values())

    # ── 1. Platform expansion opportunities ──
    all_platforms = [
        "youtube",
        "tiktok",
        "instagram",
        "x",
        "linkedin",
        "reddit",
        "pinterest",
        "blog",
        "email_newsletter",
        "substack",
        "threads",
    ]
    platform_expansions = []
    for platform in all_platforms:
        if platform not in active_platforms:
            # Score this platform's fit for the brand's niche
            niche_platform_fit = _score_niche_platform_fit(niche, platform)
            if niche_platform_fit > 0.3:
                platform_expansions.append(
                    {
                        "platform": platform,
                        "fit_score": round(niche_platform_fit, 3),
                        "rationale": _platform_rationale(niche, platform),
                        "expected_audience_size": _estimate_reachable_audience(platform, niche),
                        "action": "expand_to_platform",
                    }
                )

    platform_expansions.sort(key=lambda x: x["fit_score"], reverse=True)

    # ── 2. Adjacent niche opportunities ──
    niche_clusters = (
        (
            await db.execute(
                select(NicheCluster)
                .where(NicheCluster.brand_id == brand_id)
                .order_by(NicheCluster.monetization_potential.desc().nullslast())
                .limit(10)
            )
        )
        .scalars()
        .all()
    )

    adjacent_niches = []
    for nc in niche_clusters:
        if nc.content_gap_score and nc.content_gap_score > 0.3:
            adjacent_niches.append(
                {
                    "niche": nc.cluster_name,
                    "monetization_potential": nc.monetization_potential,
                    "content_gap": nc.content_gap_score,
                    "competition": nc.competition_density,
                    "action": "create_content_in_niche",
                }
            )

    # ── 3. Trending topics in niche ──
    trending = (
        (await db.execute(select(TrendSignal).order_by(TrendSignal.velocity.desc().nullslast()).limit(10)))
        .scalars()
        .all()
    )

    trend_opportunities = [
        {
            "keyword": t.keyword,
            "velocity": t.velocity,
            "volume": t.volume,
            "strength": t.strength.value if hasattr(t.strength, "value") else str(t.strength),
            "action": "create_content_on_trend",
        }
        for t in trending
        if t.velocity and t.velocity > 0.3
    ]

    # ── 4. Underserved content types ──
    content_type_q = await db.execute(
        select(ContentItem.content_type, func.count())
        .where(ContentItem.brand_id == brand_id)
        .group_by(ContentItem.content_type)
    )
    content_types = {str(r[0].value if hasattr(r[0], "value") else r[0]): r[1] for r in content_type_q.all()}

    all_types = ["short_video", "long_video", "static_image", "carousel", "text_post", "story"]
    underserved = [
        {"content_type": ct, "current_count": content_types.get(ct, 0), "action": "create_more_content_type"}
        for ct in all_types
        if content_types.get(ct, 0) < 3
    ]

    # ── 5. High-performing segments to double down on ──
    top_content = (
        await db.execute(
            select(
                ContentItem.platform,
                ContentItem.content_type,
                func.count(),
                func.sum(PerformanceMetric.impressions),
                func.sum(PerformanceMetric.revenue),
            )
            .outerjoin(PerformanceMetric, PerformanceMetric.content_item_id == ContentItem.id)
            .where(ContentItem.brand_id == brand_id)
            .group_by(ContentItem.platform, ContentItem.content_type)
            .order_by(func.sum(PerformanceMetric.revenue).desc().nullslast())
            .limit(5)
        )
    ).all()

    double_down = [
        {
            "platform": str(r[0] or "unknown"),
            "content_type": str(r[1].value if hasattr(r[1], "value") else r[1]),
            "content_count": r[2],
            "impressions": int(r[3] or 0),
            "revenue": float(r[4] or 0),
            "action": "scale_winning_segment",
        }
        for r in top_content
        if (r[4] or 0) > 0
    ]

    return {
        "platform_expansions": platform_expansions[:5],
        "adjacent_niches": adjacent_niches[:5],
        "trending_opportunities": trend_opportunities[:5],
        "underserved_content_types": underserved[:5],
        "double_down_segments": double_down[:5],
        "current_platforms": list(active_platforms),
        "total_revenue_90d": total_revenue,
        "total_opportunities": (
            len(platform_expansions)
            + len(adjacent_niches)
            + len(trend_opportunities)
            + len(underserved)
            + len(double_down)
        ),
    }


async def surface_audience_growth_actions(
    db: AsyncSession,
    org_id: uuid.UUID,
    brand_id: uuid.UUID,
) -> list[dict]:
    """Create operator actions from audience growth intelligence."""
    data = await discover_audience_expansion_opportunities(db, brand_id)
    created = []

    for exp in data.get("platform_expansions", [])[:3]:
        a = await emit_action(
            db,
            org_id=org_id,
            action_type="expand_to_platform",
            title=f"Expand to {exp['platform']} (fit: {exp['fit_score']:.0%})",
            description=exp.get("rationale", ""),
            category="opportunity",
            priority="high" if exp["fit_score"] > 0.6 else "medium",
            brand_id=brand_id,
            source_module="audience_growth_engine",
        )
        created.append({"type": "platform_expansion", "action_id": str(a.id)})

    for trend in data.get("trending_opportunities", [])[:2]:
        a = await emit_action(
            db,
            org_id=org_id,
            action_type="create_content_on_trend",
            title=f"Trending: {trend['keyword'][:60]}",
            description=f"Velocity: {trend['velocity']}, strength: {trend['strength']}",
            category="opportunity",
            priority="medium",
            brand_id=brand_id,
            source_module="audience_growth_engine",
        )
        created.append({"type": "trend", "action_id": str(a.id)})

    return created


def _score_niche_platform_fit(niche: str, platform: str) -> float:
    """Score how well a niche fits a platform for audience growth."""
    fit_matrix = {
        "business": {
            "linkedin": 0.9,
            "youtube": 0.8,
            "x": 0.7,
            "substack": 0.7,
            "blog": 0.6,
            "instagram": 0.4,
            "tiktok": 0.5,
        },
        "tech": {"youtube": 0.9, "x": 0.8, "reddit": 0.7, "linkedin": 0.6, "blog": 0.7, "tiktok": 0.5},
        "finance": {"youtube": 0.9, "linkedin": 0.7, "x": 0.7, "substack": 0.6, "blog": 0.6, "tiktok": 0.5},
        "education": {"youtube": 0.9, "tiktok": 0.7, "instagram": 0.6, "blog": 0.7, "substack": 0.6},
        "entertainment": {"tiktok": 0.9, "youtube": 0.8, "instagram": 0.8, "x": 0.5, "threads": 0.5},
        "health": {"youtube": 0.8, "instagram": 0.8, "tiktok": 0.7, "pinterest": 0.6, "blog": 0.5},
        "marketing": {"linkedin": 0.9, "youtube": 0.8, "x": 0.7, "blog": 0.7, "substack": 0.6, "tiktok": 0.5},
    }
    return fit_matrix.get(niche, {}).get(platform, 0.4)


def _platform_rationale(niche: str, platform: str) -> str:
    rationales = {
        "linkedin": "Professional audience with high sponsor/service conversion potential",
        "youtube": "Long-form content drives affiliate and ad revenue with strong SEO",
        "tiktok": "Short-form viral reach for audience building and brand awareness",
        "instagram": "Visual content with strong DTC and sponsor conversion",
        "x": "Real-time engagement and thought leadership for service/consulting",
        "reddit": "Niche communities with high-intent audience for affiliate offers",
        "substack": "Email-first audience building with subscription revenue potential",
        "blog": "SEO-driven evergreen content for affiliate and lead generation",
        "pinterest": "Visual discovery platform for product and affiliate offers",
        "email_newsletter": "Owned audience with highest conversion rates",
        "threads": "Emerging platform for brand awareness and audience capture",
    }
    return rationales.get(platform, f"New platform opportunity for {niche}")


def _estimate_reachable_audience(platform: str, niche: str) -> str:
    estimates = {
        "youtube": "10K-100K subscribers in 6-12 months",
        "tiktok": "5K-50K followers in 3-6 months",
        "instagram": "5K-30K followers in 6-12 months",
        "linkedin": "2K-15K connections in 3-6 months",
        "x": "1K-10K followers in 3-6 months",
        "substack": "500-5K subscribers in 6-12 months",
    }
    return estimates.get(platform, "Variable — depends on content frequency and quality")
