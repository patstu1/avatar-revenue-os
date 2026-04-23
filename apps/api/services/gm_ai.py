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

    # ── Inbound channel strategy — broad-market, NOT niche-locked ──
    # ProofHook Revenue-Ops doctrine: the GM does not recommend platforms
    # based on niche. Every brand gets the same broad-market inbound mix
    # because the machine sells packages to a broad market. Vertical
    # targeting is a tactical outbound-list filter, not a platform strategy.
    platform_plan = []
    existing_platforms = set(platforms.keys())

    # Broad-market inbound channels (identical for every brand — no niche
    # routing). Order reflects ProofHook lead-gen efficiency, not audience
    # reach, because we're generating PACKAGE LEADS, not audience.
    priority_platforms = [
        "email_outbound",       # cold outbound is the primary lead source
        "linkedin",             # decision-maker reach
        "youtube",              # high-intent search
        "x",                    # founder reach
        "email_newsletter",     # warm lead nurture
    ]

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
            "role": "inbound_lead_source",  # all channels are package-lead sources
        })

    # ── Inbound channel role plan — package-lead-generation focused ──
    # These are the ROLES each inbound channel plays in lead generation,
    # not creator archetypes. ProofHook does not run "authority educators"
    # or "affiliate closers" — it runs inbound channels that generate
    # qualified package leads for a creative services catalog.
    if not has_revenue:
        archetype_plan = [
            {"archetype": "outbound_cold_email", "count": 2, "purpose": "Generate inbound qualified package leads from cold outbound"},
            {"archetype": "decision_maker_reach", "count": 1, "purpose": "Reach buyers where they browse (LinkedIn / X founder networks)"},
        ]
    elif not has_multiple_sources:
        archetype_plan = [
            {"archetype": "outbound_cold_email", "count": 2, "purpose": "Scale the channel that's generating lead volume"},
            {"archetype": "intent_search_content", "count": 1, "purpose": "Capture high-intent buyers searching for creative services"},
            {"archetype": "referral_loop", "count": 1, "purpose": "Convert delivered packages into upsell and referral leads"},
        ]
    else:
        archetype_plan = [
            {"archetype": "outbound_cold_email", "count": 3, "purpose": "Primary lead engine at scale"},
            {"archetype": "intent_search_content", "count": 2, "purpose": "Inbound intent capture — high-lead-quality path"},
            {"archetype": "referral_loop", "count": 1, "purpose": "Post-delivery upsell and referral motion"},
            {"archetype": "warm_nurture", "count": 1, "purpose": "Re-engage stale leads into package-first funnel"},
        ]

    # ── Funnel-stage operational status — not creator monetization timing ──
    # These flags describe the state of the ProofHook Revenue-Ops funnel:
    #   package catalog → checkout → intake → production → delivery → upsell
    # NOT affiliate/sponsor/product/service monetization methods (legacy).
    monetization_plan = {
        "package_catalog_wired": "active" if has_offers else "block_all_revenue_until_fixed",
        "checkout_link_live": "active" if has_offers and has_revenue else ("pursue_now" if has_offers else "blocked_on_catalog"),
        "intake_form_automated": "active" if has_revenue else ("pursue_now" if has_offers else "blocked_on_catalog"),
        "production_queue_flowing": "active" if has_revenue and has_patterns else ("pursue_now" if has_revenue else "blocked_on_first_payment"),
        "upsell_loop_triggered": "active" if has_multiple_sources else ("pursue_now" if has_revenue else "blocked_on_first_delivery"),
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


# ═══════════════════════════════════════════════════════════════════════════════
# GM CONVERSATIONAL OPERATOR INTERFACE — TOOL-USE EXECUTION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

import json
import os

from packages.db.models.content import ContentBrief
from packages.db.models.offers import Offer
from packages.db.models.operator_permission_matrix import OperatorPermissionMatrix
from packages.db.enums import ContentType

from apps.api.services.event_bus import emit_event, emit_action
from apps.api.services.gm_system_prompt import GM_OPERATOR_PROMPT


# ── Tool Definitions for Claude API ──────────────────────────────────────────

GM_TOOLS = [
    {
        "name": "create_content_brief",
        "description": "Create a real ContentBrief record in the database. Use when the operator asks to create content, or when analysis shows content is needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Brief title"},
                "content_type": {"type": "string", "enum": ["short_video", "long_video", "static_image", "carousel", "text_post", "story"], "description": "Content format"},
                "target_platform": {"type": "string", "description": "Target platform (youtube, tiktok, instagram, etc.)"},
                "hook": {"type": "string", "description": "Opening hook text"},
                "angle": {"type": "string", "description": "Content angle / approach"},
                "key_points": {"type": "array", "items": {"type": "string"}, "description": "Key points to cover"},
                "cta_strategy": {"type": "string", "description": "Call-to-action strategy"},
                "monetization_integration": {"type": "string", "description": "How monetization is woven in"},
                "offer_id": {"type": "string", "description": "UUID of offer to attach (optional)"},
                "creator_account_id": {"type": "string", "description": "UUID of account to assign (optional)"},
            },
            "required": ["title", "content_type", "target_platform"],
        },
    },
    {
        "name": "adjust_posting_approach",
        "description": "Update an account's posting capacity and scale role. Use to throttle or accelerate an account's output.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "UUID of the creator account"},
                "posting_capacity_per_day": {"type": "integer", "description": "New daily posting capacity"},
                "scale_role": {"type": "string", "description": "New scale role: experimental, growth, anchor, cash_cow, diversifier"},
            },
            "required": ["account_id"],
        },
    },
    {
        "name": "pause_account",
        "description": "Deactivate a creator account. Use when an account is underperforming or needs rest.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "UUID of the creator account"},
                "reason": {"type": "string", "description": "Why the account is being paused"},
            },
            "required": ["account_id", "reason"],
        },
    },
    {
        "name": "resume_account",
        "description": "Reactivate a paused creator account.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "UUID of the creator account"},
            },
            "required": ["account_id"],
        },
    },
    {
        "name": "boost_offer",
        "description": "Increase an offer's priority so it gets more content and placement.",
        "input_schema": {
            "type": "object",
            "properties": {
                "offer_id": {"type": "string", "description": "UUID of the offer"},
                "new_priority": {"type": "integer", "description": "New priority (higher = more prominent)"},
                "reason": {"type": "string", "description": "Why this offer is being boosted"},
            },
            "required": ["offer_id", "new_priority"],
        },
    },
    {
        "name": "suppress_offer",
        "description": "Lower an offer's priority or deactivate it entirely.",
        "input_schema": {
            "type": "object",
            "properties": {
                "offer_id": {"type": "string", "description": "UUID of the offer"},
                "new_priority": {"type": "integer", "description": "New priority (0 to deactivate)"},
                "reason": {"type": "string", "description": "Why this offer is being suppressed"},
            },
            "required": ["offer_id", "new_priority"],
        },
    },
    {
        "name": "add_account",
        "description": "Create a new creator account on a platform.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "description": "Platform name (youtube, tiktok, instagram, etc.)"},
                "username": {"type": "string", "description": "Platform username"},
                "niche_focus": {"type": "string", "description": "Content niche for this account"},
                "scale_role": {"type": "string", "description": "Scale role: experimental, growth, anchor, cash_cow"},
                "posting_capacity_per_day": {"type": "integer", "description": "Daily posting capacity"},
            },
            "required": ["platform", "username"],
        },
    },
    {
        "name": "draft_outreach",
        "description": "Create a sponsor outreach operator action for the operator to review and send.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target_name": {"type": "string", "description": "Company or person to reach out to"},
                "outreach_type": {"type": "string", "description": "sponsor, collaboration, partnership, affiliate"},
                "pitch_summary": {"type": "string", "description": "Summary of the pitch"},
                "estimated_value": {"type": "number", "description": "Estimated deal value in USD"},
            },
            "required": ["target_name", "outreach_type", "pitch_summary"],
        },
    },
    {
        "name": "generate_blueprint",
        "description": "Generate a fresh scale blueprint from current scan data.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "reallocate_budget",
        "description": "Create an operator action to reallocate budget between platforms or accounts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "from_area": {"type": "string", "description": "Where to reduce spend"},
                "to_area": {"type": "string", "description": "Where to increase spend"},
                "amount_usd": {"type": "number", "description": "Amount to move"},
                "rationale": {"type": "string", "description": "Why this reallocation"},
            },
            "required": ["from_area", "to_area", "rationale"],
        },
    },
    {
        "name": "trigger_trend_scan",
        "description": "Dispatch a trend scanning task to find fresh content opportunities.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "express_publish",
        "description": "Dispatch an express publish task for a specific content item. Pushes content live immediately.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content_item_id": {"type": "string", "description": "UUID of the content item to publish"},
            },
            "required": ["content_item_id"],
        },
    },
    {
        "name": "create_offer",
        "description": "Create a new monetization offer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Offer name"},
                "monetization_method": {"type": "string", "enum": ["affiliate", "sponsor", "product", "course", "consulting", "membership", "lead_gen", "adsense"], "description": "Monetization method"},
                "offer_url": {"type": "string", "description": "Offer URL or landing page"},
                "payout_amount": {"type": "number", "description": "Expected payout per conversion in USD"},
                "payout_type": {"type": "string", "description": "cpa, cpc, cpm, rev_share, flat_fee"},
                "priority": {"type": "integer", "description": "Priority ranking"},
            },
            "required": ["name", "monetization_method"],
        },
    },
]


