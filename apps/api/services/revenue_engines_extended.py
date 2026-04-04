"""Revenue Engines Extended — engines 8-17 for maximum revenue capability.

These 10 engines complete the revenue maximization machine by adding:
- Simulation (what-if modeling before committing effort)
- Margin-first optimization (net revenue > gross revenue)
- Creator archetypes (classify → route → package)
- Offer packaging (bundles, upsells, continuity)
- Revenue experiments (hypothesis → test → promote/suppress)
- Payout speed intelligence (how fast does money arrive)
- Revenue leak detection (find and repair lost money)
- Creator portfolio allocation (treat accounts like capital)
- Cross-platform compounding (wins cascade to follow-on actions)
- Revenue durability scoring (short-term vs durable money)

Each engine produces ranked outputs and real actions.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.failure_family import FailureFamilyReport
from packages.db.models.offers import Offer, SponsorOpportunity, SponsorProfile
from packages.db.models.pattern_memory import LosingPatternMemory, WinningPatternMemory
from packages.db.models.publishing import PerformanceMetric
from packages.db.models.revenue_ledger import RevenueLedgerEntry

logger = structlog.get_logger()


# ══════════════════════════════════════════════════════════════════════
# ENGINE 8: REVENUE SIMULATION
# ══════════════════════════════════════════════════════════════════════

async def simulate_revenue_scenario(
    db: AsyncSession, brand_id: uuid.UUID, *,
    scenario_type: str = "mix_shift",
    target_source: Optional[str] = None,
    target_pct: Optional[float] = None,
    output_multiplier: float = 1.0,
    suppress_sources: Optional[list] = None,
) -> dict:
    """Simulate a revenue scenario before committing effort.

    Scenarios: mix_shift, output_scale, suppress_channel, add_source.
    Returns projected gross/net/margin with confidence and delta vs current.
    """
    now = datetime.now(timezone.utc)
    day_90 = now - timedelta(days=90)

    # Current state from ledger
    current_q = await db.execute(
        select(RevenueLedgerEntry.revenue_source_type,
               func.sum(RevenueLedgerEntry.gross_amount),
               func.sum(RevenueLedgerEntry.net_amount),
               func.sum(RevenueLedgerEntry.platform_fee),
               func.count())
        .where(RevenueLedgerEntry.brand_id == brand_id,
               RevenueLedgerEntry.occurred_at >= day_90,
               RevenueLedgerEntry.is_active.is_(True),
               RevenueLedgerEntry.is_refund.is_(False))
        .group_by(RevenueLedgerEntry.revenue_source_type)
    )
    current = {}
    for row in current_q.all():
        current[str(row[0])] = {
            "gross": float(row[1] or 0), "net": float(row[2] or 0),
            "fees": float(row[3] or 0), "count": row[4],
        }

    total_gross = sum(d["gross"] for d in current.values())
    total_net = sum(d["net"] for d in current.values())

    # Simulate based on scenario
    projected = {}
    for source, data in current.items():
        multiplier = output_multiplier
        if suppress_sources and source in suppress_sources:
            multiplier = 0.0
        if target_source and source == target_source and target_pct is not None:
            # Shift this source to target_pct of total
            current_pct = data["gross"] / total_gross * 100 if total_gross > 0 else 0
            multiplier = (target_pct / current_pct) if current_pct > 0 else 1.0

        projected[source] = {
            "gross": data["gross"] * multiplier,
            "net": data["net"] * multiplier,
            "fees": data["fees"] * multiplier,
            "count": int(data["count"] * multiplier),
        }

    proj_gross = sum(d["gross"] for d in projected.values())
    proj_net = sum(d["net"] for d in projected.values())
    proj_margin = proj_net / proj_gross if proj_gross > 0 else 0

    # Confidence based on data volume
    total_entries = sum(d["count"] for d in current.values())
    confidence = min(0.9, total_entries / 100) if total_entries > 0 else 0.1

    return {
        "scenario_type": scenario_type,
        "current": {"gross_90d": total_gross, "net_90d": total_net,
                     "margin": total_net / total_gross if total_gross > 0 else 0},
        "projected": {"gross_90d": round(proj_gross, 2), "net_90d": round(proj_net, 2),
                       "margin": round(proj_margin, 3)},
        "delta": {"gross": round(proj_gross - total_gross, 2),
                  "net": round(proj_net - total_net, 2),
                  "pct_change": round((proj_gross - total_gross) / total_gross * 100, 1) if total_gross > 0 else 0},
        "confidence": round(confidence, 2),
        "projected_by_source": {k: {"gross": round(v["gross"], 2)} for k, v in projected.items()},
        "recommendation": "execute" if proj_net > total_net and confidence > 0.5 else "review" if proj_net > total_net else "reject",
    }


# ══════════════════════════════════════════════════════════════════════
# ENGINE 9: MARGIN-FIRST OPTIMIZER
# ══════════════════════════════════════════════════════════════════════

async def compute_margin_rankings(
    db: AsyncSession, brand_id: uuid.UUID,
) -> list[dict]:
    """Rank revenue paths by true value: net revenue, margin, speed, risk, durability."""
    now = datetime.now(timezone.utc)
    day_90 = now - timedelta(days=90)

    source_q = await db.execute(
        select(RevenueLedgerEntry.revenue_source_type,
               func.sum(RevenueLedgerEntry.gross_amount),
               func.sum(RevenueLedgerEntry.net_amount),
               func.sum(RevenueLedgerEntry.platform_fee),
               func.sum(RevenueLedgerEntry.cost),
               func.count(),
               func.count().filter(RevenueLedgerEntry.is_refund.is_(True)),
               func.count().filter(RevenueLedgerEntry.is_dispute.is_(True)))
        .where(RevenueLedgerEntry.brand_id == brand_id,
               RevenueLedgerEntry.occurred_at >= day_90,
               RevenueLedgerEntry.is_active.is_(True))
        .group_by(RevenueLedgerEntry.revenue_source_type)
    )

    # Structural traits per source type
    traits = {
        "affiliate_commission": {"payout_speed": 0.6, "repeatability": 0.9, "operational_load": 0.1, "durability": 0.7},
        "sponsor_payment": {"payout_speed": 0.3, "repeatability": 0.5, "operational_load": 0.7, "durability": 0.6},
        "service_fee": {"payout_speed": 0.8, "repeatability": 0.6, "operational_load": 0.9, "durability": 0.5},
        "consulting_fee": {"payout_speed": 0.7, "repeatability": 0.5, "operational_load": 0.8, "durability": 0.5},
        "product_sale": {"payout_speed": 0.9, "repeatability": 0.8, "operational_load": 0.3, "durability": 0.8},
        "digital_product": {"payout_speed": 0.9, "repeatability": 0.9, "operational_load": 0.2, "durability": 0.9},
        "ad_revenue": {"payout_speed": 0.4, "repeatability": 0.8, "operational_load": 0.05, "durability": 0.6},
        "lead_gen_fee": {"payout_speed": 0.5, "repeatability": 0.7, "operational_load": 0.4, "durability": 0.6},
    }

    rankings = []
    for row in source_q.all():
        source_type = str(row[0])
        gross = float(row[1] or 0)
        net = float(row[2] or 0)
        fees = float(row[3] or 0)
        costs = float(row[4] or 0)
        count = row[5] or 0
        refunds = row[6] or 0
        disputes = row[7] or 0

        if gross == 0:
            continue

        margin = net / gross if gross > 0 else 0
        refund_rate = refunds / count if count > 0 else 0
        dispute_rate = disputes / count if count > 0 else 0
        risk_score = min(1.0, refund_rate + dispute_rate)

        t = traits.get(source_type, {"payout_speed": 0.5, "repeatability": 0.5, "operational_load": 0.5, "durability": 0.5})

        # True value score: weighted composite
        true_value = (
            0.20 * min(1.0, net / 5000) +         # net revenue magnitude
            0.20 * margin +                         # margin quality
            0.15 * t["payout_speed"] +              # cash speed
            0.15 * t["repeatability"] +             # can we do it again
            0.10 * t["durability"] +                # will it last
            0.10 * (1.0 - t["operational_load"]) +  # operational efficiency
            0.10 * (1.0 - risk_score)               # risk-adjusted
        )

        recommendation = "scale" if true_value > 0.55 else "maintain" if true_value > 0.35 else "reduce" if true_value > 0.2 else "suppress"

        rankings.append({
            "source_type": source_type,
            "gross_90d": round(gross, 2), "net_90d": round(net, 2),
            "margin": round(margin, 3), "fees": round(fees, 2), "costs": round(costs, 2),
            "count": count, "refund_rate": round(refund_rate, 3), "dispute_rate": round(dispute_rate, 3),
            "payout_speed_score": t["payout_speed"],
            "repeatability_score": t["repeatability"],
            "durability_score": t["durability"],
            "operational_load_score": t["operational_load"],
            "risk_score": round(risk_score, 3),
            "true_value_score": round(true_value, 3),
            "recommendation": recommendation,
        })

    rankings.sort(key=lambda x: x["true_value_score"], reverse=True)
    return rankings


# ══════════════════════════════════════════════════════════════════════
# ENGINE 10: CREATOR ARCHETYPE ENGINE
# ══════════════════════════════════════════════════════════════════════

ARCHETYPES = [
    "affiliate_closer", "sponsor_magnet", "product_seller",
    "community_builder", "authority_educator", "entertainment_monetizer",
    "services_consultant", "lead_gen_specialist", "licensing_creator",
    "dtc_converter", "hybrid_multi_path",
]


async def classify_creator_archetypes(
    db: AsyncSession, brand_id: uuid.UUID,
) -> list[dict]:
    """Classify each account into creator archetypes with fit scores."""
    accounts = (await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )).scalars().all()

    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    niche = brand.niche if brand else "general"

    # Get ledger data per account
    acct_revenue = {}
    rev_q = await db.execute(
        select(RevenueLedgerEntry.creator_account_id, RevenueLedgerEntry.revenue_source_type,
               func.sum(RevenueLedgerEntry.gross_amount))
        .where(RevenueLedgerEntry.brand_id == brand_id, RevenueLedgerEntry.is_active.is_(True),
               RevenueLedgerEntry.creator_account_id.isnot(None))
        .group_by(RevenueLedgerEntry.creator_account_id, RevenueLedgerEntry.revenue_source_type)
    )
    for row in rev_q.all():
        aid = str(row[0])
        if aid not in acct_revenue:
            acct_revenue[aid] = {}
        acct_revenue[aid][str(row[1])] = float(row[2] or 0)

    results = []
    for acct in accounts:
        platform = acct.platform.value if hasattr(acct.platform, 'value') else str(acct.platform) if acct.platform else "unknown"
        followers = getattr(acct, 'follower_count', 0) or 0
        engagement = getattr(acct, 'engagement_rate', 0) or getattr(acct, 'ctr', 0) or 0
        rev_data = acct_revenue.get(str(acct.id), {})

        # Score each archetype
        scores = {}
        scores["affiliate_closer"] = min(1.0, 0.3 + (rev_data.get("affiliate_commission", 0) / 1000) + (0.2 if engagement > 0.03 else 0))
        scores["sponsor_magnet"] = min(1.0, 0.2 + (followers / 100000) + (rev_data.get("sponsor_payment", 0) / 5000))
        scores["product_seller"] = min(1.0, 0.2 + (rev_data.get("product_sale", 0) / 2000) + (0.3 if niche in ("education", "tech", "business") else 0))
        scores["community_builder"] = min(1.0, 0.2 + (engagement * 5) + (0.2 if followers > 10000 else 0))
        scores["authority_educator"] = min(1.0, 0.2 + (0.4 if niche in ("education", "business", "finance", "tech") else 0.1) + (0.2 if platform in ("youtube", "blog") else 0))
        scores["entertainment_monetizer"] = min(1.0, 0.2 + (rev_data.get("ad_revenue", 0) / 3000) + (0.3 if platform in ("youtube", "tiktok") else 0))
        scores["services_consultant"] = min(1.0, 0.2 + (rev_data.get("service_fee", 0) / 3000) + (0.3 if niche in ("business", "consulting", "marketing") else 0))
        scores["lead_gen_specialist"] = min(1.0, 0.15 + (rev_data.get("lead_gen_fee", 0) / 1000) + (0.3 if niche in ("business", "finance", "saas") else 0))
        scores["licensing_creator"] = min(1.0, 0.1 + (0.3 if platform in ("youtube", "instagram") else 0) + (0.2 if followers > 50000 else 0))
        scores["dtc_converter"] = min(1.0, 0.15 + (rev_data.get("product_sale", 0) / 1500) + (0.2 if platform in ("instagram", "tiktok") else 0))
        scores["hybrid_multi_path"] = min(1.0, len([v for v in rev_data.values() if v > 100]) * 0.25)

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary = ranked[0]
        secondary = ranked[1] if len(ranked) > 1 else ("none", 0)

        results.append({
            "account_id": str(acct.id),
            "platform": platform,
            "followers": followers,
            "primary_archetype": primary[0],
            "primary_confidence": round(primary[1], 3),
            "secondary_archetype": secondary[0],
            "secondary_confidence": round(secondary[1], 3),
            "archetype_scores": {k: round(v, 3) for k, v in scores.items()},
            "best_fit_paths": [r[0] for r in ranked[:3]],
            "poor_fit_paths": [r[0] for r in ranked[-3:]],
        })

    results.sort(key=lambda x: x["primary_confidence"], reverse=True)
    return results


# ══════════════════════════════════════════════════════════════════════
# ENGINE 11: OFFER PACKAGING ENGINE
# ══════════════════════════════════════════════════════════════════════

async def compute_packaging_recommendations(
    db: AsyncSession, brand_id: uuid.UUID,
) -> list[dict]:
    """Recommend entry → core → upsell → continuity packaging per offer."""
    offers = (await db.execute(
        select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
        .order_by(Offer.payout_amount.desc().nullslast())
    )).scalars().all()

    if not offers:
        return []

    recs = []
    # Sort by priority-weighted payout: low-priority offers rank lower even with decent payout
    sorted_offers = sorted(offers, key=lambda o: float(o.payout_amount or 0) * max(0.2, (o.priority or 0) / 10))

    for i, offer in enumerate(sorted_offers):
        payout = float(offer.payout_amount or 0)
        entry_offer = sorted_offers[0] if len(sorted_offers) > 1 and i > 0 else None
        upsell_offer = sorted_offers[-1] if len(sorted_offers) > 1 and i < len(sorted_offers) - 1 else None

        recs.append({
            "offer_id": str(offer.id),
            "offer_name": offer.name,
            "payout": payout,
            "role": "entry" if payout < 30 else "core" if payout < 150 else "premium",
            "packaging": {
                "entry_offer": {"id": str(entry_offer.id), "name": entry_offer.name, "payout": float(entry_offer.payout_amount or 0)} if entry_offer else None,
                "core_offer": {"id": str(offer.id), "name": offer.name, "payout": payout},
                "upsell_offer": {"id": str(upsell_offer.id), "name": upsell_offer.name, "payout": float(upsell_offer.payout_amount or 0)} if upsell_offer and upsell_offer.id != offer.id else None,
            },
            "actions": [
                "create_bundle" if len(sorted_offers) > 1 else None,
                "create_upsell_path" if upsell_offer else None,
                "test_pricing" if payout > 50 else None,
            ],
        })

    return [r for r in recs if r]


# ══════════════════════════════════════════════════════════════════════
# ENGINE 12: REVENUE EXPERIMENT ENGINE
# ══════════════════════════════════════════════════════════════════════

async def get_experiment_opportunities(
    db: AsyncSession, brand_id: uuid.UUID,
) -> list[dict]:
    """Identify what should be tested to increase revenue."""
    from packages.db.models.promote_winner import ActiveExperiment

    # Active experiments
    active = (await db.execute(
        select(ActiveExperiment).where(
            ActiveExperiment.brand_id == brand_id, ActiveExperiment.status == "active"
        )
    )).scalars().all()

    active_vars = {e.tested_variable for e in active}

    # What SHOULD be tested
    opportunities = []
    testable = [
        ("offer_pairing", "Which offer pairs produce the best combined revenue"),
        ("pricing_tier", "What price point maximizes revenue per offer"),
        ("content_format", "Which content format converts best for each offer"),
        ("platform_routing", "Which platform produces the highest ROI per offer"),
        ("cta_style", "Which CTA generates the most conversions"),
        ("hook_type", "Which hook drives the best engagement-to-revenue"),
        ("sponsor_structure", "What deal structure maximizes sponsor revenue"),
        ("monetization_mix", "What mix of revenue sources maximizes total revenue"),
    ]

    for var, hypothesis in testable:
        if var not in active_vars:
            opportunities.append({
                "tested_variable": var,
                "hypothesis": hypothesis,
                "status": "ready_to_launch",
                "priority": "high" if var in ("offer_pairing", "pricing_tier", "content_format") else "medium",
            })

    return {
        "active_experiments": [{"id": str(e.id), "variable": e.tested_variable, "status": e.status} for e in active],
        "opportunities": opportunities,
        "active_count": len(active),
        "opportunity_count": len(opportunities),
    }


# ══════════════════════════════════════════════════════════════════════
# ENGINE 13: PAYOUT SPEED INTELLIGENCE
# ══════════════════════════════════════════════════════════════════════

async def compute_payout_speed(
    db: AsyncSession, brand_id: uuid.UUID,
) -> list[dict]:
    """Score revenue paths by how fast money arrives."""
    now = datetime.now(timezone.utc)
    day_90 = now - timedelta(days=90)

    # Average time from occurred_at to confirmed_at / paid_out_at
    speed_q = await db.execute(
        select(RevenueLedgerEntry.revenue_source_type,
               func.count(),
               func.sum(RevenueLedgerEntry.gross_amount),
               func.count().filter(RevenueLedgerEntry.payment_state == "paid"),
               func.count().filter(RevenueLedgerEntry.payment_state == "pending"))
        .where(RevenueLedgerEntry.brand_id == brand_id,
               RevenueLedgerEntry.occurred_at >= day_90,
               RevenueLedgerEntry.is_active.is_(True),
               RevenueLedgerEntry.is_refund.is_(False))
        .group_by(RevenueLedgerEntry.revenue_source_type)
    )

    # Structural speed estimates (days to cash)
    speed_estimates = {
        "affiliate_commission": {"avg_days_to_cash": 45, "reliability": 0.8},
        "sponsor_payment": {"avg_days_to_cash": 60, "reliability": 0.6},
        "service_fee": {"avg_days_to_cash": 7, "reliability": 0.9},
        "consulting_fee": {"avg_days_to_cash": 14, "reliability": 0.85},
        "product_sale": {"avg_days_to_cash": 3, "reliability": 0.95},
        "digital_product": {"avg_days_to_cash": 2, "reliability": 0.95},
        "ad_revenue": {"avg_days_to_cash": 30, "reliability": 0.9},
        "lead_gen_fee": {"avg_days_to_cash": 21, "reliability": 0.7},
    }

    results = []
    for row in speed_q.all():
        source = str(row[0])
        count = row[1]
        gross = float(row[2] or 0)
        paid = row[3] or 0
        pending = row[4] or 0

        est = speed_estimates.get(source, {"avg_days_to_cash": 30, "reliability": 0.5})
        paid_rate = paid / count if count > 0 else 0
        speed_score = max(0, 1.0 - est["avg_days_to_cash"] / 90)

        results.append({
            "source_type": source,
            "total_entries": count,
            "total_gross": round(gross, 2),
            "paid_count": paid,
            "pending_count": pending,
            "paid_rate": round(paid_rate, 3),
            "avg_days_to_cash": est["avg_days_to_cash"],
            "reliability": est["reliability"],
            "speed_score": round(speed_score, 3),
            "recommendation": "prioritize" if speed_score > 0.7 else "acceptable" if speed_score > 0.4 else "slow_payer",
        })

    results.sort(key=lambda x: x["speed_score"], reverse=True)
    return results


# ══════════════════════════════════════════════════════════════════════
# ENGINE 14: REVENUE LEAK DETECTOR
# ══════════════════════════════════════════════════════════════════════

async def detect_revenue_leaks(
    db: AsyncSession, brand_id: uuid.UUID,
) -> list[dict]:
    """Aggressively detect lost or unrealized money."""
    leaks = []

    # 1. Unattributed revenue
    unattr_q = await db.execute(
        select(func.count(), func.sum(RevenueLedgerEntry.gross_amount)).where(
            RevenueLedgerEntry.brand_id == brand_id,
            RevenueLedgerEntry.attribution_state == "unattributed",
            RevenueLedgerEntry.is_refund.is_(False),
            RevenueLedgerEntry.is_active.is_(True),
        )
    )
    unattr = unattr_q.one()
    if (unattr[0] or 0) > 0:
        leaks.append({
            "leak_type": "unattributed_revenue",
            "severity": "high",
            "count": unattr[0],
            "estimated_lost": float(unattr[1] or 0),
            "action": "attribute_revenue",
            "description": f"{unattr[0]} revenue entries with no content/offer attribution",
        })

    # 2. Published content with no offer
    unmon_count = (await db.execute(
        select(func.count()).select_from(ContentItem).where(
            ContentItem.brand_id == brand_id, ContentItem.status == "published",
            ContentItem.offer_id.is_(None),
        )
    )).scalar() or 0
    if unmon_count > 0:
        leaks.append({
            "leak_type": "unmonetized_content",
            "severity": "high",
            "count": unmon_count,
            "estimated_lost": unmon_count * 50,  # Conservative per-content estimate
            "action": "assign_offers",
            "description": f"{unmon_count} published content items earning nothing",
        })

    # 3. Active offers with no content
    offer_count = (await db.execute(
        select(func.count()).select_from(Offer).where(
            Offer.brand_id == brand_id, Offer.is_active.is_(True),
        )
    )).scalar() or 0
    orphan_count = 0
    if offer_count > 0:
        offers_q = (await db.execute(
            select(Offer.id).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
        )).scalars().all()
        for oid in offers_q:
            ct = (await db.execute(
                select(func.count()).select_from(ContentItem).where(
                    ContentItem.brand_id == brand_id, ContentItem.offer_id == oid
                )
            )).scalar() or 0
            if ct == 0:
                orphan_count += 1
    if orphan_count > 0:
        leaks.append({
            "leak_type": "orphan_offers",
            "severity": "medium",
            "count": orphan_count,
            "estimated_lost": orphan_count * 200,
            "action": "create_content_for_offers",
            "description": f"{orphan_count} active offers with no content attached",
        })

    # 4. Stalled sponsor deals
    stalled = (await db.execute(
        select(func.count()).select_from(SponsorOpportunity).where(
            SponsorOpportunity.brand_id == brand_id,
            SponsorOpportunity.status.in_(["prospect", "negotiation"]),
        )
    )).scalar() or 0
    if stalled > 0:
        leaks.append({
            "leak_type": "stalled_sponsor_deals",
            "severity": "medium",
            "count": stalled,
            "estimated_lost": stalled * 1000,
            "action": "follow_up_deals",
            "description": f"{stalled} sponsor deals stalled in early stages",
        })

    # 5. Pending revenue too long
    pending = (await db.execute(
        select(func.count(), func.sum(RevenueLedgerEntry.gross_amount)).where(
            RevenueLedgerEntry.brand_id == brand_id,
            RevenueLedgerEntry.payment_state == "pending",
            RevenueLedgerEntry.occurred_at < datetime.now(timezone.utc) - timedelta(days=30),
            RevenueLedgerEntry.is_active.is_(True),
        )
    )).one()
    if (pending[0] or 0) > 0:
        leaks.append({
            "leak_type": "pending_too_long",
            "severity": "high",
            "count": pending[0],
            "estimated_lost": float(pending[1] or 0),
            "action": "follow_up_payments",
            "description": f"${float(pending[1] or 0):.0f} pending for 30+ days",
        })

    leaks.sort(key=lambda x: x.get("estimated_lost", 0), reverse=True)
    return leaks


# ══════════════════════════════════════════════════════════════════════
# ENGINE 15: CREATOR PORTFOLIO ALLOCATOR
# ══════════════════════════════════════════════════════════════════════

async def compute_portfolio_allocation(
    db: AsyncSession, brand_id: uuid.UUID,
) -> list[dict]:
    """Treat creators like capital allocation: who deserves more support?"""
    accounts = (await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )).scalars().all()

    now = datetime.now(timezone.utc)
    day_90 = now - timedelta(days=90)

    results = []
    for acct in accounts:
        # Revenue from this account
        acct_rev = (await db.execute(
            select(func.coalesce(func.sum(RevenueLedgerEntry.gross_amount), 0.0)).where(
                RevenueLedgerEntry.brand_id == brand_id,
                RevenueLedgerEntry.creator_account_id == acct.id,
                RevenueLedgerEntry.occurred_at >= day_90,
                RevenueLedgerEntry.is_active.is_(True),
            )
        )).scalar() or 0.0

        # Content count
        content_count = (await db.execute(
            select(func.count()).select_from(ContentItem).where(
                ContentItem.brand_id == brand_id, ContentItem.creator_account_id == acct.id,
            )
        )).scalar() or 0

        followers = getattr(acct, 'follower_count', 0) or 0
        engagement = getattr(acct, 'engagement_rate', 0) or getattr(acct, 'ctr', 0) or 0
        platform = acct.platform.value if hasattr(acct.platform, 'value') else str(acct.platform)

        # Portfolio score
        revenue_score = min(1.0, float(acct_rev) / 5000)
        content_score = min(1.0, content_count / 20)
        audience_score = min(1.0, followers / 50000)
        engagement_score = min(1.0, engagement * 10)
        scale_role = getattr(acct, 'scale_role', None) or ""

        # Accounts with scale_role="reduced" get a penalty — the machine deprioritized them
        scale_penalty = 0.3 if scale_role == "reduced" else 0.0

        portfolio_score = max(0, (
            0.40 * revenue_score +
            0.20 * engagement_score +
            0.20 * audience_score +
            0.20 * content_score
        ) - scale_penalty)

        # Force "reduced" accounts into pause tier regardless of score
        if scale_role == "reduced":
            tier = "pause"
        else:
            tier = "hero" if portfolio_score > 0.6 else "growth" if portfolio_score > 0.3 else "maintain" if portfolio_score > 0.1 else "pause"

        results.append({
            "account_id": str(acct.id),
            "platform": platform,
            "revenue_90d": round(float(acct_rev), 2),
            "content_count": content_count,
            "followers": followers,
            "portfolio_score": round(portfolio_score, 3),
            "tier": tier,
            "recommendation": "scale" if tier == "hero" else "grow" if tier == "growth" else "maintain" if tier == "maintain" else "reduce",
        })

    results.sort(key=lambda x: x["portfolio_score"], reverse=True)
    return results


# ══════════════════════════════════════════════════════════════════════
# ENGINE 16: CROSS-PLATFORM COMPOUNDING
# ══════════════════════════════════════════════════════════════════════

async def detect_compounding_opportunities(
    db: AsyncSession, brand_id: uuid.UUID,
) -> list[dict]:
    """A win on one platform should cascade to follow-on actions elsewhere."""
    opportunities = []

    # Find accounts with strong performance
    accounts = (await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )).scalars().all()

    platform_rev = {}
    for acct in accounts:
        platform = acct.platform.value if hasattr(acct.platform, 'value') else str(acct.platform)
        rev = (await db.execute(
            select(func.coalesce(func.sum(RevenueLedgerEntry.gross_amount), 0.0)).where(
                RevenueLedgerEntry.brand_id == brand_id,
                RevenueLedgerEntry.creator_account_id == acct.id,
                RevenueLedgerEntry.is_active.is_(True),
            )
        )).scalar() or 0.0
        if platform not in platform_rev or float(rev) > platform_rev[platform]["revenue"]:
            platform_rev[platform] = {"revenue": float(rev), "account_id": str(acct.id)}

    # Cross-platform cascades
    cascades = {
        "youtube": ["tiktok", "instagram", "blog"],
        "tiktok": ["instagram", "youtube"],
        "instagram": ["tiktok", "youtube", "pinterest"],
        "blog": ["youtube", "linkedin", "email_newsletter"],
        "linkedin": ["blog", "email_newsletter", "youtube"],
    }

    for platform, data in platform_rev.items():
        if data["revenue"] > 200:
            targets = cascades.get(platform, [])
            existing_platforms = {p for p in platform_rev.keys()}
            for target in targets:
                if target not in existing_platforms:
                    opportunities.append({
                        "type": "cross_platform_expansion",
                        "source_platform": platform,
                        "source_revenue": data["revenue"],
                        "target_platform": target,
                        "expected_uplift_pct": 20,
                        "action": "expand_to_platform",
                        "description": f"Strong ${data['revenue']:.0f} on {platform} → expand to {target}",
                    })

    # Winning patterns that could be applied elsewhere
    winners = (await db.execute(
        select(WinningPatternMemory).where(
            WinningPatternMemory.brand_id == brand_id,
            WinningPatternMemory.is_active.is_(True),
            WinningPatternMemory.win_score >= 0.7,
        ).limit(5)
    )).scalars().all()

    for pat in winners:
        if (pat.usage_count or 0) < 5:
            opportunities.append({
                "type": "pattern_replication",
                "pattern_name": pat.pattern_name,
                "win_score": pat.win_score,
                "current_usage": pat.usage_count,
                "action": "replicate_winning_pattern",
                "description": f"Winning pattern '{pat.pattern_name}' used only {pat.usage_count}x — scale it",
            })

    opportunities.sort(key=lambda x: x.get("source_revenue", x.get("win_score", 0)), reverse=True)
    return opportunities


# ══════════════════════════════════════════════════════════════════════
# ENGINE 17: REVENUE DURABILITY SCORING
# ══════════════════════════════════════════════════════════════════════

async def compute_durability_scores(
    db: AsyncSession, brand_id: uuid.UUID,
) -> list[dict]:
    """Score revenue paths by durability: short-term vs lasting money."""
    now = datetime.now(timezone.utc)

    # Revenue over 3 periods: 30d, 60d, 90d
    periods = [
        ("recent_30d", now - timedelta(days=30), now),
        ("prior_30d", now - timedelta(days=60), now - timedelta(days=30)),
        ("oldest_30d", now - timedelta(days=90), now - timedelta(days=60)),
    ]

    source_periods = {}
    for label, start, end in periods:
        q = await db.execute(
            select(RevenueLedgerEntry.revenue_source_type, func.sum(RevenueLedgerEntry.gross_amount))
            .where(RevenueLedgerEntry.brand_id == brand_id,
                   RevenueLedgerEntry.occurred_at >= start,
                   RevenueLedgerEntry.occurred_at < end,
                   RevenueLedgerEntry.is_active.is_(True),
                   RevenueLedgerEntry.is_refund.is_(False))
            .group_by(RevenueLedgerEntry.revenue_source_type)
        )
        for row in q.all():
            source = str(row[0])
            if source not in source_periods:
                source_periods[source] = {}
            source_periods[source][label] = float(row[1] or 0)

    durability_traits = {
        "affiliate_commission": {"defensibility": 0.5, "platform_dependence": 0.6, "copyability": 0.7},
        "sponsor_payment": {"defensibility": 0.6, "platform_dependence": 0.5, "copyability": 0.4},
        "service_fee": {"defensibility": 0.7, "platform_dependence": 0.2, "copyability": 0.3},
        "product_sale": {"defensibility": 0.8, "platform_dependence": 0.3, "copyability": 0.5},
        "digital_product": {"defensibility": 0.9, "platform_dependence": 0.2, "copyability": 0.4},
        "ad_revenue": {"defensibility": 0.3, "platform_dependence": 0.9, "copyability": 0.8},
        "lead_gen_fee": {"defensibility": 0.5, "platform_dependence": 0.4, "copyability": 0.5},
    }

    results = []
    for source, periods_data in source_periods.items():
        recent = periods_data.get("recent_30d", 0)
        prior = periods_data.get("prior_30d", 0)
        oldest = periods_data.get("oldest_30d", 0)

        # Trend stability
        values = [oldest, prior, recent]
        avg = sum(values) / len([v for v in values if v > 0]) if any(v > 0 for v in values) else 0
        volatility = sum(abs(v - avg) for v in values) / (avg * len(values)) if avg > 0 else 1.0

        # Growth trend
        if prior > 0:
            growth = (recent - prior) / prior
        else:
            growth = 1.0 if recent > 0 else 0

        traits = durability_traits.get(source, {"defensibility": 0.5, "platform_dependence": 0.5, "copyability": 0.5})

        durability_score = (
            0.25 * traits["defensibility"] +
            0.20 * (1.0 - volatility) +
            0.20 * (1.0 - traits["platform_dependence"]) +
            0.15 * (1.0 - traits["copyability"]) +
            0.10 * min(1.0, max(0, growth + 0.5)) +
            0.10 * min(1.0, recent / 1000) if recent > 0 else 0
        )

        recommendation = "exploit" if durability_score > 0.6 else "diversify" if durability_score > 0.4 else "stabilize" if durability_score > 0.2 else "reduce"

        results.append({
            "source_type": source,
            "recent_30d": round(recent, 2),
            "trend": "growing" if growth > 0.1 else "stable" if growth > -0.1 else "declining",
            "volatility": round(min(1.0, volatility), 3),
            "defensibility": traits["defensibility"],
            "platform_dependence": traits["platform_dependence"],
            "durability_score": round(max(0, min(1, durability_score)), 3),
            "recommendation": recommendation,
        })

    results.sort(key=lambda x: x["durability_score"], reverse=True)
    return results
