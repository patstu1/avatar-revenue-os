"""Revenue Maximizer — the maximum-power money engine.

This service orchestrates all existing scoring engines into a unified
revenue intelligence machine that:
- Scores every account for 10 monetization paths
- Detects the highest-value revenue opportunities
- Allocates effort toward the best strategies
- Suppresses low-return activity
- Remembers what works and compounds winners
- Recommends optimal monetization mixes
- Generates next-best revenue actions

It does NOT rebuild existing engines. It COMPOSES them into a single
decision surface that maximizes total revenue.
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
from packages.db.models.brain_phase_b import ArbitrationReport, BrainDecision
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.creator_revenue import CreatorRevenueOpportunity
from packages.db.models.failure_family import FailureFamilyReport, SuppressionRule
from packages.db.models.learning import MemoryEntry
from packages.db.models.offers import Offer, SponsorOpportunity, SponsorProfile
from packages.db.models.pattern_memory import (
    LosingPatternMemory,
    PatternDecayReport,
    WinningPatternCluster,
    WinningPatternMemory,
)
from packages.db.models.promote_winner import ActiveExperiment, PromotedWinnerRule
from packages.db.models.publishing import PerformanceMetric
from packages.db.models.revenue_ledger import RevenueLedgerEntry
from packages.db.models.scoring import OpportunityScore, ProfitForecast, RecommendationQueue

logger = structlog.get_logger()

# ══════════════════════════════════════════════════════════════════════
# ENGINE 1: CREATOR MONETIZATION FIT
# ══════════════════════════════════════════════════════════════════════

MONETIZATION_PATHS = [
    "affiliate", "sponsor", "dtc", "product", "subscription",
    "services", "licensing", "lead_gen", "long_form", "short_form",
]


async def compute_creator_monetization_fit(
    db: AsyncSession, brand_id: uuid.UUID,
) -> list[dict]:
    """Score every account for 10 monetization paths.

    Uses: follower count, engagement rate, platform, niche, content
    types, existing revenue, offer history, audience quality.
    """
    accounts_q = await db.execute(
        select(CreatorAccount).where(
            CreatorAccount.brand_id == brand_id,
            CreatorAccount.is_active.is_(True),
        )
    )
    accounts = accounts_q.scalars().all()

    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    niche = brand.niche if brand else "general"

    # Get offer count and revenue for context
    offer_count = (await db.execute(
        select(func.count()).select_from(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
    )).scalar() or 0

    ledger_revenue = (await db.execute(
        select(func.coalesce(func.sum(RevenueLedgerEntry.gross_amount), 0.0)).where(
            RevenueLedgerEntry.brand_id == brand_id,
            RevenueLedgerEntry.occurred_at >= datetime.now(timezone.utc) - timedelta(days=90),
        )
    )).scalar() or 0.0

    sponsor_count = (await db.execute(
        select(func.count()).select_from(SponsorProfile).where(SponsorProfile.brand_id == brand_id)
    )).scalar() or 0

    results = []
    for acct in accounts:
        followers = acct.follower_count if hasattr(acct, 'follower_count') and acct.follower_count else 0
        engagement = acct.engagement_rate if hasattr(acct, 'engagement_rate') and acct.engagement_rate else 0.0
        platform = acct.platform.value if hasattr(acct.platform, 'value') else str(acct.platform) if acct.platform else "unknown"
        health = acct.health_status.value if hasattr(acct, 'health_status') and hasattr(acct.health_status, 'value') else "healthy"

        is_video_platform = platform in ("youtube", "tiktok", "instagram", "rumble", "twitch", "kick")
        is_long_form = platform in ("youtube", "blog", "medium", "substack", "spotify", "apple_podcasts")
        is_short_form = platform in ("tiktok", "instagram", "youtube", "x", "threads", "snapchat")

        # Score each path (0.0 to 1.0)
        scores = {}
        base = min(1.0, followers / 50000) * 0.3 + min(1.0, engagement * 10) * 0.3 + (0.4 if health == "healthy" else 0.2)

        scores["affiliate"] = min(1.0, base * (1.2 if offer_count > 0 else 0.6) * (1.1 if is_video_platform else 0.8))
        scores["sponsor"] = min(1.0, base * (1.3 if followers > 10000 else 0.4) * (1.1 if engagement > 0.03 else 0.7) * (1.2 if sponsor_count > 0 else 0.8))
        scores["dtc"] = min(1.0, base * (1.2 if followers > 5000 else 0.5) * (0.9 if platform in ("instagram", "tiktok") else 0.6))
        scores["product"] = min(1.0, base * (1.3 if float(ledger_revenue) > 1000 else 0.4) * (1.1 if niche in ("education", "tech", "business", "finance") else 0.7))
        scores["subscription"] = min(1.0, base * (1.4 if followers > 25000 else 0.3) * (1.2 if engagement > 0.05 else 0.5))
        scores["services"] = min(1.0, base * (1.5 if niche in ("business", "consulting", "tech", "marketing") else 0.6) * (1.1 if float(ledger_revenue) > 500 else 0.7))
        scores["licensing"] = min(1.0, base * (1.2 if is_video_platform else 0.4) * (0.8 if followers > 50000 else 0.3))
        scores["lead_gen"] = min(1.0, base * (1.3 if niche in ("business", "finance", "saas", "consulting") else 0.5) * (1.1 if engagement > 0.02 else 0.6))
        scores["long_form"] = min(1.0, base * (1.4 if is_long_form else 0.3) * (1.2 if platform == "youtube" else 0.8))
        scores["short_form"] = min(1.0, base * (1.3 if is_short_form else 0.3) * (1.2 if platform in ("tiktok", "instagram") else 0.7))

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_path = ranked[0][0]
        best_score = ranked[0][1]

        results.append({
            "account_id": str(acct.id),
            "platform": platform,
            "followers": followers,
            "engagement_rate": engagement,
            "health": health,
            "fit_scores": {k: round(v, 3) for k, v in scores.items()},
            "best_fit": best_path,
            "best_score": round(best_score, 3),
            "ranked_paths": [{"path": k, "score": round(v, 3)} for k, v in ranked],
        })

    results.sort(key=lambda x: x["best_score"], reverse=True)
    return results


# ══════════════════════════════════════════════════════════════════════
# ENGINE 2: REVENUE OPPORTUNITY DETECTION
# ══════════════════════════════════════════════════════════════════════

async def detect_revenue_opportunities(
    db: AsyncSession, brand_id: uuid.UUID,
) -> list[dict]:
    """Detect the highest-value revenue opportunities.

    Aggregates: opportunity scores, under-monetized content, missing offers,
    sponsor-ready accounts, product-ready accounts, weak mixes.
    """
    opportunities = []

    # 1. Top-scored opportunities from recommendation queue
    top_opps = await db.execute(
        select(RecommendationQueue).where(
            RecommendationQueue.brand_id == brand_id,
        ).order_by(RecommendationQueue.composite_score.desc()).limit(10)
    )
    for opp in top_opps.scalars().all():
        opportunities.append({
            "type": "scored_opportunity",
            "rank": opp.rank,
            "composite_score": opp.composite_score,
            "recommended_action": opp.recommended_action,
            "entity_id": str(opp.id),
            "expected_upside": opp.composite_score * 500,  # Rough upside estimate
            "source": "opportunity_scoring",
        })

    # 2. Under-monetized published content (no offer assigned)
    unmon_q = await db.execute(
        select(ContentItem).where(
            ContentItem.brand_id == brand_id,
            ContentItem.status == "published",
            ContentItem.offer_id.is_(None),
        ).limit(10)
    )
    for item in unmon_q.scalars().all():
        opportunities.append({
            "type": "under_monetized_content",
            "title": item.title[:80],
            "entity_id": str(item.id),
            "entity_type": "content_item",
            "expected_upside": 50,  # Conservative estimate per unmonetized content
            "action": "assign_offer",
            "source": "content_analysis",
        })

    # 3. Active offers with no content
    orphan_q = await db.execute(
        select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True)).limit(20)
    )
    for offer in orphan_q.scalars().all():
        ct = (await db.execute(
            select(func.count()).select_from(ContentItem).where(
                ContentItem.brand_id == brand_id, ContentItem.offer_id == offer.id
            )
        )).scalar() or 0
        if ct == 0:
            opportunities.append({
                "type": "orphan_offer",
                "offer_name": offer.name[:80],
                "payout": float(offer.payout_amount) if offer.payout_amount else 0,
                "entity_id": str(offer.id),
                "entity_type": "offer",
                "expected_upside": float(offer.payout_amount) * 10 if offer.payout_amount else 100,
                "action": "create_content_for_offer",
                "source": "offer_analysis",
            })

    # 4. Sponsor-ready accounts (high followers + engagement, no sponsor deals)
    accounts = (await db.execute(
        select(CreatorAccount).where(
            CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True)
        )
    )).scalars().all()

    active_sponsors = (await db.execute(
        select(func.count()).select_from(SponsorOpportunity).where(
            SponsorOpportunity.brand_id == brand_id, SponsorOpportunity.status == "active"
        )
    )).scalar() or 0

    for acct in accounts:
        followers = getattr(acct, 'follower_count', 0) or 0
        engagement = getattr(acct, 'engagement_rate', 0) or 0
        if followers > 10000 and engagement > 0.02 and active_sponsors == 0:
            opportunities.append({
                "type": "sponsor_ready",
                "account_platform": acct.platform.value if hasattr(acct.platform, 'value') else str(acct.platform),
                "followers": followers,
                "entity_id": str(acct.id),
                "entity_type": "creator_account",
                "expected_upside": followers * 0.05,  # $0.05 per follower sponsor value
                "action": "pursue_sponsor_deals",
                "source": "account_analysis",
            })

    # 5. Winning patterns not fully exploited
    winners_q = await db.execute(
        select(WinningPatternMemory).where(
            WinningPatternMemory.brand_id == brand_id,
            WinningPatternMemory.is_active.is_(True),
            WinningPatternMemory.win_score >= 0.7,
        ).order_by(WinningPatternMemory.win_score.desc()).limit(5)
    )
    for pat in winners_q.scalars().all():
        if (pat.usage_count or 0) < 5:
            opportunities.append({
                "type": "underexploited_winner",
                "pattern_name": pat.pattern_name,
                "win_score": pat.win_score,
                "usage_count": pat.usage_count,
                "entity_id": str(pat.id),
                "entity_type": "winning_pattern",
                "expected_upside": pat.win_score * 200,
                "action": "scale_winning_pattern",
                "source": "pattern_memory",
            })

    # Sort by expected upside
    opportunities.sort(key=lambda x: x.get("expected_upside", 0), reverse=True)
    return opportunities[:20]


# ══════════════════════════════════════════════════════════════════════
# ENGINE 3: REVENUE ALLOCATION
# ══════════════════════════════════════════════════════════════════════

async def compute_revenue_allocation(
    db: AsyncSession, brand_id: uuid.UUID,
) -> dict:
    """Where should effort go? Ranked by revenue upside × margin × repeatability."""
    now = datetime.now(timezone.utc)
    day_30 = now - timedelta(days=30)

    # Revenue by source from ledger
    by_source_q = await db.execute(
        select(RevenueLedgerEntry.revenue_source_type, func.sum(RevenueLedgerEntry.gross_amount),
               func.count())
        .where(RevenueLedgerEntry.brand_id == brand_id, RevenueLedgerEntry.occurred_at >= day_30,
               RevenueLedgerEntry.is_active.is_(True), RevenueLedgerEntry.is_refund.is_(False))
        .group_by(RevenueLedgerEntry.revenue_source_type)
    )
    source_data = {}
    for row in by_source_q.all():
        source_data[str(row[0])] = {"revenue": float(row[1] or 0), "count": row[2]}

    total_rev = sum(d["revenue"] for d in source_data.values())

    # Score each source for allocation priority
    allocations = []
    source_traits = {
        "affiliate_commission": {"margin": 0.95, "payout_speed": 0.6, "repeatability": 0.9, "operational_load": 0.1, "scalability": 0.9},
        "sponsor_payment": {"margin": 0.85, "payout_speed": 0.3, "repeatability": 0.5, "operational_load": 0.7, "scalability": 0.6},
        "service_fee": {"margin": 0.7, "payout_speed": 0.8, "repeatability": 0.6, "operational_load": 0.9, "scalability": 0.3},
        "consulting_fee": {"margin": 0.8, "payout_speed": 0.7, "repeatability": 0.5, "operational_load": 0.8, "scalability": 0.4},
        "product_sale": {"margin": 0.9, "payout_speed": 0.9, "repeatability": 0.8, "operational_load": 0.3, "scalability": 0.8},
        "digital_product": {"margin": 0.95, "payout_speed": 0.9, "repeatability": 0.9, "operational_load": 0.2, "scalability": 0.95},
        "ad_revenue": {"margin": 1.0, "payout_speed": 0.4, "repeatability": 0.8, "operational_load": 0.05, "scalability": 0.7},
        "lead_gen_fee": {"margin": 0.85, "payout_speed": 0.5, "repeatability": 0.7, "operational_load": 0.4, "scalability": 0.7},
    }

    for source_type, traits in source_traits.items():
        data = source_data.get(source_type, {"revenue": 0, "count": 0})
        revenue = data["revenue"]
        count = data["count"]

        # Composite score: weights real revenue performance + structural traits
        revenue_momentum = min(1.0, revenue / max(total_rev * 0.3, 1)) if total_rev > 0 else 0
        allocation_score = (
            0.25 * revenue_momentum +
            0.20 * traits["margin"] +
            0.15 * traits["repeatability"] +
            0.15 * traits["scalability"] +
            0.10 * traits["payout_speed"] +
            0.15 * (1.0 - traits["operational_load"])
        )

        allocations.append({
            "source_type": source_type,
            "current_revenue_30d": revenue,
            "current_share_pct": round(revenue / total_rev * 100, 1) if total_rev > 0 else 0,
            "transaction_count": count,
            "allocation_score": round(allocation_score, 3),
            "traits": traits,
            "recommendation": "scale" if allocation_score > 0.6 else "maintain" if allocation_score > 0.35 else "reduce",
        })

    allocations.sort(key=lambda x: x["allocation_score"], reverse=True)
    return {"total_revenue_30d": total_rev, "allocations": allocations}


# ══════════════════════════════════════════════════════════════════════
# ENGINE 4: SUPPRESSION TARGETS
# ══════════════════════════════════════════════════════════════════════

async def compute_suppression_targets(
    db: AsyncSession, brand_id: uuid.UUID,
) -> list[dict]:
    """What should be stopped? Weak offers, dead patterns, low-ROI paths."""
    targets = []

    # Losing patterns
    losers_q = await db.execute(
        select(LosingPatternMemory).where(
            LosingPatternMemory.brand_id == brand_id,
            LosingPatternMemory.is_active.is_(True),
        ).order_by(LosingPatternMemory.fail_score.desc()).limit(10)
    )
    for p in losers_q.scalars().all():
        targets.append({
            "type": "losing_pattern",
            "name": p.pattern_name,
            "fail_score": p.fail_score,
            "reason": p.suppress_reason,
            "action": "suppress_pattern",
        })

    # Active suppression rules
    rules_q = await db.execute(
        select(SuppressionRule).where(
            SuppressionRule.brand_id == brand_id,
            SuppressionRule.is_active.is_(True),
        ).limit(10)
    )
    for r in rules_q.scalars().all():
        targets.append({
            "type": "active_suppression",
            "family_type": r.family_type,
            "family_key": r.family_key,
            "mode": r.suppression_mode,
            "action": "already_suppressed",
        })

    # Failure families with high failure count
    failures_q = await db.execute(
        select(FailureFamilyReport).where(
            FailureFamilyReport.brand_id == brand_id,
            FailureFamilyReport.failure_count >= 3,
        ).order_by(FailureFamilyReport.failure_count.desc()).limit(5)
    )
    for f in failures_q.scalars().all():
        targets.append({
            "type": "failure_family",
            "family_type": f.family_type,
            "family_key": f.family_key,
            "failure_count": f.failure_count,
            "recommended_alternative": f.recommended_alternative,
            "action": "suppress_and_replace",
        })

    # Brain suppress decisions
    suppress_decisions = await db.execute(
        select(BrainDecision).where(
            BrainDecision.brand_id == brand_id,
            BrainDecision.is_active.is_(True),
            BrainDecision.decision_class.in_(["suppress", "throttle", "kill"]),
        ).limit(5)
    )
    for d in suppress_decisions.scalars().all():
        targets.append({
            "type": "brain_decision",
            "decision_class": d.decision_class,
            "objective": d.objective,
            "explanation": d.explanation[:200] if d.explanation else None,
            "action": "execute_suppression",
        })

    return targets


# ══════════════════════════════════════════════════════════════════════
# ENGINE 5: REVENUE MEMORY
# ══════════════════════════════════════════════════════════════════════

async def get_revenue_memory(
    db: AsyncSession, brand_id: uuid.UUID,
) -> dict:
    """What worked, for whom, in what niche, on what platform, at what margin."""
    # Winning patterns — what content patterns produce revenue
    winners_q = await db.execute(
        select(WinningPatternMemory).where(
            WinningPatternMemory.brand_id == brand_id,
            WinningPatternMemory.is_active.is_(True),
        ).order_by(WinningPatternMemory.win_score.desc()).limit(15)
    )
    patterns = [
        {"type": p.pattern_type, "name": p.pattern_name, "score": p.win_score,
         "platform": p.platform, "niche": p.niche, "band": p.performance_band,
         "usage_count": p.usage_count, "confidence": p.confidence}
        for p in winners_q.scalars().all()
    ]

    # Promoted rules — what experiments won
    rules_q = await db.execute(
        select(PromotedWinnerRule).where(
            PromotedWinnerRule.brand_id == brand_id,
            PromotedWinnerRule.is_active.is_(True),
        ).order_by(PromotedWinnerRule.weight_boost.desc()).limit(10)
    )
    promoted = [
        {"rule_type": r.rule_type, "key": r.rule_key, "value": r.rule_value,
         "boost": r.weight_boost, "platform": r.target_platform}
        for r in rules_q.scalars().all()
    ]

    # Learning entries — explicit memory records
    memory_q = await db.execute(
        select(MemoryEntry).where(
            MemoryEntry.brand_id == brand_id,
        ).order_by(MemoryEntry.confidence.desc()).limit(15)
    )
    learning = [
        {"type": m.memory_type, "key": m.key, "value": m.value,
         "confidence": m.confidence, "reinforced": m.times_reinforced}
        for m in memory_q.scalars().all()
    ]

    # Revenue by source from ledger (what monetization paths work)
    by_source_q = await db.execute(
        select(RevenueLedgerEntry.revenue_source_type, func.sum(RevenueLedgerEntry.gross_amount),
               func.avg(RevenueLedgerEntry.net_amount / RevenueLedgerEntry.gross_amount))
        .where(RevenueLedgerEntry.brand_id == brand_id, RevenueLedgerEntry.is_active.is_(True),
               RevenueLedgerEntry.is_refund.is_(False), RevenueLedgerEntry.gross_amount > 0)
        .group_by(RevenueLedgerEntry.revenue_source_type)
    )
    revenue_by_source = {str(r[0]): {"total": float(r[1] or 0), "avg_margin": round(float(r[2] or 0), 3)}
                         for r in by_source_q.all()}

    return {
        "winning_patterns": patterns,
        "promoted_rules": promoted,
        "learning_entries": learning,
        "revenue_by_source": revenue_by_source,
        "total_signals": len(patterns) + len(promoted) + len(learning),
    }


# ══════════════════════════════════════════════════════════════════════
# ENGINE 6: MONETIZATION MIX
# ══════════════════════════════════════════════════════════════════════

async def compute_monetization_mix(
    db: AsyncSession, brand_id: uuid.UUID,
) -> dict:
    """Current vs recommended monetization mix per brand."""
    now = datetime.now(timezone.utc)
    day_90 = now - timedelta(days=90)

    # Current mix from ledger
    mix_q = await db.execute(
        select(RevenueLedgerEntry.revenue_source_type, func.sum(RevenueLedgerEntry.gross_amount))
        .where(RevenueLedgerEntry.brand_id == brand_id, RevenueLedgerEntry.occurred_at >= day_90,
               RevenueLedgerEntry.is_active.is_(True), RevenueLedgerEntry.is_refund.is_(False))
        .group_by(RevenueLedgerEntry.revenue_source_type)
    )
    current_raw = {str(r[0]): float(r[1] or 0) for r in mix_q.all()}
    total = sum(current_raw.values())

    current_mix = {}
    for k, v in current_raw.items():
        current_mix[k] = round(v / total * 100, 1) if total > 0 else 0

    # Recommended mix (based on allocation scores)
    alloc = await compute_revenue_allocation(db, brand_id)
    total_score = sum(a["allocation_score"] for a in alloc["allocations"])
    recommended_mix = {}
    for a in alloc["allocations"]:
        recommended_mix[a["source_type"]] = round(
            a["allocation_score"] / total_score * 100, 1
        ) if total_score > 0 else 0

    # Gaps: where current mix diverges from recommended
    gaps = []
    all_sources = set(list(current_mix.keys()) + list(recommended_mix.keys()))
    for source in all_sources:
        current_pct = current_mix.get(source, 0)
        recommended_pct = recommended_mix.get(source, 0)
        delta = recommended_pct - current_pct
        if abs(delta) > 5:
            gaps.append({
                "source": source,
                "current_pct": current_pct,
                "recommended_pct": recommended_pct,
                "delta": round(delta, 1),
                "action": "increase" if delta > 0 else "decrease",
            })

    gaps.sort(key=lambda x: abs(x["delta"]), reverse=True)

    return {
        "current_mix": current_mix,
        "recommended_mix": recommended_mix,
        "total_revenue_90d": total,
        "gaps": gaps,
        "diversification_score": round(1.0 - max(current_mix.values()) / 100, 2) if current_mix else 0,
    }


# ══════════════════════════════════════════════════════════════════════
# ENGINE 7: NEXT-BEST REVENUE ACTIONS
# ══════════════════════════════════════════════════════════════════════

async def get_next_best_revenue_actions(
    db: AsyncSession, brand_id: uuid.UUID,
    org_id: Optional[uuid.UUID] = None,
) -> list[dict]:
    """The master 'what to do next' engine. Top actions ranked by expected value."""
    actions = []

    # Pull from all engines
    opportunities = await detect_revenue_opportunities(db, brand_id)
    suppressions = await compute_suppression_targets(db, brand_id)
    mix = await compute_monetization_mix(db, brand_id)

    # Convert opportunities to actions
    for opp in opportunities[:5]:
        actions.append({
            "action": opp.get("action", "pursue_opportunity"),
            "description": f"{opp['type']}: {opp.get('title', opp.get('offer_name', opp.get('pattern_name', 'opportunity')))}",
            "expected_value": opp.get("expected_upside", 0),
            "priority": "high" if opp.get("expected_upside", 0) > 200 else "medium",
            "source": opp.get("source", "opportunity_engine"),
            "entity_type": opp.get("entity_type"),
            "entity_id": opp.get("entity_id"),
        })

    # Convert suppressions to actions
    for sup in suppressions[:3]:
        if sup["type"] != "active_suppression":  # Skip already-suppressed
            actions.append({
                "action": "suppress",
                "description": f"Stop: {sup['type']} — {sup.get('name', sup.get('family_key', 'unknown'))}",
                "expected_value": 0,  # Suppressions save cost, not generate revenue
                "priority": "medium",
                "source": "suppression_engine",
            })

    # Convert mix gaps to actions
    for gap in mix.get("gaps", [])[:2]:
        if gap["action"] == "increase":
            actions.append({
                "action": "increase_monetization_path",
                "description": f"Increase {gap['source']}: currently {gap['current_pct']}%, recommended {gap['recommended_pct']}%",
                "expected_value": abs(gap["delta"]) * mix.get("total_revenue_90d", 0) / 100,
                "priority": "high" if abs(gap["delta"]) > 15 else "medium",
                "source": "mix_engine",
            })

    # Sort by expected value (revenue-generating actions first)
    actions.sort(key=lambda x: x.get("expected_value", 0), reverse=True)
    return actions[:10]


# ══════════════════════════════════════════════════════════════════════
# COMMAND CENTER: ALL-IN-ONE VIEW
# ══════════════════════════════════════════════════════════════════════

async def get_revenue_command_center(
    db: AsyncSession, brand_id: uuid.UUID,
    org_id: Optional[uuid.UUID] = None,
) -> dict:
    """The complete revenue maximization picture in one call."""
    from apps.api.services.monetization_bridge import get_brand_revenue_state, get_ledger_summary

    revenue = await get_brand_revenue_state(db, brand_id)
    ledger = await get_ledger_summary(db, brand_id)
    fit = await compute_creator_monetization_fit(db, brand_id)
    opportunities = await detect_revenue_opportunities(db, brand_id)
    allocation = await compute_revenue_allocation(db, brand_id)
    suppressions = await compute_suppression_targets(db, brand_id)
    memory = await get_revenue_memory(db, brand_id)
    mix = await compute_monetization_mix(db, brand_id)
    next_actions = await get_next_best_revenue_actions(db, brand_id, org_id)

    return {
        "revenue": revenue,
        "ledger_summary": ledger,
        "creator_fit": fit[:5],  # Top 5 accounts
        "opportunities": opportunities[:10],
        "allocation": allocation,
        "suppressions": suppressions[:10],
        "memory_signals": memory["total_signals"],
        "monetization_mix": mix,
        "next_actions": next_actions,
        "opportunity_count": len(opportunities),
        "suppression_count": len(suppressions),
    }


# ══════════════════════════════════════════════════════════════════════
# AUTOMATION: AUTO-SURFACE REVENUE ACTIONS
# ══════════════════════════════════════════════════════════════════════

async def auto_surface_revenue_actions(
    db: AsyncSession, org_id: uuid.UUID, brand_id: uuid.UUID,
) -> list[dict]:
    """Automatically create OperatorActions from revenue intelligence.

    Called by workers after recompute. Translates engine outputs into
    actionable items for the control layer.
    """
    created = []

    next_actions = await get_next_best_revenue_actions(db, brand_id, org_id)

    for action in next_actions[:5]:
        if action.get("expected_value", 0) > 50 or action.get("priority") == "high":
            op_action = await emit_action(
                db, org_id=org_id,
                action_type=action["action"],
                title=action["description"][:200],
                description=f"Expected value: ${action.get('expected_value', 0):.0f}. Source: {action.get('source', 'revenue_engine')}.",
                category="monetization",
                priority=action.get("priority", "medium"),
                brand_id=brand_id,
                entity_type=action.get("entity_type"),
                entity_id=uuid.UUID(action["entity_id"]) if action.get("entity_id") else None,
                source_module="revenue_maximizer",
            )
            created.append({"action_id": str(op_action.id), "type": action["action"]})

    await db.flush()
    return created