# ── Tool Executor Functions ──────────────────────────────────────────────────


async def _check_approval_required(
    db: AsyncSession, org_id: uuid.UUID, brand_id: uuid.UUID, action_class: str,
) -> bool:
    """Check the operator permission matrix to see if this action class requires approval."""
    result = await db.execute(
        select(OperatorPermissionMatrix).where(
            OperatorPermissionMatrix.organization_id == org_id,
            OperatorPermissionMatrix.action_class == action_class,
            OperatorPermissionMatrix.is_active.is_(True),
        )
    )
    matrix = result.scalar_one_or_none()
    if matrix and matrix.autonomy_mode in ("approval_required", "manual"):
        return True
    return False


async def _exec_create_content_brief(
    db: AsyncSession, org_id: uuid.UUID, brand_id: uuid.UUID, params: dict,
) -> dict:
    """Create a real ContentBrief record."""
    if await _check_approval_required(db, org_id, brand_id, "content_creation"):
        action = await emit_action(
            db, org_id=org_id, brand_id=brand_id,
            action_type="gm_create_content_brief",
            title=f"GM wants to create brief: {params['title']}",
            category="approval",
            priority="medium",
            source_module="gm_ai",
            action_payload=params,
        )
        return {"status": "approval_required", "action_id": str(action.id), "title": params["title"]}

    content_type_str = params.get("content_type", "short_video")
    try:
        ct = ContentType(content_type_str)
    except ValueError:
        ct = ContentType.SHORT_VIDEO

    brief = ContentBrief(
        brand_id=brand_id,
        title=params["title"],
        content_type=ct,
        target_platform=params.get("target_platform"),
        hook=params.get("hook"),
        angle=params.get("angle"),
        key_points=params.get("key_points", []),
        cta_strategy=params.get("cta_strategy"),
        monetization_integration=params.get("monetization_integration"),
        offer_id=uuid.UUID(params["offer_id"]) if params.get("offer_id") else None,
        creator_account_id=uuid.UUID(params["creator_account_id"]) if params.get("creator_account_id") else None,
        status="draft",
    )
    db.add(brief)
    await db.flush()

    await emit_event(
        db, domain="gm", event_type="gm.content_brief_created",
        summary=f"GM created content brief: {params['title']}",
        org_id=org_id, brand_id=brand_id,
        entity_type="content_brief", entity_id=brief.id,
        actor_type="system", actor_id="gm_ai",
    )

    return {"status": "created", "brief_id": str(brief.id), "title": params["title"]}


