"""Revenue Machine Service — The capstone operating model bridge.

Gathers real DB data (credits, plans, telemetry, transactions, content,
offers, accounts) and passes it through the scoring engine to produce
actionable diagnostics: full reports, elite readiness scorecards,
spend triggers, operating-engine health, fee projections, and
plan-aware premium output catalogs.
"""
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.core import Brand, User
from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.offers import Offer
from packages.db.models.monetization import (
    CreditLedger,
    CreditTransaction,
    UsageMeterSnapshot,
    PlanSubscription,
    PackPurchase,
    MultiplicationEvent as MultiplicationEventModel,
    MonetizationTelemetryEvent,
)
from packages.scoring.monetization_machine import (
    generate_machine_report,
    TelemetryEvent,
    UserSegment,
    design_outcome_packs,
    _get_pricing_ladder,
)

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Platform fee schedule — rates decrease as plan tier increases
# ---------------------------------------------------------------------------

PLATFORM_FEE_RATES: dict[str, dict[str, float]] = {
    "free": {
        "content_generation": 0.05,
        "platform_distribution": 0.08,
        "transaction_processing": 0.10,
        "credit_overage": 0.15,
        "affiliate_commission": 0.20,
    },
    "starter": {
        "content_generation": 0.04,
        "platform_distribution": 0.06,
        "transaction_processing": 0.08,
        "credit_overage": 0.12,
        "affiliate_commission": 0.15,
    },
    "professional": {
        "content_generation": 0.03,
        "platform_distribution": 0.04,
        "transaction_processing": 0.06,
        "credit_overage": 0.10,
        "affiliate_commission": 0.10,
    },
    "business": {
        "content_generation": 0.02,
        "platform_distribution": 0.03,
        "transaction_processing": 0.04,
        "credit_overage": 0.08,
        "affiliate_commission": 0.05,
    },
    "enterprise": {
        "content_generation": 0.01,
        "platform_distribution": 0.02,
        "transaction_processing": 0.02,
        "credit_overage": 0.05,
        "affiliate_commission": 0.03,
    },
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_org_brand_ids(db: AsyncSession, org_id: uuid.UUID) -> list[uuid.UUID]:
    rows = (
        await db.execute(select(Brand.id).where(Brand.organization_id == org_id))
    ).scalars().all()
    return list(rows)


async def _get_plan_tier(db: AsyncSession, org_id: uuid.UUID) -> str:
    plan = (
        await db.execute(
            select(PlanSubscription.plan_tier).where(
                PlanSubscription.organization_id == org_id,
                PlanSubscription.status == "active",
                PlanSubscription.is_active.is_(True),
            ).order_by(PlanSubscription.started_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    return plan or "free"


async def _get_plan_row(db: AsyncSession, org_id: uuid.UUID):
    return (
        await db.execute(
            select(PlanSubscription).where(
                PlanSubscription.organization_id == org_id,
                PlanSubscription.status == "active",
                PlanSubscription.is_active.is_(True),
            ).order_by(PlanSubscription.started_at.desc()).limit(1)
        )
    ).scalar_one_or_none()


async def _get_ledger(db: AsyncSession, org_id: uuid.UUID):
    return (
        await db.execute(
            select(CreditLedger).where(
                CreditLedger.organization_id == org_id,
                CreditLedger.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# 1. Full Revenue Machine Report
# ---------------------------------------------------------------------------

async def get_revenue_machine_report(db: AsyncSession, org_id: uuid.UUID) -> dict:
    """Gather all metrics from DB, pass to scoring engine, return full report."""
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    brand_ids = await _get_org_brand_ids(db, org_id)

    org_users = (
        await db.execute(
            select(User).where(User.organization_id == org_id, User.is_active.is_(True))
        )
    ).scalars().all()

    ledger = await _get_ledger(db, org_id)
    plan_row = await _get_plan_row(db, org_id)
    plan_tier = plan_row.plan_tier if plan_row else "free"

    content_count = 0
    offer_count = 0
    account_count = 0
    if brand_ids:
        content_count = (
            await db.execute(
                select(func.count(ContentItem.id)).where(
                    ContentItem.brand_id.in_(brand_ids),
                    ContentItem.created_at >= thirty_days_ago,
                )
            )
        ).scalar() or 0
        offer_count = (
            await db.execute(
                select(func.count(Offer.id)).where(
                    Offer.brand_id.in_(brand_ids),
                    Offer.is_active.is_(True),
                )
            )
        ).scalar() or 0
        account_count = (
            await db.execute(
                select(func.count(CreatorAccount.id)).where(
                    CreatorAccount.brand_id.in_(brand_ids),
                )
            )
        ).scalar() or 0

    credit_txns = (
        await db.execute(
            select(CreditTransaction).where(
                CreditTransaction.organization_id == org_id,
                CreditTransaction.transacted_at >= thirty_days_ago,
            )
        )
    ).scalars().all()

    packs = (
        await db.execute(
            select(PackPurchase).where(
                PackPurchase.organization_id == org_id,
                PackPurchase.purchased_at >= thirty_days_ago,
                PackPurchase.status == "completed",
            )
        )
    ).scalars().all()

    telemetry_rows = (
        await db.execute(
            select(MonetizationTelemetryEvent).where(
                MonetizationTelemetryEvent.organization_id == org_id,
                MonetizationTelemetryEvent.occurred_at >= thirty_days_ago,
            )
        )
    ).scalars().all()

    period_start = now.replace(day=1).strftime("%Y-%m-%d")
    meter_rows = (
        await db.execute(
            select(UsageMeterSnapshot).where(
                UsageMeterSnapshot.organization_id == org_id,
                UsageMeterSnapshot.period_start == period_start,
                UsageMeterSnapshot.is_active.is_(True),
            )
        )
    ).scalars().all()

    # Shape data for the scoring engine
    monthly_price = plan_row.monthly_price if plan_row else 0.0
    users_data = [
        {
            "user_id": str(u.id),
            "monthly_spend": monthly_price / max(len(org_users), 1),
            "plan": plan_tier,
            "segment": UserSegment.SERIOUS.value,
            "total_credits": ledger.total_credits if ledger else 0,
            "used_credits": ledger.used_credits if ledger else 0,
            "features_used": (plan_row.features_json if plan_row and plan_row.features_json else []),
            "spend_history": [],
            "signup_date": (
                u.created_at.isoformat()
                if hasattr(u, "created_at") and u.created_at
                else None
            ),
        }
        for u in org_users
    ]

    subscriptions_data = (
        [{"monthly_amount": plan_row.monthly_price, "status": plan_row.status}]
        if plan_row
        else []
    )

    credit_txn_data = [
        {
            "amount": abs(t.amount),
            "date": t.transacted_at.isoformat() if t.transacted_at else None,
        }
        for t in credit_txns
        if t.transaction_type == "purchase"
    ]

    pack_data = [
        {
            "amount": p.price,
            "date": p.purchased_at.isoformat() if p.purchased_at else None,
        }
        for p in packs
    ]

    usage_data = []
    if meter_rows:
        usage_data.append({
            "plan": plan_tier,
            "meters": {m.meter_type: m.units_used for m in meter_rows},
        })

    events_data = [
        TelemetryEvent(
            user_id=str(te.user_id) if te.user_id else "system",
            event_name=te.event_name,
            event_value=te.event_value,
            timestamp=te.occurred_at,
            properties=te.event_properties or {},
        )
        for te in telemetry_rows
    ]

    report = generate_machine_report(
        users=users_data,
        subscriptions=subscriptions_data,
        credit_transactions=credit_txn_data,
        pack_purchases=pack_data,
        usage_data=usage_data,
        events=events_data,
    )

    report_dict = asdict(report)
    report_dict["operational_context"] = {
        "total_brands": len(brand_ids),
        "total_content_items_30d": content_count,
        "total_active_offers": offer_count,
        "total_creator_accounts": account_count,
        "total_credit_transactions_30d": len(credit_txns),
        "total_pack_purchases_30d": len(packs),
        "total_telemetry_events_30d": len(telemetry_rows),
    }

    logger.info(
        "revenue_machine.report_generated",
        org_id=str(org_id),
        health_score=report.health_score,
    )
    return report_dict


# ---------------------------------------------------------------------------
# 2. Elite Readiness Scorecard
# ---------------------------------------------------------------------------

async def get_elite_readiness(db: AsyncSession, org_id: uuid.UUID) -> dict:
    """Compute the 7-question elite readiness scorecard using real DB data."""
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    brand_ids = await _get_org_brand_ids(db, org_id)
    plan_tier = await _get_plan_tier(db, org_id)

    # Q1 — Active paid subscription?
    has_paid_plan = plan_tier != "free"

    # Q2 — Content velocity (>= 10 items / 30 d)
    content_30d = 0
    if brand_ids:
        content_30d = (
            await db.execute(
                select(func.count(ContentItem.id)).where(
                    ContentItem.brand_id.in_(brand_ids),
                    ContentItem.created_at >= thirty_days_ago,
                )
            )
        ).scalar() or 0
    content_velocity_pass = content_30d >= 10

    # Q3 — Multi-platform presence (>= 2 distinct platforms)
    distinct_platforms = 0
    if brand_ids:
        distinct_platforms = (
            await db.execute(
                select(func.count(func.distinct(CreatorAccount.platform))).where(
                    CreatorAccount.brand_id.in_(brand_ids),
                )
            )
        ).scalar() or 0
    multi_platform_pass = distinct_platforms >= 2

    # Q4 — Credit health (remaining > 20 % of total)
    ledger = await _get_ledger(db, org_id)
    if ledger and ledger.total_credits > 0:
        credit_health_pct = (ledger.remaining_credits / ledger.total_credits) * 100
    else:
        credit_health_pct = 0.0
    credit_health_pass = credit_health_pct > 20

    # Q5 — Monetization coverage (>= 1 active offer)
    offer_count = 0
    if brand_ids:
        offer_count = (
            await db.execute(
                select(func.count(Offer.id)).where(
                    Offer.brand_id.in_(brand_ids),
                    Offer.is_active.is_(True),
                )
            )
        ).scalar() or 0
    monetization_pass = offer_count >= 1

    # Q6 — Growth trajectory (current-period events > prior-period events)
    current_period_events = (
        await db.execute(
            select(func.count(MonetizationTelemetryEvent.id)).where(
                MonetizationTelemetryEvent.organization_id == org_id,
                MonetizationTelemetryEvent.occurred_at >= thirty_days_ago,
            )
        )
    ).scalar() or 0
    prior_period_events = (
        await db.execute(
            select(func.count(MonetizationTelemetryEvent.id)).where(
                MonetizationTelemetryEvent.organization_id == org_id,
                MonetizationTelemetryEvent.occurred_at >= thirty_days_ago - timedelta(days=30),
                MonetizationTelemetryEvent.occurred_at < thirty_days_ago,
            )
        )
    ).scalar() or 0
    growth_pass = current_period_events > prior_period_events or current_period_events >= 50

    # Q7 — Automation adoption (>= 3 multiplication events in 30 d)
    mult_events = (
        await db.execute(
            select(func.count(MultiplicationEventModel.id)).where(
                MultiplicationEventModel.organization_id == org_id,
                MultiplicationEventModel.offered_at >= thirty_days_ago,
            )
        )
    ).scalar() or 0
    automation_pass = mult_events >= 3

    questions = [
        {
            "question": "Do you have an active paid subscription?",
            "key": "paid_plan",
            "passed": has_paid_plan,
            "detail": f"Current plan: {plan_tier}",
            "weight": 20,
        },
        {
            "question": "Are you generating content consistently (10+ items/month)?",
            "key": "content_velocity",
            "passed": content_velocity_pass,
            "detail": f"{content_30d} content items in the last 30 days",
            "weight": 15,
        },
        {
            "question": "Do you have multi-platform presence (2+ platforms)?",
            "key": "multi_platform",
            "passed": multi_platform_pass,
            "detail": f"{distinct_platforms} distinct platform(s) active",
            "weight": 15,
        },
        {
            "question": "Is your credit health above 20%?",
            "key": "credit_health",
            "passed": credit_health_pass,
            "detail": f"Credit remaining: {credit_health_pct:.1f}%",
            "weight": 10,
        },
        {
            "question": "Do you have at least one active monetization offer?",
            "key": "monetization_coverage",
            "passed": monetization_pass,
            "detail": f"{offer_count} active offer(s)",
            "weight": 15,
        },
        {
            "question": "Is your usage trajectory growing?",
            "key": "growth_trajectory",
            "passed": growth_pass,
            "detail": f"Current period: {current_period_events} events vs prior: {prior_period_events}",
            "weight": 10,
        },
        {
            "question": "Have you adopted automation (3+ multiplication events)?",
            "key": "automation_adoption",
            "passed": automation_pass,
            "detail": f"{mult_events} multiplication event(s) in 30 days",
            "weight": 15,
        },
    ]

    total_weight = sum(q["weight"] for q in questions)
    earned_weight = sum(q["weight"] for q in questions if q["passed"])
    readiness_score = (earned_weight / total_weight * 100) if total_weight > 0 else 0.0
    passed_count = sum(1 for q in questions if q["passed"])

    if readiness_score >= 85:
        grade = "Elite"
    elif readiness_score >= 70:
        grade = "Advanced"
    elif readiness_score >= 50:
        grade = "Growth"
    elif readiness_score >= 30:
        grade = "Foundation"
    else:
        grade = "Getting Started"

    failing = [q for q in questions if not q["passed"]]
    next_action = None
    if failing:
        highest_weight_fail = max(failing, key=lambda q: q["weight"])
        next_action = f"Focus on: {highest_weight_fail['question']}"

    return {
        "readiness_score": round(readiness_score, 1),
        "grade": grade,
        "passed": passed_count,
        "total": len(questions),
        "questions": questions,
        "next_action": next_action,
        "plan_tier": plan_tier,
    }


# ---------------------------------------------------------------------------
# 3. Active Spend Triggers
# ---------------------------------------------------------------------------

async def get_active_spend_triggers(
    db: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    current_action: str | None = None,
) -> dict:
    """Evaluate all spend triggers for the current user context."""
    now = datetime.now(timezone.utc)
    plan_tier = await _get_plan_tier(db, org_id)

    ledger = await _get_ledger(db, org_id)
    remaining = ledger.remaining_credits if ledger else 0
    total = ledger.total_credits if ledger else 0

    recent_mult = (
        await db.execute(
            select(func.count(MultiplicationEventModel.id)).where(
                MultiplicationEventModel.organization_id == org_id,
                MultiplicationEventModel.user_id == user_id,
                MultiplicationEventModel.offered_at >= now - timedelta(hours=24),
            )
        )
    ).scalar() or 0

    period_start = now.replace(day=1).strftime("%Y-%m-%d")
    meter_rows = (
        await db.execute(
            select(UsageMeterSnapshot).where(
                UsageMeterSnapshot.organization_id == org_id,
                UsageMeterSnapshot.period_start == period_start,
                UsageMeterSnapshot.is_active.is_(True),
            )
        )
    ).scalars().all()

    triggers: list[dict] = []

    if remaining < 50:
        triggers.append({
            "trigger_id": "low_credits",
            "type": "credit_topup",
            "urgency": 0.95 if remaining < 10 else 0.75,
            "message": f"Only {remaining} credits remaining — top up to keep generating",
            "recommended_action": "purchase_credit_pack",
            "recommended_pack": "credit_500" if remaining < 10 else "credit_2000",
        })

    if total > 0 and remaining / total < 0.2 and remaining >= 50:
        triggers.append({
            "trigger_id": "credit_exhaustion_near",
            "type": "credit_warning",
            "urgency": 0.6,
            "message": f"Credit balance at {remaining / total * 100:.0f}% — consider replenishing",
            "recommended_action": "purchase_credit_pack",
        })

    for m in meter_rows:
        if m.units_limit > 0 and m.utilization_pct >= 80:
            triggers.append({
                "trigger_id": f"meter_ceiling_{m.meter_type}",
                "type": "meter_warning",
                "urgency": min(m.utilization_pct / 100.0, 0.95),
                "message": f"{m.meter_type} at {m.utilization_pct:.0f}% of limit",
                "recommended_action": "upgrade_plan" if m.utilization_pct >= 95 else "monitor",
            })

    if plan_tier in ("free", "starter"):
        next_tier = "starter" if plan_tier == "free" else "professional"
        triggers.append({
            "trigger_id": "plan_upgrade",
            "type": "plan_upgrade",
            "urgency": 0.5,
            "message": "Upgrade for higher limits, more features, and lower transaction fees",
            "recommended_action": "upgrade_plan",
            "recommended_tier": next_tier,
        })

    _ACTION_TRIGGER_MAP: dict[str, dict] = {
        "generating_content": {
            "trigger_id": "premium_generation",
            "type": "premium_upsell",
            "urgency": 0.6,
            "message": "Upgrade to premium generation for faster, higher-quality outputs",
            "recommended_action": "purchase_premium_output",
        },
        "publishing": {
            "trigger_id": "priority_publishing",
            "type": "premium_upsell",
            "urgency": 0.5,
            "message": "Priority publishing gets your content live in under 30 seconds",
            "recommended_action": "purchase_priority_processing",
        },
        "running_automation": {
            "trigger_id": "automation_upgrade",
            "type": "feature_upsell",
            "urgency": 0.55,
            "message": "Unlock advanced automation workflows with a plan upgrade",
            "recommended_action": "upgrade_plan",
        },
        "viewing_analytics": {
            "trigger_id": "analytics_upgrade",
            "type": "feature_upsell",
            "urgency": 0.4,
            "message": "Advanced analytics with causal attribution available on Professional+",
            "recommended_action": "upgrade_plan",
        },
        "exporting": {
            "trigger_id": "export_upgrade",
            "type": "premium_upsell",
            "urgency": 0.45,
            "message": "Export in premium formats with custom branding",
            "recommended_action": "purchase_premium_output",
        },
    }
    if current_action and current_action in _ACTION_TRIGGER_MAP:
        triggers.append(_ACTION_TRIGGER_MAP[current_action])

    # Throttle to avoid overwhelming users with too many offers
    if recent_mult >= 5:
        triggers = [t for t in triggers if t["urgency"] >= 0.8]
    elif recent_mult >= 3:
        triggers = triggers[:3]

    triggers.sort(key=lambda t: t["urgency"], reverse=True)

    return {
        "triggers": triggers,
        "total_triggers": len(triggers),
        "recent_offers_24h": recent_mult,
        "plan_tier": plan_tier,
        "credit_remaining": remaining,
    }


# ---------------------------------------------------------------------------
# 4. Operating Model Health — 5 engines
# ---------------------------------------------------------------------------

async def get_operating_model_health(db: AsyncSession, org_id: uuid.UUID) -> dict:
    """Compute health of all 5 operating engines."""
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    brand_ids = await _get_org_brand_ids(db, org_id)
    plan_tier = await _get_plan_tier(db, org_id)

    # ---- Content Engine ----
    content_count = 0
    published_count = 0
    if brand_ids:
        content_count = (
            await db.execute(
                select(func.count(ContentItem.id)).where(
                    ContentItem.brand_id.in_(brand_ids),
                    ContentItem.created_at >= thirty_days_ago,
                )
            )
        ).scalar() or 0
        published_count = (
            await db.execute(
                select(func.count(ContentItem.id)).where(
                    ContentItem.brand_id.in_(brand_ids),
                    ContentItem.status == "published",
                    ContentItem.created_at >= thirty_days_ago,
                )
            )
        ).scalar() or 0
    content_score = min(100.0, content_count * 3 + published_count * 5)

    # ---- Distribution Engine ----
    account_count = 0
    distinct_platforms = 0
    if brand_ids:
        account_count = (
            await db.execute(
                select(func.count(CreatorAccount.id)).where(
                    CreatorAccount.brand_id.in_(brand_ids),
                )
            )
        ).scalar() or 0
        distinct_platforms = (
            await db.execute(
                select(func.count(func.distinct(CreatorAccount.platform))).where(
                    CreatorAccount.brand_id.in_(brand_ids),
                )
            )
        ).scalar() or 0
    distribution_score = min(100.0, account_count * 10 + distinct_platforms * 15 + published_count * 3)

    # ---- Monetization Engine ----
    offer_count = 0
    if brand_ids:
        offer_count = (
            await db.execute(
                select(func.count(Offer.id)).where(
                    Offer.brand_id.in_(brand_ids),
                    Offer.is_active.is_(True),
                )
            )
        ).scalar() or 0

    pack_revenue = (
        await db.execute(
            select(func.coalesce(func.sum(PackPurchase.price), 0.0)).where(
                PackPurchase.organization_id == org_id,
                PackPurchase.purchased_at >= thirty_days_ago,
                PackPurchase.status == "completed",
            )
        )
    ).scalar() or 0.0

    plan_row = await _get_plan_row(db, org_id)
    mrr = (plan_row.monthly_price if plan_row else 0) + float(pack_revenue)
    monetization_score = min(
        100.0,
        (20 if plan_tier != "free" else 0)
        + offer_count * 10
        + min(30, float(pack_revenue) * 0.5)
        + (10 if mrr > 100 else 0),
    )

    # ---- Intelligence Engine ----
    telemetry_count = (
        await db.execute(
            select(func.count(MonetizationTelemetryEvent.id)).where(
                MonetizationTelemetryEvent.organization_id == org_id,
                MonetizationTelemetryEvent.occurred_at >= thirty_days_ago,
            )
        )
    ).scalar() or 0
    intelligence_score = min(100.0, telemetry_count * 2 + (15 if content_count > 20 else 0))

    # ---- Automation Engine ----
    mult_events = (
        await db.execute(
            select(func.count(MultiplicationEventModel.id)).where(
                MultiplicationEventModel.organization_id == org_id,
                MultiplicationEventModel.offered_at >= thirty_days_ago,
            )
        )
    ).scalar() or 0
    mult_conversions = (
        await db.execute(
            select(func.count(MultiplicationEventModel.id)).where(
                MultiplicationEventModel.organization_id == org_id,
                MultiplicationEventModel.converted.is_(True),
                MultiplicationEventModel.offered_at >= thirty_days_ago,
            )
        )
    ).scalar() or 0
    automation_score = min(
        100.0,
        mult_events * 5
        + mult_conversions * 15
        + (20 if plan_tier in ("business", "enterprise") else 0),
    )

    def _status(score: float) -> str:
        if score >= 60:
            return "healthy"
        return "needs_attention" if score >= 30 else "critical"

    engines = [
        {
            "engine": "Content Engine",
            "key": "content",
            "score": round(content_score, 1),
            "status": _status(content_score),
            "metrics": {"content_items_30d": content_count, "published_30d": published_count},
        },
        {
            "engine": "Distribution Engine",
            "key": "distribution",
            "score": round(distribution_score, 1),
            "status": _status(distribution_score),
            "metrics": {"creator_accounts": account_count, "distinct_platforms": distinct_platforms},
        },
        {
            "engine": "Monetization Engine",
            "key": "monetization",
            "score": round(monetization_score, 1),
            "status": _status(monetization_score),
            "metrics": {
                "active_offers": offer_count,
                "pack_revenue_30d": round(float(pack_revenue), 2),
                "mrr": round(mrr, 2),
                "plan_tier": plan_tier,
            },
        },
        {
            "engine": "Intelligence Engine",
            "key": "intelligence",
            "score": round(intelligence_score, 1),
            "status": _status(intelligence_score),
            "metrics": {"telemetry_events_30d": telemetry_count},
        },
        {
            "engine": "Automation Engine",
            "key": "automation",
            "score": round(automation_score, 1),
            "status": _status(automation_score),
            "metrics": {
                "multiplication_events_30d": mult_events,
                "multiplication_conversions_30d": mult_conversions,
            },
        },
    ]

    avg_score = sum(e["score"] for e in engines) / len(engines)
    healthy_count = sum(1 for e in engines if e["status"] == "healthy")

    return {
        "overall_score": round(avg_score, 1),
        "overall_status": _status(avg_score),
        "healthy_engines": healthy_count,
        "total_engines": len(engines),
        "engines": engines,
    }


# ---------------------------------------------------------------------------
# 5. Transaction Fee Summary
# ---------------------------------------------------------------------------

async def get_transaction_fee_summary(db: AsyncSession, org_id: uuid.UUID) -> dict:
    """Compute projected platform fees from recent transactions."""
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    plan_tier = await _get_plan_tier(db, org_id)
    fee_rates = PLATFORM_FEE_RATES.get(plan_tier, PLATFORM_FEE_RATES["free"])
    brand_ids = await _get_org_brand_ids(db, org_id)

    spend_row = (
        await db.execute(
            select(
                func.count(CreditTransaction.id),
                func.coalesce(func.sum(func.abs(CreditTransaction.amount)), 0),
            ).where(
                CreditTransaction.organization_id == org_id,
                CreditTransaction.transaction_type == "spend",
                CreditTransaction.transacted_at >= thirty_days_ago,
            )
        )
    ).one()
    spend_count = spend_row[0] or 0
    spend_volume = int(spend_row[1] or 0)

    pack_row = (
        await db.execute(
            select(
                func.count(PackPurchase.id),
                func.coalesce(func.sum(PackPurchase.price), 0.0),
            ).where(
                PackPurchase.organization_id == org_id,
                PackPurchase.purchased_at >= thirty_days_ago,
                PackPurchase.status == "completed",
            )
        )
    ).one()
    pack_count = pack_row[0] or 0
    pack_volume = float(pack_row[1] or 0)

    content_count = 0
    if brand_ids:
        content_count = (
            await db.execute(
                select(func.count(ContentItem.id)).where(
                    ContentItem.brand_id.in_(brand_ids),
                    ContentItem.created_at >= thirty_days_ago,
                )
            )
        ).scalar() or 0

    generation_fee = content_count * fee_rates["content_generation"]
    transaction_fee = pack_volume * fee_rates["transaction_processing"]
    overage_fee = spend_volume * fee_rates["credit_overage"] * 0.05
    total_fees = generation_fee + transaction_fee + overage_fee

    free_rates = PLATFORM_FEE_RATES["free"]
    savings_vs_free = (
        round(
            (content_count * free_rates["content_generation"] + pack_volume * free_rates["transaction_processing"])
            - (generation_fee + transaction_fee),
            2,
        )
        if plan_tier != "free"
        else 0.0
    )

    return {
        "plan_tier": plan_tier,
        "period": "last_30_days",
        "total_fees": round(total_fees, 2),
        "projected_annual_fees": round(total_fees * 12, 2),
        "fee_breakdown": [
            {
                "fee_type": "content_generation",
                "description": "Platform fee on content generation",
                "volume": content_count,
                "rate": fee_rates["content_generation"],
                "amount": round(generation_fee, 2),
            },
            {
                "fee_type": "transaction_processing",
                "description": "Processing fee on pack/credit purchases",
                "volume": round(pack_volume, 2),
                "rate": fee_rates["transaction_processing"],
                "amount": round(transaction_fee, 2),
            },
            {
                "fee_type": "credit_overage",
                "description": "Fee on credit overage usage",
                "volume": spend_volume,
                "rate": fee_rates["credit_overage"],
                "amount": round(overage_fee, 2),
            },
        ],
        "fee_rates": fee_rates,
        "savings_vs_free": savings_vs_free,
        "summary": {
            "credit_spend_transactions": spend_count,
            "pack_purchases": pack_count,
            "content_items_generated": content_count,
        },
    }


# ---------------------------------------------------------------------------
# 6. Premium Output Catalog
# ---------------------------------------------------------------------------

async def get_premium_output_catalog(db: AsyncSession, org_id: uuid.UUID) -> dict:
    """Return available premium outputs with plan-aware pricing."""
    plan_tier = await _get_plan_tier(db, org_id)
    ladder = _get_pricing_ladder()
    plan_obj = ladder["plans"].get(plan_tier)

    can_purchase_premium = True
    if plan_obj and not plan_obj.can_purchase_premium_packs:
        can_purchase_premium = False

    packs = design_outcome_packs(
        product_capabilities=[
            "content_generation",
            "publishing",
            "analytics",
            "automation",
            "api_access",
            "offer_lab",
        ],
        user_segments=[UserSegment.CASUAL, UserSegment.SERIOUS, UserSegment.POWER_USER, UserSegment.OPERATOR],
    )

    catalog: list[dict] = []
    for pack in packs:
        pack_dict = asdict(pack)
        pack_dict["segment"] = pack.target_segment.value
        pack_dict["available"] = can_purchase_premium or pack.price <= 0

        if plan_tier in ("business", "enterprise") and pack.price > 0:
            pack_dict["discounted_price"] = round(pack.price * 0.85, 2)
            pack_dict["discount_pct"] = 15
        else:
            pack_dict["discounted_price"] = pack.price
            pack_dict["discount_pct"] = 0

        if not can_purchase_premium and pack.price > 0:
            pack_dict["gate_message"] = "Upgrade to Professional or higher to purchase premium packs"

        catalog.append(pack_dict)

    credit_packs = list(ladder["credit_packs"].values())
    credit_catalog = [
        {
            "pack_id": cp.pack_id,
            "name": cp.name,
            "credits": cp.credits,
            "price": cp.price,
            "price_per_credit": cp.price_per_credit,
            "bonus_credits": cp.bonus_credits,
            "valid_days": cp.valid_days,
            "best_for": cp.best_for,
            "available": plan_obj.can_purchase_credit_packs if plan_obj else False,
        }
        for cp in credit_packs
    ]

    return {
        "plan_tier": plan_tier,
        "can_purchase_premium": can_purchase_premium,
        "premium_packs": catalog,
        "credit_packs": credit_catalog,
        "total_premium_packs": len(catalog),
        "total_credit_packs": len(credit_catalog),
    }


# ---------------------------------------------------------------------------
# 7. Record Transaction Fee
# ---------------------------------------------------------------------------

async def record_transaction_fee(
    db: AsyncSession,
    org_id: uuid.UUID,
    fee_type: str,
    transaction_amount: float,
    plan_tier: str,
) -> dict:
    """Record a transaction fee event as monetization telemetry."""
    fee_rates = PLATFORM_FEE_RATES.get(plan_tier, PLATFORM_FEE_RATES["free"])
    rate = fee_rates.get(fee_type, 0.05)
    fee_amount = round(transaction_amount * rate, 4)

    event = MonetizationTelemetryEvent(
        organization_id=org_id,
        user_id=None,
        event_name=f"transaction_fee:{fee_type}",
        event_value=fee_amount,
        event_properties={
            "fee_type": fee_type,
            "transaction_amount": transaction_amount,
            "rate": rate,
            "plan_tier": plan_tier,
        },
    )
    db.add(event)
    await db.flush()

    logger.info(
        "revenue_machine.fee_recorded",
        org_id=str(org_id),
        fee_type=fee_type,
        fee_amount=fee_amount,
    )

    return {
        "event_id": str(event.id),
        "fee_type": fee_type,
        "transaction_amount": transaction_amount,
        "rate": rate,
        "fee_amount": fee_amount,
        "plan_tier": plan_tier,
        "recorded": True,
    }
