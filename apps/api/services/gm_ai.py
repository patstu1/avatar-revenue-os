"""GM AI — The General Manager of the Revenue Machine.

This is not a chatbot. This is the strategic operating brain that:
1. Scans the entire system state (accounts, platforms, revenue, offers, patterns)
2. Produces a scale blueprint (what platforms, how many accounts, which niches, what timing)
3. Issues operating directives (what to do now, what to ramp, what to suppress)
4. Maintains persistent state across conversations
5. Updates the plan as conditions change

The GM reads from ALL engines, ALL ledger data, ALL pattern memory,
ALL account state, and ALL growth intelligence to produce real plans.

It communicates like a serious operator: direct, data-driven, revenue-obsessed,
risk-aware, and always thinking about scale timing.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.learning import MemoryEntry
from packages.db.models.offers import Offer, SponsorProfile, SponsorOpportunity
from packages.db.models.pattern_memory import WinningPatternMemory, LosingPatternMemory
from packages.db.models.publishing import PerformanceMetric
from packages.db.models.revenue_ledger import RevenueLedgerEntry
from packages.db.models.system_events import OperatorAction, SystemEvent

logger = structlog.get_logger()


async def run_full_scan(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    """Phase 1: Full system scan. Reads everything the GM needs to make decisions.

    This is the research phase — gathering all data before producing a blueprint.
    """
    now = datetime.now(timezone.utc)
    day_30 = now - timedelta(days=30)
    day_90 = now - timedelta(days=90)

    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        return {"error": "Brand not found"}

    # ── Accounts scan ──
    accounts = (await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )).scalars().all()

    account_data = []
    for acct in accounts:
        platform = acct.platform.value if hasattr(acct.platform, 'value') else str(acct.platform) if acct.platform else "unknown"
        followers = getattr(acct, 'follower_count', 0) or 0
        engagement = getattr(acct, 'engagement_rate', 0) or getattr(acct, 'ctr', 0) or 0
        scale_role = getattr(acct, 'scale_role', None) or "active"
        saturation = getattr(acct, 'saturation_score', 0) or 0
        fatigue = getattr(acct, 'fatigue_score', 0) or 0

        acct_rev = (await db.execute(
            select(func.coalesce(func.sum(RevenueLedgerEntry.gross_amount), 0.0)).where(
                RevenueLedgerEntry.creator_account_id == acct.id, RevenueLedgerEntry.is_active.is_(True)
            )
        )).scalar() or 0.0

        content_count = (await db.execute(
            select(func.count()).select_from(ContentItem).where(ContentItem.creator_account_id == acct.id)
        )).scalar() or 0

        account_data.append({
            "id": str(acct.id), "platform": platform, "followers": followers,
            "engagement": engagement, "scale_role": scale_role,
            "saturation": saturation, "fatigue": fatigue,
            "revenue": float(acct_rev), "content_count": content_count,
        })

    # ── Revenue scan ──
    rev_by_source = {}
    rev_q = await db.execute(
        select(RevenueLedgerEntry.revenue_source_type, func.sum(RevenueLedgerEntry.gross_amount), func.count())
        .where(RevenueLedgerEntry.brand_id == brand_id, RevenueLedgerEntry.occurred_at >= day_90,
               RevenueLedgerEntry.is_active.is_(True), RevenueLedgerEntry.is_refund.is_(False))
        .group_by(RevenueLedgerEntry.revenue_source_type)
    )
    for r in rev_q.all():
        rev_by_source[str(r[0])] = {"total": float(r[1] or 0), "count": r[2]}
    total_revenue = sum(d["total"] for d in rev_by_source.values())

    # ── Offers scan ──
    offers = (await db.execute(
        select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
    )).scalars().all()
    offer_data = [{"id": str(o.id), "name": o.name, "epc": float(o.epc or 0),
                    "payout": float(o.payout_amount or 0), "priority": o.priority or 0}
                   for o in offers]

    # ── Patterns scan ──
    winners = (await db.execute(
        select(WinningPatternMemory).where(WinningPatternMemory.brand_id == brand_id, WinningPatternMemory.is_active.is_(True))
        .order_by(WinningPatternMemory.win_score.desc()).limit(10)
    )).scalars().all()
    losers = (await db.execute(
        select(LosingPatternMemory).where(LosingPatternMemory.brand_id == brand_id, LosingPatternMemory.is_active.is_(True))
        .order_by(LosingPatternMemory.fail_score.desc()).limit(5)
    )).scalars().all()

    # ── Sponsors scan ──
    sponsor_count = (await db.execute(
        select(func.count()).select_from(SponsorProfile).where(SponsorProfile.brand_id == brand_id)
    )).scalar() or 0
    active_deals = (await db.execute(
        select(func.count()).select_from(SponsorOpportunity).where(
            SponsorOpportunity.brand_id == brand_id, SponsorOpportunity.status.in_(["negotiation", "active", "delivering"])
        )
    )).scalar() or 0

    # ── Content scan ──
    content_total = (await db.execute(select(func.count()).select_from(ContentItem).where(ContentItem.brand_id == brand_id))).scalar() or 0
    content_published = (await db.execute(
        select(func.count()).select_from(ContentItem).where(ContentItem.brand_id == brand_id, ContentItem.status == "published")
    )).scalar() or 0
    content_unmonetized = (await db.execute(
        select(func.count()).select_from(ContentItem).where(
            ContentItem.brand_id == brand_id, ContentItem.status == "published", ContentItem.offer_id.is_(None)
        )
    )).scalar() or 0

    # ── Actions scan ──
    pending_actions = (await db.execute(
        select(func.count()).select_from(OperatorAction).where(
            OperatorAction.brand_id == brand_id, OperatorAction.status == "pending"
        )
    )).scalar() or 0

    # ── Memory scan ──
    memory_count = (await db.execute(
        select(func.count()).select_from(MemoryEntry).where(MemoryEntry.brand_id == brand_id)
    )).scalar() or 0

    # Aggregate platform data
    platforms = {}
    for a in account_data:
        p = a["platform"]
        if p not in platforms:
            platforms[p] = {"accounts": 0, "total_followers": 0, "total_revenue": 0, "total_content": 0}
        platforms[p]["accounts"] += 1
        platforms[p]["total_followers"] += a["followers"]
        platforms[p]["total_revenue"] += a["revenue"]
        platforms[p]["total_content"] += a["content_count"]

    return {
        "brand": {"id": str(brand_id), "name": brand.name, "niche": brand.niche},
        "accounts": {"total": len(account_data), "data": account_data},
        "platforms": platforms,
        "revenue": {"total_90d": total_revenue, "by_source": rev_by_source},
        "offers": {"total": len(offer_data), "data": offer_data},
        "patterns": {
            "winning": [{"type": w.pattern_type, "name": w.pattern_name, "score": w.win_score} for w in winners],
            "losing": [{"type": l.pattern_type, "name": l.pattern_name, "score": l.fail_score} for l in losers],
        },
        "sponsors": {"profiles": sponsor_count, "active_deals": active_deals},
        "content": {"total": content_total, "published": content_published, "unmonetized": content_unmonetized},
        "actions_pending": pending_actions,
        "memory_entries": memory_count,
        "scan_timestamp": now.isoformat(),
    }


async def generate_scale_blueprint(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    """Phase 2: From scan data, produce the exact scale blueprint.

    This is the GM's strategic plan: what platforms, how many accounts,
    which niches, what monetization, what timing, what sequence.
    """
    scan = await run_full_scan(db, brand_id)
    if "error" in scan:
        return scan

    niche = scan["brand"]["niche"] or "general"
    platforms = scan["platforms"]
    accounts = scan["accounts"]["data"]
    revenue = scan["revenue"]
    offers = scan["offers"]["data"]
    patterns = scan["patterns"]
    total_followers = sum(a["followers"] for a in accounts)
    total_revenue = revenue["total_90d"]

    # ── Determine current phase from OPERATING SIGNALS, not dollar bands ──
    # Phase is derived from what the machine can actually do, not arbitrary thresholds.
    has_accounts = len(accounts) > 0
    has_audience = total_followers > 0
    has_content = scan["content"]["published"] > 0
    has_offers = len(offers) > 0
    has_revenue = total_revenue > 0
    has_patterns = len(patterns["winning"]) > 0
    has_multiple_sources = len(revenue["by_source"]) >= 2
    has_sponsor_activity = scan["sponsors"]["active_deals"] > 0
    monetization_density = scan["content"]["published"] - scan["content"]["unmonetized"]  # content WITH offers
    content_velocity = scan["content"]["total"]  # total content produced
    platform_count = len(platforms)
    account_count = len(accounts)

    # Revenue per follower (yield efficiency)
    rev_per_follower = total_revenue / total_followers if total_followers > 0 else 0
    # Monetization rate
    mon_rate = monetization_density / scan["content"]["published"] if scan["content"]["published"] > 0 else 0

    if not has_accounts:
        phase = "cold_start"
    elif not has_content:
        phase = "signal_formation"
    elif not has_revenue and has_content and has_offers:
        phase = "proof_of_monetization"
    elif not has_revenue:
        phase = "warmup"
    elif not has_patterns and has_revenue:
        phase = "repeatable_monetization"
    elif has_multiple_sources and has_patterns:
        if mon_rate > 0.7 and platform_count >= 3:
            phase = "monetization_density_optimization"
        elif account_count >= 5 or platform_count >= 3:
            phase = "aggressive_expansion"
        else:
            phase = "high_yield_scaling"
    elif has_patterns and not has_multiple_sources:
        phase = "channel_diversification"
    elif has_revenue and has_patterns:
        phase = "portfolio_compounding"
    else:
        phase = "risk_managed_scale"

    # ── Platform strategy ──
    platform_plan = []
    existing_platforms = set(platforms.keys())

    # Platform priority by niche
    niche_platforms = {
        "business": ["youtube", "linkedin", "x", "tiktok", "email_newsletter"],
        "tech": ["youtube", "x", "reddit", "tiktok", "blog"],
        "finance": ["youtube", "tiktok", "x", "linkedin", "blog"],
        "education": ["youtube", "tiktok", "instagram", "blog"],
        "entertainment": ["tiktok", "youtube", "instagram", "x"],
        "health": ["youtube", "instagram", "tiktok", "pinterest"],
        "marketing": ["youtube", "linkedin", "x", "tiktok", "blog"],
    }
    priority_platforms = niche_platforms.get(niche, ["youtube", "tiktok", "instagram", "linkedin"])

    for i, platform in enumerate(priority_platforms):
        existing = platforms.get(platform, {})
        is_active = platform in existing_platforms

        if is_active:
            acct_count = existing.get("accounts", 0)
            rev = existing.get("total_revenue", 0)
            action = "scale" if rev > 100 else "maintain" if acct_count > 0 else "warmup"
            target_accounts = max(acct_count, 2 if phase in ("scaling", "optimizing") else 1)
        else:
            action = "launch" if i < 3 else "plan"
            target_accounts = 1
            acct_count = 0

        platform_plan.append({
            "platform": platform,
            "priority": i + 1,
            "current_accounts": acct_count,
            "target_accounts": target_accounts,
            "action": action,
            "timing": "immediate" if action in ("scale", "warmup") else "week_1" if action == "launch" and i < 2 else "week_2_4",
        })

    # ── Account archetype strategy ──
    archetype_plan = []
    # ── Archetype strategy — derived from current operating signals ──
    if not has_revenue:
        archetype_plan = [
            {"archetype": "authority_educator", "count": 2, "purpose": "Build trust and audience before monetization"},
            {"archetype": "affiliate_closer", "count": 1, "purpose": "Prepare for first revenue signal"},
        ]
    elif not has_multiple_sources:
        archetype_plan = [
            {"archetype": "affiliate_closer", "count": 2, "purpose": "Proven revenue — scale it"},
            {"archetype": "authority_educator", "count": 1, "purpose": "Continue audience growth"},
            {"archetype": "sponsor_magnet", "count": 1, "purpose": "Open second revenue source"},
        ]
    else:
        archetype_plan = [
            {"archetype": "affiliate_closer", "count": 3, "purpose": "Scale the proven conversion model"},
            {"archetype": "sponsor_magnet", "count": 2, "purpose": "Maximize deal flow"},
            {"archetype": "product_seller", "count": 1, "purpose": "Add digital product revenue"},
            {"archetype": "services_consultant", "count": 1, "purpose": "Add high-ticket service revenue"},
        ]

    # ── Monetization timing — derived from operating constraints, not dollar bands ──
    monetization_plan = {
        "affiliate": "active" if has_offers and has_content else "activate_when_first_offer_and_content_exist",
        "sponsor": "active" if has_sponsor_activity else ("pursue_now" if has_audience and has_content else "build_audience_first"),
        "service": "active" if has_revenue else ("pursue_now" if has_content else "build_content_portfolio_first"),
        "product": "pursue_now" if has_patterns and has_revenue else "build_after_proven_monetization_patterns",
        "lead_gen": "pursue_now" if has_audience and has_offers else "build_audience_and_offer_base_first",
    }

    # ── Expansion triggers — signal-based, not threshold-based ──
    expansion_triggers = [
        {"trigger": "account_audience_growing_consistently", "action": "add_parallel_account_on_same_platform", "signal": "follower growth rate > 0"},
        {"trigger": "platform_producing_revenue", "action": "scale_account_count_on_platform", "signal": "any ledger revenue from this platform"},
        {"trigger": "offer_epc_above_portfolio_average", "action": "create_more_content_for_this_offer", "signal": "offer outperforms the average"},
        {"trigger": "sponsor_deal_completed_successfully", "action": "pursue_renewal_and_similar_sponsors", "signal": "deal status = completed"},
        {"trigger": "content_format_wins_repeatedly", "action": "double_output_in_winning_format", "signal": "3+ winning pattern instances"},
        {"trigger": "platform_traction_gaining", "action": "increase_posting_frequency_and_offer_density", "signal": "14d vs prior 14d impression growth > 0"},
        {"trigger": "platform_traction_losing", "action": "reduce_frequency_adapt_format_or_pivot", "signal": "14d vs prior 14d impression decline"},
        {"trigger": "new_revenue_source_proven", "action": "expand_that_source_to_more_accounts", "signal": "first ledger entry for a new source type"},
        {"trigger": "monetization_density_below_portfolio_average", "action": "attach_offers_to_unmonetized_content", "signal": "published content without offers"},
        {"trigger": "revenue_per_follower_improving", "action": "scale_audience_acquisition_aggressively", "signal": "rev/follower ratio increasing quarter over quarter"},
    ]

    # ── Suppress decisions — based on relative underperformance, not fixed thresholds ──
    suppress_list = []
    avg_rev_per_account = total_revenue / len(accounts) if accounts else 0
    avg_content_per_account = scan["content"]["total"] / len(accounts) if accounts else 0
    for a in accounts:
        # Suppress if: has content but produces zero revenue AND is below average on all metrics
        if (a["revenue"] == 0 and a["content_count"] > max(5, avg_content_per_account)
                and a["followers"] < (total_followers / max(len(accounts), 1)) * 0.2):
            suppress_list.append({"account_id": a["id"], "platform": a["platform"],
                                   "reason": f"Zero revenue after {a['content_count']} content pieces, "
                                             f"audience far below portfolio average"})
    for p in patterns.get("losing", []):
        suppress_list.append({"pattern": p["name"], "type": p["type"],
                               "reason": f"Losing pattern (fail_score: {p['score']:.2f})"})

    # ── Immediate actions ──
    immediate_actions = []
    if scan["content"]["unmonetized"] > 0:
        immediate_actions.append(f"Attach offers to {scan['content']['unmonetized']} unmonetized published content")
    if len(offers) == 0:
        immediate_actions.append("Create first affiliate offer — this is blocking all monetization")
    if scan["sponsors"]["active_deals"] == 0 and has_audience and has_content:
        immediate_actions.append("Identify and outreach sponsor targets — audience and content portfolio exist")
    if scan["actions_pending"] > 5:
        immediate_actions.append(f"Process {scan['actions_pending']} pending actions in the control layer")
    if not immediate_actions:
        immediate_actions.append("System is in good operating state — continue current plan")

    return {
        "brand": scan["brand"],
        "current_phase": phase,
        "scan_summary": {
            "total_accounts": len(accounts),
            "total_followers": total_followers,
            "total_revenue_90d": total_revenue,
            "total_offers": len(offers),
            "total_content": scan["content"]["total"],
            "winning_patterns": len(patterns["winning"]),
            "losing_patterns": len(patterns["losing"]),
            "memory_entries": scan["memory_entries"],
        },
        "platform_plan": platform_plan,
        "archetype_plan": archetype_plan,
        "monetization_plan": monetization_plan,
        "expansion_triggers": expansion_triggers,
        "suppress_list": suppress_list,
        "immediate_actions": immediate_actions,
        "blueprint_generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def get_gm_directive(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    """Phase 3: The GM's current operating directive — what to do RIGHT NOW.

    This is the single most important output: the next strategic moves
    ranked by impact, with exact actions to take.
    """
    blueprint = await generate_scale_blueprint(db, brand_id)
    if "error" in blueprint:
        return blueprint

    phase = blueprint["current_phase"]
    summary = blueprint["scan_summary"]

    # Build the directive from OPERATING REALITY, not canned dollar bands
    phase_directives = {
        "cold_start": {
            "headline": "COLD START — No assets exist. Build the machine's foundation now.",
            "priority_1": "Create accounts on the highest-priority platforms for this niche",
            "priority_2": "Create your first monetizable offer (affiliate, service, or product)",
            "priority_3": "Begin content production immediately — content is the fuel",
            "risk_warning": "Speed matters. The machine generates zero value with zero assets.",
        },
        "signal_formation": {
            "headline": "SIGNAL FORMATION — Accounts exist but no content published yet.",
            "priority_1": "Produce and publish content as fast as quality allows",
            "priority_2": "Test multiple content formats to find what gets traction",
            "priority_3": "Prepare offers for immediate attachment once content is live",
            "risk_warning": "Do not wait for perfection. Publish, measure, iterate.",
        },
        "warmup": {
            "headline": "WARMUP — Content exists but no revenue signal yet.",
            "priority_1": "Attach offers to all published content that lacks monetization",
            "priority_2": "Increase content velocity — more output means faster signal",
            "priority_3": "Begin sponsor/service outreach in parallel — don't wait for affiliate revenue",
            "risk_warning": "If content exists without monetization, every impression is wasted revenue.",
        },
        "proof_of_monetization": {
            "headline": "PROOF OF MONETIZATION — Offers live, awaiting first conversion.",
            "priority_1": "Analyze which content/offer/platform combinations are getting clicks",
            "priority_2": "Optimize CTAs and offer placement on highest-traffic content",
            "priority_3": "Begin sponsor outreach — audience + content portfolio = sponsor-ready",
            "risk_warning": "First revenue is the hardest. Push through — once proven, the model compounds.",
        },
        "repeatable_monetization": {
            "headline": "REPEATABLE MONETIZATION — Revenue flowing, patterns forming. Push for diversification.",
            "priority_1": "Identify and double down on the content/offer combinations that convert",
            "priority_2": "Add a second revenue source (sponsor, service, or product) immediately",
            "priority_3": "Scale content output in the winning formats and platforms",
            "risk_warning": "Single-source revenue is fragile. Diversify NOW while momentum is building.",
        },
        "portfolio_compounding": {
            "headline": "PORTFOLIO COMPOUNDING — Proven patterns active. Scale winners, suppress losers.",
            "priority_1": "Apply winning patterns across all accounts and platforms",
            "priority_2": "Suppress every losing pattern and underperforming offer aggressively",
            "priority_3": "Add accounts on platforms where the model is proven",
            "risk_warning": "Compounding works both ways. Suppress losers as aggressively as you scale winners.",
        },
        "channel_diversification": {
            "headline": f"CHANNEL DIVERSIFICATION — Revenue proven but concentrated in one source.",
            "priority_1": "Activate the next highest-potential revenue source per the blueprint",
            "priority_2": "Expand to platforms where the niche has untapped audience",
            "priority_3": "Begin sponsor/service pipeline if not yet active",
            "risk_warning": "Revenue concentration is the #1 scaling risk. Diversify before scaling harder.",
        },
        "high_yield_scaling": {
            "headline": f"HIGH-YIELD SCALING — Multiple revenue sources, patterns proven, scaling up.",
            "priority_1": "Scale winning accounts — more content, more offers, more platforms",
            "priority_2": "Launch high-ticket monetization (services, products, premium sponsors)",
            "priority_3": "Automate everything that can be automated — the machine should handle it",
            "risk_warning": "Monitor saturation per platform. Scale means nothing if engagement collapses.",
        },
        "aggressive_expansion": {
            "headline": "AGGRESSIVE EXPANSION — {account_count} accounts, {platform_count} platforms, pushing maximum.",
            "priority_1": "Replicate winning models to new accounts and adjacent niches",
            "priority_2": "Maximize monetization density — every content piece should earn",
            "priority_3": "Build recurring/subscription revenue for portfolio durability",
            "risk_warning": "At this scale, operational efficiency matters as much as revenue. Automate aggressively.",
        },
        "monetization_density_optimization": {
            "headline": "MONETIZATION DENSITY — optimizing yield per asset.",
            "priority_1": "Optimize the revenue per content piece across all platforms",
            "priority_2": "Test pricing, packaging, and bundling on top-performing offers",
            "priority_3": "Build owned audience channels (email, community) for highest-yield monetization",
            "risk_warning": "The goal is not more content — it's more revenue per content piece.",
        },
        "risk_managed_scale": {
            "headline": f"RISK-MANAGED SCALE — Scaling with governance and risk controls active.",
            "priority_1": "Continue scaling highest-yield paths while monitoring risk signals",
            "priority_2": "Ensure platform diversification prevents single-point-of-failure",
            "priority_3": "Build moat: owned audience, proprietary data, exclusive deals",
            "risk_warning": "Scale without risk management is gambling. The GM watches both.",
        },
    }

    # Resolve dynamic values in the selected directive
    raw = phase_directives.get(phase, phase_directives["risk_managed_scale"])
    # Replace template variables with actual values from summary
    directive = {}
    for k, v in raw.items():
        if isinstance(v, str):
            v = v.replace("{account_count}", str(summary.get("total_accounts", 0)))
            v = v.replace("{platform_count}", str(len(blueprint.get("platform_plan", []))))
        directive[k] = v

    directive["phase"] = phase
    directive["immediate_actions"] = blueprint["immediate_actions"]
    directive["suppress"] = blueprint["suppress_list"]
    directive["expand_on"] = [p for p in blueprint["platform_plan"] if p["action"] in ("scale", "launch")]

    return directive


async def get_gm_status(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    """Quick GM status check — where are we and what needs attention."""
    scan = await run_full_scan(db, brand_id)
    if "error" in scan:
        return scan

    accounts = scan["accounts"]["data"]
    total_followers = sum(a["followers"] for a in accounts)
    total_revenue = scan["revenue"]["total_90d"]

    # Compute health indicators
    has_accounts = len(accounts) > 0
    has_offers = scan["offers"]["total"] > 0
    has_content = scan["content"]["published"] > 0
    has_revenue = total_revenue > 0
    has_patterns = len(scan["patterns"]["winning"]) > 0

    health = sum([has_accounts, has_offers, has_content, has_revenue, has_patterns]) / 5

    return {
        "brand": scan["brand"]["name"],
        "health_score": round(health, 2),
        "total_accounts": len(accounts),
        "total_followers": total_followers,
        "total_revenue_90d": total_revenue,
        "published_content": scan["content"]["published"],
        "unmonetized_content": scan["content"]["unmonetized"],
        "active_offers": scan["offers"]["total"],
        "active_sponsor_deals": scan["sponsors"]["active_deals"],
        "pending_actions": scan["actions_pending"],
        "winning_patterns": len(scan["patterns"]["winning"]),
        "losing_patterns": len(scan["patterns"]["losing"]),
        "status_line": _status_line(health, total_revenue, total_followers, len(accounts)),
    }


def _status_line(health: float, revenue: float, followers: int, accounts: int) -> str:
    """Status line derived from operating signals, not dollar bands."""
    if accounts == 0:
        return "No accounts configured. The machine has no assets to work with."
    if followers == 0:
        return f"{accounts} accounts created. Building initial audience. Push content now."
    if revenue == 0:
        return f"{followers:,} followers across {accounts} accounts. No revenue yet — monetization activation needed."
    # Dynamic: describe revenue relative to portfolio capacity
    rev_per_follower = revenue / followers if followers > 0 else 0
    rev_per_account = revenue / accounts if accounts > 0 else 0
    if rev_per_follower < 0.01:
        return f"${revenue:,.0f}/90d — low yield per follower. Monetization density needs improvement."
    if rev_per_follower < 0.05:
        return f"${revenue:,.0f}/90d — moderate yield. Scale winning paths, suppress weak ones."
    return f"${revenue:,.0f}/90d — strong yield ({rev_per_follower:.3f}/follower). Push for maximum scale."