async def _exec_adjust_posting_approach(
    db: AsyncSession, org_id: uuid.UUID, brand_id: uuid.UUID, params: dict,
) -> dict:
    """Update account posting capacity and/or scale role."""
    acct = (await db.execute(
        select(CreatorAccount).where(CreatorAccount.id == uuid.UUID(params["account_id"]))
    )).scalar_one_or_none()
    if not acct:
        return {"status": "error", "message": f"Account {params['account_id']} not found"}

    changes = {}
    if "posting_capacity_per_day" in params:
        acct.posting_capacity_per_day = params["posting_capacity_per_day"]
        changes["posting_capacity_per_day"] = params["posting_capacity_per_day"]
    if "scale_role" in params:
        acct.scale_role = params["scale_role"]
        changes["scale_role"] = params["scale_role"]
    await db.flush()

    return {"status": "updated", "account_id": params["account_id"], "changes": changes}


async def _exec_pause_account(
    db: AsyncSession, org_id: uuid.UUID, brand_id: uuid.UUID, params: dict,
) -> dict:
    """Deactivate a creator account."""
    if await _check_approval_required(db, org_id, brand_id, "account_management"):
        action = await emit_action(
            db, org_id=org_id, brand_id=brand_id,
            action_type="gm_pause_account",
            title=f"GM wants to pause account {params['account_id']}",
            category="approval", priority="high",
            source_module="gm_ai",
            action_payload=params,
        )
        return {"status": "approval_required", "action_id": str(action.id)}

    acct = (await db.execute(
        select(CreatorAccount).where(CreatorAccount.id == uuid.UUID(params["account_id"]))
    )).scalar_one_or_none()
    if not acct:
        return {"status": "error", "message": f"Account {params['account_id']} not found"}

    acct.is_active = False
    await db.flush()

    await emit_event(
        db, domain="gm", event_type="gm.account_paused",
        summary=f"GM paused account: {params.get('reason', 'no reason')}",
        org_id=org_id, brand_id=brand_id,
        entity_type="creator_account", entity_id=acct.id,
        actor_type="system", actor_id="gm_ai",
    )
    return {"status": "paused", "account_id": params["account_id"], "reason": params.get("reason")}


