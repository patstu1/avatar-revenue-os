"""High-Ticket Revenue Engine — Optimize high-value sales funnels.

Handles consulting pipelines, course launches, service packages,
and any revenue avenue with deal values > $500.

All functions are pure/deterministic — no DB access. Service layer handles persistence.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

# ---------------------------------------------------------------------------
# Enums & Constants
# ---------------------------------------------------------------------------

class DealStage(str, Enum):
    AWARENESS = "awareness"
    INTEREST = "interest"
    CONSIDERATION = "consideration"
    EVALUATION = "evaluation"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


STAGE_ORDER: list[DealStage] = [
    DealStage.AWARENESS,
    DealStage.INTEREST,
    DealStage.CONSIDERATION,
    DealStage.EVALUATION,
    DealStage.NEGOTIATION,
    DealStage.CLOSED_WON,
]

_STAGE_INDEX: dict[DealStage, int] = {s: i for i, s in enumerate(STAGE_ORDER)}

SOURCE_QUALITY: dict[str, float] = {
    "referral": 1.0,
    "webinar": 0.85,
    "content": 0.75,
    "ad": 0.55,
    "outbound": 0.45,
}

_BENCHMARK_DAYS_PER_STAGE: dict[DealStage, int] = {
    DealStage.AWARENESS: 14,
    DealStage.INTEREST: 10,
    DealStage.CONSIDERATION: 12,
    DealStage.EVALUATION: 10,
    DealStage.NEGOTIATION: 7,
}

_DEFAULT_STAGE_CONVERSION: dict[DealStage, float] = {
    DealStage.AWARENESS: 0.40,
    DealStage.INTEREST: 0.55,
    DealStage.CONSIDERATION: 0.50,
    DealStage.EVALUATION: 0.60,
    DealStage.NEGOTIATION: 0.70,
}

_SYNERGY_MAP: dict[tuple[str, str], float] = {
    ("saas", "community"): 1.30,
    ("community", "saas"): 1.30,
    ("course", "consulting"): 1.25,
    ("consulting", "course"): 1.25,
    ("content", "affiliate"): 1.15,
    ("affiliate", "content"): 1.15,
    ("membership", "course"): 1.20,
    ("course", "membership"): 1.20,
    ("coaching", "course"): 1.20,
    ("course", "coaching"): 1.20,
    ("service", "saas"): 1.15,
    ("saas", "service"): 1.15,
    ("consulting", "community"): 1.10,
    ("community", "consulting"): 1.10,
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Deal:
    deal_id: str
    customer_name: str
    deal_value: float
    stage: DealStage
    created_at: datetime
    last_activity_at: datetime
    expected_close_date: datetime | None
    probability: float
    source: str
    product_type: str
    notes: str = ""
    days_in_stage: int = 0
    interactions: int = 0
    score: float = 0.0


@dataclass
class PipelineAnalysis:
    total_pipeline_value: float
    weighted_pipeline_value: float
    deals_by_stage: dict[str, int]
    value_by_stage: dict[str, float]
    avg_deal_size: float
    avg_days_to_close: float
    win_rate: float
    stage_conversion_rates: dict[str, float]
    bottleneck_stage: str
    bottleneck_severity: float
    velocity: float
    forecast_30d: float
    forecast_90d: float
    health_score: float


@dataclass
class LaunchWindow:
    recommended_date: str
    audience_readiness_score: float
    competition_window_score: float
    seasonal_score: float
    composite_score: float
    reasoning: str


@dataclass
class LaunchPlan:
    product_name: str
    product_type: str
    price_point: float
    launch_phases: list[dict]
    total_expected_revenue: float
    total_expected_signups: int
    break_even_signups: int
    marketing_budget_recommended: float
    conversion_funnel: dict
    risk_factors: list[str]
    mitigation_strategies: list[str]


@dataclass
class ConsultingPackage:
    name: str
    tier: str
    price: float
    hours_included: int
    deliverables: list[str]
    ideal_client_profile: str
    avg_close_rate: float
    avg_ltv: float
    upsell_path: str | None


@dataclass
class FunnelMetrics:
    registrations: int
    show_up_rate: float
    engagement_rate: float
    offer_conversion_rate: float
    avg_order_value: float
    revenue_per_registrant: float
    cost_per_registrant: float
    roas: float
    funnel_efficiency_score: float


@dataclass
class FunnelOptimization:
    current_metrics: FunnelMetrics
    bottleneck: str
    improvement_potential: float
    recommendations: list[dict]
    projected_metrics_after_fix: FunnelMetrics


@dataclass
class RevenueStack:
    total_monthly_revenue: float
    total_annual_revenue: float
    recurring_pct: float
    stack_layers: list[dict]
    diversification_score: float
    vulnerability_score: float
    growth_trajectory: str
    next_best_avenue: str
    revenue_at_risk_single_point: float


# ---------------------------------------------------------------------------
# 1. High-Ticket Pipeline Manager
# ---------------------------------------------------------------------------

def _active_deals(deals: list[Deal]) -> list[Deal]:
    return [d for d in deals if d.stage not in (DealStage.CLOSED_WON, DealStage.CLOSED_LOST)]


def _won_deals(deals: list[Deal]) -> list[Deal]:
    return [d for d in deals if d.stage == DealStage.CLOSED_WON]


def _lost_deals(deals: list[Deal]) -> list[Deal]:
    return [d for d in deals if d.stage == DealStage.CLOSED_LOST]


def _closed_deals(deals: list[Deal]) -> list[Deal]:
    return [d for d in deals if d.stage in (DealStage.CLOSED_WON, DealStage.CLOSED_LOST)]


def _days_between(a: datetime, b: datetime) -> float:
    return max(abs((b - a).total_seconds()) / 86400, 0.01)


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    return num / den if den else default


def analyze_pipeline(
    deals: list[Deal],
    historical_deals: list[Deal] | None = None,
) -> PipelineAnalysis:
    """Comprehensive pipeline health analysis."""
    now = datetime.utcnow()
    if historical_deals is None:
        historical_deals = []

    all_deals = deals + historical_deals
    active = _active_deals(deals)
    won = _won_deals(all_deals)
    _lost_deals(all_deals)
    closed = _closed_deals(all_deals)

    # --- basic aggregates ---
    total_pipeline_value = sum(d.deal_value for d in active)
    weighted_pipeline_value = sum(d.deal_value * d.probability for d in active)

    deals_by_stage: dict[str, int] = defaultdict(int)
    value_by_stage: dict[str, float] = defaultdict(float)
    for d in active:
        deals_by_stage[d.stage.value] += 1
        value_by_stage[d.stage.value] += d.deal_value

    avg_deal_size = _safe_div(total_pipeline_value, len(active), 0.0)

    # --- cycle time from historical closed-won deals ---
    cycle_days_list: list[float] = []
    for d in won:
        if d.expected_close_date:
            cycle_days_list.append(_days_between(d.created_at, d.expected_close_date))
        else:
            cycle_days_list.append(_days_between(d.created_at, d.last_activity_at))
    avg_days_to_close = statistics.mean(cycle_days_list) if cycle_days_list else 45.0

    # --- win rate ---
    win_rate = _safe_div(len(won), len(closed), 0.25)

    # --- stage conversion rates ---
    stage_counts: dict[DealStage, int] = defaultdict(int)
    for d in all_deals:
        idx = _STAGE_INDEX.get(d.stage, 0)
        for s in STAGE_ORDER[: idx + 1]:
            stage_counts[s] += 1

    stage_conversion_rates: dict[str, float] = {}
    for i, stage in enumerate(STAGE_ORDER[:-1]):
        next_stage = STAGE_ORDER[i + 1]
        entered = stage_counts.get(stage, 0)
        advanced = stage_counts.get(next_stage, 0)
        stage_conversion_rates[stage.value] = _safe_div(advanced, entered, _DEFAULT_STAGE_CONVERSION[stage])

    # --- bottleneck: stage with worst conversion relative to benchmark ---
    worst_stage = DealStage.AWARENESS
    worst_severity = 0.0
    for stage in STAGE_ORDER[:-1]:
        actual = stage_conversion_rates.get(stage.value, 0.5)
        benchmark = _DEFAULT_STAGE_CONVERSION.get(stage, 0.5)
        gap = max(benchmark - actual, 0.0)
        severity = _safe_div(gap, benchmark, 0.0)
        if severity > worst_severity:
            worst_severity = severity
            worst_stage = stage

    # --- velocity: deals × avg_value × win_rate / avg_cycle_days ---
    velocity = _safe_div(
        len(active) * avg_deal_size * win_rate,
        avg_days_to_close,
        0.0,
    )

    # --- forecasts ---
    daily_revenue_rate = velocity
    forecast_30d = daily_revenue_rate * 30
    forecast_90d = daily_revenue_rate * 90

    # --- health score (0-100) ---
    balance_score = _pipeline_balance_score(deals_by_stage)
    aging_score = _pipeline_aging_score(active, now)
    velocity_score = min(velocity / max(avg_deal_size * 0.5, 1) * 50, 100)
    coverage_score = min(weighted_pipeline_value / max(forecast_30d, 1) * 25, 100)

    health_score = _clamp(
        balance_score * 0.25
        + aging_score * 0.25
        + velocity_score * 0.25
        + coverage_score * 0.25
    )

    return PipelineAnalysis(
        total_pipeline_value=round(total_pipeline_value, 2),
        weighted_pipeline_value=round(weighted_pipeline_value, 2),
        deals_by_stage=dict(deals_by_stage),
        value_by_stage={k: round(v, 2) for k, v in value_by_stage.items()},
        avg_deal_size=round(avg_deal_size, 2),
        avg_days_to_close=round(avg_days_to_close, 1),
        win_rate=round(win_rate, 4),
        stage_conversion_rates={k: round(v, 4) for k, v in stage_conversion_rates.items()},
        bottleneck_stage=worst_stage.value,
        bottleneck_severity=round(worst_severity, 4),
        velocity=round(velocity, 2),
        forecast_30d=round(forecast_30d, 2),
        forecast_90d=round(forecast_90d, 2),
        health_score=round(health_score, 1),
    )


def _pipeline_balance_score(deals_by_stage: dict[str, int]) -> float:
    """Higher score when pipeline has healthy top-heavy distribution."""
    if not deals_by_stage:
        return 0.0
    total = sum(deals_by_stage.values())
    if total == 0:
        return 0.0

    ideal_ratios = {
        DealStage.AWARENESS.value: 0.30,
        DealStage.INTEREST.value: 0.25,
        DealStage.CONSIDERATION.value: 0.20,
        DealStage.EVALUATION.value: 0.15,
        DealStage.NEGOTIATION.value: 0.10,
    }
    deviation = 0.0
    for stage_val, ideal in ideal_ratios.items():
        actual = _safe_div(deals_by_stage.get(stage_val, 0), total, 0.0)
        deviation += abs(actual - ideal)

    return _clamp((1 - deviation) * 100)


def _pipeline_aging_score(active: list[Deal], now: datetime) -> float:
    """Penalize pipelines where many deals are stale."""
    if not active:
        return 50.0

    stale_count = 0
    for d in active:
        benchmark = _BENCHMARK_DAYS_PER_STAGE.get(d.stage, 10)
        if d.days_in_stage > benchmark * 1.5:
            stale_count += 1

    stale_ratio = _safe_div(stale_count, len(active), 0.0)
    return _clamp((1 - stale_ratio) * 100)


def score_deal(deal: Deal, avg_cycle_days: float = 45) -> float:
    """Score a deal 0-100 based on qualification signals."""
    now = datetime.utcnow()

    # --- Stage progression velocity (0-25) ---
    days_alive = _days_between(deal.created_at, now)
    stage_idx = _STAGE_INDEX.get(deal.stage, 0)
    expected_fraction = days_alive / max(avg_cycle_days, 1)
    actual_fraction = stage_idx / (len(STAGE_ORDER) - 1) if len(STAGE_ORDER) > 1 else 0
    velocity_ratio = _safe_div(actual_fraction, expected_fraction, 0.5)
    velocity_score = _clamp(velocity_ratio * 25, 0, 25)

    # --- Engagement level (0-20) ---
    interaction_benchmark = max(stage_idx * 2, 1)
    engagement_ratio = min(deal.interactions / interaction_benchmark, 2.0)
    engagement_score = _clamp(engagement_ratio * 10, 0, 20)

    # --- Deal value sizing (0-15) — sweet spot is 0.5x-3x average ---
    avg_value = 2500.0
    ratio = _safe_div(deal.deal_value, avg_value, 1.0)
    if 0.5 <= ratio <= 3.0:
        value_score = 15.0
    elif ratio < 0.5:
        value_score = max(ratio * 30, 0)
    else:
        value_score = max(15 - (ratio - 3.0) * 3, 5)

    # --- Source quality (0-15) ---
    source_q = SOURCE_QUALITY.get(deal.source, 0.5)
    source_score = source_q * 15

    # --- Recency of activity (0-15) ---
    days_since_activity = _days_between(deal.last_activity_at, now)
    if days_since_activity <= 2:
        recency_score = 15.0
    elif days_since_activity <= 7:
        recency_score = 12.0
    elif days_since_activity <= 14:
        recency_score = 8.0
    elif days_since_activity <= 30:
        recency_score = 4.0
    else:
        recency_score = max(2 - (days_since_activity - 30) * 0.05, 0)

    # --- Time-in-stage vs benchmark (0-10) ---
    benchmark_days = _BENCHMARK_DAYS_PER_STAGE.get(deal.stage, 10)
    stage_ratio = _safe_div(deal.days_in_stage, benchmark_days, 1.0)
    if stage_ratio <= 1.0:
        stage_score = 10.0
    elif stage_ratio <= 1.5:
        stage_score = 7.0
    elif stage_ratio <= 2.0:
        stage_score = 4.0
    else:
        stage_score = max(2 - (stage_ratio - 2.0), 0)

    total = velocity_score + engagement_score + value_score + source_score + recency_score + stage_score
    return round(_clamp(total), 1)


# ---------------------------------------------------------------------------
# 2. Course/Digital Product Launch Optimizer
# ---------------------------------------------------------------------------

_BASE_CONVERSION_RATES: dict[str, dict[str, float]] = {
    "course": {
        "awareness_to_interest": 0.08,
        "interest_to_waitlist": 0.25,
        "waitlist_to_cart": 0.35,
        "cart_to_purchase": 0.12,
    },
    "digital_product": {
        "awareness_to_interest": 0.10,
        "interest_to_waitlist": 0.30,
        "waitlist_to_cart": 0.40,
        "cart_to_purchase": 0.15,
    },
    "membership": {
        "awareness_to_interest": 0.07,
        "interest_to_waitlist": 0.20,
        "waitlist_to_cart": 0.30,
        "cart_to_purchase": 0.18,
    },
    "workshop": {
        "awareness_to_interest": 0.12,
        "interest_to_waitlist": 0.35,
        "waitlist_to_cart": 0.45,
        "cart_to_purchase": 0.20,
    },
}

_SEASONAL_SCORES: dict[int, float] = {
    1: 0.95,   # Jan — new-year motivation
    2: 0.80,
    3: 0.75,
    4: 0.70,
    5: 0.65,
    6: 0.60,   # summer slump starts
    7: 0.55,
    8: 0.60,
    9: 0.85,   # back-to-school energy
    10: 0.90,
    11: 0.80,  # pre-holiday noise
    12: 0.50,  # holiday distraction
}


def _audience_quality_multiplier(engagement_rate: float) -> float:
    """Engagement rate adjusts baseline conversion rates."""
    if engagement_rate >= 0.10:
        return 1.4
    if engagement_rate >= 0.06:
        return 1.2
    if engagement_rate >= 0.03:
        return 1.0
    if engagement_rate >= 0.01:
        return 0.75
    return 0.5


def _price_conversion_dampener(price: float) -> float:
    """Higher price = lower conversion, following a log decay curve."""
    if price <= 50:
        return 1.3
    if price <= 200:
        return 1.0
    if price <= 500:
        return 0.80
    if price <= 1000:
        return 0.60
    if price <= 2000:
        return 0.45
    return max(0.25, 0.45 - (price - 2000) / 20000)


def _email_list_boost(email_list_size: int, audience_size: int) -> float:
    """Larger email list relative to audience amplifies launch."""
    ratio = _safe_div(email_list_size, audience_size, 0.0)
    if ratio >= 0.3:
        return 1.25
    if ratio >= 0.15:
        return 1.10
    if ratio >= 0.05:
        return 1.0
    return 0.80


def plan_product_launch(
    product_type: str,
    target_price: float,
    audience_size: int,
    audience_engagement_rate: float,
    email_list_size: int,
    existing_products: list[dict],
    niche: str,
    creation_cost: float = 0,
) -> LaunchPlan:
    """Create a data-driven product launch plan."""
    base_rates = _BASE_CONVERSION_RATES.get(product_type, _BASE_CONVERSION_RATES["course"])
    quality_mult = _audience_quality_multiplier(audience_engagement_rate)
    price_mult = _price_conversion_dampener(target_price)
    email_mult = _email_list_boost(email_list_size, max(audience_size, 1))

    combined_mult = quality_mult * price_mult * email_mult

    adjusted_rates = {k: min(v * combined_mult, 0.95) for k, v in base_rates.items()}

    # -- funnel math --
    awareness_reach = audience_size + email_list_size
    interested = int(awareness_reach * adjusted_rates["awareness_to_interest"])
    waitlisted = int(interested * adjusted_rates["interest_to_waitlist"])
    cart_viewers = int(waitlisted * adjusted_rates["waitlist_to_cart"])
    purchasers = int(cart_viewers * adjusted_rates["cart_to_purchase"])
    purchasers = max(purchasers, 0)

    total_expected_revenue = round(purchasers * target_price, 2)
    break_even_signups = max(math.ceil(_safe_div(creation_cost, target_price, 0)), 1)

    marketing_budget = _recommended_marketing_budget(
        target_price, purchasers, audience_size, email_list_size
    )

    # -- launch phases --
    pre_launch_signups = int(waitlisted * 0.6)
    cart_open_signups = int(purchasers * 0.55)
    cart_close_signups = int(purchasers * 0.35)
    post_launch_signups = int(purchasers * 0.10)

    launch_phases = [
        {
            "phase": "pre_launch",
            "duration_days": 21,
            "actions": [
                "Release teaser content series (3-5 posts)",
                "Open waitlist with lead magnet incentive",
                "Run early-bird pricing survey",
                "Share behind-the-scenes creation updates",
                "Launch countdown content sequence",
                "Host free mini-workshop or AMA",
            ],
            "expected_signups": pre_launch_signups,
            "conversion_target": round(adjusted_rates["interest_to_waitlist"], 4),
        },
        {
            "phase": "cart_open",
            "duration_days": 7,
            "actions": [
                "Send launch announcement email (Day 1)",
                "Publish case study or transformation story (Day 2)",
                "Run live Q&A or demo session (Day 3)",
                "Share social proof and testimonials (Day 4-5)",
                "Send urgency email — bonuses expiring (Day 6)",
                "Release bonus stack for early buyers (Day 1-3)",
            ],
            "expected_signups": cart_open_signups,
            "conversion_target": round(adjusted_rates["cart_to_purchase"], 4),
        },
        {
            "phase": "cart_close",
            "duration_days": 3,
            "actions": [
                "Send 48-hour deadline email",
                "Publish FAQ content addressing objections",
                "Final testimonial push on social",
                "Send last-chance email (Day 3, morning)",
                "Final cart-closing email (Day 3, evening)",
            ],
            "expected_signups": cart_close_signups,
            "conversion_target": round(adjusted_rates["cart_to_purchase"] * 1.3, 4),
        },
        {
            "phase": "post_launch",
            "duration_days": 14,
            "actions": [
                "Send welcome and onboarding sequence",
                "Collect feedback survey (Day 3)",
                "Offer referral incentive program",
                "Downsell non-buyers a lower-tier option",
                "Begin evergreen funnel setup",
                "Analyze full launch data and document learnings",
            ],
            "expected_signups": post_launch_signups,
            "conversion_target": 0.0,
        },
    ]

    conversion_funnel = {
        "awareness_reach": awareness_reach,
        "interested": interested,
        "waitlisted": waitlisted,
        "cart_viewers": cart_viewers,
        "purchasers": purchasers,
        "rates": adjusted_rates,
    }

    risk_factors = _identify_launch_risks(
        target_price, audience_size, email_list_size,
        audience_engagement_rate, existing_products, purchasers, creation_cost,
    )
    mitigation_strategies = _mitigation_for_risks(risk_factors)

    product_name = f"{niche.title()} {product_type.replace('_', ' ').title()}"

    return LaunchPlan(
        product_name=product_name,
        product_type=product_type,
        price_point=target_price,
        launch_phases=launch_phases,
        total_expected_revenue=total_expected_revenue,
        total_expected_signups=purchasers,
        break_even_signups=break_even_signups,
        marketing_budget_recommended=round(marketing_budget, 2),
        conversion_funnel=conversion_funnel,
        risk_factors=risk_factors,
        mitigation_strategies=mitigation_strategies,
    )


def _recommended_marketing_budget(
    price: float, expected_sales: int, audience_size: int, email_list_size: int,
) -> float:
    expected_rev = price * expected_sales
    base_pct = 0.15 if email_list_size > audience_size * 0.15 else 0.25
    return max(expected_rev * base_pct, 100.0)


def _identify_launch_risks(
    price: float,
    audience_size: int,
    email_list_size: int,
    engagement_rate: float,
    existing_products: list[dict],
    expected_purchases: int,
    creation_cost: float,
) -> list[str]:
    risks: list[str] = []
    if audience_size == 0:
        risks.append("no_audience: build audience before launching high-ticket")
    if email_list_size == 0:
        risks.append("no_email_list: build email list to support direct launch")
    if engagement_rate < 0.02:
        risks.append("low_engagement: audience may not be warmed up enough")
    if price > 1000 and not existing_products:
        risks.append("high_price_no_track_record: no prior products to build trust for premium pricing")
    if expected_purchases < 10:
        risks.append("low_volume_forecast: fewer than 10 expected sales — consider lowering price or growing audience first")
    if creation_cost > 0 and expected_purchases * price < creation_cost:
        risks.append("negative_roi_risk: expected revenue does not cover creation cost on first launch")

    recent_launches = [
        p for p in existing_products
        if p.get("launch_date") and _is_recent_launch(p["launch_date"])
    ]
    if len(recent_launches) >= 2:
        risks.append("launch_fatigue: multiple recent launches may tire your audience")

    return risks


def _is_recent_launch(launch_date: str | datetime) -> bool:
    if isinstance(launch_date, str):
        try:
            launch_date = datetime.fromisoformat(launch_date)
        except (ValueError, TypeError):
            return False
    return (datetime.utcnow() - launch_date).days < 90


def _mitigation_for_risks(risks: list[str]) -> list[str]:
    mitigations: list[str] = []
    mapping = {
        "small_audience": "Run a 30-day content blitz to grow audience before launch; partner with creators in adjacent niches.",
        "small_email_list": "Create a high-value lead magnet and run a 2-week list-building campaign before launch.",
        "low_engagement": "Run a free 5-day challenge or mini-course to re-engage audience before pitching.",
        "high_price_no_track_record": "Launch a lower-priced product first ($47-197) to build trust, then upsell.",
        "low_volume_forecast": "Consider a beta launch at reduced price to build testimonials, then relaunch at full price.",
        "negative_roi_risk": "Reduce creation cost by using an MVP approach; validate demand with pre-sales before full build.",
        "launch_fatigue": "Space launches at least 8 weeks apart; use an evergreen funnel for existing products.",
    }
    for risk in risks:
        key = risk.split(":")[0]
        if key in mapping:
            mitigations.append(mapping[key])
    return mitigations


def find_optimal_launch_window(
    audience_engagement_history: list[dict],
    competitor_launches: list[dict],
    product_type: str,
) -> LaunchWindow:
    """Pick the best 2-week window in the next 90 days for a launch."""
    now = datetime.utcnow()
    candidates: list[dict] = []

    for offset_weeks in range(0, 13):
        candidate_date = now + timedelta(weeks=offset_weeks)
        month = candidate_date.month

        seasonal = _SEASONAL_SCORES.get(month, 0.7)

        competition = _competition_window_score(candidate_date, competitor_launches)

        readiness = _audience_readiness_score(candidate_date, audience_engagement_history)

        composite = seasonal * 0.3 + competition * 0.35 + readiness * 0.35

        candidates.append({
            "date": candidate_date.strftime("%Y-%m-%d"),
            "seasonal": seasonal,
            "competition": competition,
            "readiness": readiness,
            "composite": composite,
        })

    best = max(candidates, key=lambda c: c["composite"])

    reasons: list[str] = []
    if best["seasonal"] >= 0.80:
        reasons.append("strong seasonal window")
    if best["competition"] >= 0.80:
        reasons.append("low competitor noise")
    if best["readiness"] >= 0.80:
        reasons.append("audience engagement trending up")
    reasoning = "; ".join(reasons) if reasons else "best composite score among available windows"

    return LaunchWindow(
        recommended_date=best["date"],
        audience_readiness_score=round(best["readiness"], 3),
        competition_window_score=round(best["competition"], 3),
        seasonal_score=round(best["seasonal"], 3),
        composite_score=round(best["composite"], 3),
        reasoning=reasoning,
    )


def _competition_window_score(target: datetime, competitor_launches: list[dict]) -> float:
    """Score 0-1 — higher when no competitor launches are nearby."""
    if not competitor_launches:
        return 0.90
    min_gap = float("inf")
    for cl in competitor_launches:
        launch_str = cl.get("date", cl.get("launch_date", ""))
        try:
            ld = datetime.fromisoformat(launch_str) if isinstance(launch_str, str) else launch_str
            gap = abs((target - ld).days)
            min_gap = min(min_gap, gap)
        except (ValueError, TypeError, AttributeError):
            continue
    if min_gap == float("inf"):
        return 0.90
    if min_gap >= 30:
        return 0.95
    if min_gap >= 14:
        return 0.75
    if min_gap >= 7:
        return 0.50
    return 0.25


def _audience_readiness_score(target: datetime, history: list[dict]) -> float:
    """Score 0-1 based on engagement trend leading up to target date."""
    if not history:
        return 0.65
    recent = sorted(history, key=lambda h: h.get("date", ""), reverse=True)[:8]
    rates = [h.get("engagement_rate", 0.03) for h in recent]
    if len(rates) < 2:
        return 0.65
    trend = (rates[0] - rates[-1]) / max(rates[-1], 0.001)
    if trend > 0.15:
        return 0.90
    if trend > 0.05:
        return 0.75
    if trend > -0.05:
        return 0.60
    return 0.40


# ---------------------------------------------------------------------------
# 3. Consulting Pipeline Optimizer
# ---------------------------------------------------------------------------

_MARKET_MULTIPLIERS: dict[str, float] = {
    "startup": 0.8,
    "smb": 1.0,
    "enterprise": 1.6,
}

_TIER_CONFIGS: list[dict] = [
    {
        "tier": "discovery",
        "name_suffix": "Discovery Audit",
        "hours_pct": 0.05,
        "price_mult": 0.4,
        "close_rate": 0.45,
        "ltv_mult": 3.0,
        "upsell_to": "standard",
        "deliverables_template": [
            "60-minute deep-dive diagnostic call",
            "Written audit report with findings",
            "Priority action roadmap (top 3 quick wins)",
        ],
    },
    {
        "tier": "standard",
        "name_suffix": "Growth Engagement",
        "hours_pct": 0.30,
        "price_mult": 1.0,
        "close_rate": 0.30,
        "ltv_mult": 2.0,
        "upsell_to": "premium",
        "deliverables_template": [
            "Weekly strategy sessions",
            "Custom implementation plan",
            "Hands-on execution support",
            "Bi-weekly progress reports",
            "Email/Slack access for async questions",
        ],
    },
    {
        "tier": "premium",
        "name_suffix": "Strategic Partnership",
        "hours_pct": 0.50,
        "price_mult": 2.5,
        "close_rate": 0.18,
        "ltv_mult": 1.5,
        "upsell_to": "retainer",
        "deliverables_template": [
            "Dedicated weekly working sessions",
            "Full strategy development and execution",
            "Team training and knowledge transfer",
            "Monthly executive briefings",
            "Priority support with 4-hour SLA",
            "Quarterly business review",
        ],
    },
    {
        "tier": "retainer",
        "name_suffix": "Ongoing Retainer",
        "hours_pct": 0.25,
        "price_mult": 1.8,
        "close_rate": 0.20,
        "ltv_mult": 6.0,
        "upsell_to": None,
        "deliverables_template": [
            "Monthly strategy session",
            "On-call advisory hours",
            "Quarterly deep-dive reviews",
            "Priority access for urgent needs",
            "Annual planning workshop",
        ],
    },
]


def design_consulting_packages(
    hourly_rate: float,
    expertise_areas: list[str],
    target_market: str,
    max_hours_per_month: int,
) -> list[ConsultingPackage]:
    """Design a tiered consulting package ladder optimized for revenue."""
    market_mult = _MARKET_MULTIPLIERS.get(target_market, 1.0)
    effective_rate = hourly_rate * market_mult
    expertise_label = " & ".join(expertise_areas[:2]) if expertise_areas else "Strategy"

    packages: list[ConsultingPackage] = []
    for cfg in _TIER_CONFIGS:
        hours = max(int(max_hours_per_month * cfg["hours_pct"]), 1)
        base_price = effective_rate * hours * cfg["price_mult"]

        base_price = _round_to_attractive_price(base_price)

        deliverables = list(cfg["deliverables_template"])
        if expertise_areas:
            deliverables.insert(0, f"Focus areas: {', '.join(expertise_areas)}")

        ideal_profile = _ideal_client_for_tier(cfg["tier"], target_market, expertise_areas)

        ltv = base_price * cfg["ltv_mult"]

        packages.append(ConsultingPackage(
            name=f"{expertise_label} — {cfg['name_suffix']}",
            tier=cfg["tier"],
            price=base_price,
            hours_included=hours,
            deliverables=deliverables,
            ideal_client_profile=ideal_profile,
            avg_close_rate=cfg["close_rate"],
            avg_ltv=round(ltv, 2),
            upsell_path=cfg["upsell_to"],
        ))

    return packages


def _round_to_attractive_price(price: float) -> float:
    """Round to psychologically appealing price points."""
    if price < 500:
        return math.ceil(price / 50) * 50 - 3
    if price < 2000:
        return math.ceil(price / 100) * 100 - 3
    if price < 10000:
        return math.ceil(price / 500) * 500 - 3
    return math.ceil(price / 1000) * 1000 - 3


def _ideal_client_for_tier(tier: str, market: str, expertise: list[str]) -> str:
    profiles = {
        "discovery": f"{market.upper()} businesses exploring {expertise[0] if expertise else 'strategy'} improvements, budget-conscious, need proof of value before committing.",
        "standard": f"{market.upper()} companies ready to invest in {expertise[0] if expertise else 'growth'}, have internal team to execute with guidance.",
        "premium": f"{market.upper()} organizations needing end-to-end {expertise[0] if expertise else 'transformation'}, willing to invest for comprehensive results.",
        "retainer": f"{market.upper()} clients who've seen results and want ongoing advisory to maintain momentum.",
    }
    return profiles.get(tier, f"{market.upper()} businesses seeking expert consulting.")


def optimize_consulting_utilization(
    packages: list[ConsultingPackage],
    current_clients: list[dict],
    max_hours_per_month: int,
    target_monthly_revenue: float,
) -> dict:
    """Optimize consulting utilization to maximize revenue per hour."""
    total_hours_used = sum(c.get("hours_used", 0) for c in current_clients)
    total_hours_allocated = sum(c.get("hours_remaining", 0) + c.get("hours_used", 0) for c in current_clients)
    current_monthly_revenue = sum(c.get("monthly_revenue", 0) for c in current_clients)

    utilization_rate = _safe_div(total_hours_used, max_hours_per_month, 0.0)
    revenue_per_hour = _safe_div(current_monthly_revenue, max(total_hours_used, 1), 0.0)
    capacity_hours = max(max_hours_per_month - total_hours_allocated, 0)

    revenue_gap = max(target_monthly_revenue - current_monthly_revenue, 0)

    # --- package performance analysis ---
    package_map = {p.tier: p for p in packages}
    client_by_tier: dict[str, list[dict]] = defaultdict(list)
    for c in current_clients:
        client_by_tier[c.get("package", "standard")].append(c)

    tier_analysis: list[dict] = []
    for pkg in packages:
        tier_clients = client_by_tier.get(pkg.tier, [])
        tier_hours = sum(c.get("hours_used", 0) for c in tier_clients)
        tier_revenue = sum(c.get("monthly_revenue", 0) for c in tier_clients)
        tier_rph = _safe_div(tier_revenue, max(tier_hours, 1), 0.0)
        tier_analysis.append({
            "tier": pkg.tier,
            "clients": len(tier_clients),
            "hours_used": tier_hours,
            "revenue": tier_revenue,
            "revenue_per_hour": round(tier_rph, 2),
            "package_price": pkg.price,
        })

    tier_analysis.sort(key=lambda t: t["revenue_per_hour"], reverse=True)

    # --- recommended mix changes ---
    recommendations: list[str] = []
    if utilization_rate < 0.6:
        recommendations.append(
            f"Utilization at {utilization_rate:.0%} — aggressively fill capacity. "
            f"You have {capacity_hours}h available."
        )
    elif utilization_rate > 0.9:
        recommendations.append(
            "Near full capacity — raise rates by 15-25% for new clients or prioritize higher-tier packages."
        )

    if tier_analysis:
        best_tier = tier_analysis[0]["tier"]
        worst_tier = tier_analysis[-1]["tier"] if len(tier_analysis) > 1 else None
        if worst_tier and tier_analysis[-1]["revenue_per_hour"] < revenue_per_hour * 0.6:
            recommendations.append(
                f"Consider phasing out {worst_tier} tier (${tier_analysis[-1]['revenue_per_hour']:.0f}/hr) "
                f"in favor of {best_tier} (${tier_analysis[0]['revenue_per_hour']:.0f}/hr)."
            )

    if revenue_gap > 0 and capacity_hours > 0:
        best_pkg = package_map.get(
            tier_analysis[0]["tier"] if tier_analysis else "standard"
        )
        if best_pkg:
            clients_needed = math.ceil(revenue_gap / best_pkg.price)
            recommendations.append(
                f"To close ${revenue_gap:,.0f} gap: add {clients_needed} "
                f"{best_pkg.tier}-tier client(s) at ${best_pkg.price:,.0f}/mo."
            )

    # --- capacity plan ---
    new_client_slots: list[dict] = []
    remaining_capacity = capacity_hours
    for ta in tier_analysis:
        pkg = package_map.get(ta["tier"])
        if pkg and remaining_capacity >= pkg.hours_included:
            slots = remaining_capacity // pkg.hours_included
            new_client_slots.append({
                "tier": pkg.tier,
                "max_new_clients": slots,
                "potential_monthly_revenue": slots * pkg.price,
                "hours_per_client": pkg.hours_included,
            })
            remaining_capacity -= slots * pkg.hours_included

    return {
        "utilization_rate": round(utilization_rate, 4),
        "revenue_per_hour": round(revenue_per_hour, 2),
        "current_monthly_revenue": round(current_monthly_revenue, 2),
        "target_monthly_revenue": round(target_monthly_revenue, 2),
        "revenue_gap": round(revenue_gap, 2),
        "capacity_hours_available": capacity_hours,
        "tier_analysis": tier_analysis,
        "recommendations": recommendations,
        "new_client_slots": new_client_slots,
        "projected_max_revenue": round(
            current_monthly_revenue + sum(s["potential_monthly_revenue"] for s in new_client_slots),
            2,
        ),
    }


# ---------------------------------------------------------------------------
# 4. Webinar/VSL Funnel Optimizer
# ---------------------------------------------------------------------------

_DEFAULT_BENCHMARKS: dict[str, dict[str, float]] = {
    "webinar": {
        "show_up_rate": 0.35,
        "engagement_rate": 0.65,
        "offer_conversion_rate": 0.10,
        "revenue_per_registrant": 50.0,
        "cost_per_registrant": 8.0,
    },
    "vsl": {
        "show_up_rate": 0.70,
        "engagement_rate": 0.50,
        "offer_conversion_rate": 0.03,
        "revenue_per_registrant": 25.0,
        "cost_per_registrant": 5.0,
    },
}

_LIFT_ESTIMATES: dict[str, float] = {
    "show_up": 0.25,
    "engagement": 0.20,
    "conversion": 0.30,
    "aov": 0.20,
}

_FIX_PLAYBOOKS: dict[str, list[str]] = {
    "show_up": [
        "Add SMS reminder sequence (24hr, 1hr, 5min before)",
        "Send pre-event value content to build anticipation",
        "Offer a bonus for live attendance (not available on replay)",
        "Change event time — test different days and time slots",
    ],
    "engagement": [
        "Restructure first 10 minutes with a pattern interrupt or bold claim",
        "Add live polls and Q&A to increase participation",
        "Shorten presentation to 45-60 min (cut fluff)",
        "Use more stories and case studies, fewer slides",
    ],
    "conversion": [
        "Strengthen the offer stack — add bonuses that remove objections",
        "Add a risk reversal (money-back guarantee, performance guarantee)",
        "Use urgency and scarcity (limited seats, deadline bonuses)",
        "Add social proof during the pitch (testimonials, results)",
        "Test a lower entry price with payment plan option",
    ],
    "aov": [
        "Introduce order bump (add-on at 30-50% of main offer price)",
        "Offer premium tier with extra support or access",
        "Create payment plan that totals more than pay-in-full",
        "Add 1-on-1 implementation upsell post-purchase",
    ],
}


def analyze_funnel(
    registrations: int,
    attendees: int,
    stayed_to_offer: int,
    purchases: int,
    total_revenue: float,
    ad_spend: float = 0,
    industry_benchmarks: dict | None = None,
) -> FunnelOptimization:
    """Analyze a webinar/VSL funnel and identify the highest-leverage optimization."""
    registrations = max(registrations, 1)
    attendees = max(attendees, 0)
    stayed_to_offer = max(stayed_to_offer, 0)
    purchases = max(purchases, 0)

    show_up_rate = _safe_div(attendees, registrations, 0.0)
    engagement_rate = _safe_div(stayed_to_offer, max(attendees, 1), 0.0)
    offer_conversion_rate = _safe_div(purchases, max(stayed_to_offer, 1), 0.0)
    avg_order_value = _safe_div(total_revenue, max(purchases, 1), 0.0)
    revenue_per_registrant = _safe_div(total_revenue, registrations, 0.0)
    cost_per_registrant = _safe_div(ad_spend, registrations, 0.0)
    roas = _safe_div(total_revenue, max(ad_spend, 0.01), 0.0)

    funnel_efficiency = _compute_funnel_efficiency(
        show_up_rate, engagement_rate, offer_conversion_rate, roas
    )

    current = FunnelMetrics(
        registrations=registrations,
        show_up_rate=round(show_up_rate, 4),
        engagement_rate=round(engagement_rate, 4),
        offer_conversion_rate=round(offer_conversion_rate, 4),
        avg_order_value=round(avg_order_value, 2),
        revenue_per_registrant=round(revenue_per_registrant, 2),
        cost_per_registrant=round(cost_per_registrant, 2),
        roas=round(roas, 2),
        funnel_efficiency_score=round(funnel_efficiency, 1),
    )

    bench = industry_benchmarks or _DEFAULT_BENCHMARKS["webinar"]

    # --- identify bottleneck: area with worst gap vs benchmark ---
    gaps = {
        "show_up": _safe_div(
            bench.get("show_up_rate", 0.35) - show_up_rate,
            bench.get("show_up_rate", 0.35),
            0.0,
        ),
        "engagement": _safe_div(
            bench.get("engagement_rate", 0.65) - engagement_rate,
            bench.get("engagement_rate", 0.65),
            0.0,
        ),
        "conversion": _safe_div(
            bench.get("offer_conversion_rate", 0.10) - offer_conversion_rate,
            bench.get("offer_conversion_rate", 0.10),
            0.0,
        ),
        "aov": _safe_div(
            bench.get("revenue_per_registrant", 50.0) - revenue_per_registrant,
            bench.get("revenue_per_registrant", 50.0),
            0.0,
        ),
    }
    bottleneck = max(gaps, key=lambda k: gaps[k])

    # --- build recommendations ---
    recommendations: list[dict] = []
    for area, gap_pct in sorted(gaps.items(), key=lambda x: x[1], reverse=True):
        if gap_pct <= 0:
            continue
        bench_key_map = {
            "show_up": ("show_up_rate", show_up_rate),
            "engagement": ("engagement_rate", engagement_rate),
            "conversion": ("offer_conversion_rate", offer_conversion_rate),
            "aov": ("revenue_per_registrant", revenue_per_registrant),
        }
        bk, current_val = bench_key_map[area]
        bench_val = bench.get(bk, 0)
        lift = _LIFT_ESTIMATES.get(area, 0.15)
        fixes = _FIX_PLAYBOOKS.get(area, [])
        recommendations.append({
            "area": area,
            "current": round(current_val, 4),
            "benchmark": round(bench_val, 4),
            "gap_pct": round(gap_pct, 4),
            "fix": fixes,
            "expected_lift": round(lift, 4),
        })

    # --- project metrics after fixing the bottleneck ---
    projected = _project_fixed_metrics(
        current, bottleneck, bench, registrations, ad_spend
    )

    improvement_potential = max(projected.revenue_per_registrant * registrations - total_revenue, 0)

    return FunnelOptimization(
        current_metrics=current,
        bottleneck=bottleneck,
        improvement_potential=round(improvement_potential, 2),
        recommendations=recommendations,
        projected_metrics_after_fix=projected,
    )


def _compute_funnel_efficiency(
    show_up: float, engagement: float, conversion: float, roas: float,
) -> float:
    """Composite funnel efficiency score 0-100."""
    show_up_score = min(show_up / 0.45, 1.0) * 25
    engagement_score = min(engagement / 0.75, 1.0) * 25
    conversion_score = min(conversion / 0.12, 1.0) * 25
    roas_score = min(roas / 5.0, 1.0) * 25 if roas > 0 else 12.5
    return _clamp(show_up_score + engagement_score + conversion_score + roas_score)


def _project_fixed_metrics(
    current: FunnelMetrics,
    bottleneck: str,
    bench: dict,
    registrations: int,
    ad_spend: float,
) -> FunnelMetrics:
    """Project what metrics look like if the bottleneck is fixed to benchmark level."""
    proj_show_up = current.show_up_rate
    proj_engagement = current.engagement_rate
    proj_conversion = current.offer_conversion_rate
    proj_aov = current.avg_order_value

    if bottleneck == "show_up":
        proj_show_up = max(current.show_up_rate, bench.get("show_up_rate", 0.35))
    elif bottleneck == "engagement":
        proj_engagement = max(current.engagement_rate, bench.get("engagement_rate", 0.65))
    elif bottleneck == "conversion":
        proj_conversion = max(current.offer_conversion_rate, bench.get("offer_conversion_rate", 0.10))
    elif bottleneck == "aov":
        proj_aov = current.avg_order_value * 1.25

    proj_attendees = int(registrations * proj_show_up)
    proj_stayed = int(proj_attendees * proj_engagement)
    proj_purchases = int(proj_stayed * proj_conversion)
    proj_revenue = proj_purchases * proj_aov
    proj_rpr = _safe_div(proj_revenue, registrations, 0.0)
    proj_cpr = _safe_div(ad_spend, registrations, 0.0)
    proj_roas = _safe_div(proj_revenue, max(ad_spend, 0.01), 0.0)

    proj_efficiency = _compute_funnel_efficiency(
        proj_show_up, proj_engagement, proj_conversion, proj_roas
    )

    return FunnelMetrics(
        registrations=registrations,
        show_up_rate=round(proj_show_up, 4),
        engagement_rate=round(proj_engagement, 4),
        offer_conversion_rate=round(proj_conversion, 4),
        avg_order_value=round(proj_aov, 2),
        revenue_per_registrant=round(proj_rpr, 2),
        cost_per_registrant=round(proj_cpr, 2),
        roas=round(proj_roas, 2),
        funnel_efficiency_score=round(proj_efficiency, 1),
    )


# ---------------------------------------------------------------------------
# 5. Revenue Stacking Calculator
# ---------------------------------------------------------------------------

_AVENUE_CATEGORIES: dict[str, str] = {
    "consulting": "service",
    "coaching": "service",
    "freelance": "service",
    "agency": "service",
    "course": "product",
    "digital_product": "product",
    "ebook": "product",
    "template": "product",
    "saas": "recurring",
    "membership": "recurring",
    "community": "recurring",
    "subscription": "recurring",
    "affiliate": "passive",
    "ad_revenue": "passive",
    "sponsorship": "passive",
    "licensing": "passive",
}

_NEXT_BEST_AVENUE_MAP: dict[str, list[str]] = {
    "service": ["course", "membership", "community"],
    "product": ["membership", "consulting", "community"],
    "recurring": ["course", "consulting", "affiliate"],
    "passive": ["course", "membership", "consulting"],
}


def compute_revenue_stack(
    active_avenues: list[dict],
    audience_size: int,
    content_reach_per_month: int,
) -> RevenueStack:
    """Compute the full revenue stack analysis with diversification and vulnerability scoring."""
    if not active_avenues:
        return RevenueStack(
            total_monthly_revenue=0,
            total_annual_revenue=0,
            recurring_pct=0,
            stack_layers=[],
            diversification_score=0,
            vulnerability_score=1.0,
            growth_trajectory="stalled",
            next_best_avenue="course",
            revenue_at_risk_single_point=0,
        )

    total_monthly = sum(a.get("monthly_revenue", 0) for a in active_avenues)
    total_annual = total_monthly * 12

    recurring_monthly = sum(
        a.get("monthly_revenue", 0) for a in active_avenues if a.get("is_recurring")
    )
    recurring_pct = _safe_div(recurring_monthly, total_monthly, 0.0)

    avenue_names = [a.get("avenue", "unknown") for a in active_avenues]

    # --- build stack layers with synergy detection ---
    stack_layers: list[dict] = []
    for avenue in active_avenues:
        monthly = avenue.get("monthly_revenue", 0)
        margin = avenue.get("margin", 0.7)
        growth = avenue.get("growth_rate", 0.0)

        synergies = _detect_synergies(avenue.get("avenue", ""), avenue_names)

        stack_layers.append({
            "avenue": avenue.get("avenue", "unknown"),
            "monthly": round(monthly, 2),
            "annual": round(monthly * 12, 2),
            "margin": round(margin, 4),
            "is_recurring": avenue.get("is_recurring", False),
            "growth_rate": round(growth, 4),
            "synergies": synergies,
            "pct_of_total": round(_safe_div(monthly, total_monthly, 0.0), 4),
        })

    stack_layers.sort(key=lambda s: s["monthly"], reverse=True)

    # --- diversification score (Herfindahl-Hirschman inversion) ---
    shares = [_safe_div(a.get("monthly_revenue", 0), total_monthly, 0.0) for a in active_avenues]
    hhi = sum(s ** 2 for s in shares)
    diversification = _clamp(1 - hhi, 0, 1)

    # --- vulnerability score ---
    max_share = max(shares) if shares else 1.0
    vulnerability = _compute_vulnerability(max_share, len(active_avenues), recurring_pct)

    revenue_at_risk = max_share * total_monthly

    # --- growth trajectory ---
    [a.get("growth_rate", 0.0) for a in active_avenues]
    weighted_growth = sum(
        a.get("growth_rate", 0.0) * _safe_div(a.get("monthly_revenue", 0), total_monthly, 0.0)
        for a in active_avenues
    )
    growth_trajectory = _classify_growth(weighted_growth)

    # --- next best avenue ---
    next_best = _suggest_next_avenue(active_avenues, audience_size, content_reach_per_month)

    return RevenueStack(
        total_monthly_revenue=round(total_monthly, 2),
        total_annual_revenue=round(total_annual, 2),
        recurring_pct=round(recurring_pct, 4),
        stack_layers=stack_layers,
        diversification_score=round(diversification, 4),
        vulnerability_score=round(vulnerability, 4),
        growth_trajectory=growth_trajectory,
        next_best_avenue=next_best,
        revenue_at_risk_single_point=round(revenue_at_risk, 2),
    )


def _detect_synergies(avenue_name: str, all_names: list[str]) -> list[dict]:
    """Find synergy multipliers between this avenue and others in the stack."""
    synergies: list[dict] = []
    for other in all_names:
        if other == avenue_name:
            continue
        key = (avenue_name.lower(), other.lower())
        mult = _SYNERGY_MAP.get(key)
        if mult:
            synergies.append({
                "paired_with": other,
                "multiplier": mult,
                "description": _synergy_description(avenue_name, other, mult),
            })
    return synergies


def _synergy_description(a: str, b: str, mult: float) -> str:
    descriptions = {
        ("saas", "community"): "Community reduces SaaS churn through peer support and accountability",
        ("community", "saas"): "SaaS tool drives community engagement and retention",
        ("course", "consulting"): "Course graduates become warm consulting leads",
        ("consulting", "course"): "Consulting insights fuel course content and credibility",
        ("content", "affiliate"): "More content surfaces more affiliate conversion opportunities",
        ("affiliate", "content"): "Affiliate revenue funds more content creation",
        ("membership", "course"): "Membership provides ongoing access; courses drive upgrades",
        ("course", "membership"): "Course completers convert to long-term members",
        ("coaching", "course"): "Coaching clients validate and improve course material",
        ("course", "coaching"): "Course students upgrade to coaching for deeper support",
        ("service", "saas"): "Service delivery insights shape SaaS product features",
        ("saas", "service"): "SaaS users become service clients for custom implementation",
        ("consulting", "community"): "Community nurtures consulting pipeline with trust",
        ("community", "consulting"): "Consulting expertise adds value to community",
    }
    key = (a.lower(), b.lower())
    return descriptions.get(key, f"{a} and {b} create a {mult:.0%} synergy multiplier")


def _compute_vulnerability(max_share: float, num_avenues: int, recurring_pct: float) -> float:
    """0-1 vulnerability where lower is better."""
    concentration_risk = max_share
    diversification_protection = min(num_avenues / 5, 1.0) * 0.3
    recurring_protection = recurring_pct * 0.2

    raw = concentration_risk - diversification_protection - recurring_protection
    return _clamp(raw, 0, 1)


def _classify_growth(weighted_rate: float) -> str:
    if weighted_rate >= 0.20:
        return "hypergrowth"
    if weighted_rate >= 0.10:
        return "strong_growth"
    if weighted_rate >= 0.03:
        return "moderate_growth"
    if weighted_rate >= -0.02:
        return "stable"
    if weighted_rate >= -0.10:
        return "declining"
    return "stalled"


def _suggest_next_avenue(
    active: list[dict], audience_size: int, content_reach: int,
) -> str:
    """Suggest the next revenue avenue to add based on gaps and audience."""
    existing = {a.get("avenue", "").lower() for a in active}

    existing_categories = set()
    for av in existing:
        cat = _AVENUE_CATEGORIES.get(av, "other")
        existing_categories.add(cat)

    candidates: list[tuple[str, float]] = []

    if "product" not in existing_categories:
        if audience_size >= 5000:
            candidates.append(("course", 0.9))
        else:
            candidates.append(("digital_product", 0.8))

    if "recurring" not in existing_categories:
        if audience_size >= 2000:
            candidates.append(("membership", 0.85))
        else:
            candidates.append(("community", 0.7))

    if "passive" not in existing_categories and content_reach >= 10000:
        candidates.append(("affiliate", 0.75))

    if "service" not in existing_categories:
        candidates.append(("consulting", 0.65))

    for cat, suggestions in _NEXT_BEST_AVENUE_MAP.items():
        if cat in existing_categories:
            for sug in suggestions:
                if sug not in existing:
                    candidates.append((sug, 0.5))
                    break

    if not candidates:
        if "course" not in existing:
            return "course"
        if "membership" not in existing:
            return "membership"
        return "consulting"

    candidates.sort(key=lambda c: c[1], reverse=True)
    return candidates[0][0]


# ---------------------------------------------------------------------------
# 6. Convenience / orchestration helpers
# ---------------------------------------------------------------------------

def score_all_deals(deals: list[Deal], avg_cycle_days: float = 45) -> list[Deal]:
    """Score every deal in-place and return sorted by score descending."""
    for d in deals:
        d.score = score_deal(d, avg_cycle_days)
    return sorted(deals, key=lambda d: d.score, reverse=True)


def pipeline_summary_text(analysis: PipelineAnalysis) -> str:
    """Human-readable pipeline summary for dashboards or notifications."""
    lines = [
        f"Pipeline: ${analysis.total_pipeline_value:,.0f} total | ${analysis.weighted_pipeline_value:,.0f} weighted",
        f"Velocity: ${analysis.velocity:,.0f}/day | Win rate: {analysis.win_rate:.0%}",
        f"Avg deal: ${analysis.avg_deal_size:,.0f} | Avg cycle: {analysis.avg_days_to_close:.0f} days",
        f"Health: {analysis.health_score:.0f}/100",
        f"Bottleneck: {analysis.bottleneck_stage} (severity {analysis.bottleneck_severity:.0%})",
        f"Forecast: ${analysis.forecast_30d:,.0f} (30d) | ${analysis.forecast_90d:,.0f} (90d)",
    ]
    return "\n".join(lines)


def funnel_summary_text(opt: FunnelOptimization) -> str:
    """Human-readable funnel optimization summary."""
    m = opt.current_metrics
    lines = [
        f"Registrations: {m.registrations} | Show-up: {m.show_up_rate:.0%} | Engagement: {m.engagement_rate:.0%}",
        f"Conversion: {m.offer_conversion_rate:.0%} | AOV: ${m.avg_order_value:,.0f}",
        f"Revenue/reg: ${m.revenue_per_registrant:.2f} | ROAS: {m.roas:.1f}x",
        f"Efficiency: {m.funnel_efficiency_score:.0f}/100",
        f"Bottleneck: {opt.bottleneck} | Improvement potential: ${opt.improvement_potential:,.0f}",
    ]
    return "\n".join(lines)


def revenue_stack_summary_text(stack: RevenueStack) -> str:
    """Human-readable revenue stack summary."""
    lines = [
        f"Monthly: ${stack.total_monthly_revenue:,.0f} | Annual: ${stack.total_annual_revenue:,.0f}",
        f"Recurring: {stack.recurring_pct:.0%} | Diversification: {stack.diversification_score:.2f}",
        f"Vulnerability: {stack.vulnerability_score:.2f} | Growth: {stack.growth_trajectory}",
        f"At-risk (single point): ${stack.revenue_at_risk_single_point:,.0f}",
        f"Next best avenue: {stack.next_best_avenue}",
    ]
    for layer in stack.stack_layers:
        syn = f" [synergies: {len(layer['synergies'])}]" if layer["synergies"] else ""
        lines.append(
            f"  {layer['avenue']}: ${layer['monthly']:,.0f}/mo "
            f"({layer['pct_of_total']:.0%}) margin={layer['margin']:.0%}{syn}"
        )
    return "\n".join(lines)
