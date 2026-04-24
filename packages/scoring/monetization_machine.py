"""Monetization Machine Engine — The revenue architecture brain.

This is not a feature engine. This is the economic engine that turns
product usage into multi-layered revenue. It implements:
- Metered economics (every costly action tracked and billable)
- Hybrid monetization (subscription + credits + packs + enterprise + transaction fees)
- Ascension path (free → starter → power → business → enterprise)
- Revenue multiplication events (premium moments that create spend beyond base plan)
- Monetization telemetry (track everything that predicts revenue behavior)
- Job-to-be-done packaging (sell outcomes, not features)
- Revenue segmentation (different users spend differently)
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: METERED ECONOMICS
# ═══════════════════════════════════════════════════════════════════════════════


class MeterType(str, Enum):
    AI_GENERATION = "ai_generation"
    AI_ANALYSIS = "ai_analysis"
    EXPORT = "export"
    AUTOMATION_RUN = "automation_run"
    PUBLISH = "publish"
    STORAGE_GB = "storage_gb"
    SEAT = "seat"
    API_CALL = "api_call"
    PREMIUM_OUTPUT = "premium_output"
    CONCIERGE_ACTION = "concierge_action"


@dataclass
class UsageMeter:
    meter_type: MeterType
    used: int
    limit: int  # -1 = unlimited
    overage_rate: float
    reset_period: str  # "monthly", "never"
    cost_per_unit: float
    value_per_unit: float
    margin_per_unit: float = 0.0

    def __post_init__(self) -> None:
        self.margin_per_unit = self.value_per_unit - self.cost_per_unit

    @property
    def utilization_pct(self) -> float:
        if self.limit <= 0:
            return 0.0
        return min(self.used / self.limit, 1.0) * 100.0

    @property
    def overage_units(self) -> int:
        if self.limit < 0:
            return 0
        return max(0, self.used - self.limit)


@dataclass
class CreditBalance:
    total_credits: int
    used_credits: int
    remaining_credits: int
    expiry_date: str | None
    replenishment_rate: int
    overage_enabled: bool
    overage_rate: float

    def __post_init__(self) -> None:
        self.remaining_credits = self.total_credits - self.used_credits


METER_COST_TABLE: dict[str, float] = {
    MeterType.AI_GENERATION: 0.035,
    MeterType.AI_ANALYSIS: 0.012,
    MeterType.EXPORT: 0.001,
    MeterType.AUTOMATION_RUN: 0.008,
    MeterType.PUBLISH: 0.015,
    MeterType.STORAGE_GB: 0.023,
    MeterType.SEAT: 0.00,
    MeterType.API_CALL: 0.002,
    MeterType.PREMIUM_OUTPUT: 0.45,
    MeterType.CONCIERGE_ACTION: 2.50,
}


def compute_usage_economics(
    meters: list[UsageMeter],
    plan_price: float,
) -> dict:
    """Compute the unit economics of current usage."""
    total_cogs = 0.0
    total_usage_units = 0
    most_expensive_meter: str | None = None
    most_expensive_cost = 0.0
    meters_near_limit: list[dict] = []
    overage_revenue = 0.0

    for m in meters:
        meter_cogs = m.used * m.cost_per_unit
        total_cogs += meter_cogs
        total_usage_units += m.used

        if meter_cogs > most_expensive_cost:
            most_expensive_cost = meter_cogs
            most_expensive_meter = m.meter_type.value

        if m.limit > 0 and m.utilization_pct >= 80.0:
            meters_near_limit.append({
                "meter": m.meter_type.value,
                "used": m.used,
                "limit": m.limit,
                "utilization_pct": round(m.utilization_pct, 1),
            })

        overage_units = m.overage_units
        if overage_units > 0:
            overage_revenue += overage_units * m.overage_rate

    gross_margin = plan_price - total_cogs + overage_revenue
    margin_pct = (gross_margin / plan_price * 100.0) if plan_price > 0 else 0.0
    usage_efficiency = (plan_price / total_usage_units) if total_usage_units > 0 else 0.0

    overage_potential = 0.0
    for m in meters:
        if m.limit > 0 and m.used > 0:
            daily_rate = m.used / 30.0
            30 - min(30, int(m.used / max(daily_rate, 0.001)))
            projected_overage = max(0, int(daily_rate * 30) - m.limit)
            overage_potential += projected_overage * m.overage_rate

    if margin_pct < 20:
        recommended_action = "at_risk"
    elif len(meters_near_limit) >= 2:
        recommended_action = "upsell"
    elif any(m.overage_units > 0 for m in meters):
        recommended_action = "add_credits"
    else:
        recommended_action = "monitor"

    return {
        "total_cost_of_goods": round(total_cogs, 4),
        "gross_margin": round(gross_margin, 2),
        "margin_pct": round(margin_pct, 1),
        "most_expensive_meter": most_expensive_meter,
        "usage_efficiency": round(usage_efficiency, 4),
        "meters_near_limit": meters_near_limit,
        "overage_revenue_potential": round(overage_potential, 2),
        "recommended_action": recommended_action,
        "overage_revenue_actual": round(overage_revenue, 2),
        "total_usage_units": total_usage_units,
    }


def predict_credit_exhaustion(
    balance: CreditBalance,
    daily_usage_history: list[int],
) -> dict:
    """Predict when credits will run out using EWMA trend detection."""
    if not daily_usage_history:
        return {
            "days_until_exhaustion": -1,
            "exhaustion_date": None,
            "daily_burn_rate": 0.0,
            "trend": "steady",
            "recommended_pack": None,
            "urgency": "comfortable",
        }

    alpha = 0.3
    ewma = float(daily_usage_history[0])
    for val in daily_usage_history[1:]:
        ewma = alpha * val + (1.0 - alpha) * ewma
    daily_burn_rate = max(ewma, 0.001)

    remaining = max(balance.remaining_credits, 0)
    days_until_exhaustion = int(remaining / daily_burn_rate) if daily_burn_rate > 0 else 9999

    exhaustion_date = (datetime.utcnow() + timedelta(days=days_until_exhaustion)).strftime(
        "%Y-%m-%d"
    )

    n = len(daily_usage_history)
    if n >= 7:
        first_half = statistics.mean(daily_usage_history[: n // 2])
        second_half = statistics.mean(daily_usage_history[n // 2 :])
        change_pct = ((second_half - first_half) / max(first_half, 1)) * 100
        if change_pct > 15:
            trend = "accelerating"
        elif change_pct < -15:
            trend = "declining"
        else:
            trend = "steady"
    else:
        trend = "steady"

    if trend == "accelerating":
        days_until_exhaustion = max(1, int(days_until_exhaustion * 0.7))
        exhaustion_date = (
            datetime.utcnow() + timedelta(days=days_until_exhaustion)
        ).strftime("%Y-%m-%d")

    if days_until_exhaustion <= 3:
        urgency = "critical"
    elif days_until_exhaustion <= 7:
        urgency = "soon"
    elif days_until_exhaustion <= 14:
        urgency = "upcoming"
    else:
        urgency = "comfortable"

    projected_30d_usage = int(daily_burn_rate * 30)
    if projected_30d_usage <= 100:
        recommended_pack = "starter_100"
    elif projected_30d_usage <= 500:
        recommended_pack = "growth_500"
    elif projected_30d_usage <= 2000:
        recommended_pack = "power_2000"
    else:
        recommended_pack = "agency_10000"

    return {
        "days_until_exhaustion": days_until_exhaustion,
        "exhaustion_date": exhaustion_date,
        "daily_burn_rate": round(daily_burn_rate, 2),
        "trend": trend,
        "recommended_pack": recommended_pack,
        "urgency": urgency,
    }


def compute_meter_pricing(
    meter_type: MeterType,
    volume_per_month: int,
    target_margin: float = 0.80,
) -> dict:
    """Compute optimal pricing for a metered action with volume tiers."""
    base_cost = METER_COST_TABLE.get(meter_type, 0.01)
    base_price = base_cost / (1.0 - target_margin) if target_margin < 1.0 else base_cost * 5

    tiers = [
        {"name": "casual", "min": 0, "max": 50, "multiplier": 1.5},
        {"name": "standard", "min": 51, "max": 500, "multiplier": 1.0},
        {"name": "heavy", "min": 501, "max": 5000, "multiplier": 0.7},
        {"name": "enterprise", "min": 5001, "max": -1, "multiplier": 0.45},
    ]

    pricing_tiers = []
    for tier in tiers:
        tier_price = round(base_price * tier["multiplier"], 4)
        tier_cost = base_cost
        tier_margin = ((tier_price - tier_cost) / tier_price * 100) if tier_price > 0 else 0
        pricing_tiers.append({
            "tier_name": tier["name"],
            "volume_min": tier["min"],
            "volume_max": tier["max"],
            "price_per_unit": tier_price,
            "cost_per_unit": tier_cost,
            "margin_pct": round(tier_margin, 1),
        })

    active_tier = pricing_tiers[0]
    for pt in pricing_tiers:
        if volume_per_month >= pt["volume_min"]:
            if pt["volume_max"] == -1 or volume_per_month <= pt["volume_max"]:
                active_tier = pt
                break

    monthly_revenue = volume_per_month * active_tier["price_per_unit"]
    monthly_cost = volume_per_month * base_cost
    monthly_margin = monthly_revenue - monthly_cost

    flat_rate = volume_per_month * base_price * 0.85
    flat_margin = ((flat_rate - monthly_cost) / flat_rate * 100) if flat_rate > 0 else 0

    return {
        "meter_type": meter_type.value,
        "base_cost": base_cost,
        "base_price": round(base_price, 4),
        "volume_per_month": volume_per_month,
        "active_tier": active_tier["tier_name"],
        "active_price_per_unit": active_tier["price_per_unit"],
        "pricing_tiers": pricing_tiers,
        "monthly_revenue_estimate": round(monthly_revenue, 2),
        "monthly_cost_estimate": round(monthly_cost, 2),
        "monthly_margin_estimate": round(monthly_margin, 2),
        "unlimited_flat_rate": round(flat_rate, 2),
        "unlimited_flat_margin_pct": round(flat_margin, 1),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: HYBRID MONETIZATION SPINE
# ═══════════════════════════════════════════════════════════════════════════════


class PlanTier(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


@dataclass
class PricingPlan:
    tier: PlanTier
    name: str
    monthly_price: float
    annual_price: float
    annual_discount_pct: float
    included_credits: int
    meter_limits: dict[str, int]
    features: list[str]
    max_seats: int
    support_level: str
    sla_uptime_pct: float | None
    can_purchase_credit_packs: bool
    can_purchase_premium_packs: bool
    api_access: bool
    white_label: bool
    custom_branding: bool


@dataclass
class CreditPack:
    pack_id: str
    name: str
    credits: int
    price: float
    price_per_credit: float
    valid_days: int
    bonus_credits: int
    best_for: str


@dataclass
class PremiumPack:
    pack_id: str
    name: str
    description: str
    price: float
    pack_type: str
    included_items: list[dict]
    total_value: float
    savings_pct: float


def design_pricing_ladder() -> dict:
    """Design the complete pricing architecture."""
    plans = [
        PricingPlan(
            tier=PlanTier.FREE,
            name="Free",
            monthly_price=0.0,
            annual_price=0.0,
            annual_discount_pct=0.0,
            included_credits=50,
            meter_limits={
                MeterType.AI_GENERATION.value: 25,
                MeterType.AI_ANALYSIS.value: 10,
                MeterType.EXPORT.value: 5,
                MeterType.AUTOMATION_RUN.value: 0,
                MeterType.PUBLISH.value: 5,
                MeterType.STORAGE_GB.value: 1,
                MeterType.SEAT.value: 1,
                MeterType.API_CALL.value: 0,
                MeterType.PREMIUM_OUTPUT.value: 0,
                MeterType.CONCIERGE_ACTION.value: 0,
            },
            features=[
                "basic_content_generation",
                "basic_analytics",
                "single_brand",
                "community_templates",
            ],
            max_seats=1,
            support_level="community",
            sla_uptime_pct=None,
            can_purchase_credit_packs=False,
            can_purchase_premium_packs=False,
            api_access=False,
            white_label=False,
            custom_branding=False,
        ),
        PricingPlan(
            tier=PlanTier.STARTER,
            name="Starter",
            monthly_price=29.0,
            annual_price=23.17,
            annual_discount_pct=20.0,
            included_credits=500,
            meter_limits={
                MeterType.AI_GENERATION.value: 200,
                MeterType.AI_ANALYSIS.value: 100,
                MeterType.EXPORT.value: 50,
                MeterType.AUTOMATION_RUN.value: 10,
                MeterType.PUBLISH.value: 30,
                MeterType.STORAGE_GB.value: 5,
                MeterType.SEAT.value: 2,
                MeterType.API_CALL.value: 100,
                MeterType.PREMIUM_OUTPUT.value: 5,
                MeterType.CONCIERGE_ACTION.value: 0,
            },
            features=[
                "basic_content_generation",
                "advanced_analytics",
                "single_brand",
                "community_templates",
                "premium_templates",
                "email_support",
                "scheduling",
                "basic_automation",
            ],
            max_seats=2,
            support_level="email",
            sla_uptime_pct=None,
            can_purchase_credit_packs=True,
            can_purchase_premium_packs=False,
            api_access=False,
            white_label=False,
            custom_branding=False,
        ),
        PricingPlan(
            tier=PlanTier.PROFESSIONAL,
            name="Professional",
            monthly_price=79.0,
            annual_price=63.17,
            annual_discount_pct=20.0,
            included_credits=2000,
            meter_limits={
                MeterType.AI_GENERATION.value: 1000,
                MeterType.AI_ANALYSIS.value: 500,
                MeterType.EXPORT.value: 200,
                MeterType.AUTOMATION_RUN.value: 100,
                MeterType.PUBLISH.value: 100,
                MeterType.STORAGE_GB.value: 25,
                MeterType.SEAT.value: 5,
                MeterType.API_CALL.value: 1000,
                MeterType.PREMIUM_OUTPUT.value: 25,
                MeterType.CONCIERGE_ACTION.value: 2,
            },
            features=[
                "basic_content_generation",
                "advanced_analytics",
                "multi_brand_3",
                "all_templates",
                "priority_support",
                "scheduling",
                "full_automation",
                "ab_testing",
                "content_calendar",
                "team_collaboration",
                "api_access",
                "webhook_integration",
            ],
            max_seats=5,
            support_level="priority",
            sla_uptime_pct=99.5,
            can_purchase_credit_packs=True,
            can_purchase_premium_packs=True,
            api_access=True,
            white_label=False,
            custom_branding=True,
        ),
        PricingPlan(
            tier=PlanTier.BUSINESS,
            name="Business",
            monthly_price=199.0,
            annual_price=159.17,
            annual_discount_pct=20.0,
            included_credits=10000,
            meter_limits={
                MeterType.AI_GENERATION.value: 5000,
                MeterType.AI_ANALYSIS.value: 2500,
                MeterType.EXPORT.value: -1,
                MeterType.AUTOMATION_RUN.value: 500,
                MeterType.PUBLISH.value: 500,
                MeterType.STORAGE_GB.value: 100,
                MeterType.SEAT.value: 15,
                MeterType.API_CALL.value: 10000,
                MeterType.PREMIUM_OUTPUT.value: 100,
                MeterType.CONCIERGE_ACTION.value: 10,
            },
            features=[
                "basic_content_generation",
                "advanced_analytics",
                "unlimited_brands",
                "all_templates",
                "dedicated_support",
                "scheduling",
                "full_automation",
                "ab_testing",
                "content_calendar",
                "team_collaboration",
                "api_access",
                "webhook_integration",
                "white_label",
                "custom_branding",
                "bulk_operations",
                "agency_dashboard",
                "advanced_reporting",
                "revenue_analytics",
            ],
            max_seats=15,
            support_level="dedicated",
            sla_uptime_pct=99.9,
            can_purchase_credit_packs=True,
            can_purchase_premium_packs=True,
            api_access=True,
            white_label=True,
            custom_branding=True,
        ),
        PricingPlan(
            tier=PlanTier.ENTERPRISE,
            name="Enterprise",
            monthly_price=0.0,  # custom pricing
            annual_price=0.0,
            annual_discount_pct=0.0,
            included_credits=-1,
            meter_limits={
                MeterType.AI_GENERATION.value: -1,
                MeterType.AI_ANALYSIS.value: -1,
                MeterType.EXPORT.value: -1,
                MeterType.AUTOMATION_RUN.value: -1,
                MeterType.PUBLISH.value: -1,
                MeterType.STORAGE_GB.value: -1,
                MeterType.SEAT.value: -1,
                MeterType.API_CALL.value: -1,
                MeterType.PREMIUM_OUTPUT.value: -1,
                MeterType.CONCIERGE_ACTION.value: -1,
            },
            features=[
                "everything_in_business",
                "sso_saml",
                "custom_sla",
                "dedicated_csm",
                "custom_integrations",
                "on_premise_option",
                "audit_log",
                "advanced_security",
                "custom_training",
                "quarterly_business_review",
            ],
            max_seats=-1,
            support_level="dedicated",
            sla_uptime_pct=99.99,
            can_purchase_credit_packs=True,
            can_purchase_premium_packs=True,
            api_access=True,
            white_label=True,
            custom_branding=True,
        ),
    ]

    credit_packs = [
        CreditPack(
            pack_id="starter_100",
            name="Starter Pack",
            credits=100,
            price=9.0,
            price_per_credit=0.09,
            valid_days=90,
            bonus_credits=0,
            best_for="casual top-up",
        ),
        CreditPack(
            pack_id="growth_500",
            name="Growth Pack",
            credits=500,
            price=39.0,
            price_per_credit=0.078,
            valid_days=180,
            bonus_credits=25,
            best_for="power user",
        ),
        CreditPack(
            pack_id="power_2000",
            name="Power Pack",
            credits=2000,
            price=129.0,
            price_per_credit=0.0645,
            valid_days=365,
            bonus_credits=150,
            best_for="heavy operator",
        ),
        CreditPack(
            pack_id="agency_10000",
            name="Agency Pack",
            credits=10000,
            price=499.0,
            price_per_credit=0.0499,
            valid_days=-1,
            bonus_credits=1000,
            best_for="agency burst",
        ),
    ]

    premium_packs = [
        PremiumPack(
            pack_id="launch_pack",
            name="Launch Pack",
            description="Launch your first monetized content campaign",
            price=149.0,
            pack_type="launch_pack",
            included_items=[
                {"item": "ai_generations", "quantity": 50, "value": 25.0},
                {"item": "scripts", "quantity": 10, "value": 50.0},
                {"item": "published_pieces", "quantity": 5, "value": 25.0},
                {"item": "offer_setup", "quantity": 1, "value": 75.0},
                {"item": "analytics_30d", "quantity": 1, "value": 49.0},
                {"item": "onboarding_call", "quantity": 1, "value": 99.0},
            ],
            total_value=323.0,
            savings_pct=53.9,
        ),
        PremiumPack(
            pack_id="pipeline_pack",
            name="Pipeline Pack",
            description="Build a full content-to-revenue pipeline",
            price=249.0,
            pack_type="pipeline_pack",
            included_items=[
                {"item": "ai_generations", "quantity": 200, "value": 100.0},
                {"item": "scripts", "quantity": 30, "value": 150.0},
                {"item": "published_pieces", "quantity": 20, "value": 100.0},
                {"item": "offer_setups", "quantity": 5, "value": 375.0},
                {"item": "crm_setup", "quantity": 1, "value": 149.0},
                {"item": "analytics_90d", "quantity": 1, "value": 99.0},
            ],
            total_value=973.0,
            savings_pct=74.4,
        ),
        PremiumPack(
            pack_id="creator_pack",
            name="Creator Pack",
            description="Run a full creator operation for a quarter",
            price=499.0,
            pack_type="creator_pack",
            included_items=[
                {"item": "unlimited_generations_90d", "quantity": 1, "value": 450.0},
                {"item": "published_pieces", "quantity": 100, "value": 500.0},
                {"item": "full_analytics", "quantity": 1, "value": 199.0},
                {"item": "ab_testing", "quantity": 1, "value": 149.0},
                {"item": "automations", "quantity": 5, "value": 250.0},
                {"item": "priority_support", "quantity": 1, "value": 99.0},
            ],
            total_value=1647.0,
            savings_pct=69.7,
        ),
        PremiumPack(
            pack_id="automation_pack",
            name="Automation Pack",
            description="Automate your entire content workflow",
            price=399.0,
            pack_type="automation_pack",
            included_items=[
                {"item": "workflow_builders", "quantity": 10, "value": 500.0},
                {"item": "automation_runs", "quantity": 500, "value": 250.0},
                {"item": "priority_processing", "quantity": 1, "value": 149.0},
                {"item": "api_access", "quantity": 1, "value": 199.0},
                {"item": "webhook_setup", "quantity": 5, "value": 125.0},
            ],
            total_value=1223.0,
            savings_pct=67.4,
        ),
        PremiumPack(
            pack_id="agency_pack",
            name="Agency Pack",
            description="Manage 5 brands from one dashboard",
            price=999.0,
            pack_type="agency_pack",
            included_items=[
                {"item": "brand_slots", "quantity": 5, "value": 500.0},
                {"item": "team_seats", "quantity": 10, "value": 500.0},
                {"item": "white_label", "quantity": 1, "value": 499.0},
                {"item": "bulk_operations", "quantity": 1, "value": 299.0},
                {"item": "agency_analytics", "quantity": 1, "value": 399.0},
                {"item": "dedicated_support", "quantity": 1, "value": 299.0},
            ],
            total_value=2496.0,
            savings_pct=60.0,
        ),
        PremiumPack(
            pack_id="enterprise_pack",
            name="Enterprise Pack",
            description="Full platform for your organization",
            price=0.0,  # custom pricing
            pack_type="enterprise_pack",
            included_items=[
                {"item": "unlimited_everything", "quantity": 1, "value": 0.0},
                {"item": "sso_saml", "quantity": 1, "value": 0.0},
                {"item": "custom_sla", "quantity": 1, "value": 0.0},
                {"item": "dedicated_csm", "quantity": 1, "value": 0.0},
                {"item": "custom_integrations", "quantity": 1, "value": 0.0},
            ],
            total_value=0.0,
            savings_pct=0.0,
        ),
    ]

    upgrade_triggers = {
        PlanTier.FREE.value: {
            "to": PlanTier.STARTER.value,
            "triggers": [
                "hit_generation_limit",
                "wants_scheduling",
                "wants_more_storage",
                "wants_email_support",
                "tried_premium_template",
            ],
        },
        PlanTier.STARTER.value: {
            "to": PlanTier.PROFESSIONAL.value,
            "triggers": [
                "hit_generation_limit",
                "needs_api_access",
                "needs_more_seats",
                "wants_automation",
                "wants_ab_testing",
                "credit_purchases_increasing",
            ],
        },
        PlanTier.PROFESSIONAL.value: {
            "to": PlanTier.BUSINESS.value,
            "triggers": [
                "manages_multiple_brands",
                "needs_white_label",
                "needs_more_seats",
                "hit_automation_limit",
                "wants_bulk_operations",
                "revenue_analytics_needed",
            ],
        },
        PlanTier.BUSINESS.value: {
            "to": PlanTier.ENTERPRISE.value,
            "triggers": [
                "needs_sso",
                "needs_custom_sla",
                "needs_dedicated_csm",
                "team_size_over_15",
                "compliance_requirements",
                "custom_integration_request",
            ],
        },
    }

    enterprise_criteria = {
        "min_seats": 10,
        "min_monthly_spend": 500,
        "requires_sso": True,
        "requires_sla": True,
        "requires_compliance": True,
        "typical_deal_size_annual": 24000,
    }

    return {
        "plans": {p.tier.value: p for p in plans},
        "credit_packs": {cp.pack_id: cp for cp in credit_packs},
        "premium_packs": {pp.pack_id: pp for pp in premium_packs},
        "upgrade_triggers": upgrade_triggers,
        "enterprise_criteria": enterprise_criteria,
    }


_PRICING_LADDER: dict | None = None


def _get_pricing_ladder() -> dict:
    global _PRICING_LADDER
    if _PRICING_LADDER is None:
        _PRICING_LADDER = design_pricing_ladder()
    return _PRICING_LADDER


_PLAN_TIER_ORDER = [
    PlanTier.FREE,
    PlanTier.STARTER,
    PlanTier.PROFESSIONAL,
    PlanTier.BUSINESS,
    PlanTier.ENTERPRISE,
]


def _next_tier(current: PlanTier) -> PlanTier | None:
    try:
        idx = _PLAN_TIER_ORDER.index(current)
        if idx < len(_PLAN_TIER_ORDER) - 1:
            return _PLAN_TIER_ORDER[idx + 1]
    except ValueError:
        pass
    return None


def compute_plan_recommendation(
    current_usage: dict[str, int],
    current_plan: PlanTier,
    monthly_spend: float,
    usage_trend: str,
) -> dict:
    """Recommend the optimal plan based on actual usage patterns."""
    ladder = _get_pricing_ladder()
    plans: dict[str, PricingPlan] = ladder["plans"]
    ladder["credit_packs"]

    current_plan_obj = plans.get(current_plan.value)
    if current_plan_obj is None:
        return {
            "recommended_plan": current_plan.value,
            "recommended_add_ons": [],
            "savings_vs_current": 0.0,
            "reasoning": "Unable to determine current plan details.",
            "urgency": "low",
        }

    exceeded_meters: list[str] = []
    utilization_scores: list[float] = []

    for meter_str, used in current_usage.items():
        limit = current_plan_obj.meter_limits.get(meter_str, 0)
        if limit == -1:
            utilization_scores.append(0.3)
            continue
        if limit == 0 and used > 0:
            exceeded_meters.append(meter_str)
            utilization_scores.append(1.5)
            continue
        if limit > 0:
            util = used / limit
            utilization_scores.append(util)
            if util > 1.0:
                exceeded_meters.append(meter_str)

    avg_utilization = statistics.mean(utilization_scores) if utilization_scores else 0.0

    best_plan = current_plan
    best_cost = monthly_spend
    best_savings = 0.0

    for plan_tier in _PLAN_TIER_ORDER:
        candidate = plans[plan_tier.value]
        if candidate.monthly_price == 0 and plan_tier == PlanTier.ENTERPRISE:
            continue

        fits = True
        for meter_str, used in current_usage.items():
            limit = candidate.meter_limits.get(meter_str, 0)
            if limit == -1:
                continue
            headroom = 1.2 if usage_trend == "accelerating" else 1.0
            if used * headroom > limit:
                fits = False
                break

        if fits:
            effective_price = candidate.monthly_price
            if effective_price <= 0 and plan_tier != PlanTier.FREE:
                continue
            if _PLAN_TIER_ORDER.index(plan_tier) >= _PLAN_TIER_ORDER.index(current_plan):
                if effective_price < best_cost or (
                    effective_price == best_cost
                    and _PLAN_TIER_ORDER.index(plan_tier) <= _PLAN_TIER_ORDER.index(best_plan)
                ):
                    best_plan = plan_tier
                    best_cost = effective_price
                    best_savings = monthly_spend - effective_price

    if best_plan == current_plan and exceeded_meters:
        next_t = _next_tier(current_plan)
        if next_t and next_t != PlanTier.ENTERPRISE:
            best_plan = next_t
            best_cost = plans[next_t.value].monthly_price
            best_savings = monthly_spend - best_cost

    recommended_add_ons: list[str] = []
    if avg_utilization > 0.7 and best_plan == current_plan:
        overage_est = sum(
            max(0, v - current_plan_obj.meter_limits.get(k, 0))
            for k, v in current_usage.items()
            if current_plan_obj.meter_limits.get(k, 0) > 0
        )
        if overage_est <= 100:
            recommended_add_ons.append("starter_100")
        elif overage_est <= 500:
            recommended_add_ons.append("growth_500")
        else:
            recommended_add_ons.append("power_2000")

    reasons: list[str] = []
    if exceeded_meters:
        reasons.append(
            f"You've exceeded limits on: {', '.join(exceeded_meters)}"
        )
    if avg_utilization > 0.8:
        reasons.append(
            f"Average meter utilization is {avg_utilization:.0%}, suggesting your plan is tight"
        )
    if usage_trend == "accelerating":
        reasons.append("Your usage is accelerating, so headroom matters more")
    if best_savings > 0:
        reasons.append(f"Switching would save you ${best_savings:.2f}/month")
    elif best_plan != current_plan:
        upgrade_price = plans[best_plan.value].monthly_price
        reasons.append(
            f"Upgrading to {best_plan.value} (${upgrade_price}/mo) removes limits and adds features"
        )
    if not reasons:
        reasons.append("Your current plan is well-fitted for your usage.")

    if exceeded_meters:
        urgency = "high"
    elif avg_utilization > 0.85 or usage_trend == "accelerating":
        urgency = "medium"
    else:
        urgency = "low"

    return {
        "recommended_plan": best_plan.value,
        "recommended_add_ons": recommended_add_ons,
        "savings_vs_current": round(best_savings, 2),
        "reasoning": " ".join(reasons),
        "urgency": urgency,
        "exceeded_meters": exceeded_meters,
        "avg_utilization": round(avg_utilization, 2),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: ASCENSION PATH ENGINE
# ═══════════════════════════════════════════════════════════════════════════════


class UserSegment(str, Enum):
    CASUAL = "casual"
    SERIOUS = "serious"
    POWER_USER = "power_user"
    OPERATOR = "operator"
    AGENCY = "agency"
    ENTERPRISE = "enterprise"


@dataclass
class AscensionProfile:
    user_id: str
    current_segment: UserSegment
    current_plan: PlanTier
    monthly_spend: float
    account_age_days: int
    ascension_score: float
    next_tier: PlanTier
    upgrade_triggers: list[dict]
    expansion_potential: float
    time_to_next_upgrade: int | None
    recommended_nudges: list[dict]


def classify_user_segment(
    usage_data: dict,
    spend_history: list[float],
    feature_adoption: dict[str, bool],
    team_size: int,
    account_age_days: int,
) -> UserSegment:
    """Classify user into segment based on behavior, not self-report."""
    total_actions = sum(usage_data.get(mt.value, 0) for mt in MeterType)
    monthly_spend = statistics.mean(spend_history) if spend_history else 0.0
    adoption_rate = (
        sum(1 for v in feature_adoption.values() if v) / max(len(feature_adoption), 1)
    )

    has_api = feature_adoption.get("api_access", False)
    has_automation = feature_adoption.get("full_automation", False) or feature_adoption.get(
        "basic_automation", False
    )
    has_white_label = feature_adoption.get("white_label", False)
    has_sso = feature_adoption.get("sso_saml", False)
    manages_brands = usage_data.get("brands_managed", 0)

    if has_sso or (team_size > 10 and monthly_spend > 500):
        return UserSegment.ENTERPRISE

    if manages_brands >= 3 or (
        has_white_label and team_size >= 3
    ):
        return UserSegment.AGENCY

    if has_api and has_automation and total_actions > 500:
        return UserSegment.OPERATOR

    if (
        total_actions > 200
        and adoption_rate > 0.6
        and monthly_spend > 50
        and account_age_days > 30
    ):
        return UserSegment.POWER_USER

    if monthly_spend > 0 and total_actions > 20 and account_age_days > 14:
        return UserSegment.SERIOUS

    return UserSegment.CASUAL


_SEGMENT_TIER_MAP = {
    UserSegment.CASUAL: PlanTier.STARTER,
    UserSegment.SERIOUS: PlanTier.PROFESSIONAL,
    UserSegment.POWER_USER: PlanTier.PROFESSIONAL,
    UserSegment.OPERATOR: PlanTier.BUSINESS,
    UserSegment.AGENCY: PlanTier.BUSINESS,
    UserSegment.ENTERPRISE: PlanTier.ENTERPRISE,
}

_SEGMENT_EXPANSION_MULTIPLIER = {
    UserSegment.CASUAL: 1.5,
    UserSegment.SERIOUS: 2.0,
    UserSegment.POWER_USER: 2.5,
    UserSegment.OPERATOR: 3.0,
    UserSegment.AGENCY: 4.0,
    UserSegment.ENTERPRISE: 5.0,
}


def compute_ascension_profile(
    user_id: str,
    segment: UserSegment,
    current_plan: PlanTier,
    monthly_spend: float,
    usage_meters: dict[str, int],
    spend_history: list[float],
    feature_adoption: dict[str, bool],
    account_age_days: int,
    team_size: int,
) -> AscensionProfile:
    """Compute the full ascension profile with upgrade triggers and nudge recommendations."""
    ladder = _get_pricing_ladder()
    plans: dict[str, PricingPlan] = ladder["plans"]
    current_plan_obj = plans.get(current_plan.value)

    next_tier = _next_tier(current_plan)
    if next_tier is None:
        next_tier = current_plan

    # --- Compute upgrade triggers ---
    triggers: list[dict] = []

    if current_plan_obj:
        for meter_str, used in usage_meters.items():
            limit = current_plan_obj.meter_limits.get(meter_str, 0)
            if limit > 0 and used / limit >= 0.8:
                triggers.append({
                    "trigger": "meter_limit",
                    "status": True,
                    "description": f"{meter_str} at {used}/{limit} ({used / limit:.0%} used)",
                })

    if len(spend_history) >= 2:
        prev = statistics.mean(spend_history[:-1]) if len(spend_history) > 1 else spend_history[0]
        curr = spend_history[-1]
        if prev > 0 and (curr - prev) / prev > 0.2:
            triggers.append({
                "trigger": "usage_velocity",
                "status": True,
                "description": f"Spend increased {((curr - prev) / prev) * 100:.0f}% month-over-month",
            })

    if len(spend_history) >= 3:
        credit_trend = spend_history[-1] - spend_history[-3]
        if credit_trend > 0:
            triggers.append({
                "trigger": "credit_purchases_increasing",
                "status": True,
                "description": "Credit spending trending upward over last 3 months",
            })

    if team_size > 1:
        triggers.append({
            "trigger": "team_growth",
            "status": True,
            "description": f"Team has {team_size} members",
        })

    premium_features = {
        "ab_testing", "full_automation", "api_access", "white_label",
        "bulk_operations", "advanced_analytics", "webhook_integration",
    }
    discovered = [f for f in premium_features if feature_adoption.get(f, False)]
    if discovered:
        triggers.append({
            "trigger": "feature_discovery",
            "status": True,
            "description": f"Using premium features: {', '.join(discovered)}",
        })

    total_actions = sum(usage_meters.values())
    if total_actions > 100:
        content_value_est = total_actions * 2.5
        triggers.append({
            "trigger": "value_milestone",
            "status": True,
            "description": f"Generated ~${content_value_est:,.0f} in content value this month",
        })

    if account_age_days > 60:
        triggers.append({
            "trigger": "time_based",
            "status": True,
            "description": f"On current plan for {account_age_days} days (>60 day threshold)",
        })

    avg_usage = total_actions
    typical_for_plan = {
        PlanTier.FREE: 15,
        PlanTier.STARTER: 80,
        PlanTier.PROFESSIONAL: 300,
        PlanTier.BUSINESS: 1000,
        PlanTier.ENTERPRISE: 3000,
    }
    plan_avg = typical_for_plan.get(current_plan, 100)
    if avg_usage > plan_avg * 1.5:
        triggers.append({
            "trigger": "peer_comparison",
            "status": True,
            "description": f"Usage ({avg_usage}) is {avg_usage / max(plan_avg, 1):.1f}x the average for {current_plan.value} plan",
        })

    active_triggers = [t for t in triggers if t["status"]]
    trigger_count = len(active_triggers)

    ascension_score = min(100.0, trigger_count * 14.0 + (account_age_days / 365) * 10)
    if monthly_spend > 0:
        ascension_score = min(100.0, ascension_score + 10)
    if segment in (UserSegment.POWER_USER, UserSegment.OPERATOR, UserSegment.AGENCY):
        ascension_score = min(100.0, ascension_score + 15)

    ideal_tier = _SEGMENT_TIER_MAP.get(segment, PlanTier.STARTER)
    ideal_idx = _PLAN_TIER_ORDER.index(ideal_tier)
    current_idx = _PLAN_TIER_ORDER.index(current_plan)
    if ideal_idx > current_idx:
        ascension_score = min(100.0, ascension_score + 20)

    multiplier = _SEGMENT_EXPANSION_MULTIPLIER.get(segment, 1.5)
    expansion_potential = monthly_spend * (multiplier - 1.0)

    if ascension_score >= 80:
        time_to_next_upgrade = 7
    elif ascension_score >= 60:
        time_to_next_upgrade = 21
    elif ascension_score >= 40:
        time_to_next_upgrade = 45
    elif ascension_score >= 20:
        time_to_next_upgrade = 90
    else:
        time_to_next_upgrade = None

    # --- Nudge recommendations ---
    nudges: list[dict] = []

    for t in active_triggers:
        if t["trigger"] == "meter_limit":
            nudges.append({
                "nudge_type": "soft_limit",
                "message": f"You've used most of your monthly allowance — {t['description']}. Upgrade to get more.",
                "timing": "in_app_immediate",
            })

    if any(t["trigger"] == "value_milestone" for t in active_triggers):
        value_trigger = next(t for t in active_triggers if t["trigger"] == "value_milestone")
        plan_price = current_plan_obj.monthly_price if current_plan_obj else 0
        nudges.append({
            "nudge_type": "value_anchor",
            "message": f"{value_trigger['description']} on a ${plan_price}/mo plan. You're getting incredible ROI.",
            "timing": "dashboard_banner",
        })

    if any(t["trigger"] == "peer_comparison" for t in active_triggers):
        nudges.append({
            "nudge_type": "peer_proof",
            "message": f"Users like you typically upgrade to {next_tier.value.title()} for more headroom.",
            "timing": "email_weekly",
        })

    if current_plan in (PlanTier.FREE, PlanTier.STARTER):
        nudges.append({
            "nudge_type": "feature_preview",
            "message": "Try priority processing free for 7 days — see how fast your content gets generated.",
            "timing": "in_app_contextual",
        })

    if ascension_score > 50:
        nudges.append({
            "nudge_type": "scarcity",
            "message": "Lock in annual pricing before rates adjust next quarter.",
            "timing": "email_targeted",
        })

    if team_size > 1 and segment in (UserSegment.OPERATOR, UserSegment.AGENCY):
        nudges.append({
            "nudge_type": "expansion",
            "message": f"Add {max(2, 5 - team_size)} more team seats and unlock agency features for your growing team.",
            "timing": "dashboard_prompt",
        })

    return AscensionProfile(
        user_id=user_id,
        current_segment=segment,
        current_plan=current_plan,
        monthly_spend=monthly_spend,
        account_age_days=account_age_days,
        ascension_score=round(ascension_score, 1),
        next_tier=next_tier,
        upgrade_triggers=triggers,
        expansion_potential=round(expansion_potential, 2),
        time_to_next_upgrade=time_to_next_upgrade,
        recommended_nudges=nudges,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: REVENUE MULTIPLICATION EVENTS
# ═══════════════════════════════════════════════════════════════════════════════


class MultiplicationEvent(str, Enum):
    FASTER_PROCESSING = "faster_processing"
    PREMIUM_OUTPUT_QUALITY = "premium_output_quality"
    PREMIUM_TEMPLATE = "premium_template"
    PREMIUM_WORKFLOW = "premium_workflow"
    UNLOCKABLE_AUTOMATION = "unlockable_automation"
    EXTRA_SEAT = "extra_seat"
    API_ACCESS = "api_access"
    EXPORT_UPGRADE = "export_upgrade"
    WHITE_LABEL = "white_label"
    PRIORITY_EXECUTION = "priority_execution"
    CONCIERGE_ASSIST = "concierge_assist"
    CUSTOM_BRANDING = "custom_branding"
    ADVANCED_ANALYTICS = "advanced_analytics"
    BULK_OPERATIONS = "bulk_operations"


@dataclass
class MultiplicationOpportunity:
    event_type: MultiplicationEvent
    user_id: str
    trigger_context: str
    offer_price: float
    offer_description: str
    expected_conversion_rate: float
    expected_revenue: float
    urgency: str
    display_method: str


_MULTIPLICATION_CONFIG: dict[str, dict] = {
    MultiplicationEvent.FASTER_PROCESSING.value: {
        "price": 4.99,
        "description": "Skip the queue — get your content generated in under 30 seconds",
        "base_conversion": 0.12,
        "display": "inline_prompt",
    },
    MultiplicationEvent.PREMIUM_OUTPUT_QUALITY.value: {
        "price": 2.99,
        "description": "Upgrade this output to premium quality with enhanced detail and polish",
        "base_conversion": 0.18,
        "display": "inline_prompt",
    },
    MultiplicationEvent.PREMIUM_TEMPLATE.value: {
        "price": 9.99,
        "description": "Use this premium template designed by top creators",
        "base_conversion": 0.08,
        "display": "modal",
    },
    MultiplicationEvent.PREMIUM_WORKFLOW.value: {
        "price": 19.99,
        "description": "Unlock this advanced workflow with multi-step automation",
        "base_conversion": 0.06,
        "display": "modal",
    },
    MultiplicationEvent.UNLOCKABLE_AUTOMATION.value: {
        "price": 14.99,
        "description": "Automate this recurring task — save hours every week",
        "base_conversion": 0.10,
        "display": "banner",
    },
    MultiplicationEvent.EXTRA_SEAT.value: {
        "price": 12.00,
        "description": "Add a team member to collaborate on this project",
        "base_conversion": 0.15,
        "display": "modal",
    },
    MultiplicationEvent.API_ACCESS.value: {
        "price": 29.00,
        "description": "Connect your tools via API for seamless integration",
        "base_conversion": 0.05,
        "display": "banner",
    },
    MultiplicationEvent.EXPORT_UPGRADE.value: {
        "price": 4.99,
        "description": "Export in premium formats with custom branding",
        "base_conversion": 0.14,
        "display": "inline_prompt",
    },
    MultiplicationEvent.WHITE_LABEL.value: {
        "price": 49.00,
        "description": "Remove our branding — present to clients under your brand",
        "base_conversion": 0.04,
        "display": "email",
    },
    MultiplicationEvent.PRIORITY_EXECUTION.value: {
        "price": 7.99,
        "description": "Priority processing for your next 10 actions",
        "base_conversion": 0.11,
        "display": "inline_prompt",
    },
    MultiplicationEvent.CONCIERGE_ASSIST.value: {
        "price": 99.00,
        "description": "Let our team handle this for you — done-for-you execution",
        "base_conversion": 0.03,
        "display": "modal",
    },
    MultiplicationEvent.CUSTOM_BRANDING.value: {
        "price": 29.00,
        "description": "Add your brand colors, logo, and voice to all outputs",
        "base_conversion": 0.07,
        "display": "banner",
    },
    MultiplicationEvent.ADVANCED_ANALYTICS.value: {
        "price": 19.99,
        "description": "Unlock deep analytics — see exactly what's driving your revenue",
        "base_conversion": 0.09,
        "display": "banner",
    },
    MultiplicationEvent.BULK_OPERATIONS.value: {
        "price": 24.99,
        "description": "Process up to 100 items at once with bulk operations",
        "base_conversion": 0.07,
        "display": "modal",
    },
}

_ACTION_TO_EVENTS: dict[str, list[MultiplicationEvent]] = {
    "generating_content": [
        MultiplicationEvent.PREMIUM_OUTPUT_QUALITY,
        MultiplicationEvent.FASTER_PROCESSING,
        MultiplicationEvent.PREMIUM_TEMPLATE,
    ],
    "waiting_for_processing": [
        MultiplicationEvent.FASTER_PROCESSING,
        MultiplicationEvent.PRIORITY_EXECUTION,
    ],
    "exporting": [
        MultiplicationEvent.EXPORT_UPGRADE,
        MultiplicationEvent.CUSTOM_BRANDING,
    ],
    "running_automation": [
        MultiplicationEvent.UNLOCKABLE_AUTOMATION,
        MultiplicationEvent.PREMIUM_WORKFLOW,
        MultiplicationEvent.BULK_OPERATIONS,
    ],
    "adding_team_member": [
        MultiplicationEvent.EXTRA_SEAT,
        MultiplicationEvent.WHITE_LABEL,
    ],
    "viewing_analytics": [
        MultiplicationEvent.ADVANCED_ANALYTICS,
    ],
    "publishing": [
        MultiplicationEvent.PRIORITY_EXECUTION,
        MultiplicationEvent.PREMIUM_OUTPUT_QUALITY,
    ],
    "managing_brand": [
        MultiplicationEvent.CUSTOM_BRANDING,
        MultiplicationEvent.WHITE_LABEL,
    ],
    "building_workflow": [
        MultiplicationEvent.PREMIUM_WORKFLOW,
        MultiplicationEvent.UNLOCKABLE_AUTOMATION,
        MultiplicationEvent.API_ACCESS,
    ],
    "requesting_help": [
        MultiplicationEvent.CONCIERGE_ASSIST,
    ],
}

_SEGMENT_CONVERSION_MULTIPLIER = {
    UserSegment.CASUAL: 0.6,
    UserSegment.SERIOUS: 1.0,
    UserSegment.POWER_USER: 1.3,
    UserSegment.OPERATOR: 1.5,
    UserSegment.AGENCY: 1.8,
    UserSegment.ENTERPRISE: 0.5,  # enterprise buys in bulk, not one-off
}


def detect_multiplication_opportunities(
    user_segment: UserSegment,
    current_plan: PlanTier,
    current_action: str,
    usage_context: dict,
    already_purchased: set[str],
) -> list[MultiplicationOpportunity]:
    """Detect real-time opportunities for revenue multiplication."""
    candidate_events = _ACTION_TO_EVENTS.get(current_action, [])
    if not candidate_events:
        for action_key, events in _ACTION_TO_EVENTS.items():
            if action_key in current_action or current_action in action_key:
                candidate_events = events
                break

    if not candidate_events:
        candidate_events = [
            MultiplicationEvent.FASTER_PROCESSING,
            MultiplicationEvent.PREMIUM_OUTPUT_QUALITY,
        ]

    segment_mult = _SEGMENT_CONVERSION_MULTIPLIER.get(user_segment, 1.0)

    plan_tier_idx = _PLAN_TIER_ORDER.index(current_plan)
    plan_discount = max(0.4, 1.0 - plan_tier_idx * 0.15)

    opportunities: list[MultiplicationOpportunity] = []

    for event in candidate_events:
        if event.value in already_purchased:
            continue

        config = _MULTIPLICATION_CONFIG.get(event.value)
        if config is None:
            continue

        ladder = _get_pricing_ladder()
        plan_obj: PricingPlan = ladder["plans"].get(current_plan.value)
        if plan_obj:
            if event == MultiplicationEvent.API_ACCESS and plan_obj.api_access:
                continue
            if event == MultiplicationEvent.WHITE_LABEL and plan_obj.white_label:
                continue
            if event == MultiplicationEvent.CUSTOM_BRANDING and plan_obj.custom_branding:
                continue

        base_conv = config["base_conversion"]
        adjusted_conv = min(0.50, base_conv * segment_mult * plan_discount)

        context_boost = 1.0
        if usage_context.get("is_high_value_content"):
            context_boost = 1.3
        if usage_context.get("is_time_sensitive"):
            context_boost *= 1.2
        if usage_context.get("is_first_time_action"):
            context_boost *= 0.7
        if usage_context.get("session_duration_minutes", 0) > 30:
            context_boost *= 1.15

        adjusted_conv = min(0.50, adjusted_conv * context_boost)

        price = config["price"]
        expected_revenue = round(price * adjusted_conv, 2)

        if usage_context.get("is_time_sensitive"):
            urgency = "immediate"
        elif usage_context.get("is_high_value_content"):
            urgency = "session"
        else:
            urgency = "this_week"

        trigger_context = (
            f"User is {current_action} "
            f"({usage_context.get('content_type', 'standard')} content, "
            f"{user_segment.value} segment, {current_plan.value} plan)"
        )

        opportunities.append(
            MultiplicationOpportunity(
                event_type=event,
                user_id=usage_context.get("user_id", "unknown"),
                trigger_context=trigger_context,
                offer_price=price,
                offer_description=config["description"],
                expected_conversion_rate=round(adjusted_conv, 3),
                expected_revenue=expected_revenue,
                urgency=urgency,
                display_method=config["display"],
            )
        )

    opportunities.sort(key=lambda o: o.expected_revenue, reverse=True)
    return opportunities


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: MONETIZATION TELEMETRY
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class TelemetryEvent:
    user_id: str
    event_name: str
    event_value: float
    timestamp: datetime
    properties: dict = field(default_factory=dict)


@dataclass
class MonetizationHealth:
    total_users: int
    paying_users: int
    free_to_paid_rate: float
    avg_revenue_per_user: float
    avg_revenue_per_paying_user: float
    median_time_to_first_value_hours: float
    median_time_to_first_spend_hours: float
    upgrade_rate_30d: float
    expansion_rate_30d: float
    credit_purchase_rate: float
    churn_rate_30d: float
    net_revenue_retention: float
    spend_by_segment: dict[str, float]
    top_upgrade_triggers: list[dict]
    top_churn_triggers: list[dict]
    feature_revenue_correlation: list[dict]
    monetization_score: float


def compute_monetization_health(
    users: list[dict],
    events: list[TelemetryEvent],
    revenue_data: list[dict],
) -> MonetizationHealth:
    """Compute comprehensive monetization health metrics."""
    total_users = len(users)
    if total_users == 0:
        return MonetizationHealth(
            total_users=0, paying_users=0, free_to_paid_rate=0.0,
            avg_revenue_per_user=0.0, avg_revenue_per_paying_user=0.0,
            median_time_to_first_value_hours=0.0,
            median_time_to_first_spend_hours=0.0,
            upgrade_rate_30d=0.0, expansion_rate_30d=0.0,
            credit_purchase_rate=0.0, churn_rate_30d=0.0,
            net_revenue_retention=100.0, spend_by_segment={},
            top_upgrade_triggers=[], top_churn_triggers=[],
            feature_revenue_correlation=[], monetization_score=0.0,
        )

    paying_users = [u for u in users if u.get("monthly_spend", 0) > 0]
    paying_count = len(paying_users)
    total_users - paying_count
    free_to_paid_rate = (paying_count / total_users) * 100 if total_users > 0 else 0.0

    total_revenue = sum(r.get("amount", 0) for r in revenue_data)
    arpu = total_revenue / total_users if total_users > 0 else 0.0
    arppu = total_revenue / paying_count if paying_count > 0 else 0.0

    time_to_first_value: list[float] = []
    time_to_first_spend: list[float] = []

    user_signup_map: dict[str, datetime] = {}
    for u in users:
        uid = u.get("user_id", "")
        signup = u.get("signup_date")
        if isinstance(signup, str):
            try:
                signup = datetime.fromisoformat(signup)
            except (ValueError, TypeError):
                signup = None
        if signup:
            user_signup_map[uid] = signup

    user_first_value: dict[str, datetime] = {}
    user_first_spend: dict[str, datetime] = {}

    for ev in sorted(events, key=lambda e: e.timestamp):
        uid = ev.user_id
        if uid not in user_first_value and ev.event_name in (
            "content_generated", "first_publish", "first_export", "first_analysis",
        ):
            user_first_value[uid] = ev.timestamp
        if uid not in user_first_spend and ev.event_name in (
            "subscription_created", "credit_purchased", "pack_purchased",
        ):
            user_first_spend[uid] = ev.timestamp

    for uid, signup in user_signup_map.items():
        if uid in user_first_value:
            delta = (user_first_value[uid] - signup).total_seconds() / 3600
            if delta >= 0:
                time_to_first_value.append(delta)
        if uid in user_first_spend:
            delta = (user_first_spend[uid] - signup).total_seconds() / 3600
            if delta >= 0:
                time_to_first_spend.append(delta)

    median_ttfv = statistics.median(time_to_first_value) if time_to_first_value else 0.0
    median_ttfs = statistics.median(time_to_first_spend) if time_to_first_spend else 0.0

    now = datetime.utcnow()
    cutoff_30d = now - timedelta(days=30)

    upgrades_30d = [
        ev for ev in events
        if ev.event_name == "plan_upgraded" and ev.timestamp >= cutoff_30d
    ]
    upgrading_users = {ev.user_id for ev in upgrades_30d}
    upgrade_rate = (len(upgrading_users) / paying_count * 100) if paying_count > 0 else 0.0

    expansions_30d = [
        ev for ev in events
        if ev.event_name in ("seat_added", "credit_purchased", "pack_purchased")
        and ev.timestamp >= cutoff_30d
    ]
    expanding_users = {ev.user_id for ev in expansions_30d}
    expansion_rate = (len(expanding_users) / paying_count * 100) if paying_count > 0 else 0.0

    credit_purchasers = {
        ev.user_id for ev in events
        if ev.event_name == "credit_purchased" and ev.timestamp >= cutoff_30d
    }
    credit_purchase_rate = (
        len(credit_purchasers) / paying_count * 100
    ) if paying_count > 0 else 0.0

    churned_30d = [
        ev for ev in events
        if ev.event_name in ("subscription_cancelled", "churned")
        and ev.timestamp >= cutoff_30d
    ]
    churned_users = {ev.user_id for ev in churned_30d}
    churn_rate = (len(churned_users) / paying_count * 100) if paying_count > 0 else 0.0

    prior_month_revenue = sum(
        r.get("amount", 0) for r in revenue_data
        if _parse_date(r.get("date")) and cutoff_30d - timedelta(days=30) <= _parse_date(r.get("date")) < cutoff_30d
    )
    current_month_revenue = sum(
        r.get("amount", 0) for r in revenue_data
        if _parse_date(r.get("date")) and _parse_date(r.get("date")) >= cutoff_30d
    )
    nrr = (
        (current_month_revenue / prior_month_revenue * 100)
        if prior_month_revenue > 0
        else 100.0
    )

    spend_by_segment: dict[str, float] = defaultdict(float)
    for u in users:
        seg = u.get("segment", "casual")
        spend_by_segment[seg] += u.get("monthly_spend", 0)

    user_features_for_corr = []
    for u in users:
        features_used = set(u.get("features_used", []))
        user_features_for_corr.append({
            "user_id": u.get("user_id"),
            "features_used": features_used,
            "monthly_spend": u.get("monthly_spend", 0),
        })
    feature_corr = compute_feature_revenue_correlation(user_features_for_corr)

    upgrade_triggers = detect_upgrade_triggers(events, [
        {
            "user_id": ev.user_id,
            "upgrade_date": ev.timestamp.isoformat(),
            "from_plan": ev.properties.get("from_plan", "unknown"),
            "to_plan": ev.properties.get("to_plan", "unknown"),
        }
        for ev in upgrades_30d
    ], window_days=14)

    churn_triggers = detect_churn_triggers(events, [
        {"user_id": ev.user_id, "churn_date": ev.timestamp.isoformat()}
        for ev in churned_30d
    ], window_days=14)

    score = 0.0
    if free_to_paid_rate > 5:
        score += 15
    elif free_to_paid_rate > 2:
        score += 8
    if upgrade_rate > 10:
        score += 15
    elif upgrade_rate > 5:
        score += 8
    if expansion_rate > 15:
        score += 15
    elif expansion_rate > 5:
        score += 8
    if churn_rate < 3:
        score += 15
    elif churn_rate < 7:
        score += 8
    if nrr > 110:
        score += 15
    elif nrr > 100:
        score += 8
    if arppu > 50:
        score += 10
    elif arppu > 20:
        score += 5
    if median_ttfv < 24:
        score += 8
    elif median_ttfv < 72:
        score += 4
    if credit_purchase_rate > 10:
        score += 7
    elif credit_purchase_rate > 3:
        score += 3

    return MonetizationHealth(
        total_users=total_users,
        paying_users=paying_count,
        free_to_paid_rate=round(free_to_paid_rate, 2),
        avg_revenue_per_user=round(arpu, 2),
        avg_revenue_per_paying_user=round(arppu, 2),
        median_time_to_first_value_hours=round(median_ttfv, 1),
        median_time_to_first_spend_hours=round(median_ttfs, 1),
        upgrade_rate_30d=round(upgrade_rate, 2),
        expansion_rate_30d=round(expansion_rate, 2),
        credit_purchase_rate=round(credit_purchase_rate, 2),
        churn_rate_30d=round(churn_rate, 2),
        net_revenue_retention=round(nrr, 2),
        spend_by_segment=dict(spend_by_segment),
        top_upgrade_triggers=upgrade_triggers[:10],
        top_churn_triggers=churn_triggers[:10],
        feature_revenue_correlation=feature_corr[:10],
        monetization_score=round(min(100, score), 1),
    )


def _parse_date(date_val: Any) -> datetime | None:
    if date_val is None:
        return None
    if isinstance(date_val, datetime):
        return date_val
    if isinstance(date_val, str):
        try:
            return datetime.fromisoformat(date_val)
        except (ValueError, TypeError):
            return None
    return None


def compute_feature_revenue_correlation(
    user_features: list[dict],
) -> list[dict]:
    """Compute which features correlate most strongly with revenue.

    Uses point-biserial correlation between binary feature adoption
    and continuous spend amount.
    """
    if not user_features:
        return []

    all_features: set[str] = set()
    for uf in user_features:
        all_features.update(uf.get("features_used", set()))

    if not all_features:
        return []

    spends = [uf.get("monthly_spend", 0) for uf in user_features]
    n = len(spends)
    if n < 3:
        return []

    statistics.mean(spends)
    global_std = statistics.stdev(spends) if n > 1 else 1.0
    if global_std == 0:
        global_std = 1.0

    results: list[dict] = []

    for feature in all_features:
        adopters_spend: list[float] = []
        non_adopters_spend: list[float] = []

        for uf in user_features:
            spend = uf.get("monthly_spend", 0)
            if feature in uf.get("features_used", set()):
                adopters_spend.append(spend)
            else:
                non_adopters_spend.append(spend)

        n1 = len(adopters_spend)
        n0 = len(non_adopters_spend)

        if n1 < 2 or n0 < 2:
            continue

        m1 = statistics.mean(adopters_spend)
        m0 = statistics.mean(non_adopters_spend)

        p = n1 / n
        q = 1 - p

        if p * q <= 0:
            continue

        r_pb = ((m1 - m0) / global_std) * math.sqrt(p * q)
        r_pb = max(-1.0, min(1.0, r_pb))

        revenue_impact = m1 - m0

        results.append({
            "feature": feature,
            "correlation": round(r_pb, 4),
            "revenue_impact": round(revenue_impact, 2),
            "adopter_count": n1,
            "adopter_avg_spend": round(m1, 2),
            "non_adopter_avg_spend": round(m0, 2),
        })

    results.sort(key=lambda x: abs(x["correlation"]), reverse=True)
    return results


def detect_upgrade_triggers(
    event_stream: list[TelemetryEvent],
    upgrades: list[dict],
    window_days: int = 14,
) -> list[dict]:
    """Identify which events most commonly precede upgrades."""
    if not upgrades or not event_stream:
        return []

    user_events: dict[str, list[TelemetryEvent]] = defaultdict(list)
    for ev in event_stream:
        user_events[ev.user_id].append(ev)

    all_user_ids = set(user_events.keys())
    upgrade_user_ids = {u["user_id"] for u in upgrades}
    non_upgrade_user_ids = all_user_ids - upgrade_user_ids

    pre_upgrade_events: dict[str, int] = defaultdict(int)
    total_upgrade_windows = 0

    for upgrade in upgrades:
        uid = upgrade["user_id"]
        upgrade_date = _parse_date(upgrade.get("upgrade_date"))
        if upgrade_date is None:
            continue

        window_start = upgrade_date - timedelta(days=window_days)
        events_in_window = [
            ev for ev in user_events.get(uid, [])
            if window_start <= ev.timestamp < upgrade_date
            and ev.event_name != "plan_upgraded"
        ]

        seen_events: set[str] = set()
        for ev in events_in_window:
            if ev.event_name not in seen_events:
                pre_upgrade_events[ev.event_name] += 1
                seen_events.add(ev.event_name)

        total_upgrade_windows += 1

    if total_upgrade_windows == 0:
        return []

    baseline_rates: dict[str, float] = defaultdict(float)
    non_upgrade_count = max(len(non_upgrade_user_ids), 1)

    for uid in non_upgrade_user_ids:
        seen: set[str] = set()
        for ev in user_events.get(uid, []):
            if ev.event_name not in seen:
                baseline_rates[ev.event_name] += 1
                seen.add(ev.event_name)

    for k in baseline_rates:
        baseline_rates[k] /= non_upgrade_count

    results: list[dict] = []
    for event_name, count in pre_upgrade_events.items():
        upgrade_rate = count / total_upgrade_windows
        base_rate = baseline_rates.get(event_name, 0.0)
        lift = (upgrade_rate / base_rate) if base_rate > 0 else (upgrade_rate * 10 if upgrade_rate > 0 else 0)

        results.append({
            "event": event_name,
            "pre_upgrade_frequency": round(upgrade_rate, 3),
            "baseline_frequency": round(base_rate, 3),
            "lift": round(lift, 2),
            "occurrences_in_window": count,
            "total_windows": total_upgrade_windows,
        })

    results.sort(key=lambda x: x["lift"], reverse=True)
    return results


def detect_churn_triggers(
    event_stream: list[TelemetryEvent],
    churns: list[dict],
    window_days: int = 14,
) -> list[dict]:
    """Identify which events (or lack of events) precede churn."""
    if not churns or not event_stream:
        return []

    user_events: dict[str, list[TelemetryEvent]] = defaultdict(list)
    for ev in event_stream:
        user_events[ev.user_id].append(ev)

    all_user_ids = set(user_events.keys())
    churn_user_ids = {c["user_id"] for c in churns}
    active_user_ids = all_user_ids - churn_user_ids

    pre_churn_events: dict[str, int] = defaultdict(int)
    total_churn_windows = 0

    churn_window_event_counts: list[int] = []

    for churn in churns:
        uid = churn["user_id"]
        churn_date = _parse_date(churn.get("churn_date"))
        if churn_date is None:
            continue

        window_start = churn_date - timedelta(days=window_days)
        events_in_window = [
            ev for ev in user_events.get(uid, [])
            if window_start <= ev.timestamp < churn_date
        ]

        churn_window_event_counts.append(len(events_in_window))

        seen_events: set[str] = set()
        for ev in events_in_window:
            if ev.event_name not in seen_events:
                pre_churn_events[ev.event_name] += 1
                seen_events.add(ev.event_name)

        total_churn_windows += 1

    if total_churn_windows == 0:
        return []

    active_rates: dict[str, float] = defaultdict(float)
    active_count = max(len(active_user_ids), 1)

    active_event_counts: list[int] = []

    for uid in active_user_ids:
        user_evts = user_events.get(uid, [])
        active_event_counts.append(len(user_evts))
        seen: set[str] = set()
        for ev in user_evts:
            if ev.event_name not in seen:
                active_rates[ev.event_name] += 1
                seen.add(ev.event_name)

    for k in active_rates:
        active_rates[k] /= active_count

    results: list[dict] = []

    for event_name, count in pre_churn_events.items():
        churn_rate = count / total_churn_windows
        active_rate = active_rates.get(event_name, 0.0)
        lift = (churn_rate / active_rate) if active_rate > 0 else (churn_rate * 10 if churn_rate > 0 else 0)

        results.append({
            "event": event_name,
            "pre_churn_frequency": round(churn_rate, 3),
            "active_frequency": round(active_rate, 3),
            "lift": round(lift, 2),
            "type": "presence",
        })

    avg_churn_events = statistics.mean(churn_window_event_counts) if churn_window_event_counts else 0
    avg_active_events = statistics.mean(active_event_counts) if active_event_counts else 0

    if avg_churn_events < avg_active_events * 0.5:
        results.append({
            "event": "__low_activity__",
            "pre_churn_frequency": round(avg_churn_events, 1),
            "active_frequency": round(avg_active_events, 1),
            "lift": round(
                (avg_active_events / max(avg_churn_events, 0.1)), 2
            ),
            "type": "absence",
            "description": "Churning users had significantly fewer events before churn",
        })

    all_event_names = set(active_rates.keys())
    churn_event_names = set(pre_churn_events.keys())
    missing_events = all_event_names - churn_event_names

    for event_name in missing_events:
        active_rate = active_rates.get(event_name, 0)
        if active_rate > 0.3:
            results.append({
                "event": event_name,
                "pre_churn_frequency": 0.0,
                "active_frequency": round(active_rate, 3),
                "lift": 0.0,
                "type": "absence",
                "description": f"Active users do '{event_name}' but churners rarely did",
            })

    results.sort(key=lambda x: x["lift"], reverse=True)
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: JOB-TO-BE-DONE PACKAGING
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class OutcomePack:
    pack_id: str
    name: str
    tagline: str
    target_segment: UserSegment
    target_job: str
    included_outputs: list[dict]
    price: float
    anchor_value: float
    monthly_equivalent: float
    savings_vs_ala_carte: float
    conversion_triggers: list[str]
    upsell_to: str | None


def design_outcome_packs(
    product_capabilities: list[str],
    user_segments: list[UserSegment],
) -> list[OutcomePack]:
    """Design job-to-be-done outcome packs that sell completed outcomes."""

    packs = [
        OutcomePack(
            pack_id="launch_outcome",
            name="Launch Pack",
            tagline="Launch your first monetized content campaign",
            target_segment=UserSegment.CASUAL,
            target_job="Go from zero to published, monetized content",
            included_outputs=[
                {"output": "AI-generated content pieces", "quantity": 50, "description": "Blog posts, social media, scripts"},
                {"output": "Polished scripts", "quantity": 10, "description": "Ready-to-record video/podcast scripts"},
                {"output": "Published pieces", "quantity": 5, "description": "Cross-platform publishing"},
                {"output": "Offer setup", "quantity": 1, "description": "Your first monetization offer configured"},
                {"output": "Analytics dashboard (30 days)", "quantity": 1, "description": "Track what's working"},
                {"output": "Onboarding strategy call", "quantity": 1, "description": "30-min setup call"},
            ],
            price=149.0,
            anchor_value=397.0,
            monthly_equivalent=265.0,
            savings_vs_ala_carte=62.5,
            conversion_triggers=[
                "user_completes_signup",
                "user_creates_first_content",
                "user_views_pricing_page",
                "user_hits_free_limit",
            ],
            upsell_to="pipeline_outcome",
        ),
        OutcomePack(
            pack_id="pipeline_outcome",
            name="Pipeline Pack",
            tagline="Build a full content-to-revenue pipeline",
            target_segment=UserSegment.SERIOUS,
            target_job="Create a repeatable system from content to cash",
            included_outputs=[
                {"output": "AI-generated content pieces", "quantity": 200, "description": "Multi-format content library"},
                {"output": "Polished scripts", "quantity": 30, "description": "A month of daily scripts"},
                {"output": "Published pieces", "quantity": 20, "description": "Multi-platform presence"},
                {"output": "Offer setups", "quantity": 5, "description": "Multiple revenue streams configured"},
                {"output": "CRM pipeline setup", "quantity": 1, "description": "Lead capture and nurture flows"},
                {"output": "Analytics (90 days)", "quantity": 1, "description": "Full funnel visibility"},
            ],
            price=249.0,
            anchor_value=973.0,
            monthly_equivalent=83.0,
            savings_vs_ala_carte=74.4,
            conversion_triggers=[
                "user_completed_launch_pack",
                "user_has_3_plus_published_pieces",
                "user_attempts_offer_setup",
                "user_asks_about_automation",
            ],
            upsell_to="creator_outcome",
        ),
        OutcomePack(
            pack_id="creator_outcome",
            name="Creator Pack",
            tagline="Run a full creator operation for a quarter",
            target_segment=UserSegment.POWER_USER,
            target_job="Operate like a professional creator with systems",
            included_outputs=[
                {"output": "Unlimited AI generations (90 days)", "quantity": 1, "description": "No limits on creation"},
                {"output": "Published pieces", "quantity": 100, "description": "Consistent publishing cadence"},
                {"output": "Full analytics suite", "quantity": 1, "description": "Revenue + engagement analytics"},
                {"output": "A/B testing", "quantity": 1, "description": "Optimize every piece"},
                {"output": "Automation workflows", "quantity": 5, "description": "Set-and-forget content flows"},
                {"output": "Priority support", "quantity": 1, "description": "Direct access to help"},
            ],
            price=499.0,
            anchor_value=1647.0,
            monthly_equivalent=166.0,
            savings_vs_ala_carte=69.7,
            conversion_triggers=[
                "user_generating_daily",
                "user_bought_credit_pack_twice",
                "user_hitting_publish_limit",
                "user_has_revenue_from_content",
            ],
            upsell_to="automation_outcome",
        ),
        OutcomePack(
            pack_id="automation_outcome",
            name="Automation Pack",
            tagline="Automate your entire content workflow",
            target_segment=UserSegment.OPERATOR,
            target_job="Remove yourself from the content production loop",
            included_outputs=[
                {"output": "Workflow builders", "quantity": 10, "description": "Drag-and-drop automation setup"},
                {"output": "Automation runs", "quantity": 500, "description": "Monthly automated actions"},
                {"output": "Priority processing", "quantity": 1, "description": "Sub-30s generation times"},
                {"output": "Full API access", "quantity": 1, "description": "Integrate with your stack"},
                {"output": "Webhook configurations", "quantity": 5, "description": "Real-time event triggers"},
                {"output": "Automation strategy session", "quantity": 1, "description": "45-min workflow design call"},
            ],
            price=399.0,
            anchor_value=1223.0,
            monthly_equivalent=133.0,
            savings_vs_ala_carte=67.4,
            conversion_triggers=[
                "user_runs_manual_workflow_3x",
                "user_asks_about_api",
                "user_exports_data_frequently",
                "user_manages_multiple_content_types",
            ],
            upsell_to="agency_outcome",
        ),
        OutcomePack(
            pack_id="agency_outcome",
            name="Agency Pack",
            tagline="Manage 5 brands from one dashboard",
            target_segment=UserSegment.AGENCY,
            target_job="Scale content operations across multiple clients",
            included_outputs=[
                {"output": "Brand slots", "quantity": 5, "description": "Independent brand workspaces"},
                {"output": "Team seats", "quantity": 10, "description": "Full team access"},
                {"output": "White-label outputs", "quantity": 1, "description": "Your branding, not ours"},
                {"output": "Bulk operations", "quantity": 1, "description": "Process 100+ items at once"},
                {"output": "Agency analytics", "quantity": 1, "description": "Cross-brand performance view"},
                {"output": "Dedicated support", "quantity": 1, "description": "Slack channel + CSM"},
            ],
            price=999.0,
            anchor_value=2496.0,
            monthly_equivalent=333.0,
            savings_vs_ala_carte=60.0,
            conversion_triggers=[
                "user_adds_second_brand",
                "user_invites_third_team_member",
                "user_asks_about_white_label",
                "user_exports_client_reports",
            ],
            upsell_to="enterprise_outcome",
        ),
        OutcomePack(
            pack_id="enterprise_outcome",
            name="Enterprise Pack",
            tagline="Full platform for your organization",
            target_segment=UserSegment.ENTERPRISE,
            target_job="Deploy AI content operations org-wide with compliance",
            included_outputs=[
                {"output": "Unlimited everything", "quantity": 1, "description": "No metered limits"},
                {"output": "SSO/SAML", "quantity": 1, "description": "Enterprise authentication"},
                {"output": "Custom SLA", "quantity": 1, "description": "Guaranteed uptime and response"},
                {"output": "Dedicated CSM", "quantity": 1, "description": "Named customer success manager"},
                {"output": "Custom integrations", "quantity": 3, "description": "Built to your spec"},
                {"output": "Quarterly business review", "quantity": 1, "description": "Strategic alignment sessions"},
            ],
            price=0.0,  # custom
            anchor_value=0.0,
            monthly_equivalent=0.0,
            savings_vs_ala_carte=0.0,
            conversion_triggers=[
                "user_has_10_plus_seats",
                "user_requests_sso",
                "user_requests_sla",
                "user_mentions_compliance",
                "user_spends_over_500_monthly",
            ],
            upsell_to=None,
        ),
    ]

    if product_capabilities:
        set(product_capabilities)
        for pack in packs:
            relevant_outputs = []
            for output in pack.included_outputs:
                relevant_outputs.append(output)
            pack.included_outputs = relevant_outputs

    return packs


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7: REVENUE SEGMENTATION & FULL MACHINE REPORT
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class RevenueSegmentProfile:
    segment: UserSegment
    user_count: int
    total_revenue: float
    avg_revenue: float
    median_revenue: float
    revenue_share_pct: float
    growth_rate: float
    avg_feature_adoption: float
    top_spend_categories: list[dict]
    upgrade_propensity: float
    churn_risk: float
    expansion_potential: float
    recommended_strategy: str


def segment_revenue(
    users: list[dict],
) -> list[RevenueSegmentProfile]:
    """Segment users by spend behavior and compute per-segment strategy."""
    segment_buckets: dict[str, list[dict]] = defaultdict(list)
    for u in users:
        seg = u.get("segment", UserSegment.CASUAL.value)
        segment_buckets[seg].append(u)

    grand_total_revenue = sum(u.get("monthly_spend", 0) for u in users)

    profiles: list[RevenueSegmentProfile] = []

    strategy_map = {
        UserSegment.CASUAL.value: "Activate with low-friction entry offers; surface value quickly; convert to Starter",
        UserSegment.SERIOUS.value: "Deepen engagement with feature education; recommend Professional plan; offer credit packs",
        UserSegment.POWER_USER.value: "Maximize LTV with automation upsells and premium packs; watch for agency expansion signals",
        UserSegment.OPERATOR.value: "Sell efficiency — automation packs, API access, bulk operations; position Business tier",
        UserSegment.AGENCY.value: "Multi-brand value; white-label; dedicated support; position for annual commitment",
        UserSegment.ENTERPRISE.value: "Custom pricing; SLA; dedicated CSM; land-and-expand within organization",
    }

    for seg_value in [s.value for s in UserSegment]:
        bucket = segment_buckets.get(seg_value, [])
        user_count = len(bucket)
        if user_count == 0:
            profiles.append(RevenueSegmentProfile(
                segment=UserSegment(seg_value),
                user_count=0,
                total_revenue=0.0,
                avg_revenue=0.0,
                median_revenue=0.0,
                revenue_share_pct=0.0,
                growth_rate=0.0,
                avg_feature_adoption=0.0,
                top_spend_categories=[],
                upgrade_propensity=0.0,
                churn_risk=0.0,
                expansion_potential=0.0,
                recommended_strategy=strategy_map.get(seg_value, "Monitor"),
            ))
            continue

        spends = [u.get("monthly_spend", 0) for u in bucket]
        total_rev = sum(spends)
        avg_rev = statistics.mean(spends)
        median_rev = statistics.median(spends)
        rev_share = (total_rev / grand_total_revenue * 100) if grand_total_revenue > 0 else 0

        growth_rates: list[float] = []
        for u in bucket:
            hist = u.get("spend_history", [])
            if len(hist) >= 2 and hist[-2] > 0:
                gr = (hist[-1] - hist[-2]) / hist[-2]
                growth_rates.append(gr)
        avg_growth = statistics.mean(growth_rates) if growth_rates else 0.0

        adoption_rates: list[float] = []
        for u in bucket:
            features = u.get("features_used", [])
            total_features = u.get("total_features", 15)
            if total_features > 0:
                adoption_rates.append(len(features) / total_features)
        avg_adoption = statistics.mean(adoption_rates) if adoption_rates else 0.0

        spend_categories: dict[str, float] = defaultdict(float)
        for u in bucket:
            for cat, amount in u.get("spend_categories", {}).items():
                spend_categories[cat] += amount
        top_categories = sorted(
            [{"category": k, "amount": round(v, 2)} for k, v in spend_categories.items()],
            key=lambda x: x["amount"],
            reverse=True,
        )[:5]

        if seg_value in (UserSegment.CASUAL.value, UserSegment.SERIOUS.value):
            upgrade_prop = min(1.0, avg_growth + 0.3 + avg_adoption * 0.5)
        elif seg_value == UserSegment.POWER_USER.value:
            upgrade_prop = min(1.0, avg_growth + 0.2 + avg_adoption * 0.3)
        else:
            upgrade_prop = min(1.0, avg_growth * 0.5 + 0.1)

        if avg_adoption < 0.2 and avg_rev < 20:
            churn_risk = 0.7
        elif avg_growth < -0.1:
            churn_risk = 0.5
        elif avg_adoption < 0.4:
            churn_risk = 0.3
        else:
            churn_risk = 0.1

        multiplier = _SEGMENT_EXPANSION_MULTIPLIER.get(UserSegment(seg_value), 1.5)
        expansion = avg_rev * (multiplier - 1.0) * user_count

        profiles.append(RevenueSegmentProfile(
            segment=UserSegment(seg_value),
            user_count=user_count,
            total_revenue=round(total_rev, 2),
            avg_revenue=round(avg_rev, 2),
            median_revenue=round(median_rev, 2),
            revenue_share_pct=round(rev_share, 1),
            growth_rate=round(avg_growth * 100, 1),
            avg_feature_adoption=round(avg_adoption * 100, 1),
            top_spend_categories=top_categories,
            upgrade_propensity=round(upgrade_prop, 3),
            churn_risk=round(churn_risk, 3),
            expansion_potential=round(expansion, 2),
            recommended_strategy=strategy_map.get(seg_value, "Monitor"),
        ))

    profiles.sort(key=lambda p: p.total_revenue, reverse=True)
    return profiles


@dataclass
class MonetizationMachineReport:
    """The complete monetization machine health report."""
    health_score: float
    health_grade: str
    mrr: float
    arr: float
    arpu: float
    arppu: float
    free_to_paid_rate: float
    expansion_rate: float
    credit_utilization_rate: float
    segments: list[RevenueSegmentProfile]
    ascension_pipeline: dict
    multiplication_revenue: float
    pack_revenue: float
    top_upgrade_triggers: list[dict]
    top_churn_triggers: list[dict]
    pricing_optimization: dict
    recommended_actions: list[dict]
    projected_impact: dict


def _score_to_grade(score: float) -> str:
    if score >= 95:
        return "A+"
    if score >= 90:
        return "A"
    if score >= 85:
        return "A-"
    if score >= 80:
        return "B+"
    if score >= 75:
        return "B"
    if score >= 70:
        return "B-"
    if score >= 65:
        return "C+"
    if score >= 60:
        return "C"
    if score >= 55:
        return "C-"
    if score >= 50:
        return "D+"
    if score >= 45:
        return "D"
    if score >= 40:
        return "D-"
    return "F"


def generate_machine_report(
    users: list[dict],
    subscriptions: list[dict],
    credit_transactions: list[dict],
    pack_purchases: list[dict],
    usage_data: list[dict],
    events: list[TelemetryEvent],
) -> MonetizationMachineReport:
    """Generate the complete monetization machine health report."""

    # --- Core revenue metrics ---
    total_users = len(users)
    paying_users = [u for u in users if u.get("monthly_spend", 0) > 0]
    paying_count = len(paying_users)

    subscription_mrr = sum(s.get("monthly_amount", 0) for s in subscriptions if s.get("status") == "active")

    credit_revenue_30d = sum(
        ct.get("amount", 0) for ct in credit_transactions
        if _parse_date(ct.get("date")) and _parse_date(ct.get("date")) >= datetime.utcnow() - timedelta(days=30)
    )

    pack_revenue_30d = sum(
        pp.get("amount", 0) for pp in pack_purchases
        if _parse_date(pp.get("date")) and _parse_date(pp.get("date")) >= datetime.utcnow() - timedelta(days=30)
    )

    mrr = subscription_mrr + credit_revenue_30d + pack_revenue_30d
    arr = mrr * 12
    arpu = mrr / total_users if total_users > 0 else 0.0
    arppu = mrr / paying_count if paying_count > 0 else 0.0

    free_to_paid_rate = (paying_count / total_users * 100) if total_users > 0 else 0.0

    # --- Expansion & credit utilization ---
    now = datetime.utcnow()
    cutoff = now - timedelta(days=30)

    expansion_events = [
        ev for ev in events
        if ev.event_name in ("seat_added", "credit_purchased", "pack_purchased", "plan_upgraded")
        and ev.timestamp >= cutoff
    ]
    expanding_user_ids = {ev.user_id for ev in expansion_events}
    expansion_rate = (len(expanding_user_ids) / paying_count * 100) if paying_count > 0 else 0.0

    total_credits_allocated = sum(u.get("total_credits", 0) for u in users)
    total_credits_used = sum(u.get("used_credits", 0) for u in users)
    credit_utilization = (
        total_credits_used / total_credits_allocated * 100
    ) if total_credits_allocated > 0 else 0.0

    # --- Segments ---
    segments = segment_revenue(users)

    # --- Ascension pipeline ---
    pipeline: dict[str, int] = defaultdict(int)
    for u in users:
        plan = u.get("plan", PlanTier.FREE.value)
        pipeline[plan] = pipeline.get(plan, 0) + 1

    # --- Telemetry-driven insights ---
    revenue_records = [
        {"amount": u.get("monthly_spend", 0), "date": u.get("last_charge_date")}
        for u in users
    ]
    health = compute_monetization_health(users, events, revenue_records)

    # --- Pricing optimization ---
    avg_utilization_by_plan: dict[str, float] = defaultdict(list)
    for ud in usage_data:
        plan = ud.get("plan", "free")
        meters = ud.get("meters", {})
        ladder = _get_pricing_ladder()
        plan_obj: PricingPlan | None = ladder["plans"].get(plan)
        if plan_obj:
            utils = []
            for meter_str, used in meters.items():
                limit = plan_obj.meter_limits.get(meter_str, 0)
                if limit > 0:
                    utils.append(used / limit)
            if utils:
                avg_utilization_by_plan[plan].append(statistics.mean(utils))

    pricing_optimization: dict[str, Any] = {}
    for plan, util_lists in avg_utilization_by_plan.items():
        if not util_lists:
            continue
        avg_util = statistics.mean(util_lists)
        if avg_util > 0.9:
            pricing_optimization[plan] = {
                "avg_utilization": round(avg_util, 2),
                "recommendation": "Consider raising limits or tier price — users are extracting maximum value",
                "action": "raise_price_5_10_pct",
            }
        elif avg_util < 0.3:
            pricing_optimization[plan] = {
                "avg_utilization": round(avg_util, 2),
                "recommendation": "Users are underutilizing — consider lowering price to improve activation or adding more value",
                "action": "lower_price_or_add_value",
            }
        else:
            pricing_optimization[plan] = {
                "avg_utilization": round(avg_util, 2),
                "recommendation": "Utilization is healthy — maintain current pricing",
                "action": "maintain",
            }

    # --- Recommended actions ---
    recommended_actions: list[dict] = []

    if free_to_paid_rate < 3:
        recommended_actions.append({
            "action": "improve_free_to_paid_conversion",
            "description": "Free-to-paid rate is below 3%. Improve onboarding, add in-app upgrade prompts, and tighten free limits.",
            "priority": "critical",
            "expected_impact_pct": 25,
            "category": "conversion",
        })

    if health.churn_rate_30d > 5:
        recommended_actions.append({
            "action": "reduce_churn",
            "description": f"Churn at {health.churn_rate_30d}% is above healthy threshold. Implement win-back campaigns and improve onboarding.",
            "priority": "critical",
            "expected_impact_pct": 20,
            "category": "retention",
        })

    if expansion_rate < 5:
        recommended_actions.append({
            "action": "increase_expansion_revenue",
            "description": "Expansion rate is low. Deploy multiplication events, credit pack nudges, and seat expansion prompts.",
            "priority": "high",
            "expected_impact_pct": 15,
            "category": "expansion",
        })

    if credit_utilization < 40:
        recommended_actions.append({
            "action": "improve_credit_utilization",
            "description": "Users are not consuming their credits. Improve feature discovery and credit-consuming workflows.",
            "priority": "medium",
            "expected_impact_pct": 10,
            "category": "activation",
        })

    casual_seg = next((s for s in segments if s.segment == UserSegment.CASUAL), None)
    if casual_seg and casual_seg.user_count > total_users * 0.6:
        recommended_actions.append({
            "action": "activate_casual_users",
            "description": f"{casual_seg.user_count} casual users ({casual_seg.user_count / max(total_users, 1) * 100:.0f}%). Deploy activation campaigns and outcome packs.",
            "priority": "high",
            "expected_impact_pct": 18,
            "category": "activation",
        })

    enterprise_seg = next((s for s in segments if s.segment == UserSegment.ENTERPRISE), None)
    if enterprise_seg and enterprise_seg.user_count > 0 and enterprise_seg.expansion_potential > 0:
        recommended_actions.append({
            "action": "expand_enterprise_accounts",
            "description": f"${enterprise_seg.expansion_potential:,.0f} expansion potential in enterprise segment. Deploy dedicated CSM outreach.",
            "priority": "high",
            "expected_impact_pct": 12,
            "category": "expansion",
        })

    if pack_revenue_30d < mrr * 0.1:
        recommended_actions.append({
            "action": "promote_outcome_packs",
            "description": "Pack revenue is under 10% of MRR. Deploy contextual pack offers and email campaigns.",
            "priority": "medium",
            "expected_impact_pct": 8,
            "category": "monetization",
        })

    for plan_key, opt in pricing_optimization.items():
        if opt["action"] == "raise_price_5_10_pct":
            recommended_actions.append({
                "action": f"raise_price_{plan_key}",
                "description": f"{plan_key.title()} plan utilization at {opt['avg_utilization']:.0%}. Test 5-10% price increase.",
                "priority": "medium",
                "expected_impact_pct": 7,
                "category": "pricing",
            })

    recommended_actions.sort(key=lambda a: a.get("expected_impact_pct", 0), reverse=True)

    # --- Projected impact ---
    total_projected_impact_pct = sum(a["expected_impact_pct"] for a in recommended_actions[:5])
    projected_mrr_increase = mrr * (total_projected_impact_pct / 100)
    projected_arr_increase = projected_mrr_increase * 12

    projected_impact = {
        "top_5_actions_combined_impact_pct": total_projected_impact_pct,
        "projected_mrr_increase": round(projected_mrr_increase, 2),
        "projected_arr_increase": round(projected_arr_increase, 2),
        "current_mrr": round(mrr, 2),
        "projected_mrr": round(mrr + projected_mrr_increase, 2),
        "timeframe": "90 days",
    }

    # --- Health score ---
    score = health.monetization_score

    conversion_score = min(25, free_to_paid_rate * 3)
    retention_score = min(25, max(0, 25 - health.churn_rate_30d * 3))
    expansion_score = min(25, expansion_rate * 2)
    efficiency_score = min(25, credit_utilization * 0.3 + (arppu / max(arpu, 1)) * 5)

    composite_score = (
        conversion_score + retention_score + expansion_score + efficiency_score
    )
    final_score = (score + composite_score) / 2.0
    final_score = min(100.0, max(0.0, final_score))

    return MonetizationMachineReport(
        health_score=round(final_score, 1),
        health_grade=_score_to_grade(final_score),
        mrr=round(mrr, 2),
        arr=round(arr, 2),
        arpu=round(arpu, 2),
        arppu=round(arppu, 2),
        free_to_paid_rate=round(free_to_paid_rate, 2),
        expansion_rate=round(expansion_rate, 2),
        credit_utilization_rate=round(credit_utilization, 2),
        segments=segments,
        ascension_pipeline=dict(pipeline),
        multiplication_revenue=round(credit_revenue_30d * 0.4, 2),
        pack_revenue=round(pack_revenue_30d, 2),
        top_upgrade_triggers=health.top_upgrade_triggers,
        top_churn_triggers=health.top_churn_triggers,
        pricing_optimization=pricing_optimization,
        recommended_actions=recommended_actions,
        projected_impact=projected_impact,
    )