async def _exec_resume_account(
    db: AsyncSession, org_id: uuid.UUID, brand_id: uuid.UUID, params: dict,
) -> dict:
    """Reactivate a creator account."""
    acct = (await db.execute(
        select(CreatorAccount).where(CreatorAccount.id == uuid.UUID(params["account_id"]))
    )).scalar_one_or_none()
    if not acct:
        return {"status": "error", "message": f"Account {params['account_id']} not found"}

    acct.is_active = True
    await db.flush()

    await emit_event(
        db, domain="gm", event_type="gm.account_resumed",
        summary=f"GM resumed account",
        org_id=org_id, brand_id=brand_id,
        entity_type="creator_account", entity_id=acct.id,
        actor_type="system", actor_id="gm_ai",
    )
    return {"status": "resumed", "account_id": params["account_id"]}


async def _exec_boost_offer(
    db: AsyncSession, org_id: uuid.UUID, brand_id: uuid.UUID, params: dict,
) -> dict:
    """Increase an offer's priority."""
    offer = (await db.execute(
        select(Offer).where(Offer.id == uuid.UUID(params["offer_id"]))
    )).scalar_one_or_none()
    if not offer:
        return {"status": "error", "message": f"Offer {params['offer_id']} not found"}

    old_priority = offer.priority
    offer.priority = params["new_priority"]
    await db.flush()

    await emit_event(
        db, domain="gm", event_type="gm.offer_boosted",
        summary=f"GM boosted offer '{offer.name}': priority {old_priority} -> {params['new_priority']}. {params.get('reason', '')}",
        org_id=org_id, brand_id=brand_id,
        entity_type="offer", entity_id=offer.id,
        actor_type="system", actor_id="gm_ai",
    )
    return {"status": "boosted", "offer_id": params["offer_id"], "name": offer.name,
            "old_priority": old_priority, "new_priority": params["new_priority"]}


