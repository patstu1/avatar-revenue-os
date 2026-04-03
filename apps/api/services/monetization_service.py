"""Monetization Machine Service — credits, meters, plans, packs, telemetry, ascension."""
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, func, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.monetization import (
    CreditLedger,
    CreditTransaction,
    UsageMeterSnapshot,
    PlanSubscription,
    PackPurchase,
    MultiplicationEvent,
    MonetizationTelemetryEvent,
)

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Pricing ladder (static catalog — move to DB/config when needed)
# ---------------------------------------------------------------------------

PRICING_LADDER = [
    {
        "tier": "free",
        "name": "Starter (Free)",
        "monthly_price": 0,
        "annual_price": 0,
        "included_credits": 100,
        "max_seats": 1,
        "max_brands": 1,
        "features": ["basic_content", "1_platform", "community_support"],
        "meter_limits": {
            "content_generations": 20,
            "ai_analyses": 50,
            "publishing_jobs": 10,
            "api_calls": 1000,
        },
    },
    {
        "tier": "starter",
        "name": "Starter",
        "monthly_price": 49,
        "annual_price": 468,
        "included_credits": 1_000,
        "max_seats": 2,
        "max_brands": 2,
        "features": ["all_content_forms", "3_platforms", "email_support", "basic_analytics"],
        "meter_limits": {
            "content_generations": 100,
            "ai_analyses": 500,
            "publishing_jobs": 50,
            "api_calls": 10_000,
        },
    },
    {
        "tier": "professional",
        "name": "Professional",
        "monthly_price": 149,
        "annual_price": 1_428,
        "included_credits": 5_000,
        "max_seats": 5,
        "max_brands": 5,
        "features": [
            "all_content_forms", "unlimited_platforms", "priority_support",
            "advanced_analytics", "experiment_engine", "offer_lab",
            "affiliate_intel", "brand_governance",
        ],
        "meter_limits": {
            "content_generations": 500,
            "ai_analyses": 5_000,
            "publishing_jobs": 250,
            "api_calls": 100_000,
        },
    },
    {
        "tier": "business",
        "name": "Business",
        "monthly_price": 399,
        "annual_price": 3_828,
        "included_credits": 20_000,
        "max_seats": 15,
        "max_brands": 20,
        "features": [
            "everything_in_professional", "autonomous_execution", "brain_decisions",
            "agent_mesh", "digital_twin", "revenue_intelligence",
            "enterprise_security", "workflow_builder", "custom_integrations",
        ],
        "meter_limits": {
            "content_generations": 2_000,
            "ai_analyses": 25_000,
            "publishing_jobs": 1_000,
            "api_calls": 500_000,
        },
    },
    {
        "tier": "enterprise",
        "name": "Enterprise",
        "monthly_price": 999,
        "annual_price": 9_588,
        "included_credits": 100_000,
        "max_seats": -1,
        "max_brands": -1,
        "features": [
            "everything_in_business", "dedicated_support", "sla",
            "custom_models", "white_label", "api_priority",
            "compliance_controls", "sso",
        ],
        "meter_limits": {
            "content_generations": -1,
            "ai_analyses": -1,
            "publishing_jobs": -1,
            "api_calls": -1,
        },
    },
]

OUTCOME_PACKS = [
    {
        "pack_id": "credit_500",
        "pack_type": "credit_pack",
        "name": "500 Credit Boost",
        "price": 19.99,
        "credits": 500,
        "items": {},
    },
    {
        "pack_id": "credit_2000",
        "pack_type": "credit_pack",
        "name": "2,000 Credit Pack",
        "price": 59.99,
        "credits": 2_000,
        "items": {},
    },
    {
        "pack_id": "credit_10000",
        "pack_type": "credit_pack",
        "name": "10,000 Credit Mega Pack",
        "price": 199.99,
        "credits": 10_000,
        "items": {},
    },
    {
        "pack_id": "outcome_viral",
        "pack_type": "outcome_pack",
        "name": "Viral Launch Pack",
        "price": 99.99,
        "credits": 3_000,
        "items": {
            "trend_scans": 10,
            "ai_optimizations": 5,
            "priority_publishing": True,
        },
    },
    {
        "pack_id": "outcome_revenue",
        "pack_type": "outcome_pack",
        "name": "Revenue Accelerator Pack",
        "price": 149.99,
        "credits": 5_000,
        "items": {
            "offer_lab_experiments": 10,
            "revenue_intel_reports": 5,
            "causal_attributions": 5,
            "digital_twin_simulations": 3,
        },
    },
    {
        "pack_id": "outcome_scale",
        "pack_type": "outcome_pack",
        "name": "Scale Blitz Pack",
        "price": 249.99,
        "credits": 12_000,
        "items": {
            "account_launches": 5,
            "warmup_acceleration": True,
            "priority_content_generation": 50,
            "autonomous_execution_hours": 100,
        },
    },
    {
        "pack_id": "premium_brain",
        "pack_type": "premium_pack",
        "name": "AI Brain Upgrade",
        "price": 79.99,
        "credits": 2_000,
        "items": {
            "brain_decisions_boost": 100,
            "agent_mesh_priority": True,
            "pattern_memory_retention": "extended",
        },
    },
]

