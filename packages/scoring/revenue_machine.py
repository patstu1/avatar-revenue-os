"""Revenue Machine Engine — The capstone architecture that ties everything together.

Implements the "elite-machine architecture" framework:
- Transaction/success fee layer on platform-generated revenue
- Premium output pricing for exports, deliverables, white-label
- 5 operating engines with health scores (Acquisition, Conversion, Expansion, Retention, Monetization)
- Elite Readiness Scorecard (7-question diagnostic)
- Contextual Spend Trigger system (upgrade nudges at critical moments)
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    return num / den if den else default


def _mean(vals: list[float], default: float = 0.0) -> float:
    return statistics.mean(vals) if vals else default


def _score_to_grade(score: float) -> str:
    if score >= 90:
        return "S"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C"
    if score >= 45:
        return "D"
    return "F"


def _correlation(xs: list[float], ys: list[float]) -> float:
    """Pearson correlation coefficient. Returns 0 if insufficient data."""
    n = len(xs)
    if n < 3 or len(ys) != n:
        return 0.0
    x_bar = statistics.mean(xs)
    y_bar = statistics.mean(ys)
    ss_xy = sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, ys))
    ss_xx = sum((x - x_bar) ** 2 for x in xs)
    ss_yy = sum((y - y_bar) ** 2 for y in ys)
    denom = math.sqrt(ss_xx * ss_yy)
    return ss_xy / denom if denom > 0 else 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: TRANSACTION / SUCCESS FEE LAYER
# ═══════════════════════════════════════════════════════════════════════════════


class FeeType(str, Enum):
    AFFILIATE_COMMISSION = "affiliate_commission"
    AD_REVENUE_SHARE = "ad_revenue_share"
    BOOKING_FEE = "booking_fee"
    LEAD_ROUTING_FEE = "lead_routing_fee"
    COMMERCE_TRANSACTION = "commerce_transaction"
    SPONSOR_DEAL_FEE = "sponsor_deal_fee"
    PREMIUM_PLACEMENT = "premium_placement"


@dataclass
class TransactionFeeSchedule:
    fee_type: FeeType
    base_rate_pct: float
    tiered_rates: list[dict] = field(default_factory=list)
    cap_per_transaction: float = 0.0
    min_per_transaction: float = 0.0
    plan_discounts: dict = field(default_factory=dict)


DEFAULT_FEE_SCHEDULES: dict[FeeType, TransactionFeeSchedule] = {
    FeeType.AFFILIATE_COMMISSION: TransactionFeeSchedule(
        fee_type=FeeType.AFFILIATE_COMMISSION,
        base_rate_pct=5.0,
        tiered_rates=[
            {"min_revenue": 0, "max_revenue": 1000, "rate_pct": 5.0},
            {"min_revenue": 1000, "max_revenue": 10000, "rate_pct": 4.0},
            {"min_revenue": 10000, "max_revenue": 100000, "rate_pct": 3.0},
            {"min_revenue": 100000, "max_revenue": float("inf"), "rate_pct": 2.0},
        ],
        plan_discounts={"starter": 1.0, "professional": 0.8, "business": 0.6, "enterprise": 0.4},
    ),
    FeeType.AD_REVENUE_SHARE: TransactionFeeSchedule(
        fee_type=FeeType.AD_REVENUE_SHARE,
        base_rate_pct=3.0,
        tiered_rates=[
            {"min_revenue": 0, "max_revenue": 5000, "rate_pct": 3.0},
            {"min_revenue": 5000, "max_revenue": 50000, "rate_pct": 2.5},
            {"min_revenue": 50000, "max_revenue": float("inf"), "rate_pct": 1.5},
        ],
        plan_discounts={"starter": 1.0, "professional": 0.7, "business": 0.5, "enterprise": 0.3},
    ),
    FeeType.SPONSOR_DEAL_FEE: TransactionFeeSchedule(
        fee_type=FeeType.SPONSOR_DEAL_FEE,
        base_rate_pct=8.0,
        tiered_rates=[
            {"min_revenue": 0, "max_revenue": 5000, "rate_pct": 8.0},
            {"min_revenue": 5000, "max_revenue": 50000, "rate_pct": 6.0},
            {"min_revenue": 50000, "max_revenue": float("inf"), "rate_pct": 4.0},
        ],
        plan_discounts={"starter": 1.0, "professional": 0.75, "business": 0.5, "enterprise": 0.3},
    ),
    FeeType.COMMERCE_TRANSACTION: TransactionFeeSchedule(
        fee_type=FeeType.COMMERCE_TRANSACTION,
        base_rate_pct=2.5,
        cap_per_transaction=500.0,
        tiered_rates=[
            {"min_revenue": 0, "max_revenue": 10000, "rate_pct": 2.5},
            {"min_revenue": 10000, "max_revenue": 100000, "rate_pct": 2.0},
            {"min_revenue": 100000, "max_revenue": float("inf"), "rate_pct": 1.5},
        ],
        plan_discounts={"starter": 1.0, "professional": 0.8, "business": 0.6, "enterprise": 0.3},
    ),
    FeeType.BOOKING_FEE: TransactionFeeSchedule(
        fee_type=FeeType.BOOKING_FEE,
        base_rate_pct=10.0,
        cap_per_transaction=200.0,
        tiered_rates=[
            {"min_revenue": 0, "max_revenue": 2000, "rate_pct": 10.0},
            {"min_revenue": 2000, "max_revenue": 20000, "rate_pct": 7.0},
            {"min_revenue": 20000, "max_revenue": float("inf"), "rate_pct": 5.0},
        ],
        plan_discounts={"starter": 1.0, "professional": 0.7, "business": 0.5, "enterprise": 0.3},
    ),
    FeeType.LEAD_ROUTING_FEE: TransactionFeeSchedule(
        fee_type=FeeType.LEAD_ROUTING_FEE,
        base_rate_pct=7.5,
        tiered_rates=[
            {"min_revenue": 0, "max_revenue": 3000, "rate_pct": 7.5},
            {"min_revenue": 3000, "max_revenue": 30000, "rate_pct": 5.5},
            {"min_revenue": 30000, "max_revenue": float("inf"), "rate_pct": 3.5},
        ],
        plan_discounts={"starter": 1.0, "professional": 0.75, "business": 0.5, "enterprise": 0.3},
    ),
    FeeType.PREMIUM_PLACEMENT: TransactionFeeSchedule(
        fee_type=FeeType.PREMIUM_PLACEMENT,
        base_rate_pct=15.0,
        tiered_rates=[
            {"min_revenue": 0, "max_revenue": 1000, "rate_pct": 15.0},
            {"min_revenue": 1000, "max_revenue": 10000, "rate_pct": 12.0},
            {"min_revenue": 10000, "max_revenue": float("inf"), "rate_pct": 8.0},
        ],
        plan_discounts={"starter": 1.0, "professional": 0.8, "business": 0.6, "enterprise": 0.4},
    ),
}


def _resolve_tiered_rate(schedule: TransactionFeeSchedule, cumulative_revenue: float) -> float:
    """Walk the tier table and return the rate_pct matching cumulative revenue."""
    if not schedule.tiered_rates:
        return schedule.base_rate_pct
    for tier in schedule.tiered_rates:
        if tier["min_revenue"] <= cumulative_revenue < tier["max_revenue"]:
            return tier["rate_pct"]
    return schedule.tiered_rates[-1]["rate_pct"]


def calculate_transaction_fee(
    fee_type: FeeType | str,
    transaction_amount: float,
    plan_tier: str = "starter",
    cumulative_monthly_revenue: float = 0.0,
    custom_schedule: TransactionFeeSchedule | None = None,
) -> dict:
    """Calculate the platform fee for a single revenue-generating transaction.

    Returns dict with fee_amount, effective_rate, savings_vs_starter, and breakdown.
    """
    if isinstance(fee_type, str):
        fee_type = FeeType(fee_type)

    schedule = custom_schedule or DEFAULT_FEE_SCHEDULES.get(fee_type)
    if schedule is None:
        return {
            "fee_amount": 0.0,
            "effective_rate_pct": 0.0,
            "savings_vs_starter": 0.0,
            "error": f"No fee schedule for {fee_type}",
        }

    rate_pct = _resolve_tiered_rate(schedule, cumulative_monthly_revenue)
    plan_multiplier = schedule.plan_discounts.get(plan_tier, 1.0)
    adjusted_rate = rate_pct * plan_multiplier

    raw_fee = transaction_amount * (adjusted_rate / 100.0)

    if schedule.min_per_transaction > 0:
        raw_fee = max(raw_fee, schedule.min_per_transaction)
    if schedule.cap_per_transaction > 0:
        raw_fee = min(raw_fee, schedule.cap_per_transaction)

    effective_rate = _safe_div(raw_fee, transaction_amount) * 100.0

    starter_rate = rate_pct * schedule.plan_discounts.get("starter", 1.0)
    starter_fee = transaction_amount * (starter_rate / 100.0)
    if schedule.min_per_transaction > 0:
        starter_fee = max(starter_fee, schedule.min_per_transaction)
    if schedule.cap_per_transaction > 0:
        starter_fee = min(starter_fee, schedule.cap_per_transaction)
    savings = starter_fee - raw_fee

    return {
        "fee_type": fee_type.value,
        "transaction_amount": round(transaction_amount, 2),
        "plan_tier": plan_tier,
        "base_rate_pct": rate_pct,
        "plan_multiplier": plan_multiplier,
        "adjusted_rate_pct": round(adjusted_rate, 4),
        "fee_amount": round(raw_fee, 2),
        "effective_rate_pct": round(effective_rate, 4),
        "savings_vs_starter": round(max(savings, 0.0), 2),
        "cap_applied": schedule.cap_per_transaction > 0 and raw_fee >= schedule.cap_per_transaction,
        "tier_used_revenue_range": f"{cumulative_monthly_revenue:.0f}+",
    }


def project_transaction_fee_revenue(
    transactions_by_type: list[dict],
    plan_tier: str = "starter",
) -> dict:
    """Project total platform fee revenue from a list of transactions.

    Each entry in transactions_by_type: {"fee_type": str, "amount": float, "count": int}
    """
    results_by_type: dict[str, dict] = {}
    total_fee_revenue = 0.0
    total_transaction_volume = 0.0
    total_savings = 0.0

    for txn in transactions_by_type:
        ft = txn.get("fee_type", "")
        amount = txn.get("amount", 0.0)
        count = txn.get("count", 1)

        cumulative = 0.0
        type_fees = 0.0
        type_savings = 0.0

        for _ in range(count):
            result = calculate_transaction_fee(ft, amount, plan_tier, cumulative)
            fee = result.get("fee_amount", 0.0)
            type_fees += fee
            type_savings += result.get("savings_vs_starter", 0.0)
            cumulative += amount

        total_fee_revenue += type_fees
        total_transaction_volume += amount * count
        total_savings += type_savings

        results_by_type[ft] = {
            "transaction_count": count,
            "total_volume": round(amount * count, 2),
            "total_fees": round(type_fees, 2),
            "effective_rate_pct": round(_safe_div(type_fees, amount * count) * 100, 4),
            "savings_vs_starter": round(type_savings, 2),
        }

    blended_rate = _safe_div(total_fee_revenue, total_transaction_volume) * 100.0

    return {
        "plan_tier": plan_tier,
        "total_transaction_volume": round(total_transaction_volume, 2),
        "total_fee_revenue": round(total_fee_revenue, 2),
        "blended_effective_rate_pct": round(blended_rate, 4),
        "total_savings_vs_starter": round(total_savings, 2),
        "annual_projected_fee_revenue": round(total_fee_revenue * 12, 2),
        "breakdown_by_type": results_by_type,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: PREMIUM OUTPUT PRICING
# ═══════════════════════════════════════════════════════════════════════════════


class OutputAccessLevel(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


@dataclass
class PremiumOutput:
    output_type: str
    display_name: str
    description: str
    base_price: float
    credit_cost: int
    plan_access_level: OutputAccessLevel
    bulk_discount_tiers: list[dict] = field(default_factory=list)
    category: str = "general"


_PREMIUM_CATALOG: list[PremiumOutput] = [
    PremiumOutput(
        output_type="export_hd_video",
        display_name="HD Video Export",
        description="Export content as a polished HD video with branding and transitions",
        base_price=4.99,
        credit_cost=25,
        plan_access_level=OutputAccessLevel.STARTER,
        bulk_discount_tiers=[{"min_qty": 5, "discount_pct": 10}, {"min_qty": 20, "discount_pct": 20}],
        category="export",
    ),
    PremiumOutput(
        output_type="production_pdf_report",
        display_name="Production PDF Report",
        description="Generate a branded PDF analytics/strategy report with charts",
        base_price=9.99,
        credit_cost=40,
        plan_access_level=OutputAccessLevel.PROFESSIONAL,
        bulk_discount_tiers=[{"min_qty": 3, "discount_pct": 15}, {"min_qty": 10, "discount_pct": 25}],
        category="report",
    ),
    PremiumOutput(
        output_type="white_label_asset",
        display_name="White-Label Asset Pack",
        description="Remove all platform branding for client-ready deliverables",
        base_price=14.99,
        credit_cost=60,
        plan_access_level=OutputAccessLevel.BUSINESS,
        bulk_discount_tiers=[{"min_qty": 5, "discount_pct": 15}, {"min_qty": 25, "discount_pct": 30}],
        category="white_label",
    ),
    PremiumOutput(
        output_type="api_bulk_export",
        display_name="API Bulk Data Export",
        description="Export raw data via API for external analytics or BI tools",
        base_price=19.99,
        credit_cost=80,
        plan_access_level=OutputAccessLevel.BUSINESS,
        bulk_discount_tiers=[{"min_qty": 3, "discount_pct": 10}],
        category="export",
    ),
    PremiumOutput(
        output_type="branded_template",
        display_name="Custom Branded Template",
        description="AI-generated content template with full brand guidelines applied",
        base_price=7.99,
        credit_cost=35,
        plan_access_level=OutputAccessLevel.PROFESSIONAL,
        bulk_discount_tiers=[{"min_qty": 5, "discount_pct": 10}, {"min_qty": 15, "discount_pct": 20}],
        category="template",
    ),
    PremiumOutput(
        output_type="investor_deck",
        display_name="Investor/Pitch Deck",
        description="AI-crafted pitch deck with financial projections and market analysis",
        base_price=29.99,
        credit_cost=120,
        plan_access_level=OutputAccessLevel.BUSINESS,
        bulk_discount_tiers=[{"min_qty": 2, "discount_pct": 10}],
        category="report",
    ),
    PremiumOutput(
        output_type="automated_campaign_build",
        display_name="Automated Campaign Build",
        description="Full campaign setup: copy, assets, scheduling, and tracking links",
        base_price=24.99,
        credit_cost=100,
        plan_access_level=OutputAccessLevel.PROFESSIONAL,
        bulk_discount_tiers=[{"min_qty": 3, "discount_pct": 15}],
        category="automation",
    ),
    PremiumOutput(
        output_type="priority_render",
        display_name="Priority Render Queue",
        description="Skip the queue — get AI outputs in under 30 seconds",
        base_price=1.99,
        credit_cost=5,
        plan_access_level=OutputAccessLevel.STARTER,
        bulk_discount_tiers=[{"min_qty": 20, "discount_pct": 25}, {"min_qty": 50, "discount_pct": 40}],
        category="speed",
    ),
    PremiumOutput(
        output_type="concierge_review",
        display_name="Concierge Review",
        description="Expert human review and optimization of AI-generated content",
        base_price=49.99,
        credit_cost=200,
        plan_access_level=OutputAccessLevel.BUSINESS,
        bulk_discount_tiers=[{"min_qty": 3, "discount_pct": 10}],
        category="service",
    ),
    PremiumOutput(
        output_type="custom_voiceover",
        display_name="Custom AI Voiceover",
        description="Generate professional voiceover with cloned or premium AI voices",
        base_price=6.99,
        credit_cost=30,
        plan_access_level=OutputAccessLevel.PROFESSIONAL,
        bulk_discount_tiers=[{"min_qty": 10, "discount_pct": 15}, {"min_qty": 30, "discount_pct": 25}],
        category="media",
    ),
    PremiumOutput(
        output_type="analytics_deep_dive",
        display_name="Analytics Deep Dive",
        description="Comprehensive performance report with predictive insights and recommendations",
        base_price=19.99,
        credit_cost=75,
        plan_access_level=OutputAccessLevel.PROFESSIONAL,
        bulk_discount_tiers=[{"min_qty": 3, "discount_pct": 15}],
        category="report",
    ),
    PremiumOutput(
        output_type="competitor_audit",
        display_name="Competitor Audit Report",
        description="Full competitor teardown: content strategy, audience overlap, gap analysis",
        base_price=34.99,
        credit_cost=150,
        plan_access_level=OutputAccessLevel.BUSINESS,
        bulk_discount_tiers=[{"min_qty": 2, "discount_pct": 10}, {"min_qty": 5, "discount_pct": 20}],
        category="report",
    ),
]

_ACCESS_LEVEL_ORDER: dict[OutputAccessLevel, int] = {
    OutputAccessLevel.FREE: 0,
    OutputAccessLevel.STARTER: 1,
    OutputAccessLevel.PROFESSIONAL: 2,
    OutputAccessLevel.BUSINESS: 3,
    OutputAccessLevel.ENTERPRISE: 4,
}

_PLAN_TO_ACCESS: dict[str, OutputAccessLevel] = {
    "free": OutputAccessLevel.FREE,
    "starter": OutputAccessLevel.STARTER,
    "professional": OutputAccessLevel.PROFESSIONAL,
    "business": OutputAccessLevel.BUSINESS,
    "enterprise": OutputAccessLevel.ENTERPRISE,
}


def get_premium_output_catalog() -> list[dict]:
    """Return the full premium output catalog as serializable dicts."""
    return [
        {
            "output_type": p.output_type,
            "display_name": p.display_name,
            "description": p.description,
            "base_price": p.base_price,
            "credit_cost": p.credit_cost,
            "plan_access_level": p.plan_access_level.value,
            "bulk_discount_tiers": p.bulk_discount_tiers,
            "category": p.category,
        }
        for p in _PREMIUM_CATALOG
    ]


def calculate_output_price(
    output_type: str,
    plan_tier: str = "starter",
    quantity: int = 1,
) -> dict:
    """Price a premium output purchase, applying access checks and bulk discounts."""
    output = next((p for p in _PREMIUM_CATALOG if p.output_type == output_type), None)
    if output is None:
        return {"error": f"Unknown output type: {output_type}", "total_price": 0.0}

    user_access = _PLAN_TO_ACCESS.get(plan_tier, OutputAccessLevel.FREE)
    required_level = _ACCESS_LEVEL_ORDER[output.plan_access_level]
    user_level = _ACCESS_LEVEL_ORDER[user_access]

    if user_level < required_level:
        return {
            "output_type": output_type,
            "accessible": False,
            "required_plan": output.plan_access_level.value,
            "current_plan": plan_tier,
            "upgrade_message": f"Upgrade to {output.plan_access_level.value} to unlock {output.display_name}",
            "total_price": 0.0,
        }

    discount_pct = 0.0
    for tier in sorted(output.bulk_discount_tiers, key=lambda t: t["min_qty"], reverse=True):
        if quantity >= tier["min_qty"]:
            discount_pct = tier["discount_pct"]
            break

    unit_price = output.base_price * (1.0 - discount_pct / 100.0)
    total_price = unit_price * quantity
    total_credits = output.credit_cost * quantity
    savings = (output.base_price * quantity) - total_price

    return {
        "output_type": output_type,
        "display_name": output.display_name,
        "accessible": True,
        "quantity": quantity,
        "unit_price": round(unit_price, 2),
        "total_price": round(total_price, 2),
        "credit_cost_total": total_credits,
        "bulk_discount_applied_pct": discount_pct,
        "savings": round(savings, 2),
        "category": output.category,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: OPERATING MODEL — 5 ENGINES
# ═══════════════════════════════════════════════════════════════════════════════


class EngineGrade(str, Enum):
    ELITE = "elite"
    STRONG = "strong"
    HEALTHY = "healthy"
    UNDERPERFORMING = "underperforming"
    CRITICAL = "critical"


@dataclass
class EngineHealth:
    engine_name: str
    health_score: float
    grade: str
    signals: list[dict] = field(default_factory=list)
    bottlenecks: list[str] = field(default_factory=list)
    recommended_actions: list[dict] = field(default_factory=list)


def _grade_engine(score: float) -> str:
    if score >= 85:
        return EngineGrade.ELITE.value
    if score >= 70:
        return EngineGrade.STRONG.value
    if score >= 55:
        return EngineGrade.HEALTHY.value
    if score >= 35:
        return EngineGrade.UNDERPERFORMING.value
    return EngineGrade.CRITICAL.value


def _score_acquisition(m: dict) -> EngineHealth:
    """Acquisition engine: clear wedge, fast demo value, low friction, shareable outputs."""
    signals: list[dict] = []
    bottlenecks: list[str] = []
    actions: list[dict] = []

    signup_rate = m.get("weekly_signup_rate", 0)
    organic_pct = m.get("organic_signup_pct", 0.0)
    time_to_first_value = m.get("median_time_to_first_value_seconds", 600)
    viral_coefficient = m.get("viral_coefficient", 0.0)
    share_rate = m.get("output_share_rate", 0.0)
    activation_rate = m.get("day1_activation_rate", 0.0)
    cac = m.get("cac", 0.0)
    ltv = m.get("ltv", 0.0)

    signup_score = min(25, (signup_rate / max(m.get("signup_target", 100), 1)) * 25)
    signals.append({"metric": "weekly_signups", "value": signup_rate, "score": round(signup_score, 1)})

    ttfv_score = 25.0 if time_to_first_value <= 120 else max(0, 25 - (time_to_first_value - 120) / 30)
    ttfv_score = _clamp(ttfv_score, 0, 25)
    signals.append({"metric": "time_to_first_value_sec", "value": time_to_first_value, "score": round(ttfv_score, 1)})
    if time_to_first_value > 300:
        bottlenecks.append(f"Time-to-first-value is {time_to_first_value}s — target is under 300s")
        actions.append(
            {
                "action": "reduce_time_to_value",
                "description": "Streamline onboarding to deliver value in under 5 minutes. Pre-fill templates, skip optional steps.",
                "priority": "critical",
                "expected_impact_pct": 20,
            }
        )

    viral_score = min(25, viral_coefficient * 25)
    share_bonus = min(5, share_rate * 50)
    viral_score = _clamp(viral_score + share_bonus, 0, 25)
    signals.append(
        {"metric": "viral_coefficient", "value": round(viral_coefficient, 3), "score": round(viral_score, 1)}
    )
    if viral_coefficient < 0.3:
        bottlenecks.append(f"Viral coefficient is {viral_coefficient:.2f} — organic growth is weak")
        actions.append(
            {
                "action": "increase_shareability",
                "description": "Add share CTAs to outputs, watermark free exports with viral links, implement referral rewards.",
                "priority": "high",
                "expected_impact_pct": 15,
            }
        )

    friction_raw = activation_rate * 100
    friction_score = min(25, friction_raw * 0.5)
    organic_bonus = min(5, organic_pct * 10)
    friction_score = _clamp(friction_score + organic_bonus, 0, 25)
    signals.append(
        {"metric": "day1_activation_rate", "value": round(activation_rate, 3), "score": round(friction_score, 1)}
    )
    if activation_rate < 0.4:
        bottlenecks.append(f"Day-1 activation is {activation_rate:.0%} — too many users drop off before seeing value")
        actions.append(
            {
                "action": "reduce_onboarding_friction",
                "description": "Implement progressive disclosure, remove mandatory fields, add skip-to-value path.",
                "priority": "high",
                "expected_impact_pct": 18,
            }
        )

    ltv_cac = _safe_div(ltv, cac, 0)
    if cac > 0 and ltv_cac < 3:
        bottlenecks.append(f"LTV:CAC ratio is {ltv_cac:.1f}x — below healthy 3x threshold")
        actions.append(
            {
                "action": "improve_ltv_cac",
                "description": "Reduce paid acquisition spend, double down on organic/viral channels, improve retention.",
                "priority": "high",
                "expected_impact_pct": 12,
            }
        )

    total = _clamp(signup_score + ttfv_score + viral_score + friction_score)

    return EngineHealth(
        engine_name="acquisition",
        health_score=round(total, 1),
        grade=_grade_engine(total),
        signals=signals,
        bottlenecks=bottlenecks,
        recommended_actions=sorted(actions, key=lambda a: a.get("expected_impact_pct", 0), reverse=True),
    )


def _score_conversion(m: dict) -> EngineHealth:
    """Conversion engine: immediate proof, clear upgrade reason, metered moments, packaging."""
    signals: list[dict] = []
    bottlenecks: list[str] = []
    actions: list[dict] = []

    free_to_paid = m.get("free_to_paid_rate", 0.0)
    m.get("trial_to_paid_rate", 0.0)
    first_purchase_time_hrs = m.get("median_time_to_first_purchase_hours", 168)
    upgrade_cta_click_rate = m.get("upgrade_cta_click_rate", 0.0)
    paywall_encounter_rate = m.get("paywall_encounter_rate", 0.0)
    pricing_page_conversion = m.get("pricing_page_conversion_rate", 0.0)

    f2p_score = min(30, free_to_paid * 100 * 2)
    signals.append({"metric": "free_to_paid_rate", "value": round(free_to_paid, 4), "score": round(f2p_score, 1)})
    if free_to_paid < 0.03:
        bottlenecks.append(f"Free-to-paid conversion is {free_to_paid:.1%} — below 3% benchmark")
        actions.append(
            {
                "action": "improve_free_to_paid",
                "description": "Add upgrade prompts at value moments, limit free tier to create urgency, show before/after proof.",
                "priority": "critical",
                "expected_impact_pct": 25,
            }
        )

    speed_score = 20.0 if first_purchase_time_hrs <= 24 else max(0, 20 - (first_purchase_time_hrs - 24) / 20)
    speed_score = _clamp(speed_score, 0, 20)
    signals.append(
        {"metric": "time_to_first_purchase_hrs", "value": first_purchase_time_hrs, "score": round(speed_score, 1)}
    )
    if first_purchase_time_hrs > 168:
        bottlenecks.append(f"Median first purchase takes {first_purchase_time_hrs:.0f}h — must shorten decision window")
        actions.append(
            {
                "action": "accelerate_first_purchase",
                "description": "Add time-limited offers, usage-based triggers, and clear 'you just hit a limit' messaging.",
                "priority": "high",
                "expected_impact_pct": 15,
            }
        )

    metered_score = min(20, paywall_encounter_rate * 100 * 2)
    signals.append(
        {
            "metric": "paywall_encounter_rate",
            "value": round(paywall_encounter_rate, 4),
            "score": round(metered_score, 1),
        }
    )
    if paywall_encounter_rate < 0.1:
        bottlenecks.append("Too few users hitting premium moments — free tier may be too generous")
        actions.append(
            {
                "action": "increase_premium_moments",
                "description": "Tighten free limits, gate 2-3 high-value features, show premium outputs as previews.",
                "priority": "high",
                "expected_impact_pct": 18,
            }
        )

    packaging_score = min(15, pricing_page_conversion * 100 * 1.5)
    signals.append(
        {
            "metric": "pricing_page_conversion",
            "value": round(pricing_page_conversion, 4),
            "score": round(packaging_score, 1),
        }
    )

    cta_score = min(15, upgrade_cta_click_rate * 100 * 1.5)
    signals.append(
        {"metric": "upgrade_cta_click_rate", "value": round(upgrade_cta_click_rate, 4), "score": round(cta_score, 1)}
    )
    if upgrade_cta_click_rate < 0.05:
        actions.append(
            {
                "action": "optimize_upgrade_ctas",
                "description": "A/B test CTA copy, placement, and timing. Show savings or ROI in the CTA.",
                "priority": "medium",
                "expected_impact_pct": 10,
            }
        )

    total = _clamp(f2p_score + speed_score + metered_score + packaging_score + cta_score)

    return EngineHealth(
        engine_name="conversion",
        health_score=round(total, 1),
        grade=_grade_engine(total),
        signals=signals,
        bottlenecks=bottlenecks,
        recommended_actions=sorted(actions, key=lambda a: a.get("expected_impact_pct", 0), reverse=True),
    )


def _score_expansion(m: dict) -> EngineHealth:
    """Expansion engine: credits, seats, automations, premium modules, enterprise asks."""
    signals: list[dict] = []
    bottlenecks: list[str] = []
    actions: list[dict] = []

    expansion_revenue_pct = m.get("expansion_revenue_pct", 0.0)
    credit_purchase_rate = m.get("credit_purchase_rate", 0.0)
    seat_expansion_rate = m.get("seat_expansion_rate", 0.0)
    addon_attach_rate = m.get("addon_attach_rate", 0.0)
    upgrade_rate = m.get("plan_upgrade_rate", 0.0)
    arpu_growth_monthly = m.get("arpu_growth_rate_monthly", 0.0)

    exp_rev_score = min(25, expansion_revenue_pct * 100)
    signals.append(
        {"metric": "expansion_revenue_pct", "value": round(expansion_revenue_pct, 4), "score": round(exp_rev_score, 1)}
    )
    if expansion_revenue_pct < 0.10:
        bottlenecks.append(f"Expansion revenue is only {expansion_revenue_pct:.0%} of total — needs to be 20%+")
        actions.append(
            {
                "action": "drive_expansion_revenue",
                "description": "Deploy credit pack nudges at usage peaks, add premium module offers, enable seat-based scaling.",
                "priority": "critical",
                "expected_impact_pct": 22,
            }
        )

    credit_score = min(20, credit_purchase_rate * 100 * 2)
    signals.append(
        {"metric": "credit_purchase_rate", "value": round(credit_purchase_rate, 4), "score": round(credit_score, 1)}
    )
    if credit_purchase_rate < 0.05:
        bottlenecks.append("Credit purchase rate is low — users may not understand the credit value")
        actions.append(
            {
                "action": "promote_credit_packs",
                "description": "Show credits-remaining warnings, offer bonus credits on bulk purchase, tie credits to visible outcomes.",
                "priority": "high",
                "expected_impact_pct": 14,
            }
        )

    seat_score = min(20, seat_expansion_rate * 100 * 2)
    signals.append(
        {"metric": "seat_expansion_rate", "value": round(seat_expansion_rate, 4), "score": round(seat_score, 1)}
    )
    if seat_expansion_rate < 0.03:
        actions.append(
            {
                "action": "encourage_team_expansion",
                "description": "Show collaboration features, add 'invite team' prompts, offer team trial periods.",
                "priority": "medium",
                "expected_impact_pct": 10,
            }
        )

    addon_score = min(20, addon_attach_rate * 100 * 2)
    signals.append(
        {"metric": "addon_attach_rate", "value": round(addon_attach_rate, 4), "score": round(addon_score, 1)}
    )

    upgrade_score = min(15, upgrade_rate * 100 * 1.5)
    signals.append({"metric": "plan_upgrade_rate", "value": round(upgrade_rate, 4), "score": round(upgrade_score, 1)})

    arpu_growth_bonus = min(5, max(0, arpu_growth_monthly * 100))
    total = _clamp(exp_rev_score + credit_score + seat_score + addon_score + upgrade_score + arpu_growth_bonus)

    return EngineHealth(
        engine_name="expansion",
        health_score=round(total, 1),
        grade=_grade_engine(total),
        signals=signals,
        bottlenecks=bottlenecks,
        recommended_actions=sorted(actions, key=lambda a: a.get("expected_impact_pct", 0), reverse=True),
    )


def _score_retention(m: dict) -> EngineHealth:
    """Retention engine: saved workflows, stored assets, recurring output dependence, compounding setup."""
    signals: list[dict] = []
    bottlenecks: list[str] = []
    actions: list[dict] = []

    monthly_retention = m.get("monthly_retention_rate", 0.0)
    net_revenue_retention = m.get("net_revenue_retention", 0.0)
    saved_workflows_per_user = m.get("avg_saved_workflows_per_user", 0.0)
    stored_assets_per_user = m.get("avg_stored_assets_per_user", 0.0)
    recurring_usage_rate = m.get("recurring_weekly_usage_rate", 0.0)
    setup_investment_hours = m.get("avg_setup_investment_hours", 0.0)
    m.get("churn_rate_30d", 0.0)

    retention_score = min(30, monthly_retention * 30)
    signals.append(
        {"metric": "monthly_retention_rate", "value": round(monthly_retention, 4), "score": round(retention_score, 1)}
    )
    if monthly_retention < 0.85:
        bottlenecks.append(f"Monthly retention at {monthly_retention:.0%} — must exceed 85%")
        actions.append(
            {
                "action": "improve_retention",
                "description": "Implement win-back campaigns, add usage nudges for dormant users, build switching cost through saved data.",
                "priority": "critical",
                "expected_impact_pct": 25,
            }
        )

    nrr_score = 0.0
    if net_revenue_retention > 0:
        nrr_score = min(20, max(0, (net_revenue_retention - 0.8) * 100))
    signals.append(
        {"metric": "net_revenue_retention", "value": round(net_revenue_retention, 4), "score": round(nrr_score, 1)}
    )
    if net_revenue_retention < 1.0:
        bottlenecks.append(f"NRR is {net_revenue_retention:.0%} — below 100% means contraction")
        actions.append(
            {
                "action": "improve_nrr",
                "description": "Drive expansion within retained accounts — upsell credits, seats, and premium features.",
                "priority": "high",
                "expected_impact_pct": 18,
            }
        )

    stickiness_raw = (
        min(10, saved_workflows_per_user * 2)
        + min(10, stored_assets_per_user * 0.5)
        + min(10, setup_investment_hours * 1.5)
    )
    stickiness_score = _clamp(stickiness_raw, 0, 25)
    signals.append(
        {"metric": "stickiness_composite", "value": round(stickiness_raw, 2), "score": round(stickiness_score, 1)}
    )
    if saved_workflows_per_user < 2:
        bottlenecks.append("Low saved workflows — users aren't building switching costs")
        actions.append(
            {
                "action": "increase_saved_workflows",
                "description": "Prompt users to save workflows after successful runs, auto-save templates, show 'your library' dashboard.",
                "priority": "high",
                "expected_impact_pct": 12,
            }
        )

    recurring_score = min(25, recurring_usage_rate * 100 * 0.5)
    signals.append(
        {
            "metric": "recurring_weekly_usage_rate",
            "value": round(recurring_usage_rate, 4),
            "score": round(recurring_score, 1),
        }
    )
    if recurring_usage_rate < 0.4:
        bottlenecks.append(f"Only {recurring_usage_rate:.0%} of users return weekly — habitual use is low")
        actions.append(
            {
                "action": "build_usage_habits",
                "description": "Add scheduled automations, weekly digest emails, and streak rewards to build recurring behavior.",
                "priority": "high",
                "expected_impact_pct": 15,
            }
        )

    total = _clamp(retention_score + nrr_score + stickiness_score + recurring_score)

    return EngineHealth(
        engine_name="retention",
        health_score=round(total, 1),
        grade=_grade_engine(total),
        signals=signals,
        bottlenecks=bottlenecks,
        recommended_actions=sorted(actions, key=lambda a: a.get("expected_impact_pct", 0), reverse=True),
    )


def _score_monetization(m: dict) -> EngineHealth:
    """Monetization engine: multiple spend points, pricing tied to value delivered."""
    signals: list[dict] = []
    bottlenecks: list[str] = []
    actions: list[dict] = []

    revenue_streams_active = m.get("active_revenue_stream_count", 1)
    arpu = m.get("arpu", 0.0)
    arppu = m.get("arppu", 0.0)
    ltv = m.get("ltv", 0.0)
    pricing_satisfaction = m.get("pricing_satisfaction_score", 0.0)
    revenue_per_action = m.get("avg_revenue_per_value_action", 0.0)
    transaction_fee_revenue_pct = m.get("transaction_fee_revenue_pct", 0.0)
    premium_output_revenue_pct = m.get("premium_output_revenue_pct", 0.0)

    diversification_score = min(25, revenue_streams_active * 5)
    signals.append(
        {"metric": "active_revenue_streams", "value": revenue_streams_active, "score": round(diversification_score, 1)}
    )
    if revenue_streams_active < 3:
        bottlenecks.append(f"Only {revenue_streams_active} revenue stream(s) — need 3+ for resilience")
        actions.append(
            {
                "action": "diversify_revenue",
                "description": "Add transaction fees, premium outputs, and credit packs alongside subscriptions.",
                "priority": "critical",
                "expected_impact_pct": 20,
            }
        )

    arpu_score = min(20, arpu * 0.2)
    arppu_bonus = min(5, _safe_div(arppu, max(arpu, 1)) * 2)
    arpu_score = _clamp(arpu_score + arppu_bonus, 0, 25)
    signals.append({"metric": "arpu", "value": round(arpu, 2), "score": round(arpu_score, 1)})

    value_alignment = min(20, revenue_per_action * 20) if revenue_per_action > 0 else min(20, pricing_satisfaction * 20)
    signals.append(
        {
            "metric": "value_alignment",
            "value": round(revenue_per_action or pricing_satisfaction, 4),
            "score": round(value_alignment, 1),
        }
    )
    if pricing_satisfaction > 0 and pricing_satisfaction < 0.6:
        bottlenecks.append(f"Pricing satisfaction is {pricing_satisfaction:.0%} — users feel price ≠ value")
        actions.append(
            {
                "action": "align_pricing_to_value",
                "description": "Shift pricing anchors to outcomes delivered (ROI shown at upgrade moment), add usage-based components.",
                "priority": "high",
                "expected_impact_pct": 15,
            }
        )

    ltv_score = min(15, ltv * 0.01)
    signals.append({"metric": "ltv", "value": round(ltv, 2), "score": round(ltv_score, 1)})

    layered_rev = min(15, (transaction_fee_revenue_pct + premium_output_revenue_pct) * 100)
    signals.append(
        {
            "metric": "layered_revenue_pct",
            "value": round(transaction_fee_revenue_pct + premium_output_revenue_pct, 4),
            "score": round(layered_rev, 1),
        }
    )
    if transaction_fee_revenue_pct + premium_output_revenue_pct < 0.1:
        bottlenecks.append("Transaction fees + premium outputs are under 10% of revenue — untapped layers")
        actions.append(
            {
                "action": "activate_layered_revenue",
                "description": "Enable transaction fees on platform-generated revenue, promote premium output catalog.",
                "priority": "high",
                "expected_impact_pct": 18,
            }
        )

    total = _clamp(diversification_score + arpu_score + value_alignment + ltv_score + layered_rev)

    return EngineHealth(
        engine_name="monetization",
        health_score=round(total, 1),
        grade=_grade_engine(total),
        signals=signals,
        bottlenecks=bottlenecks,
        recommended_actions=sorted(actions, key=lambda a: a.get("expected_impact_pct", 0), reverse=True),
    )


def compute_operating_model(metrics: dict) -> dict:
    """Score all 5 operating engines and return a unified operating model report."""
    engines = [
        _score_acquisition(metrics),
        _score_conversion(metrics),
        _score_expansion(metrics),
        _score_retention(metrics),
        _score_monetization(metrics),
    ]

    scores = [e.health_score for e in engines]
    composite = _mean(scores)
    weakest = min(engines, key=lambda e: e.health_score)
    strongest = max(engines, key=lambda e: e.health_score)

    all_bottlenecks = []
    all_actions = []
    for e in engines:
        for b in e.bottlenecks:
            all_bottlenecks.append({"engine": e.engine_name, "bottleneck": b})
        for a in e.recommended_actions:
            all_actions.append({**a, "engine": e.engine_name})

    all_actions.sort(key=lambda a: a.get("expected_impact_pct", 0), reverse=True)

    return {
        "composite_score": round(composite, 1),
        "composite_grade": _score_to_grade(composite),
        "engines": {
            e.engine_name: {
                "health_score": e.health_score,
                "grade": e.grade,
                "signals": e.signals,
                "bottlenecks": e.bottlenecks,
                "recommended_actions": e.recommended_actions,
            }
            for e in engines
        },
        "weakest_engine": weakest.engine_name,
        "strongest_engine": strongest.engine_name,
        "score_spread": round(strongest.health_score - weakest.health_score, 1),
        "all_bottlenecks": all_bottlenecks,
        "top_actions": all_actions[:10],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: ELITE READINESS SCORECARD (7-QUESTION DIAGNOSTIC)
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ReadinessQuestion:
    question_id: str
    question: str
    metric_key: str
    threshold: Any
    comparator: str  # "lt", "gt", "gte", "lte", "eq", "bool_and"
    weight: float = 1.0


_ELITE_QUESTIONS: list[ReadinessQuestion] = [
    ReadinessQuestion(
        question_id="q1_fast_value",
        question="Can a free user reach value fast?",
        metric_key="median_time_to_first_value_seconds",
        threshold=300,
        comparator="lte",
        weight=1.5,
    ),
    ReadinessQuestion(
        question_id="q2_first_paid_action",
        question="Is there a clear first paid action?",
        metric_key="free_to_first_spend_rate",
        threshold=0.15,
        comparator="gte",
        weight=1.5,
    ),
    ReadinessQuestion(
        question_id="q3_reason_to_keep_paying",
        question="Is there a reason to keep paying monthly?",
        metric_key="monthly_retention_rate",
        threshold=0.85,
        comparator="gte",
        weight=1.5,
    ),
    ReadinessQuestion(
        question_id="q4_spend_beyond_monthly",
        question="Is there a reason to spend beyond monthly?",
        metric_key="expansion_revenue_pct",
        threshold=0.20,
        comparator="gte",
        weight=1.0,
    ),
    ReadinessQuestion(
        question_id="q5_account_expansion_path",
        question="Is there a path to 5x-20x account expansion?",
        metric_key="_arpu_expansion_ratio",
        threshold=5.0,
        comparator="gte",
        weight=1.0,
    ),
    ReadinessQuestion(
        question_id="q6_usage_margin",
        question="Does higher usage increase margin?",
        metric_key="_usage_margin_correlation",
        threshold=0.3,
        comparator="gte",
        weight=1.0,
    ),
    ReadinessQuestion(
        question_id="q7_self_serve_and_enterprise",
        question="Can the same product support self-serve and high-ticket?",
        metric_key="_has_dual_motion",
        threshold=True,
        comparator="eq",
        weight=1.0,
    ),
]

_QUESTION_REMEDIES: dict[str, dict] = {
    "q1_fast_value": {
        "action": "accelerate_time_to_value",
        "description": "Implement template gallery, pre-populated workspace, or guided wizard so first value arrives in under 5 minutes.",
        "priority": "critical",
        "expected_impact_pct": 20,
    },
    "q2_first_paid_action": {
        "action": "define_first_paid_action",
        "description": "Create one irresistible paid moment (credit pack, premium export, or single-feature unlock) that appears naturally during onboarding.",
        "priority": "critical",
        "expected_impact_pct": 22,
    },
    "q3_reason_to_keep_paying": {
        "action": "strengthen_recurring_value",
        "description": "Build switching costs: saved workflows, stored data, scheduled automations, and recurring outputs that depend on active subscription.",
        "priority": "critical",
        "expected_impact_pct": 25,
    },
    "q4_spend_beyond_monthly": {
        "action": "create_expansion_hooks",
        "description": "Add credit packs, premium outputs, seat-based pricing, and usage-based overages to create spend beyond the base plan.",
        "priority": "high",
        "expected_impact_pct": 18,
    },
    "q5_account_expansion_path": {
        "action": "build_expansion_ladder",
        "description": "Design clear path from starter ($X/mo) to enterprise ($20X+/mo): seats, automations, API access, SLA, dedicated support.",
        "priority": "high",
        "expected_impact_pct": 15,
    },
    "q6_usage_margin": {
        "action": "align_cost_to_usage",
        "description": "Negotiate volume-based AI/API costs, implement caching, batch operations, and ensure heavy users contribute proportional margin.",
        "priority": "medium",
        "expected_impact_pct": 12,
    },
    "q7_self_serve_and_enterprise": {
        "action": "enable_dual_motion",
        "description": "Add enterprise tier with SSO, SLA, audit logs, and custom onboarding alongside self-serve. Share core product, differentiate wrapper.",
        "priority": "high",
        "expected_impact_pct": 16,
    },
}


def compute_elite_readiness(metrics: dict) -> dict:
    """Run the 7-question Elite Readiness Scorecard.

    Returns per-question pass/fail, composite score (0-100), grade, and gap analysis.
    """
    top_decile_arpu = metrics.get("top_decile_arpu", 0.0)
    bottom_decile_arpu = metrics.get("bottom_decile_arpu", 1.0)
    arpu_expansion_ratio = _safe_div(top_decile_arpu, bottom_decile_arpu, 0.0)

    usage_values = metrics.get("usage_volume_series", [])
    margin_values = metrics.get("margin_per_user_series", [])
    usage_margin_corr = (
        _correlation(usage_values, margin_values)
        if usage_values and margin_values
        else metrics.get("usage_margin_correlation", 0.0)
    )

    has_enterprise = metrics.get("has_enterprise_tier", False)
    has_self_serve = metrics.get("has_self_serve", False)
    has_dual_motion = has_enterprise and has_self_serve

    derived: dict[str, Any] = {
        "_arpu_expansion_ratio": arpu_expansion_ratio,
        "_usage_margin_correlation": usage_margin_corr,
        "_has_dual_motion": has_dual_motion,
    }
    combined = {**metrics, **derived}

    results: list[dict] = []
    total_weight = 0.0
    passed_weight = 0.0

    for q in _ELITE_QUESTIONS:
        actual = combined.get(q.metric_key)
        if actual is None:
            results.append(
                {
                    "question_id": q.question_id,
                    "question": q.question,
                    "passed": False,
                    "actual_value": None,
                    "threshold": q.threshold,
                    "comparator": q.comparator,
                    "data_missing": True,
                    "remedy": _QUESTION_REMEDIES.get(q.question_id, {}),
                }
            )
            total_weight += q.weight
            continue

        if q.comparator == "lte":
            passed = actual <= q.threshold
        elif q.comparator == "gte":
            passed = actual >= q.threshold
        elif q.comparator == "lt":
            passed = actual < q.threshold
        elif q.comparator == "gt":
            passed = actual > q.threshold
        elif q.comparator == "eq":
            passed = actual == q.threshold
        else:
            passed = False

        total_weight += q.weight
        if passed:
            passed_weight += q.weight

        entry: dict[str, Any] = {
            "question_id": q.question_id,
            "question": q.question,
            "passed": passed,
            "actual_value": actual if not isinstance(actual, bool) else actual,
            "threshold": q.threshold,
            "comparator": q.comparator,
            "data_missing": False,
        }
        if not passed:
            entry["remedy"] = _QUESTION_REMEDIES.get(q.question_id, {})
            if (
                q.comparator in ("gte", "gt")
                and isinstance(actual, (int, float))
                and isinstance(q.threshold, (int, float))
            ):
                gap_pct = _safe_div(q.threshold - actual, q.threshold) * 100
                entry["gap_pct"] = round(gap_pct, 1)
            elif (
                q.comparator in ("lte", "lt")
                and isinstance(actual, (int, float))
                and isinstance(q.threshold, (int, float))
            ):
                overshoot_pct = _safe_div(actual - q.threshold, q.threshold) * 100
                entry["overshoot_pct"] = round(overshoot_pct, 1)
        results.append(entry)

    elite_score = _safe_div(passed_weight, total_weight) * 100 if total_weight > 0 else 0.0
    elite_score = round(_clamp(elite_score), 1)

    passed_count = sum(1 for r in results if r["passed"])
    failed_count = sum(1 for r in results if not r["passed"])

    failing_remedies = [r["remedy"] for r in results if not r["passed"] and r.get("remedy")]
    failing_remedies.sort(key=lambda a: a.get("expected_impact_pct", 0), reverse=True)

    if passed_count == 7:
        readiness_status = "ELITE — all 7 questions pass. Machine is operational."
    elif passed_count >= 5:
        readiness_status = f"STRONG — {passed_count}/7 passing. Close gaps to reach elite status."
    elif passed_count >= 3:
        readiness_status = f"DEVELOPING — {passed_count}/7 passing. Foundational gaps remain."
    else:
        readiness_status = f"EARLY STAGE — {passed_count}/7 passing. Core architecture needs work."

    return {
        "elite_score": elite_score,
        "grade": _score_to_grade(elite_score),
        "readiness_status": readiness_status,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "questions": results,
        "gap_analysis": failing_remedies,
        "top_priority_fix": failing_remedies[0] if failing_remedies else None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: CONTEXTUAL SPEND TRIGGERS
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class SpendTrigger:
    trigger_id: str
    display_name: str
    condition_fn: str  # key for the evaluator
    priority: int
    nudge_message: str
    cta_text: str
    cta_action: str
    estimated_revenue_impact: float
    category: str


_TRIGGER_DEFINITIONS: list[SpendTrigger] = [
    SpendTrigger(
        trigger_id="credit_exhaustion_imminent",
        display_name="Credits Running Low",
        condition_fn="credit_exhaustion_imminent",
        priority=9,
        nudge_message="You have less than 10% of your credits remaining. Top up now to keep creating without interruption.",
        cta_text="Buy Credit Pack",
        cta_action="buy_credits",
        estimated_revenue_impact=29.99,
        category="credits",
    ),
    SpendTrigger(
        trigger_id="generation_limit_approaching",
        display_name="Generation Limit Near",
        condition_fn="generation_limit_approaching",
        priority=9,
        nudge_message="You've used {usage_pct}% of your monthly generations. Upgrade for unlimited access.",
        cta_text="Upgrade Plan",
        cta_action="upgrade",
        estimated_revenue_impact=49.00,
        category="limits",
    ),
    SpendTrigger(
        trigger_id="team_invite_blocked",
        display_name="Seat Limit Reached",
        condition_fn="team_invite_blocked",
        priority=8,
        nudge_message="You've hit your seat limit. Add more seats to bring your team onboard.",
        cta_text="Add Seats",
        cta_action="add_seats",
        estimated_revenue_impact=39.00,
        category="seats",
    ),
    SpendTrigger(
        trigger_id="premium_output_attempted",
        display_name="Premium Feature Attempted",
        condition_fn="premium_output_attempted",
        priority=8,
        nudge_message="You just tried to use {feature_name} — unlock it with a plan upgrade or credits.",
        cta_text="Unlock Now",
        cta_action="upgrade",
        estimated_revenue_impact=24.99,
        category="features",
    ),
    SpendTrigger(
        trigger_id="high_usage_streak",
        display_name="Power User Streak",
        condition_fn="high_usage_streak",
        priority=7,
        nudge_message="You've been a power user for {streak_days} days straight! Upgrade to lock in priority processing and extra credits.",
        cta_text="Go Pro",
        cta_action="upgrade",
        estimated_revenue_impact=49.00,
        category="engagement",
    ),
    SpendTrigger(
        trigger_id="milestone_hit",
        display_name="Milestone Achieved",
        condition_fn="milestone_hit",
        priority=6,
        nudge_message="Congratulations on reaching {milestone}! Celebrate by upgrading and unlocking the next level.",
        cta_text="Level Up",
        cta_action="upgrade",
        estimated_revenue_impact=49.00,
        category="engagement",
    ),
    SpendTrigger(
        trigger_id="competitor_feature_gap",
        display_name="Feature Gap Detected",
        condition_fn="competitor_feature_gap",
        priority=5,
        nudge_message="Users on {higher_tier} get {feature_name} — an essential tool your competitors are already using.",
        cta_text="Bridge the Gap",
        cta_action="upgrade",
        estimated_revenue_impact=49.00,
        category="competitive",
    ),
    SpendTrigger(
        trigger_id="export_blocked",
        display_name="Export Blocked",
        condition_fn="export_blocked",
        priority=8,
        nudge_message="Your plan doesn't include this export format. Upgrade to download your content.",
        cta_text="Unlock Exports",
        cta_action="upgrade",
        estimated_revenue_impact=24.99,
        category="features",
    ),
    SpendTrigger(
        trigger_id="automation_limit_hit",
        display_name="Automation Limit Reached",
        condition_fn="automation_limit_hit",
        priority=8,
        nudge_message="You've maxed out your active automations. Upgrade for more slots and advanced triggers.",
        cta_text="Expand Automations",
        cta_action="upgrade",
        estimated_revenue_impact=49.00,
        category="limits",
    ),
    SpendTrigger(
        trigger_id="storage_approaching_cap",
        display_name="Storage Nearly Full",
        condition_fn="storage_approaching_cap",
        priority=7,
        nudge_message="You're using {storage_pct}% of your storage. Upgrade for more space or purchase additional storage.",
        cta_text="Get More Storage",
        cta_action="upgrade",
        estimated_revenue_impact=19.99,
        category="limits",
    ),
    SpendTrigger(
        trigger_id="api_rate_limited",
        display_name="API Rate Limited",
        condition_fn="api_rate_limited",
        priority=7,
        nudge_message="Your API requests are being throttled. Upgrade for higher rate limits and priority access.",
        cta_text="Increase Limits",
        cta_action="upgrade",
        estimated_revenue_impact=99.00,
        category="limits",
    ),
    SpendTrigger(
        trigger_id="priority_queue_available",
        display_name="Priority Processing Available",
        condition_fn="priority_queue_available",
        priority=5,
        nudge_message="Skip the queue — get results in seconds with Priority Processing.",
        cta_text="Go Priority",
        cta_action="buy_credits",
        estimated_revenue_impact=9.99,
        category="speed",
    ),
    SpendTrigger(
        trigger_id="annual_billing_discount",
        display_name="Annual Billing Savings",
        condition_fn="annual_billing_discount",
        priority=4,
        nudge_message="Switch to annual billing and save {savings_pct}% — that's ${annual_savings:.0f}/year back in your pocket.",
        cta_text="Save with Annual",
        cta_action="switch_annual",
        estimated_revenue_impact=0.0,
        category="billing",
    ),
    SpendTrigger(
        trigger_id="new_feature_gated",
        display_name="New Feature Available",
        condition_fn="new_feature_gated",
        priority=6,
        nudge_message="We just launched {feature_name} — available on {required_tier} and above.",
        cta_text="Try It Now",
        cta_action="upgrade",
        estimated_revenue_impact=49.00,
        category="features",
    ),
    SpendTrigger(
        trigger_id="success_moment",
        display_name="Success Moment",
        condition_fn="success_moment",
        priority=7,
        nudge_message="You just {achievement}! Imagine what you could do with full access. Upgrade now.",
        cta_text="Unlock Full Power",
        cta_action="upgrade",
        estimated_revenue_impact=49.00,
        category="engagement",
    ),
]


def _check_credit_exhaustion(ctx: dict) -> dict | None:
    remaining_pct = _safe_div(ctx.get("credits_remaining", 100), ctx.get("credits_total", 100)) * 100
    if remaining_pct < 10:
        return {"credits_remaining_pct": round(remaining_pct, 1)}
    return None


def _check_generation_limit(ctx: dict) -> dict | None:
    used = ctx.get("generations_used", 0)
    limit = ctx.get("generations_limit", 0)
    if limit <= 0:
        return None
    usage_pct = (used / limit) * 100
    if usage_pct > 80:
        return {"usage_pct": round(usage_pct, 1)}
    return None


def _check_team_invite_blocked(ctx: dict) -> dict | None:
    seats_used = ctx.get("seats_used", 0)
    seats_limit = ctx.get("seats_limit", 0)
    if seats_limit > 0 and seats_used >= seats_limit and ctx.get("pending_invite", False):
        return {"seats_used": seats_used, "seats_limit": seats_limit}
    return None


def _check_premium_output_attempted(ctx: dict) -> dict | None:
    attempted = ctx.get("premium_output_attempted")
    if attempted:
        return {"feature_name": attempted}
    return None


def _check_high_usage_streak(ctx: dict) -> dict | None:
    streak = ctx.get("consecutive_heavy_use_days", 0)
    if streak >= 5:
        return {"streak_days": streak}
    return None


def _check_milestone_hit(ctx: dict) -> dict | None:
    milestone = ctx.get("milestone_reached")
    if milestone:
        return {"milestone": milestone}
    return None


def _check_competitor_feature_gap(ctx: dict) -> dict | None:
    gap = ctx.get("competitor_feature_gap")
    if gap:
        return {"feature_name": gap.get("feature"), "higher_tier": gap.get("available_on", "professional")}
    return None


def _check_export_blocked(ctx: dict) -> dict | None:
    if ctx.get("export_blocked", False):
        return {"blocked_format": ctx.get("blocked_export_format", "unknown")}
    return None


def _check_automation_limit(ctx: dict) -> dict | None:
    active = ctx.get("active_automations", 0)
    limit = ctx.get("automation_limit", 0)
    if limit > 0 and active >= limit:
        return {"active": active, "limit": limit}
    return None


def _check_storage_cap(ctx: dict) -> dict | None:
    used = ctx.get("storage_used_gb", 0)
    cap = ctx.get("storage_cap_gb", 0)
    if cap > 0:
        pct = (used / cap) * 100
        if pct > 85:
            return {"storage_pct": round(pct, 1)}
    return None


def _check_api_rate_limited(ctx: dict) -> dict | None:
    if ctx.get("api_rate_limited", False):
        return {"current_tier_limit": ctx.get("api_rate_limit", 0)}
    return None


def _check_priority_queue(ctx: dict) -> dict | None:
    if ctx.get("queue_wait_seconds", 0) > 30 and not ctx.get("has_priority_processing", False):
        return {"queue_wait": ctx.get("queue_wait_seconds", 0)}
    return None


def _check_annual_billing(ctx: dict) -> dict | None:
    if ctx.get("billing_cycle") == "monthly" and ctx.get("months_subscribed", 0) >= 3:
        monthly_price = ctx.get("current_monthly_price", 0)
        annual_monthly_price = monthly_price * 0.8
        annual_savings = (monthly_price - annual_monthly_price) * 12
        return {"savings_pct": 20, "annual_savings": annual_savings}
    return None


def _check_new_feature_gated(ctx: dict) -> dict | None:
    gated = ctx.get("new_gated_feature")
    if gated:
        return {"feature_name": gated.get("name", ""), "required_tier": gated.get("required_tier", "professional")}
    return None


def _check_success_moment(ctx: dict) -> dict | None:
    achievement = ctx.get("recent_achievement")
    if achievement:
        return {"achievement": achievement}
    return None


_CONDITION_EVALUATORS: dict[str, Any] = {
    "credit_exhaustion_imminent": _check_credit_exhaustion,
    "generation_limit_approaching": _check_generation_limit,
    "team_invite_blocked": _check_team_invite_blocked,
    "premium_output_attempted": _check_premium_output_attempted,
    "high_usage_streak": _check_high_usage_streak,
    "milestone_hit": _check_milestone_hit,
    "competitor_feature_gap": _check_competitor_feature_gap,
    "export_blocked": _check_export_blocked,
    "automation_limit_hit": _check_automation_limit,
    "storage_approaching_cap": _check_storage_cap,
    "api_rate_limited": _check_api_rate_limited,
    "priority_queue_available": _check_priority_queue,
    "annual_billing_discount": _check_annual_billing,
    "new_feature_gated": _check_new_feature_gated,
    "success_moment": _check_success_moment,
}


def evaluate_spend_triggers(user_context: dict) -> list[dict]:
    """Evaluate all contextual spend triggers and return a prioritized list of active nudges."""
    active_triggers: list[dict] = []

    for trigger in _TRIGGER_DEFINITIONS:
        evaluator = _CONDITION_EVALUATORS.get(trigger.condition_fn)
        if evaluator is None:
            continue

        result = evaluator(user_context)
        if result is None:
            continue

        message = trigger.nudge_message
        for key, val in result.items():
            placeholder = "{" + key + "}"
            if placeholder in message:
                message = message.replace(placeholder, str(val))

        active_triggers.append(
            {
                "trigger_id": trigger.trigger_id,
                "display_name": trigger.display_name,
                "priority": trigger.priority,
                "nudge_message": message,
                "cta_text": trigger.cta_text,
                "cta_action": trigger.cta_action,
                "estimated_revenue_impact": trigger.estimated_revenue_impact,
                "category": trigger.category,
                "context_data": result,
            }
        )

    active_triggers.sort(key=lambda t: t["priority"], reverse=True)
    return active_triggers


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: FULL REVENUE MACHINE REPORT
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class RevenueMachineReport:
    composite_score: float
    composite_grade: str
    operating_model: dict
    elite_readiness: dict
    active_triggers: list[dict]
    transaction_fee_projection: dict
    premium_output_summary: dict
    top_recommended_actions: list[dict]
    revenue_summary: dict
    generated_at: str


def generate_revenue_machine_report(
    metrics: dict,
    user_context: dict | None = None,
    transactions: list[dict] | None = None,
    plan_tier: str = "starter",
) -> dict:
    """Generate the comprehensive Revenue Machine report combining all subsystems."""

    operating_model = compute_operating_model(metrics)

    elite_readiness = compute_elite_readiness(metrics)

    active_triggers = evaluate_spend_triggers(user_context or {})

    fee_projection = project_transaction_fee_revenue(transactions or [], plan_tier)

    catalog = get_premium_output_catalog()
    accessible_count = 0
    total_catalog_value = 0.0
    user_access = _PLAN_TO_ACCESS.get(plan_tier, OutputAccessLevel.FREE)
    user_level = _ACCESS_LEVEL_ORDER[user_access]
    for item in catalog:
        required = _ACCESS_LEVEL_ORDER.get(
            OutputAccessLevel(item["plan_access_level"]),
            0,
        )
        total_catalog_value += item["base_price"]
        if user_level >= required:
            accessible_count += 1

    premium_output_summary = {
        "total_outputs_available": len(catalog),
        "accessible_on_current_plan": accessible_count,
        "locked_outputs": len(catalog) - accessible_count,
        "total_catalog_value_per_unit": round(total_catalog_value, 2),
        "plan_tier": plan_tier,
    }

    all_actions: list[dict] = []
    for a in operating_model.get("top_actions", []):
        all_actions.append({**a, "source": "operating_model"})
    for a in elite_readiness.get("gap_analysis", []):
        all_actions.append({**a, "source": "elite_readiness"})
    for t in active_triggers[:5]:
        all_actions.append(
            {
                "action": t["cta_action"],
                "description": t["nudge_message"],
                "priority": "high" if t["priority"] >= 7 else "medium",
                "expected_impact_pct": round(t["estimated_revenue_impact"] / max(metrics.get("mrr", 100), 1) * 100, 1),
                "source": "spend_trigger",
                "trigger_id": t["trigger_id"],
            }
        )

    all_actions.sort(key=lambda a: a.get("expected_impact_pct", 0), reverse=True)
    top_actions = all_actions[:15]

    om_score = operating_model.get("composite_score", 0)
    er_score = elite_readiness.get("elite_score", 0)
    trigger_density = min(10, len(active_triggers) * 2)
    fee_health = min(10, fee_projection.get("blended_effective_rate_pct", 0) * 2)

    composite_score = _clamp(om_score * 0.40 + er_score * 0.35 + trigger_density + fee_health)

    mrr = metrics.get("mrr", 0)
    arr = mrr * 12
    fee_annual = fee_projection.get("annual_projected_fee_revenue", 0)
    premium_monthly_est = metrics.get("premium_output_revenue_monthly", 0)

    revenue_summary = {
        "subscription_mrr": round(mrr, 2),
        "subscription_arr": round(arr, 2),
        "transaction_fee_arr_projected": round(fee_annual, 2),
        "premium_output_monthly_est": round(premium_monthly_est, 2),
        "premium_output_arr_est": round(premium_monthly_est * 12, 2),
        "total_blended_arr_est": round(arr + fee_annual + premium_monthly_est * 12, 2),
        "revenue_mix": {
            "subscription_pct": round(_safe_div(arr, arr + fee_annual + premium_monthly_est * 12) * 100, 1),
            "transaction_fees_pct": round(_safe_div(fee_annual, arr + fee_annual + premium_monthly_est * 12) * 100, 1),
            "premium_outputs_pct": round(
                _safe_div(premium_monthly_est * 12, arr + fee_annual + premium_monthly_est * 12) * 100, 1
            ),
        },
    }

    now = datetime.utcnow().isoformat() + "Z"

    report = RevenueMachineReport(
        composite_score=round(composite_score, 1),
        composite_grade=_score_to_grade(composite_score),
        operating_model=operating_model,
        elite_readiness=elite_readiness,
        active_triggers=active_triggers,
        transaction_fee_projection=fee_projection,
        premium_output_summary=premium_output_summary,
        top_recommended_actions=top_actions,
        revenue_summary=revenue_summary,
        generated_at=now,
    )

    return {
        "composite_score": report.composite_score,
        "composite_grade": report.composite_grade,
        "operating_model": report.operating_model,
        "elite_readiness": report.elite_readiness,
        "active_triggers": report.active_triggers,
        "transaction_fee_projection": report.transaction_fee_projection,
        "premium_output_summary": report.premium_output_summary,
        "top_recommended_actions": report.top_recommended_actions,
        "revenue_summary": report.revenue_summary,
        "generated_at": report.generated_at,
    }