async def _exec_suppress_offer(
    db: AsyncSession, org_id: uuid.UUID, brand_id: uuid.UUID, params: dict,
) -> dict:
    """Lower or deactivate an offer."""
    offer = (await db.execute(
        select(Offer).where(Offer.id == uuid.UUID(params["offer_id"]))
    )).scalar_one_or_none()
    if not offer:
        return {"status": "error", "message": f"Offer {params['offer_id']} not found"}

    old_priority = offer.priority
    offer.priority = params["new_priority"]
    if params["new_priority"] == 0:
        offer.is_active = False
    await db.flush()

    await emit_event(
        db, domain="gm", event_type="gm.offer_suppressed",
        summary=f"GM suppressed offer '{offer.name}': priority {old_priority} -> {params['new_priority']}. {params.get('reason', '')}",
        org_id=org_id, brand_id=brand_id,
        entity_type="offer", entity_id=offer.id,
        actor_type="system", actor_id="gm_ai",
    )
    return {"status": "suppressed", "offer_id": params["offer_id"], "name": offer.name,
            "old_priority": old_priority, "new_priority": params["new_priority"]}


async def _exec_add_account(
    db: AsyncSession, org_id: uuid.UUID, brand_id: uuid.UUID, params: dict,
) -> dict:
    """Create a new creator account."""
    if await _check_approval_required(db, org_id, brand_id, "account_management"):
        action = await emit_action(
            db, org_id=org_id, brand_id=brand_id,
            action_type="gm_add_account",
            title=f"GM wants to add {params['platform']} account: @{params['username']}",
            category="approval", priority="medium",
            source_module="gm_ai",
            action_payload=params,
        )
        return {"status": "approval_required", "action_id": str(action.id)}

    from packages.db.enums import Platform, AccountType
    _platform_aliases = {"x": "twitter", "twitter/x": "twitter", "x/twitter": "twitter"}
    raw = params["platform"].lower().strip()
    raw = _platform_aliases.get(raw, raw)
    try:
        platform = Platform(raw)
    except ValueError:
        platform = Platform.YOUTUBE

    acct = CreatorAccount(
        brand_id=brand_id,
        platform=platform,
        account_type=AccountType.ORGANIC,
        platform_username=params["username"],
        niche_focus=params.get("niche_focus", ""),
        scale_role=params.get("scale_role", "experimental"),
        posting_capacity_per_day=params.get("posting_capacity_per_day", 1),
    )
    db.add(acct)
    await db.flush()

    await emit_event(
        db, domain="gm", event_type="gm.account_created",
        summary=f"GM created {params['platform']} account: @{params['username']}",
        org_id=org_id, brand_id=brand_id,
        entity_type="creator_account", entity_id=acct.id,
        actor_type="system", actor_id="gm_ai",
    )
    return {"status": "created", "account_id": str(acct.id), "platform": params["platform"], "username": params["username"]}


async def _exec_draft_outreach(
    db: AsyncSession, org_id: uuid.UUID, brand_id: uuid.UUID, params: dict,
) -> dict:
    """Create an outreach operator action."""
    action = await emit_action(
        db, org_id=org_id, brand_id=brand_id,
        action_type="gm_draft_outreach",
        title=f"Outreach: {params['target_name']} ({params['outreach_type']})",
        description=params["pitch_summary"],
        category="opportunity",
        priority="medium",
        source_module="gm_ai",
        action_payload=params,
    )
    return {"status": "drafted", "action_id": str(action.id), "target": params["target_name"]}


async def _exec_generate_blueprint(
    db: AsyncSession, org_id: uuid.UUID, brand_id: uuid.UUID, params: dict,
) -> dict:
    """Generate a fresh scale blueprint."""
    bp = await generate_scale_blueprint(db, brand_id)
    return {"status": "generated", "phase": bp.get("current_phase"), "summary": bp.get("scan_summary")}


