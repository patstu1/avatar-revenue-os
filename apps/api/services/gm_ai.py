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

    # ── Determine current phase ──
    if len(accounts) == 0:
        phase = "cold_start"
    elif total_followers < 5000:
        phase = "warmup"
    elif total_revenue < 500:
        phase = "pre_monetization"
    elif total_revenue < 5000:
        phase = "early_monetization"
    elif total_revenue < 25000:
        phase = "scaling"
    else:
        phase = "optimizing"

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
    if phase in ("cold_start", "warmup"):
        archetype_plan = [
            {"archetype": "authority_educator", "count": 2, "purpose": "Build trust and audience"},
            {"archetype": "affiliate_closer", "count": 1, "purpose": "Start monetization early"},
        ]
    elif phase in ("pre_monetization", "early_monetization"):
        archetype_plan = [
            {"archetype": "affiliate_closer", "count": 2, "purpose": "Drive affiliate revenue"},
            {"archetype": "authority_educator", "count": 1, "purpose": "Audience growth"},
            {"archetype": "sponsor_magnet", "count": 1, "purpose": "Attract sponsor deals"},
        ]
    else:
        archetype_plan = [
            {"archetype": "affiliate_closer", "count": 3, "purpose": "Maximize affiliate revenue"},
            {"archetype": "sponsor_magnet", "count": 2, "purpose": "Sponsor deal flow"},
            {"archetype": "product_seller", "count": 1, "purpose": "Digital product revenue"},
            {"archetype": "services_consultant", "count": 1, "purpose": "High-ticket service revenue"},
        ]

    # ── Monetization timing ──
    monetization_plan = {
        "affiliate_start": "immediate" if len(offers) > 0 else "after_first_offer_created",
        "sponsor_start": "after_10k_total_followers" if total_followers < 10000 else "immediate",
        "service_start": "after_first_5_content_pieces" if scan["content"]["published"] < 5 else "immediate",
        "product_start": "after_stable_affiliate_revenue" if total_revenue < 2000 else "plan_now",
    }

    # ── Expansion triggers ──
    expansion_triggers = [
        {"trigger": "account_reaches_5k_followers", "action": "add_second_account_on_platform"},
        {"trigger": "platform_revenue_exceeds_1k_month", "action": "scale_to_3_accounts"},
        {"trigger": "affiliate_epc_above_2", "action": "create_more_content_for_offer"},
        {"trigger": "sponsor_deal_closes", "action": "pursue_renewal_and_similar_sponsors"},
        {"trigger": "content_format_wins_3x", "action": "double_output_in_that_format"},
        {"trigger": "platform_traction_gaining", "action": "increase_posting_frequency"},
        {"trigger": "platform_traction_losing", "action": "reduce_frequency_and_adapt"},
    ]

    # ── Suppress decisions ──
    suppress_list = []
    for a in accounts:
        if a["revenue"] == 0 and a["content_count"] > 10 and a["followers"] < 500:
            suppress_list.append({"account_id": a["id"], "platform": a["platform"],
                                   "reason": "Zero revenue after 10+ content pieces with <500 followers"})
    for p in patterns.get("losing", []):
        suppress_list.append({"pattern": p["name"], "type": p["type"],
                               "reason": f"Losing pattern (fail_score: {p['score']:.2f})"})

    # ── Immediate actions ──
    immediate_actions = []
    if scan["content"]["unmonetized"] > 0:
        immediate_actions.append(f"Attach offers to {scan['content']['unmonetized']} unmonetized published content")
    if len(offers) == 0:
        immediate_actions.append("Create first affiliate offer — this is blocking all monetization")
    if scan["sponsors"]["active_deals"] == 0 and total_followers > 10000:
        immediate_actions.append("Identify and outreach first 5 sponsor targets")
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

    # Build the directive based on current phase
    if phase == "cold_start":
        directive = {
            "headline": "COLD START — Build the Foundation",
            "priority_1": "Create 2-3 creator accounts on your highest-priority platforms",
            "priority_2": "Create your first affiliate offer (this unlocks monetization)",
            "priority_3": "Produce first 5 content pieces to establish presence",
            "risk_warning": "Do not try to monetize before establishing content quality and audience",
            "timeline": "Weeks 1-4: account creation + warmup. Weeks 5-8: content ramping. Week 9+: first monetization.",
        }
    elif phase == "warmup":
        directive = {
            "headline": "WARMUP PHASE — Build Audience Before Monetizing",
            "priority_1": f"Continue content output on {len(blueprint['platform_plan'])} platforms",
            "priority_2": "Focus on engagement quality over follower count",
            "priority_3": "Prepare affiliate offers for activation when audience is ready",
            "risk_warning": "Premature monetization kills audience trust. Wait for organic traction.",
            "timeline": "Continue warmup until 5K+ followers on primary platform, then begin monetization.",
        }
    elif phase == "pre_monetization":
        directive = {
            "headline": "PRE-MONETIZATION — Audience Ready, Begin Revenue Activation",
            "priority_1": f"Attach offers to {summary['total_content']} existing content pieces",
            "priority_2": "Launch first affiliate campaigns on top-performing content",
            "priority_3": "Begin outreach to first 5 sponsor targets",
            "risk_warning": "Start with soft monetization (affiliate links) before aggressive sells",
            "timeline": "Weeks 1-2: offer attachment. Weeks 3-4: first revenue. Month 2: sponsor outreach.",
        }
    elif phase == "early_monetization":
        directive = {
            "headline": f"EARLY MONETIZATION — ${summary['total_revenue_90d']:,.0f} Revenue, Scaling Up",
            "priority_1": "Double down on winning content/offer combinations",
            "priority_2": "Expand to additional platforms per the blueprint",
            "priority_3": "Close first sponsor deal to diversify revenue",
            "risk_warning": "Don't over-optimize for one revenue source. Diversify.",
            "timeline": "Target $5K/month within 60 days. Add sponsor revenue within 90 days.",
        }
    elif phase == "scaling":
        directive = {
            "headline": f"SCALING PHASE — ${summary['total_revenue_90d']:,.0f}/90d, Push for Maximum",
            "priority_1": "Scale winning accounts to 2-3 per platform",
            "priority_2": "Add high-ticket service revenue alongside affiliate",
            "priority_3": "Launch digital products from winning content patterns",
            "risk_warning": "Monitor saturation and fatigue. Suppress underperformers aggressively.",
            "timeline": "Target $25K/month. Diversify across 3+ revenue sources.",
        }
    else:
        directive = {
            "headline": f"OPTIMIZATION — ${summary['total_revenue_90d']:,.0f}/90d, Maximize Efficiency",
            "priority_1": "Optimize monetization mix for maximum margin",
            "priority_2": "Expand to adjacent niches with proven patterns",
            "priority_3": "Build recurring/subscription revenue for durability",
            "risk_warning": "At scale, the biggest risk is platform dependence. Diversify.",
            "timeline": "Continuous optimization. Monthly strategy reviews.",
        }

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
    if accounts == 0:
        return "No accounts configured. Create your first account to begin."
    if followers < 1000:
        return "Warmup phase. Building initial audience. Focus on content quality."
    if revenue == 0:
        return f"{followers:,} followers, no revenue yet. Time to activate monetization."
    if revenue < 1000:
        return f"Early revenue: ${revenue:,.0f}/90d. Scaling opportunity detected."
    if revenue < 10000:
        return f"Growing: ${revenue:,.0f}/90d. Double down on winners, suppress losers."
    return f"Strong: ${revenue:,.0f}/90d. Optimize mix, expand platforms, push for scale."