# Credit costs per meter action
METER_CREDIT_COSTS: dict[str, int] = {
    "content_generation": 5,
    "ai_analysis": 1,
    "publishing_job": 2,
    "experiment_run": 10,
    "offer_lab_test": 8,
    "digital_twin_sim": 15,
    "revenue_intel_report": 3,
    "brain_decision": 1,
    "agent_run": 5,
    "causal_attribution": 5,
    "trend_scan": 2,
    "landing_page_gen": 10,
    "campaign_launch": 8,
    "api_call": 0,
}


# ---------------------------------------------------------------------------
# Core credit operations
# ---------------------------------------------------------------------------

async def get_credit_balance(db: AsyncSession, org_id: uuid.UUID) -> dict:
    """Return current credit balance for the organization."""
    row = (
        await db.execute(
            select(CreditLedger).where(
                CreditLedger.organization_id == org_id,
                CreditLedger.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()

    if not row:
        return {
            "total_credits": 0,
            "used_credits": 0,
            "remaining_credits": 0,
            "bonus_credits": 0,
            "replenishment_rate": 0,
            "overage_enabled": False,
            "overage_rate": 0.10,
            "next_replenishment_at": None,
        }

    return {
        "total_credits": row.total_credits,
        "used_credits": row.used_credits,
        "remaining_credits": row.remaining_credits,
        "bonus_credits": row.bonus_credits,
        "replenishment_rate": row.replenishment_rate,
        "overage_enabled": row.overage_enabled,
        "overage_rate": row.overage_rate,
        "next_replenishment_at": row.next_replenishment_at.isoformat() if row.next_replenishment_at else None,
    }


async def spend_credits(
    db: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    amount: int,
    meter_type: str,
    reference_id: str | None = None,
    description: str | None = None,
) -> dict:
    """Deduct credits and record the transaction. Returns new balance."""
    ledger = (
        await db.execute(
            select(CreditLedger).where(
                CreditLedger.organization_id == org_id,
                CreditLedger.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()

    if not ledger:
        return {"error": "no_ledger", "message": "No active credit ledger found"}

    effective_amount = amount if amount > 0 else METER_CREDIT_COSTS.get(meter_type, 1)

    if ledger.remaining_credits < effective_amount and not ledger.overage_enabled:
        return {
            "error": "insufficient_credits",
            "remaining": ledger.remaining_credits,
            "required": effective_amount,
        }

    original_remaining = ledger.remaining_credits
    ledger.used_credits += effective_amount
    ledger.remaining_credits = max(0, original_remaining - effective_amount)

    overage_cost = 0.0
    if original_remaining < effective_amount and ledger.overage_enabled:
        overage_units = effective_amount - original_remaining
        overage_cost = overage_units * ledger.overage_rate

    txn = CreditTransaction(
        organization_id=org_id,
        user_id=user_id,
        transaction_type="spend",
        amount=-effective_amount,
        balance_after=ledger.remaining_credits,
        meter_type=meter_type,
        reference_id=reference_id,
        description=description or f"Spent {effective_amount} credits on {meter_type}",
        metadata_json={"overage_cost": overage_cost} if overage_cost > 0 else {},
    )
    db.add(txn)
    await db.flush()

    logger.info("credits.spent", org_id=str(org_id), amount=effective_amount, meter_type=meter_type, remaining=ledger.remaining_credits)

    return {
        "spent": effective_amount,
        "remaining_credits": ledger.remaining_credits,
        "overage_cost": overage_cost,
        "transaction_id": str(txn.id),
    }


async def purchase_credits(
    db: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    pack_id: str,
    payment_id: str | None = None,
) -> dict:
    """Add credits from a pack purchase."""
    pack = next((p for p in OUTCOME_PACKS if p["pack_id"] == pack_id), None)
    if not pack:
        return {"error": "invalid_pack", "message": f"Pack {pack_id} not found"}

    ledger = (
        await db.execute(
            select(CreditLedger).where(
                CreditLedger.organization_id == org_id,
                CreditLedger.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()

    if not ledger:
        ledger = CreditLedger(
            organization_id=org_id,
            total_credits=pack["credits"],
            used_credits=0,
            remaining_credits=pack["credits"],
            bonus_credits=0,
        )
        db.add(ledger)
    else:
        ledger.total_credits += pack["credits"]
        ledger.remaining_credits += pack["credits"]

    purchase = PackPurchase(
        organization_id=org_id,
        user_id=user_id,
        pack_type=pack["pack_type"],
        pack_id=pack_id,
        pack_name=pack["name"],
        price=pack["price"],
        credits_awarded=pack["credits"],
        items_json=pack.get("items", {}),
        stripe_payment_id=payment_id,
        status="completed",
    )
    db.add(purchase)

    txn = CreditTransaction(
        organization_id=org_id,
        user_id=user_id,
        transaction_type="purchase",
        amount=pack["credits"],
        balance_after=ledger.remaining_credits,
        meter_type=None,
        reference_id=pack_id,
        description=f"Purchased {pack['name']} (+{pack['credits']} credits)",
    )
    db.add(txn)
    await db.flush()

    logger.info("credits.purchased", org_id=str(org_id), pack_id=pack_id, credits=pack["credits"])

    return {
        "pack_id": pack_id,
        "pack_name": pack["name"],
        "credits_awarded": pack["credits"],
        "new_balance": ledger.remaining_credits,
        "purchase_id": str(purchase.id),
    }


# ---------------------------------------------------------------------------
# Usage & plan
# ---------------------------------------------------------------------------

async def get_usage_summary(db: AsyncSession, org_id: uuid.UUID) -> dict:
    """All meter usage for the current billing period."""
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1).strftime("%Y-%m-%d")

    rows = (
        await db.execute(
            select(UsageMeterSnapshot).where(
                UsageMeterSnapshot.organization_id == org_id,
                UsageMeterSnapshot.period_start == period_start,
                UsageMeterSnapshot.is_active.is_(True),
            )
        )
    ).scalars().all()

    meters = []
    total_used = 0
    total_limit = 0
    total_overage_cost = 0.0

    for row in rows:
        meters.append({
            "meter_type": row.meter_type,
            "units_used": row.units_used,
            "units_limit": row.units_limit,
            "utilization_pct": row.utilization_pct,
            "overage_units": row.overage_units,
            "overage_cost": row.overage_cost,
        })
        total_used += row.units_used
        total_limit += row.units_limit
        total_overage_cost += row.overage_cost

    return {
        "period_start": period_start,
        "period_end": (now.replace(day=28) + timedelta(days=4)).replace(day=1).strftime("%Y-%m-%d"),
        "meters": meters,
        "total_units_used": total_used,
        "total_units_limit": total_limit,
        "total_overage_cost": total_overage_cost,
    }


async def get_plan_details(db: AsyncSession, org_id: uuid.UUID) -> dict:
    """Current plan with limits and usage."""
    plan = (
        await db.execute(
            select(PlanSubscription).where(
                PlanSubscription.organization_id == org_id,
                PlanSubscription.status == "active",
                PlanSubscription.is_active.is_(True),
            ).order_by(PlanSubscription.started_at.desc())
        )
    ).scalar_one_or_none()

    if not plan:
        free_plan = PRICING_LADDER[0]
        return {
            "plan_tier": "free",
            "plan_name": free_plan["name"],
            "monthly_price": 0,
            "billing_interval": "monthly",
            "included_credits": free_plan["included_credits"],
            "max_seats": free_plan["max_seats"],
            "max_brands": free_plan["max_brands"],
            "features": free_plan["features"],
            "meter_limits": free_plan["meter_limits"],
            "status": "active",
            "started_at": None,
            "current_period_end": None,
        }

    return {
        "plan_tier": plan.plan_tier,
        "plan_name": plan.plan_name,
        "monthly_price": plan.monthly_price,
        "billing_interval": plan.billing_interval,
        "included_credits": plan.included_credits,
        "max_seats": plan.max_seats,
        "max_brands": plan.max_brands,
        "features": plan.features_json or [],
        "meter_limits": plan.meter_limits_json or {},
        "status": plan.status,
        "started_at": plan.started_at.isoformat() if plan.started_at else None,
        "current_period_end": plan.current_period_end.isoformat() if plan.current_period_end else None,
    }


# ---------------------------------------------------------------------------
# Ascension & multiplication
# ---------------------------------------------------------------------------

ASCENSION_TRIGGERS = [
    {"trigger": "credit_exhaustion", "label": "Credits running low", "upgrade_tiers": ["starter", "professional"]},
    {"trigger": "seat_limit", "label": "Team seats maxed out", "upgrade_tiers": ["professional", "business"]},
    {"trigger": "brand_limit", "label": "Brand limit reached", "upgrade_tiers": ["professional", "business"]},
    {"trigger": "feature_gate", "label": "Attempted gated feature", "upgrade_tiers": ["professional", "business", "enterprise"]},
    {"trigger": "meter_ceiling", "label": "Usage meter at >80%", "upgrade_tiers": ["starter", "professional", "business"]},
    {"trigger": "high_engagement", "label": "Power user pattern detected", "upgrade_tiers": ["professional", "business"]},
    {"trigger": "revenue_velocity", "label": "Revenue growing fast", "upgrade_tiers": ["business", "enterprise"]},
    {"trigger": "api_volume", "label": "API call volume surging", "upgrade_tiers": ["business", "enterprise"]},
]


async def get_ascension_profile(
    db: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict:
    """Compute user's ascension state and active triggers."""
    balance = await get_credit_balance(db, org_id)
    plan = await get_plan_details(db, org_id)
    usage = await get_usage_summary(db, org_id)

    active_triggers = []

    if balance["remaining_credits"] < 50:
        active_triggers.append({
            **next(t for t in ASCENSION_TRIGGERS if t["trigger"] == "credit_exhaustion"),
            "urgency": 0.9,
            "context": f"Only {balance['remaining_credits']} credits remaining",
        })

    for meter in usage.get("meters", []):
        if meter["utilization_pct"] > 80:
            active_triggers.append({
                **next(t for t in ASCENSION_TRIGGERS if t["trigger"] == "meter_ceiling"),
                "urgency": min(meter["utilization_pct"] / 100.0, 1.0),
                "context": f"{meter['meter_type']} at {meter['utilization_pct']:.0f}% utilization",
            })

    current_tier = plan["plan_tier"]
    tier_index = next((i for i, p in enumerate(PRICING_LADDER) if p["tier"] == current_tier), 0)
    recommended_plan = PRICING_LADDER[tier_index + 1] if tier_index < len(PRICING_LADDER) - 1 else None

    savings = 0.0
    if recommended_plan and recommended_plan["monthly_price"] > 0:
        savings = (recommended_plan["monthly_price"] * 12 - recommended_plan["annual_price"])

    return {
        "current_tier": current_tier,
        "active_triggers": active_triggers,
        "trigger_count": len(active_triggers),
        "recommended_plan": recommended_plan,
        "annual_savings": savings,
        "ascension_score": min(len(active_triggers) * 0.25, 1.0),
        "credit_balance": balance,
        "usage_summary": usage,
    }


async def get_multiplication_opportunities(
    db: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    current_action: str | None = None,
) -> dict:
    """Detect real-time upsell moments based on user behaviour."""
    balance = await get_credit_balance(db, org_id)
    plan = await get_plan_details(db, org_id)

    opportunities: list[dict] = []

    if balance["remaining_credits"] < 100:
        opportunities.append({
            "type": "credit_topup",
            "message": "Running low on credits — top up to keep momentum",
            "recommended_pack": "credit_500",
            "urgency": 0.85,
        })

    if current_action and current_action in ("digital_twin_sim", "experiment_run", "offer_lab_test"):
        opportunities.append({
            "type": "power_feature_upsell",
            "message": f"Unlock unlimited {current_action.replace('_', ' ')} with a plan upgrade",
            "recommended_tier": "business",
            "urgency": 0.7,
        })

    if plan["plan_tier"] in ("free", "starter"):
        opportunities.append({
            "type": "plan_upgrade",
            "message": "Upgrade to Professional for 5x more credits and advanced features",
            "recommended_tier": "professional",
            "urgency": 0.6,
        })

    recent_events = (
        await db.execute(
            select(func.count(MultiplicationEvent.id)).where(
                MultiplicationEvent.organization_id == org_id,
                MultiplicationEvent.user_id == user_id,
                MultiplicationEvent.offered_at >= datetime.now(timezone.utc) - timedelta(hours=24),
            )
        )
    ).scalar() or 0

    if recent_events >= 3:
        opportunities = opportunities[:1]

    return {
        "opportunities": opportunities,
        "total_opportunities": len(opportunities),
        "recent_offers_24h": recent_events,
    }


# ---------------------------------------------------------------------------
# Health report
# ---------------------------------------------------------------------------

async def get_monetization_health(db: AsyncSession, org_id: uuid.UUID) -> dict:
    """Full monetization machine health report."""
    balance = await get_credit_balance(db, org_id)
    plan = await get_plan_details(db, org_id)
    usage = await get_usage_summary(db, org_id)

    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    total_revenue_result = (
        await db.execute(
            select(func.coalesce(func.sum(PackPurchase.price), 0.0)).where(
                PackPurchase.organization_id == org_id,
                PackPurchase.purchased_at >= thirty_days_ago,
                PackPurchase.status == "completed",
            )
        )
    ).scalar() or 0.0

    total_purchases_result = (
        await db.execute(
            select(func.count(PackPurchase.id)).where(
                PackPurchase.organization_id == org_id,
                PackPurchase.purchased_at >= thirty_days_ago,
                PackPurchase.status == "completed",
            )
        )
    ).scalar() or 0

    multiplication_conversions = (
        await db.execute(
            select(func.count(MultiplicationEvent.id)).where(
                MultiplicationEvent.organization_id == org_id,
                MultiplicationEvent.converted.is_(True),
                MultiplicationEvent.offered_at >= thirty_days_ago,
            )
        )
    ).scalar() or 0

    multiplication_offered = (
        await db.execute(
            select(func.count(MultiplicationEvent.id)).where(
                MultiplicationEvent.organization_id == org_id,
                MultiplicationEvent.offered_at >= thirty_days_ago,
            )
        )
    ).scalar() or 0

    multiplication_revenue = (
        await db.execute(
            select(func.coalesce(func.sum(MultiplicationEvent.revenue), 0.0)).where(
                MultiplicationEvent.organization_id == org_id,
                MultiplicationEvent.converted.is_(True),
                MultiplicationEvent.offered_at >= thirty_days_ago,
            )
        )
    ).scalar() or 0.0

    credit_utilization = (
        balance["used_credits"] / max(balance["total_credits"], 1)
    ) * 100

    health_score = 50.0
    if plan["plan_tier"] != "free":
        health_score += 15
    if credit_utilization > 20:
        health_score += 10
    if total_purchases_result > 0:
        health_score += 10
    if multiplication_conversions > 0:
        health_score += 15
    health_score = min(health_score, 100.0)

    conversion_rate = (
        (multiplication_conversions / max(multiplication_offered, 1)) * 100
    )

    return {
        "health_score": round(health_score, 1),
        "plan_tier": plan["plan_tier"],
        "credit_utilization_pct": round(credit_utilization, 1),
        "monthly_pack_revenue": round(total_revenue_result, 2),
        "monthly_pack_purchases": total_purchases_result,
        "subscription_mrr": plan["monthly_price"],
        "total_mrr": round(plan["monthly_price"] + (total_revenue_result / max(1, 1)), 2),
        "multiplication": {
            "offered_30d": multiplication_offered,
            "converted_30d": multiplication_conversions,
            "conversion_rate_pct": round(conversion_rate, 1),
            "revenue_30d": round(multiplication_revenue, 2),
        },
        "usage_summary": usage,
        "credit_balance": balance,
    }


# ---------------------------------------------------------------------------
# Static catalog accessors
# ---------------------------------------------------------------------------

def get_pricing_ladder() -> list[dict]:
    """Return complete pricing architecture."""
    return PRICING_LADDER


def get_outcome_packs() -> list[dict]:
    """Return all available outcome and credit packs."""
    return OUTCOME_PACKS


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------

async def record_telemetry(
    db: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    event_name: str,
    event_value: float = 0.0,
    properties: dict | None = None,
    session_id: str | None = None,
) -> dict:
    """Track a monetization telemetry event."""
    event = MonetizationTelemetryEvent(
        organization_id=org_id,
        user_id=user_id,
        event_name=event_name,
        event_value=event_value,
        event_properties=properties or {},
        session_id=session_id,
    )
    db.add(event)
    await db.flush()

    logger.info("monetization.telemetry", org_id=str(org_id), event_name=event_name, value=event_value)

    return {
        "event_id": str(event.id),
        "event_name": event_name,
        "recorded": True,
    }