async def _exec_reallocate_budget(
    db: AsyncSession, org_id: uuid.UUID, brand_id: uuid.UUID, params: dict,
) -> dict:
    """Create a budget reallocation operator action."""
    action = await emit_action(
        db, org_id=org_id, brand_id=brand_id,
        action_type="gm_reallocate_budget",
        title=f"Budget reallocation: {params['from_area']} -> {params['to_area']}",
        description=params.get("rationale", ""),
        category="opportunity",
        priority="medium",
        source_module="gm_ai",
        action_payload=params,
    )
    return {"status": "proposed", "action_id": str(action.id)}


async def _exec_trigger_trend_scan(
    db: AsyncSession, org_id: uuid.UUID, brand_id: uuid.UUID, params: dict,
) -> dict:
    """Dispatch a trend scan Celery task."""
    try:
        from workers.celery_app import app as celery_app
        celery_app.send_task("workers.trend_viral_worker.tasks.trend_light_scan")
        return {"status": "dispatched", "task": "trend_light_scan"}
    except Exception as e:
        logger.warning("gm.trend_scan_dispatch_failed", error=str(e))
        return {"status": "dispatch_failed", "error": str(e)}


async def _exec_express_publish(
    db: AsyncSession, org_id: uuid.UUID, brand_id: uuid.UUID, params: dict,
) -> dict:
    """Dispatch express publish for a content item."""
    if await _check_approval_required(db, org_id, brand_id, "publishing"):
        action = await emit_action(
            db, org_id=org_id, brand_id=brand_id,
            action_type="gm_express_publish",
            title=f"GM wants to express-publish content {params['content_item_id']}",
            category="approval", priority="high",
            source_module="gm_ai",
            entity_type="content_item",
            entity_id=uuid.UUID(params["content_item_id"]),
            action_payload=params,
        )
        return {"status": "approval_required", "action_id": str(action.id)}

    try:
        from workers.celery_app import app as celery_app
        celery_app.send_task(
            "workers.publishing_worker.publish_content",
            args=[params["content_item_id"]],
        )
        return {"status": "dispatched", "content_item_id": params["content_item_id"]}
    except Exception as e:
        logger.warning("gm.express_publish_failed", error=str(e))
        return {"status": "dispatch_failed", "error": str(e)}


async def _exec_create_offer(
    db: AsyncSession, org_id: uuid.UUID, brand_id: uuid.UUID, params: dict,
) -> dict:
    """Create a new offer."""
    from packages.db.enums import MonetizationMethod

    method_map = {
        "affiliate": MonetizationMethod.AFFILIATE,
        "sponsor": MonetizationMethod.SPONSOR,
        "product": MonetizationMethod.PRODUCT,
        "course": MonetizationMethod.COURSE,
        "consulting": MonetizationMethod.CONSULTING,
        "membership": MonetizationMethod.MEMBERSHIP,
        "lead_gen": MonetizationMethod.LEAD_GEN,
        "adsense": MonetizationMethod.ADSENSE,
    }
    method_str = params.get("monetization_method", "affiliate").lower()
    method = method_map.get(method_str, MonetizationMethod.AFFILIATE)

    offer = Offer(
        brand_id=brand_id,
        name=params["name"],
        monetization_method=method,
        offer_url=params.get("offer_url", ""),
        payout_amount=float(params.get("payout_amount", 0)),
        payout_type=params.get("payout_type", "cpa"),
        priority=params.get("priority", 1),
        is_active=True,
    )
    db.add(offer)
    await db.flush()

    await emit_event(
        db, domain="gm", event_type="gm.offer_created",
        summary=f"GM created offer: {params['name']} ({method_str})",
        org_id=org_id, brand_id=brand_id,
        entity_type="offer", entity_id=offer.id,
        actor_type="system", actor_id="gm_ai",
    )
    return {"status": "created", "offer_id": str(offer.id), "name": params["name"], "method": method_str}


# ── Tool Dispatcher ──────────────────────────────────────────────────────────

_TOOL_MAP = {
    "create_content_brief": _exec_create_content_brief,
    "adjust_posting_approach": _exec_adjust_posting_approach,
    "pause_account": _exec_pause_account,
    "resume_account": _exec_resume_account,
    "boost_offer": _exec_boost_offer,
    "suppress_offer": _exec_suppress_offer,
    "add_account": _exec_add_account,
    "draft_outreach": _exec_draft_outreach,
    "generate_blueprint": _exec_generate_blueprint,
    "reallocate_budget": _exec_reallocate_budget,
    "trigger_trend_scan": _exec_trigger_trend_scan,
    "express_publish": _exec_express_publish,
    "create_offer": _exec_create_offer,
}


async def _execute_tool(
    db: AsyncSession, org_id: uuid.UUID, brand_id: uuid.UUID,
    tool_name: str, tool_input: dict,
) -> dict:
    """Execute a GM tool by name and return the result."""
    executor = _TOOL_MAP.get(tool_name)
    if not executor:
        return {"status": "error", "message": f"Unknown tool: {tool_name}"}
    try:
        return await executor(db, org_id, brand_id, tool_input)
    except Exception as e:
        logger.error("gm.tool_execution_failed", tool=tool_name, error=str(e))
        return {"status": "error", "message": str(e)}


# ── Main Conversational GM Endpoint ──────────────────────────────────────────

async def gm_conversation(
    db: AsyncSession,
    org_id: uuid.UUID,
    brand_id: uuid.UUID,
    user_message: str,
    conversation_history: list[dict],
) -> dict:
    """Run a conversational GM turn with full tool-use execution.

    1. Scans the full machine state
    2. Loads the current directive
    3. Calls Claude with tool definitions
    4. Executes any tool_use blocks via real DB operations
    5. Loops until Claude returns a final text response
    6. Returns the response + actions taken
    """
    # Phase 1: Fresh system scan
    scan_data = await run_full_scan(db, brand_id)
    directive = await get_gm_directive(db, brand_id)

    # Phase 2: Build system prompt with full state
    state_block = json.dumps(scan_data, indent=2, default=str)
    directive_block = json.dumps(directive, indent=2, default=str)

    system_prompt = f"""{GM_OPERATOR_PROMPT}

## CURRENT MACHINE STATE
{state_block}

## CURRENT DIRECTIVE
{directive_block}
"""

    # Phase 3: Build messages from conversation history
    messages = []
    for msg in conversation_history[-20:]:
        role = msg.get("role", "user")
        if role == "gm":
            role = "assistant"
        content = msg.get("content", "")
        if content:
            messages.append({"role": role, "content": content})

    # Add the new user message
    messages.append({"role": "user", "content": user_message})

    # Phase 4: Get API key
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        try:
            from apps.api.services import secrets_service
            db_keys = await secrets_service.get_all_keys(db, org_id)
            api_key = db_keys.get("anthropic", "")
        except Exception:
            pass

    if not api_key:
        return {
            "response": "I need an Anthropic API key to operate. Configure it in Settings or as ANTHROPIC_API_KEY.",
            "actions_taken": [],
        }

    # Phase 5: Call Claude with tool-use loop
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    actions_taken = []
    max_iterations = 10  # safety limit on tool-use loops

    for iteration in range(max_iterations):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8000,
                system=system_prompt,
                tools=GM_TOOLS,
                messages=messages,
            )
        except Exception as e:
            logger.error("gm.claude_api_failed", error=str(e), iteration=iteration)
            return {
                "response": f"Claude API call failed: {str(e)}",
                "actions_taken": actions_taken,
            }

        # Check if we got a final text response (no more tool calls)
        has_tool_use = any(block.type == "tool_use" for block in response.content)

        if response.stop_reason == "end_turn" and not has_tool_use:
            # Final text response — extract it
            text_parts = [block.text for block in response.content if block.type == "text"]
            final_text = "\n".join(text_parts) if text_parts else ""
            return {
                "response": final_text,
                "actions_taken": actions_taken,
            }

        # Process tool_use blocks
        tool_results = []
        assistant_content = []

        for block in response.content:
            if block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

                # Execute the tool
                result = await _execute_tool(db, org_id, brand_id, block.name, block.input)
                actions_taken.append({
                    "tool": block.name,
                    "input": block.input,
                    "result": result,
                })

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, default=str),
                })

        # Add the assistant's response (with tool_use blocks) and tool results to the conversation
        messages.append({"role": "assistant", "content": assistant_content})
        messages.append({"role": "user", "content": tool_results})

    # If we exhaust iterations, return what we have
    return {
        "response": "GM completed maximum tool execution iterations. Actions were taken — see actions_taken.",
        "actions_taken": actions_taken,
    }


# ---------------------------------------------------------------------------
# Startup Prompt — org-level state-aware opener for first-boot conversations
# ---------------------------------------------------------------------------

async def get_startup_prompt(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> Optional[str]:
    """Return a state-aware GM opening message, or None if fully configured.

    Checks org-level counts and returns the appropriate conversational opener:
    - Zero brands AND zero accounts: warm opener about niche/audience/goals
    - Some brands but no accounts: message about connecting platforms
    - Brands + accounts but no offers: message about monetization setup
    - Everything present: None (normal operation, no startup prompt needed)
    """
    brand_count = (await db.execute(
        select(func.count()).select_from(Brand).where(
            Brand.organization_id == org_id, Brand.is_active.is_(True)
        )
    )).scalar() or 0

    account_count = 0
    offer_count = 0
    if brand_count > 0:
        brand_ids_q = select(Brand.id).where(
            Brand.organization_id == org_id, Brand.is_active.is_(True)
        )
        account_count = (await db.execute(
            select(func.count()).select_from(CreatorAccount).where(
                CreatorAccount.brand_id.in_(brand_ids_q),
                CreatorAccount.is_active.is_(True),
            )
        )).scalar() or 0

        offer_count = (await db.execute(
            select(func.count()).select_from(Offer).where(
                Offer.brand_id.in_(brand_ids_q),
                Offer.is_active.is_(True),
            )
        )).scalar() or 0

    if brand_count == 0 and account_count == 0:
        return (
            "Welcome to the machine. I'm your Strategic GM — I build the revenue "
            "blueprint, plan the account architecture, and run the scaling strategy.\n\n"
            "Right now the system is a blank slate. Before I can build anything, "
            "I need to understand what we're working with.\n\n"
            "Let's start with the basics:\n"
            "- What niche or market are you targeting?\n"
            "- Who is the audience?\n"
            "- What are you selling, or what do you want to monetize?\n"
            "- What are your goals — revenue target, timeline, scale ambitions?\n\n"
            "Tell me as much or as little as you want. I'll build the full launch "
            "blueprint from there — brands, accounts, content angles, monetization "
            "strategy, the whole architecture. You approve or adjust before anything "
            "gets created."
        )

    if account_count == 0:
        return (
            f"Good — {brand_count} brand{'s' if brand_count != 1 else ''} configured. "
            "But we have no publishing accounts connected yet. The machine can't "
            "distribute content or generate revenue without platform accounts.\n\n"
            "What platforms are you targeting? YouTube, TikTok, Instagram, X, LinkedIn? "
            "Tell me your platform strategy and I'll map the account architecture."
        )

    if offer_count == 0:
        return (
            f"The machine has {brand_count} brand{'s' if brand_count != 1 else ''} and "
            f"{account_count} account{'s' if account_count != 1 else ''} — content "
            "infrastructure is in place. But there are no monetization offers configured.\n\n"
            "What's the revenue play? Affiliate offers, your own product, sponsorships, "
            "services, lead gen? Let's get the money side wired up so every piece of "
            "content can earn."
        )

    # Fully configured — no startup prompt needed
    return None
