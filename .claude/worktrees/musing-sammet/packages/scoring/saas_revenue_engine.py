"""SaaS / Subscription Revenue Intelligence Engine.

Computes every SaaS metric that matters — MRR, NRR, churn prediction,
expansion scoring, pricing elasticity, cohort analysis, and revenue-stream
prioritisation — from raw subscription data using only the Python stdlib.

All functions are pure/deterministic. No DB access, no numpy, no sklearn.
Uses: math, statistics, collections, dataclasses, datetime, itertools.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _parse_date(d: str | datetime | None) -> Optional[datetime]:
    if d is None:
        return None
    if isinstance(d, datetime):
        return d
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(d, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {d}")


def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid."""
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    return num / den if den else default


def _mean(vals: list[float], default: float = 0.0) -> float:
    return statistics.mean(vals) if vals else default


def _linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """OLS slope, intercept, R². len(xs) must equal len(ys) >= 2."""
    n = len(xs)
    if n < 2:
        return 0.0, (_mean(ys),), 0.0  # type: ignore[return-value]
    x_bar = statistics.mean(xs)
    y_bar = statistics.mean(ys)
    ss_xy = sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, ys))
    ss_xx = sum((x - x_bar) ** 2 for x in xs)
    if ss_xx == 0:
        return 0.0, y_bar, 0.0
    slope = ss_xy / ss_xx
    intercept = y_bar - slope * x_bar
    ss_yy = sum((y - y_bar) ** 2 for y in ys)
    r_sq = (ss_xy ** 2) / (ss_xx * ss_yy) if ss_yy else 0.0
    return slope, intercept, r_sq


def _months_between(start: datetime, end: datetime) -> float:
    return (end - start).days / 30.44


# ══════════════════════════════════════════════════════════════════════════════
# 1. SaaS METRICS CALCULATOR
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SaaSMetrics:
    mrr: float = 0.0
    arr: float = 0.0
    net_new_mrr: float = 0.0
    new_mrr: float = 0.0
    expansion_mrr: float = 0.0
    churned_mrr: float = 0.0
    contraction_mrr: float = 0.0
    reactivation_mrr: float = 0.0
    gross_churn_rate: float = 0.0
    net_churn_rate: float = 0.0
    net_revenue_retention: float = 0.0
    ltv: float = 0.0
    cac: float = 0.0
    ltv_cac_ratio: float = 0.0
    payback_months: float = 0.0
    arpu: float = 0.0
    arppu: float = 0.0
    quick_ratio: float = 0.0
    magic_number: float = 0.0
    burn_multiple: float = 0.0
    rule_of_40_score: float = 0.0
    total_customers: int = 0
    paying_customers: int = 0


def compute_saas_metrics(
    subscriptions: list[dict],
    period_start: str,
    period_end: str,
    prior_period_sales_spend: float = 0.0,
    total_costs: float = 0.0,
) -> SaaSMetrics:
    """Compute every SaaS metric from raw subscription records.

    Each subscription dict should have at minimum:
        customer_id, plan, mrr, status, start_date
    Optional: cancel_date, previous_mrr, previous_status
    """
    p_start = _parse_date(period_start)
    p_end = _parse_date(period_end)

    active_start: dict[str, float] = {}
    active_end: dict[str, float] = {}
    new_customers: dict[str, float] = {}
    churned: dict[str, float] = {}
    expansion: dict[str, float] = {}
    contraction: dict[str, float] = {}
    reactivation: dict[str, float] = {}

    for sub in subscriptions:
        cid = sub["customer_id"]
        mrr = float(sub.get("mrr", 0))
        status = sub.get("status", "active")
        start_dt = _parse_date(sub.get("start_date"))
        cancel_dt = _parse_date(sub.get("cancel_date"))
        prev_mrr = float(sub.get("previous_mrr", 0))
        prev_status = sub.get("previous_status", "")

        was_active_at_start = (
            start_dt is not None
            and start_dt < p_start
            and (cancel_dt is None or cancel_dt >= p_start)
            and prev_status != "cancelled"
        )
        is_active_at_end = (
            status in ("active", "trialing", "past_due")
            and start_dt is not None
            and start_dt <= p_end
            and (cancel_dt is None or cancel_dt > p_end)
        )

        if was_active_at_start:
            active_start[cid] = active_start.get(cid, 0) + prev_mrr if prev_mrr else active_start.get(cid, 0) + mrr

        if is_active_at_end:
            active_end[cid] = active_end.get(cid, 0) + mrr

        is_new = (
            start_dt is not None
            and p_start <= start_dt <= p_end
            and (prev_status in ("", "new", None) or cid not in active_start)
            and prev_status != "cancelled"
        )
        is_reactivation = (
            start_dt is not None
            and p_start <= start_dt <= p_end
            and prev_status == "cancelled"
        )
        is_churned = (
            cancel_dt is not None
            and p_start <= cancel_dt <= p_end
            and status in ("cancelled", "churned")
        )

        if is_reactivation:
            reactivation[cid] = reactivation.get(cid, 0) + mrr
        elif is_new:
            new_customers[cid] = new_customers.get(cid, 0) + mrr

        if is_churned:
            lost_mrr = prev_mrr if prev_mrr else mrr
            churned[cid] = churned.get(cid, 0) + lost_mrr

        if was_active_at_start and is_active_at_end and not is_new and not is_reactivation:
            base = prev_mrr if prev_mrr else active_start.get(cid, mrr)
            diff = mrr - base
            if diff > 0:
                expansion[cid] = expansion.get(cid, 0) + diff
            elif diff < 0 and not is_churned:
                contraction[cid] = contraction.get(cid, 0) + abs(diff)

    start_mrr = sum(active_start.values())
    end_mrr = sum(active_end.values())
    new_mrr_total = sum(new_customers.values())
    expansion_total = sum(expansion.values())
    churned_total = sum(churned.values())
    contraction_total = sum(contraction.values())
    reactivation_total = sum(reactivation.values())

    net_new = new_mrr_total + expansion_total + reactivation_total - churned_total - contraction_total

    gross_churn_rate = _safe_div(churned_total, start_mrr)
    net_churn_rate = _safe_div(churned_total + contraction_total - expansion_total, start_mrr)
    nrr = _safe_div(start_mrr + expansion_total - churned_total - contraction_total, start_mrr, 1.0)

    total_customers = len(active_end)
    paying = {cid for cid, m in active_end.items() if m > 0}
    paying_count = len(paying)

    arpu = _safe_div(end_mrr, total_customers)
    arppu = _safe_div(end_mrr, paying_count)

    monthly_churn_rate = _safe_div(len(churned), len(active_start)) if active_start else 0.05
    if monthly_churn_rate <= 0:
        monthly_churn_rate = 0.001
    ltv = _safe_div(arpu, monthly_churn_rate)

    new_cust_count = len(new_customers)
    cac = _safe_div(prior_period_sales_spend, new_cust_count) if new_cust_count else 0.0
    ltv_cac = _safe_div(ltv, cac) if cac else 0.0
    payback = _safe_div(cac, arpu) if arpu else 0.0

    inflows = new_mrr_total + expansion_total + reactivation_total
    outflows = churned_total + contraction_total
    quick_ratio = _safe_div(inflows, outflows)

    net_new_arr = net_new * 12
    magic = _safe_div(net_new_arr, prior_period_sales_spend) if prior_period_sales_spend else 0.0

    period_months = max(_months_between(p_start, p_end), 1.0)
    revenue_this_period = end_mrr * period_months
    net_burn = total_costs - revenue_this_period
    burn_multiple = _safe_div(net_burn, net_new_arr) if net_new_arr > 0 else 0.0

    revenue_growth = _safe_div(net_new, start_mrr) if start_mrr else 0.0
    profit_margin = _safe_div(revenue_this_period - total_costs, revenue_this_period) if revenue_this_period else 0.0
    rule_of_40 = (revenue_growth * 100) + (profit_margin * 100)

    return SaaSMetrics(
        mrr=end_mrr,
        arr=end_mrr * 12,
        net_new_mrr=net_new,
        new_mrr=new_mrr_total,
        expansion_mrr=expansion_total,
        churned_mrr=churned_total,
        contraction_mrr=contraction_total,
        reactivation_mrr=reactivation_total,
        gross_churn_rate=gross_churn_rate,
        net_churn_rate=net_churn_rate,
        net_revenue_retention=nrr,
        ltv=ltv,
        cac=cac,
        ltv_cac_ratio=ltv_cac,
        payback_months=payback,
        arpu=arpu,
        arppu=arppu,
        quick_ratio=quick_ratio,
        magic_number=magic,
        burn_multiple=burn_multiple,
        rule_of_40_score=rule_of_40,
        total_customers=total_customers,
        paying_customers=paying_count,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 2. CHURN PREDICTION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class CustomerHealthSignals:
    customer_id: str
    mrr: float
    tenure_months: float
    login_frequency_30d: int
    feature_adoption_pct: float
    support_tickets_30d: int
    nps_score: Optional[float] = None
    usage_trend: str = "stable"
    billing_issues: int = 0
    engagement_score: float = 50.0
    last_active_days_ago: int = 0
    contract_months_remaining: Optional[int] = None
    expansion_signals: int = 0


@dataclass
class ChurnRiskProfile:
    customer_id: str
    churn_probability: float
    risk_tier: str
    days_until_likely_churn: int
    risk_factors: list[dict] = field(default_factory=list)
    recommended_interventions: list[dict] = field(default_factory=list)
    revenue_at_risk: float = 0.0
    intervention_roi: float = 0.0


# Per-factor sigmoid parameters: (midpoint, steepness, weight)
_CHURN_FACTOR_CONFIG = {
    "usage_decline": {
        "weight": 0.40,
        "description": "Usage trend declining or cliff-like drop",
    },
    "engagement_drop": {
        "weight": 0.20,
        "description": "Low engagement score relative to baseline",
    },
    "support_spike": {
        "weight": 0.15,
        "description": "Elevated support ticket volume",
    },
    "billing_issues": {
        "weight": 0.10,
        "description": "Failed payments or billing disputes",
    },
    "low_adoption": {
        "weight": 0.10,
        "description": "Low feature adoption percentage",
    },
    "nps_detractor": {
        "weight": 0.05,
        "description": "NPS score in detractor range (<=6)",
    },
}

_INTERVENTION_CATALOG = [
    {
        "action": "personal_outreach_call",
        "cost": 50.0,
        "expected_retention_lift": 0.25,
        "urgency_threshold": "critical",
        "description": "Direct call from CSM to understand pain points",
    },
    {
        "action": "success_plan_review",
        "cost": 100.0,
        "expected_retention_lift": 0.30,
        "urgency_threshold": "critical",
        "description": "Co-create a 90-day success plan with milestones",
    },
    {
        "action": "feature_training_session",
        "cost": 75.0,
        "expected_retention_lift": 0.20,
        "urgency_threshold": "high",
        "description": "Guided walkthrough of under-used features",
    },
    {
        "action": "loyalty_discount_offer",
        "cost": 200.0,
        "expected_retention_lift": 0.35,
        "urgency_threshold": "high",
        "description": "Offer 15-20% discount for annual commitment",
    },
    {
        "action": "usage_reactivation_campaign",
        "cost": 25.0,
        "expected_retention_lift": 0.15,
        "urgency_threshold": "medium",
        "description": "Automated drip campaign showcasing value and tips",
    },
    {
        "action": "executive_sponsor_intro",
        "cost": 150.0,
        "expected_retention_lift": 0.28,
        "urgency_threshold": "critical",
        "description": "Connect exec sponsor to deepen relationship",
    },
    {
        "action": "billing_resolution",
        "cost": 10.0,
        "expected_retention_lift": 0.40,
        "urgency_threshold": "high",
        "description": "Proactively resolve billing/payment issues",
    },
    {
        "action": "product_feedback_session",
        "cost": 60.0,
        "expected_retention_lift": 0.18,
        "urgency_threshold": "medium",
        "description": "Invite customer to share feedback and roadmap input",
    },
    {
        "action": "health_check_email",
        "cost": 5.0,
        "expected_retention_lift": 0.08,
        "urgency_threshold": "low",
        "description": "Friendly automated check-in with resource links",
    },
]


def _score_usage_decline(signals: CustomerHealthSignals) -> float:
    """Score usage decline risk [0-1] using a sigmoid on multiple signals."""
    trend_scores = {"increasing": -0.3, "stable": 0.0, "declining": 0.6, "cliff": 1.0}
    base = trend_scores.get(signals.usage_trend, 0.0)

    inactivity_risk = _sigmoid((signals.last_active_days_ago - 7) / 5.0)

    login_risk = _sigmoid((5 - signals.login_frequency_30d) / 3.0) if signals.login_frequency_30d < 20 else 0.0

    raw = 0.45 * base + 0.30 * inactivity_risk + 0.25 * login_risk
    return _clamp(raw)


def _score_engagement_drop(signals: CustomerHealthSignals) -> float:
    """Score engagement risk. Engagement 0-100; lower = higher risk."""
    return _clamp(_sigmoid((40 - signals.engagement_score) / 15.0))


def _score_support_spike(signals: CustomerHealthSignals) -> float:
    """High ticket volume (>3/month) is a strong churn signal."""
    return _clamp(_sigmoid((signals.support_tickets_30d - 3) / 2.0))


def _score_billing_issues(signals: CustomerHealthSignals) -> float:
    if signals.billing_issues <= 0:
        return 0.0
    return _clamp(_sigmoid((signals.billing_issues - 0.5) / 1.0))


def _score_low_adoption(signals: CustomerHealthSignals) -> float:
    """Feature adoption < 30% is concerning; < 15% is critical."""
    return _clamp(_sigmoid((0.30 - signals.feature_adoption_pct) / 0.12))


def _score_nps_detractor(signals: CustomerHealthSignals) -> float:
    if signals.nps_score is None:
        return 0.3  # missing NPS = slight risk bump
    if signals.nps_score <= 6:
        return _clamp(_sigmoid((6 - signals.nps_score) / 2.0) * 0.8 + 0.2)
    return 0.0


_FACTOR_SCORERS = {
    "usage_decline": _score_usage_decline,
    "engagement_drop": _score_engagement_drop,
    "support_spike": _score_support_spike,
    "billing_issues": _score_billing_issues,
    "low_adoption": _score_low_adoption,
    "nps_detractor": _score_nps_detractor,
}


def _bayesian_adjust(prior: float, likelihood: float, evidence_strength: float = 1.0) -> float:
    """Simple Bayesian posterior: P(churn|signals) ∝ P(signals|churn) * P(churn).

    evidence_strength scales how much the likelihood shifts the prior.
    """
    p_signal_given_churn = likelihood
    p_signal_given_no_churn = 1.0 - likelihood * evidence_strength * 0.5
    p_signal_given_no_churn = max(p_signal_given_no_churn, 0.05)

    numerator = p_signal_given_churn * prior
    denominator = numerator + p_signal_given_no_churn * (1.0 - prior)
    if denominator <= 0:
        return prior
    return _clamp(numerator / denominator)


def _estimate_days_until_churn(signals: CustomerHealthSignals, churn_prob: float) -> int:
    """Estimate days until likely churn based on decline velocity and risk level."""
    if churn_prob < 0.1:
        return 365

    base_days = 180
    velocity_map = {"cliff": 0.15, "declining": 0.40, "stable": 0.75, "increasing": 1.0}
    velocity_factor = velocity_map.get(signals.usage_trend, 0.5)

    inactivity_factor = max(0.1, 1.0 - signals.last_active_days_ago / 60.0)

    contract_factor = 1.0
    if signals.contract_months_remaining is not None:
        contract_factor = min(1.0, signals.contract_months_remaining / 6.0)

    estimated = base_days * velocity_factor * inactivity_factor * contract_factor * (1.0 - churn_prob * 0.5)
    return max(7, int(estimated))


def _select_interventions(
    risk_tier: str,
    risk_factors: list[dict],
    revenue_at_risk: float,
) -> list[dict]:
    urgency_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    tier_urgency = {"critical": "critical", "high": "high", "medium": "medium", "low": "low", "safe": "low"}
    max_urgency = tier_urgency.get(risk_tier, "low")
    max_urgency_val = urgency_order.get(max_urgency, 3)

    top_factor_names = {f["factor"] for f in sorted(risk_factors, key=lambda x: -x["value"])[:3]}

    factor_to_actions = {
        "usage_decline": ["personal_outreach_call", "usage_reactivation_campaign", "feature_training_session"],
        "engagement_drop": ["usage_reactivation_campaign", "feature_training_session", "product_feedback_session"],
        "support_spike": ["personal_outreach_call", "success_plan_review", "executive_sponsor_intro"],
        "billing_issues": ["billing_resolution"],
        "low_adoption": ["feature_training_session", "success_plan_review"],
        "nps_detractor": ["product_feedback_session", "executive_sponsor_intro", "loyalty_discount_offer"],
    }

    candidate_actions: set[str] = set()
    for factor_name in top_factor_names:
        for action in factor_to_actions.get(factor_name, []):
            candidate_actions.add(action)

    if not candidate_actions:
        candidate_actions.add("health_check_email")

    results = []
    for item in _INTERVENTION_CATALOG:
        if item["action"] not in candidate_actions:
            continue
        item_urgency_val = urgency_order.get(item["urgency_threshold"], 3)
        if item_urgency_val > max_urgency_val + 1:
            continue
        expected_saved = revenue_at_risk * item["expected_retention_lift"]
        roi = _safe_div(expected_saved - item["cost"], item["cost"])
        results.append({
            "action": item["action"],
            "description": item["description"],
            "cost": item["cost"],
            "expected_retention_lift": item["expected_retention_lift"],
            "expected_revenue_saved": round(expected_saved, 2),
            "urgency": item["urgency_threshold"],
            "roi": round(roi, 2),
        })

    results.sort(key=lambda x: -x["roi"])
    return results[:5]


def predict_churn_risk(
    customer: CustomerHealthSignals,
    cohort_baseline_churn: float = 0.05,
) -> ChurnRiskProfile:
    """Predict churn risk using a multi-factor logistic scoring model with
    Bayesian adjustment against the cohort baseline."""

    factor_scores: list[dict] = []
    weighted_sum = 0.0

    for factor_name, scorer_fn in _FACTOR_SCORERS.items():
        cfg = _CHURN_FACTOR_CONFIG[factor_name]
        raw_score = scorer_fn(customer)
        weighted = raw_score * cfg["weight"]
        weighted_sum += weighted
        factor_scores.append({
            "factor": factor_name,
            "weight": cfg["weight"],
            "value": round(raw_score, 4),
            "weighted_value": round(weighted, 4),
            "explanation": cfg["description"],
        })

    composite_likelihood = _clamp(weighted_sum / sum(c["weight"] for c in _CHURN_FACTOR_CONFIG.values()))

    tenure_factor = min(1.0, customer.tenure_months / 12.0)
    composite_likelihood *= (1.0 - tenure_factor * 0.15)

    if customer.expansion_signals > 0:
        dampening = 1.0 - min(0.3, customer.expansion_signals * 0.08)
        composite_likelihood *= dampening

    evidence_strength = 0.5 + 0.5 * min(1.0, len([f for f in factor_scores if f["value"] > 0.3]) / 3.0)
    churn_prob = _bayesian_adjust(cohort_baseline_churn, composite_likelihood, evidence_strength)

    if churn_prob < 0.10:
        risk_tier = "safe"
    elif churn_prob < 0.25:
        risk_tier = "low"
    elif churn_prob < 0.50:
        risk_tier = "medium"
    elif churn_prob < 0.75:
        risk_tier = "high"
    else:
        risk_tier = "critical"

    days_until = _estimate_days_until_churn(customer, churn_prob)

    annual_revenue_at_risk = customer.mrr * 12 * churn_prob

    interventions = _select_interventions(risk_tier, factor_scores, annual_revenue_at_risk)
    best_roi = interventions[0]["roi"] if interventions else 0.0

    return ChurnRiskProfile(
        customer_id=customer.customer_id,
        churn_probability=round(churn_prob, 4),
        risk_tier=risk_tier,
        days_until_likely_churn=days_until,
        risk_factors=sorted(factor_scores, key=lambda f: -f["weighted_value"]),
        recommended_interventions=interventions,
        revenue_at_risk=round(annual_revenue_at_risk, 2),
        intervention_roi=round(best_roi, 2),
    )


def batch_churn_analysis(
    customers: list[CustomerHealthSignals],
    cohort_baseline: float = 0.05,
) -> dict:
    """Analyze the entire customer base for churn risk, returning aggregate metrics
    and a prioritised intervention queue."""

    profiles = [predict_churn_risk(c, cohort_baseline) for c in customers]

    tier_buckets: dict[str, list[ChurnRiskProfile]] = defaultdict(list)
    for p in profiles:
        tier_buckets[p.risk_tier].append(p)

    tier_summary = {}
    for tier in ("critical", "high", "medium", "low", "safe"):
        members = tier_buckets.get(tier, [])
        tier_summary[tier] = {
            "count": len(members),
            "revenue_at_risk": round(sum(m.revenue_at_risk for m in members), 2),
            "avg_churn_probability": round(_mean([m.churn_probability for m in members]), 4),
            "customer_ids": [m.customer_id for m in members],
        }

    total_rev_at_risk = sum(t["revenue_at_risk"] for t in tier_summary.values())

    priority_queue = sorted(profiles, key=lambda p: (-p.revenue_at_risk, -p.churn_probability))

    avg_retention_lift = 0.20
    expected_saves = 0
    expected_revenue_recovered = 0.0
    intervention_plan: list[dict] = []
    for p in priority_queue:
        if p.risk_tier in ("safe", "low"):
            continue
        best = p.recommended_interventions[0] if p.recommended_interventions else None
        if best:
            expected_saved = p.revenue_at_risk * best["expected_retention_lift"]
            expected_revenue_recovered += expected_saved
            expected_saves += 1
            intervention_plan.append({
                "customer_id": p.customer_id,
                "risk_tier": p.risk_tier,
                "churn_probability": p.churn_probability,
                "revenue_at_risk": p.revenue_at_risk,
                "recommended_action": best["action"],
                "expected_revenue_saved": round(expected_saved, 2),
                "roi": best["roi"],
            })

    return {
        "total_customers_analyzed": len(customers),
        "tier_summary": tier_summary,
        "total_revenue_at_risk": round(total_rev_at_risk, 2),
        "intervention_priority_queue": intervention_plan[:50],
        "expected_saves": expected_saves,
        "expected_revenue_recovered": round(expected_revenue_recovered, 2),
        "expected_save_rate": round(_safe_div(expected_saves, len(customers)), 4),
        "risk_distribution": {
            tier: round(_safe_div(len(tier_buckets.get(tier, [])), len(customers)), 4)
            for tier in ("critical", "high", "medium", "low", "safe")
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3. EXPANSION REVENUE OPTIMIZER
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ExpansionOpportunity:
    customer_id: str
    opportunity_type: str
    current_plan: str
    recommended_plan: str
    current_mrr: float
    potential_mrr: float
    expansion_mrr: float
    probability: float
    expected_value: float
    timing: str
    trigger_signals: list[str] = field(default_factory=list)
    recommended_approach: str = ""


def _find_next_plan(current_plan: str, plan_ladder: list[dict]) -> Optional[dict]:
    """Find the next tier up from the current plan."""
    sorted_plans = sorted(plan_ladder, key=lambda p: p.get("mrr", 0))
    found_current = False
    for plan in sorted_plans:
        if found_current:
            return plan
        if plan.get("plan_name", "") == current_plan:
            found_current = True
    return None


def _find_plan_by_name(name: str, plan_ladder: list[dict]) -> Optional[dict]:
    for plan in plan_ladder:
        if plan.get("plan_name", "") == name:
            return plan
    return None


def _score_upsell_readiness(
    customer: CustomerHealthSignals,
    usage_pcts: dict[str, float],
    current_plan: dict,
    next_plan: Optional[dict],
) -> tuple[float, list[str], str]:
    """Score upsell readiness [0-1] and identify trigger signals."""
    if next_plan is None:
        return 0.0, [], ""

    signals: list[str] = []
    score = 0.0

    high_usage_features = [f for f, pct in usage_pcts.items() if pct > 0.80]
    if high_usage_features:
        feature_pressure = min(1.0, len(high_usage_features) / 3.0)
        score += 0.30 * feature_pressure
        signals.append(f"Usage >80% on {len(high_usage_features)} features/limits")

    if customer.feature_adoption_pct > 0.70:
        score += 0.20
        signals.append(f"High feature adoption ({customer.feature_adoption_pct:.0%})")

    if customer.usage_trend == "increasing":
        score += 0.15
        signals.append("Usage trend is increasing")

    if customer.engagement_score > 70:
        score += 0.15
        signals.append(f"Strong engagement score ({customer.engagement_score:.0f})")

    if customer.tenure_months > 6:
        tenure_bonus = min(0.10, (customer.tenure_months - 6) / 24 * 0.10)
        score += tenure_bonus
        signals.append(f"Loyal customer ({customer.tenure_months:.0f} months)")

    if customer.nps_score is not None and customer.nps_score >= 9:
        score += 0.10
        signals.append(f"NPS promoter (score {customer.nps_score})")

    approach_parts = []
    if high_usage_features:
        approach_parts.append("Highlight how the upgrade removes current usage limits")
    if customer.feature_adoption_pct > 0.70:
        approach_parts.append("showcase advanced features they'll benefit from")
    if customer.nps_score is not None and customer.nps_score >= 9:
        approach_parts.append("leverage their positive sentiment with a loyalty offer")
    approach = ". ".join(approach_parts) + "." if approach_parts else "Standard upgrade pitch with value focus."

    return _clamp(score), signals, approach


def _score_seat_expansion(
    customer: CustomerHealthSignals,
    current_plan: dict,
) -> tuple[float, list[str], str]:
    """Score likelihood of seat expansion."""
    seat_limit = current_plan.get("seat_limit", 0)
    if not seat_limit:
        return 0.0, [], ""

    signals: list[str] = []
    score = 0.0

    if customer.expansion_signals > 0:
        score += min(0.50, customer.expansion_signals * 0.15)
        signals.append(f"{customer.expansion_signals} expansion signal(s) detected (seat inquiries)")

    if customer.usage_trend == "increasing" and customer.engagement_score > 60:
        score += 0.25
        signals.append("Growing team activity patterns")

    if customer.tenure_months > 3:
        score += 0.15
        signals.append("Established customer with stable usage")

    approach = "Offer volume discount for additional seats with self-serve provisioning."
    return _clamp(score), signals, approach


def identify_expansion_opportunities(
    customers: list[CustomerHealthSignals],
    plan_ladder: list[dict],
    usage_data: list[dict],
) -> list[ExpansionOpportunity]:
    """Identify expansion opportunities using usage-based signals."""

    usage_by_customer: dict[str, dict[str, float]] = defaultdict(dict)
    for ud in usage_data:
        cid = ud.get("customer_id", "")
        feature = ud.get("feature", "")
        pct = float(ud.get("usage_pct", 0))
        usage_by_customer[cid][feature] = pct

    customer_plan_map: dict[str, str] = {}
    for c in customers:
        best_match = None
        best_diff = float("inf")
        for plan in plan_ladder:
            diff = abs(plan.get("mrr", 0) - c.mrr)
            if diff < best_diff:
                best_diff = diff
                best_match = plan
        if best_match:
            customer_plan_map[c.customer_id] = best_match.get("plan_name", "")

    opportunities: list[ExpansionOpportunity] = []

    for customer in customers:
        cid = customer.customer_id
        current_plan_name = customer_plan_map.get(cid, "")
        current_plan = _find_plan_by_name(current_plan_name, plan_ladder)
        if current_plan is None:
            continue
        next_plan = _find_next_plan(current_plan_name, plan_ladder)
        usage_pcts = usage_by_customer.get(cid, {})

        upsell_score, upsell_signals, upsell_approach = _score_upsell_readiness(
            customer, usage_pcts, current_plan, next_plan,
        )
        if upsell_score > 0.25 and next_plan is not None:
            next_mrr = float(next_plan.get("mrr", 0))
            exp_mrr = next_mrr - customer.mrr
            if exp_mrr > 0:
                timing = "immediate" if upsell_score > 0.65 else ("this_month" if upsell_score > 0.45 else "next_quarter")
                opportunities.append(ExpansionOpportunity(
                    customer_id=cid,
                    opportunity_type="upsell",
                    current_plan=current_plan_name,
                    recommended_plan=next_plan.get("plan_name", ""),
                    current_mrr=customer.mrr,
                    potential_mrr=next_mrr,
                    expansion_mrr=exp_mrr,
                    probability=round(upsell_score, 3),
                    expected_value=round(exp_mrr * upsell_score, 2),
                    timing=timing,
                    trigger_signals=upsell_signals,
                    recommended_approach=upsell_approach,
                ))

        seat_score, seat_signals, seat_approach = _score_seat_expansion(customer, current_plan)
        if seat_score > 0.20:
            per_seat = current_plan.get("mrr", 0) / max(current_plan.get("seat_limit", 1), 1)
            additional_seats = max(1, customer.expansion_signals)
            seat_exp_mrr = per_seat * additional_seats
            if seat_exp_mrr > 0:
                timing = "immediate" if seat_score > 0.55 else "this_month"
                opportunities.append(ExpansionOpportunity(
                    customer_id=cid,
                    opportunity_type="seat_expansion",
                    current_plan=current_plan_name,
                    recommended_plan=current_plan_name,
                    current_mrr=customer.mrr,
                    potential_mrr=customer.mrr + seat_exp_mrr,
                    expansion_mrr=seat_exp_mrr,
                    probability=round(seat_score, 3),
                    expected_value=round(seat_exp_mrr * seat_score, 2),
                    timing=timing,
                    trigger_signals=seat_signals,
                    recommended_approach=seat_approach,
                ))

        power_user = (
            customer.feature_adoption_pct > 0.80
            and customer.engagement_score > 75
            and customer.usage_trend == "increasing"
        )
        top_plan = sorted(plan_ladder, key=lambda p: p.get("mrr", 0))[-1] if plan_ladder else None
        if power_user and top_plan and top_plan.get("plan_name") != current_plan_name:
            top_mrr = float(top_plan.get("mrr", 0))
            exp_mrr = top_mrr - customer.mrr
            if exp_mrr > 0:
                opportunities.append(ExpansionOpportunity(
                    customer_id=cid,
                    opportunity_type="usage_upgrade",
                    current_plan=current_plan_name,
                    recommended_plan=top_plan.get("plan_name", ""),
                    current_mrr=customer.mrr,
                    potential_mrr=top_mrr,
                    expansion_mrr=exp_mrr,
                    probability=round(min(0.85, upsell_score + 0.20), 3),
                    expected_value=round(exp_mrr * min(0.85, upsell_score + 0.20), 2),
                    timing="immediate",
                    trigger_signals=["Power user pattern: high adoption + engagement + growth"],
                    recommended_approach="VIP treatment — offer exclusive beta features, dedicated support, or custom pricing.",
                ))

        cross_sell_features = [
            f for f, pct in usage_pcts.items()
            if pct > 0.60 and next_plan
            and f in next_plan.get("features", [])
            and f not in current_plan.get("features", [])
        ]
        if cross_sell_features and next_plan:
            next_mrr = float(next_plan.get("mrr", 0))
            exp_mrr = next_mrr - customer.mrr
            if exp_mrr > 0:
                prob = min(0.70, 0.30 + len(cross_sell_features) * 0.10)
                opportunities.append(ExpansionOpportunity(
                    customer_id=cid,
                    opportunity_type="cross_sell",
                    current_plan=current_plan_name,
                    recommended_plan=next_plan.get("plan_name", ""),
                    current_mrr=customer.mrr,
                    potential_mrr=next_mrr,
                    expansion_mrr=exp_mrr,
                    probability=round(prob, 3),
                    expected_value=round(exp_mrr * prob, 2),
                    timing="this_month",
                    trigger_signals=[f"Heavy usage of higher-tier feature: {f}" for f in cross_sell_features],
                    recommended_approach=f"Highlight that upgrading unlocks full access to {', '.join(cross_sell_features)}.",
                ))

    opportunities.sort(key=lambda o: -o.expected_value)
    return opportunities


# ══════════════════════════════════════════════════════════════════════════════
# 4. PRICING INTELLIGENCE ENGINE
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PriceElasticityResult:
    segment: str
    elasticity: float
    optimal_price: float
    max_revenue_price: float
    max_profit_price: float
    sensitivity_class: str
    r_squared: float = 0.0
    data_points: int = 0


@dataclass
class PricingRecommendation:
    segment: str
    current_price: float
    recommended_price: float
    price_change_pct: float
    expected_conversion_impact: float
    expected_revenue_impact: float
    expected_ltv_impact: float
    confidence: float
    reasoning: str


def estimate_price_elasticity(
    price_history: list[dict],
    cost_per_unit: float = 0.0,
    segment: str = "default",
) -> PriceElasticityResult:
    """Estimate price elasticity using log-log regression on price-conversion data.

    ln(Q) = a + b * ln(P), where b is the elasticity coefficient.
    Revenue R = P * Q, so dR/dP = 0 yields optimal price = cost / (1 + 1/b)
    when b < -1 (elastic demand).
    """
    valid = [
        h for h in price_history
        if float(h.get("price", 0)) > 0 and float(h.get("conversions", 0)) > 0
    ]
    if len(valid) < 2:
        return PriceElasticityResult(
            segment=segment,
            elasticity=-1.0,
            optimal_price=valid[0]["price"] if valid else 0.0,
            max_revenue_price=valid[0]["price"] if valid else 0.0,
            max_profit_price=valid[0]["price"] if valid else 0.0,
            sensitivity_class="unknown",
            data_points=len(valid),
        )

    ln_prices = [math.log(float(h["price"])) for h in valid]
    ln_quantities = [math.log(float(h["conversions"])) for h in valid]

    elasticity, intercept, r_sq = _linear_regression(ln_prices, ln_quantities)

    if elasticity >= 0:
        elasticity = -0.5

    if abs(elasticity) > 0.01 and abs(elasticity) != 1.0:
        max_revenue_price = math.exp(-intercept / (elasticity + 1)) if elasticity < -1 else max(h["price"] for h in valid)
    else:
        max_revenue_price = _mean([float(h["price"]) for h in valid])

    if elasticity < -1:
        optimal_price = max_revenue_price
    else:
        optimal_price = max(float(h["price"]) for h in valid)

    if cost_per_unit > 0 and elasticity < -1:
        max_profit_price = cost_per_unit * elasticity / (elasticity + 1)
        max_profit_price = max(max_profit_price, cost_per_unit * 1.1)
    else:
        max_profit_price = optimal_price

    abs_e = abs(elasticity)
    if abs_e < 0.5:
        sensitivity = "inelastic"
    elif abs_e < 1.0:
        sensitivity = "inelastic"
    elif abs(abs_e - 1.0) < 0.1:
        sensitivity = "unit_elastic"
    elif abs_e < 2.0:
        sensitivity = "elastic"
    else:
        sensitivity = "highly_elastic"

    return PriceElasticityResult(
        segment=segment,
        elasticity=round(elasticity, 4),
        optimal_price=round(max(0.01, optimal_price), 2),
        max_revenue_price=round(max(0.01, max_revenue_price), 2),
        max_profit_price=round(max(0.01, max_profit_price), 2),
        sensitivity_class=sensitivity,
        r_squared=round(r_sq, 4),
        data_points=len(valid),
    )


def optimize_pricing_tiers(
    segments: list[dict],
    cost_structure: dict,
    target_margin: float = 0.80,
) -> list[PricingRecommendation]:
    """Optimize pricing across segments to maximise total revenue while
    maintaining target margins.

    For each segment, uses its elasticity to compute the revenue-maximising
    price, then adjusts to meet the target margin floor.
    """
    fixed_cost = float(cost_structure.get("fixed_cost_per_user", 0))
    variable_cost = float(cost_structure.get("variable_cost_per_unit", 0))

    recommendations: list[PricingRecommendation] = []

    for seg in segments:
        seg_name = seg.get("segment_name", "unknown")
        size = int(seg.get("size", 0))
        current_price = float(seg.get("current_price", 0))
        elasticity = float(seg.get("elasticity", -1.0))
        avg_usage = float(seg.get("avg_usage", 1.0))

        unit_cost = fixed_cost + variable_cost * avg_usage
        min_price_for_margin = unit_cost / (1.0 - target_margin) if target_margin < 1.0 else unit_cost * 5

        if elasticity < -1:
            revenue_max_price = current_price * abs(elasticity) / (abs(elasticity) - 1)
        else:
            revenue_max_price = current_price * 1.15

        if unit_cost > 0 and elasticity < -1:
            profit_max_price = unit_cost * abs(elasticity) / (abs(elasticity) - 1)
        else:
            profit_max_price = revenue_max_price

        recommended = max(revenue_max_price, min_price_for_margin)

        max_increase = current_price * 1.30
        min_decrease = current_price * 0.70
        recommended = _clamp(recommended, min_decrease, max_increase)
        recommended = round(recommended, 2)

        change_pct = _safe_div(recommended - current_price, current_price) if current_price else 0.0

        if abs(elasticity) > 0.01:
            conversion_impact = elasticity * change_pct
        else:
            conversion_impact = 0.0
        conversion_impact = _clamp(conversion_impact, -0.50, 0.50)

        new_conversions = size * (1 + conversion_impact)
        old_revenue = current_price * size
        new_revenue = recommended * new_conversions
        revenue_impact = new_revenue - old_revenue

        ltv_impact_factor = 1.0
        if change_pct > 0:
            ltv_impact_factor = 1.0 + change_pct * 0.5 * (1 + conversion_impact)
        else:
            ltv_impact_factor = 1.0 + change_pct * 0.3

        confidence = 0.5
        data_quality_bonus = min(0.3, size / 1000 * 0.3)
        confidence += data_quality_bonus
        if abs(elasticity) > 0.3:
            confidence += 0.1
        confidence = _clamp(confidence, 0.1, 0.95)

        reasoning_parts = []
        if change_pct > 0.02:
            reasoning_parts.append(f"Market can bear a {change_pct:.0%} increase")
            if abs(elasticity) < 1:
                reasoning_parts.append("demand is inelastic so volume loss is minimal")
        elif change_pct < -0.02:
            reasoning_parts.append(f"A {abs(change_pct):.0%} decrease will drive volume")
            reasoning_parts.append("expected volume gain outweighs per-unit loss")
        else:
            reasoning_parts.append("Current pricing is near-optimal")
        if recommended < min_price_for_margin:
            reasoning_parts.append(f"floored at {min_price_for_margin:.2f} to maintain {target_margin:.0%} margin")
        reasoning = "; ".join(reasoning_parts) + "."

        recommendations.append(PricingRecommendation(
            segment=seg_name,
            current_price=current_price,
            recommended_price=recommended,
            price_change_pct=round(change_pct, 4),
            expected_conversion_impact=round(conversion_impact, 4),
            expected_revenue_impact=round(revenue_impact, 2),
            expected_ltv_impact=round(ltv_impact_factor, 4),
            confidence=round(confidence, 3),
            reasoning=reasoning,
        ))

    recommendations.sort(key=lambda r: -abs(r.expected_revenue_impact))
    return recommendations


# ══════════════════════════════════════════════════════════════════════════════
# 5. COHORT ANALYSIS ENGINE
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class CohortMetrics:
    cohort_id: str
    cohort_size: int
    retention_curve: list[float] = field(default_factory=list)
    revenue_curve: list[float] = field(default_factory=list)
    ltv_estimate: float = 0.0
    avg_months_retained: float = 0.0
    best_retained_segment: str = ""
    worst_retained_segment: str = ""


def _cohort_key(dt: datetime, granularity: str) -> str:
    if granularity == "weekly":
        iso = dt.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    if granularity == "quarterly":
        q = (dt.month - 1) // 3 + 1
        return f"{dt.year}-Q{q}"
    return f"{dt.year}-{dt.month:02d}"


def analyze_cohorts(
    subscriptions: list[dict],
    cohort_granularity: str = "monthly",
) -> list[CohortMetrics]:
    """Build cohort retention and revenue curves from subscription records."""

    cohort_members: dict[str, list[dict]] = defaultdict(list)

    for sub in subscriptions:
        start_dt = _parse_date(sub.get("start_date"))
        if start_dt is None:
            continue
        key = _cohort_key(start_dt, cohort_granularity)
        cohort_members[key].append(sub)

    now = datetime.utcnow()
    results: list[CohortMetrics] = []

    for cohort_id in sorted(cohort_members.keys()):
        members = cohort_members[cohort_id]
        cohort_size = len(members)
        if cohort_size == 0:
            continue

        earliest_start = min(_parse_date(m["start_date"]) for m in members)
        max_months = int(_months_between(earliest_start, now)) + 1
        max_months = max(1, min(max_months, 60))

        retention_curve: list[float] = []
        revenue_curve: list[float] = []

        segment_retention: dict[str, list[float]] = defaultdict(list)

        for month_idx in range(max_months):
            month_boundary = earliest_start + timedelta(days=month_idx * 30.44)
            active = 0
            month_revenue = 0.0

            for m in members:
                m_start = _parse_date(m["start_date"])
                m_cancel = _parse_date(m.get("cancel_date"))
                mrr_val = float(m.get("mrr", 0))
                segment = m.get("segment", "default")

                is_active = (
                    m_start is not None
                    and m_start <= month_boundary
                    and (m_cancel is None or m_cancel > month_boundary)
                )
                if is_active:
                    active += 1
                    month_revenue += mrr_val
                    if month_idx > 0:
                        segment_retention[segment].append(1.0)
                    else:
                        segment_retention[segment].append(1.0)
                elif month_idx > 0:
                    segment_retention[segment].append(0.0)

            retention_rate = _safe_div(active, cohort_size, 1.0)
            retention_curve.append(round(retention_rate, 4))

            cumulative = (revenue_curve[-1] if revenue_curve else 0.0) + month_revenue
            revenue_curve.append(round(cumulative, 2))

        avg_months = sum(retention_curve) if retention_curve else 0.0

        avg_mrr = _mean([float(m.get("mrr", 0)) for m in members])
        ltv = avg_mrr * avg_months

        best_seg = ""
        worst_seg = ""
        best_ret = -1.0
        worst_ret = 2.0
        for seg, vals in segment_retention.items():
            seg_avg = _mean(vals)
            if seg_avg > best_ret:
                best_ret = seg_avg
                best_seg = seg
            if seg_avg < worst_ret:
                worst_ret = seg_avg
                worst_seg = seg

        results.append(CohortMetrics(
            cohort_id=cohort_id,
            cohort_size=cohort_size,
            retention_curve=retention_curve,
            revenue_curve=revenue_curve,
            ltv_estimate=round(ltv, 2),
            avg_months_retained=round(avg_months, 2),
            best_retained_segment=best_seg,
            worst_retained_segment=worst_seg,
        ))

    return results


def project_cohort_revenue(
    cohort: CohortMetrics,
    months_forward: int = 24,
) -> list[dict]:
    """Project future revenue using power-law retention curve extrapolation.

    Fits retention_rate ~ a * month^(-b) to observed data, then extrapolates.
    """
    curve = cohort.retention_curve
    if len(curve) < 2:
        avg_mrr = _safe_div(cohort.revenue_curve[-1] if cohort.revenue_curve else 0, max(len(curve), 1))
        return [
            {
                "month": i + 1,
                "projected_retention": max(0.01, 1.0 - i * 0.05),
                "projected_revenue": round(avg_mrr * max(0.01, 1.0 - i * 0.05) * cohort.cohort_size, 2),
                "cumulative_revenue": 0.0,
            }
            for i in range(months_forward)
        ]

    xs = []
    ys = []
    for i, r in enumerate(curve):
        if i == 0:
            continue
        if r > 0:
            xs.append(math.log(max(i, 1)))
            ys.append(math.log(r))

    if len(xs) >= 2:
        decay_exp, log_a, _ = _linear_regression(xs, ys)
        a_coeff = math.exp(log_a)
    else:
        a_coeff = 1.0
        decay_exp = -0.15

    decay_exp = max(decay_exp, -2.0)
    a_coeff = _clamp(a_coeff, 0.01, 2.0)

    last_observed_month = len(curve) - 1
    avg_mrr_per_customer = 0.0
    if cohort.revenue_curve and cohort.cohort_size > 0:
        total_months_active = sum(curve)
        avg_mrr_per_customer = _safe_div(
            cohort.revenue_curve[-1],
            total_months_active * cohort.cohort_size,
        ) if total_months_active > 0 else _safe_div(cohort.revenue_curve[-1], max(len(curve), 1) * cohort.cohort_size)

    if avg_mrr_per_customer <= 0 and cohort.revenue_curve:
        avg_mrr_per_customer = _safe_div(cohort.revenue_curve[-1], max(len(curve), 1))

    projections: list[dict] = []
    cumulative = cohort.revenue_curve[-1] if cohort.revenue_curve else 0.0

    for m in range(1, months_forward + 1):
        future_month = last_observed_month + m
        if future_month <= 0:
            retention = 1.0
        else:
            retention = a_coeff * (future_month ** decay_exp)

        retention = _clamp(retention, 0.001, 1.0)

        monthly_rev = avg_mrr_per_customer * retention * cohort.cohort_size
        cumulative += monthly_rev

        projections.append({
            "month": future_month,
            "projected_retention": round(retention, 4),
            "projected_revenue": round(monthly_rev, 2),
            "cumulative_revenue": round(cumulative, 2),
        })

    return projections


# ══════════════════════════════════════════════════════════════════════════════
# 6. REVENUE STREAM PRIORITIZER
# ══════════════════════════════════════════════════════════════════════════════

REVENUE_AVENUE_PROFILES: dict[str, dict] = {
    "saas": {
        "avg_margin": 0.85, "recurring": True, "scalability": 0.95,
        "ltv_multiple": 36, "setup_effort": "high", "time_to_revenue_months": 3,
    },
    "digital_product": {
        "avg_margin": 0.90, "recurring": False, "scalability": 0.90,
        "ltv_multiple": 1.5, "setup_effort": "medium", "time_to_revenue_months": 1,
    },
    "membership": {
        "avg_margin": 0.80, "recurring": True, "scalability": 0.85,
        "ltv_multiple": 18, "setup_effort": "medium", "time_to_revenue_months": 2,
    },
    "consulting": {
        "avg_margin": 0.70, "recurring": False, "scalability": 0.30,
        "ltv_multiple": 3, "setup_effort": "low", "time_to_revenue_months": 0.5,
    },
    "high_ticket_service": {
        "avg_margin": 0.75, "recurring": False, "scalability": 0.40,
        "ltv_multiple": 2, "setup_effort": "low", "time_to_revenue_months": 0.5,
    },
    "course": {
        "avg_margin": 0.88, "recurring": False, "scalability": 0.92,
        "ltv_multiple": 2, "setup_effort": "high", "time_to_revenue_months": 2,
    },
    "affiliate": {
        "avg_margin": 1.00, "recurring": False, "scalability": 0.80,
        "ltv_multiple": 1, "setup_effort": "low", "time_to_revenue_months": 0,
    },
    "sponsor": {
        "avg_margin": 0.95, "recurring": False, "scalability": 0.50,
        "ltv_multiple": 4, "setup_effort": "medium", "time_to_revenue_months": 1,
    },
    "ad_revenue": {
        "avg_margin": 1.00, "recurring": True, "scalability": 0.85,
        "ltv_multiple": 12, "setup_effort": "low", "time_to_revenue_months": 0,
    },
    "licensing": {
        "avg_margin": 0.90, "recurring": True, "scalability": 0.70,
        "ltv_multiple": 24, "setup_effort": "high", "time_to_revenue_months": 6,
    },
    "community": {
        "avg_margin": 0.75, "recurring": True, "scalability": 0.80,
        "ltv_multiple": 14, "setup_effort": "medium", "time_to_revenue_months": 2,
    },
    "ecommerce": {
        "avg_margin": 0.40, "recurring": False, "scalability": 0.65,
        "ltv_multiple": 2, "setup_effort": "medium", "time_to_revenue_months": 1,
    },
}

_EFFORT_NUMERIC = {"low": 1.0, "medium": 2.0, "high": 3.0}

_SKILL_REQUIREMENTS: dict[str, str] = {
    "saas": "advanced",
    "digital_product": "intermediate",
    "membership": "intermediate",
    "consulting": "beginner",
    "high_ticket_service": "beginner",
    "course": "intermediate",
    "affiliate": "beginner",
    "sponsor": "intermediate",
    "ad_revenue": "beginner",
    "licensing": "expert",
    "community": "intermediate",
    "ecommerce": "intermediate",
}

_SKILL_LEVEL_NUMERIC = {"beginner": 1, "intermediate": 2, "advanced": 3, "expert": 4}

_SYNERGY_PAIRS: dict[tuple[str, str], float] = {
    ("saas", "community"): 0.25,
    ("community", "saas"): 0.25,
    ("saas", "consulting"): 0.15,
    ("consulting", "saas"): 0.15,
    ("course", "membership"): 0.20,
    ("membership", "course"): 0.20,
    ("course", "consulting"): 0.15,
    ("consulting", "course"): 0.15,
    ("digital_product", "affiliate"): 0.10,
    ("affiliate", "digital_product"): 0.10,
    ("community", "course"): 0.20,
    ("course", "community"): 0.20,
    ("sponsor", "ad_revenue"): 0.15,
    ("ad_revenue", "sponsor"): 0.15,
    ("membership", "community"): 0.20,
    ("community", "membership"): 0.20,
    ("saas", "digital_product"): 0.10,
    ("digital_product", "saas"): 0.10,
    ("licensing", "saas"): 0.15,
    ("saas", "licensing"): 0.15,
    ("ecommerce", "affiliate"): 0.12,
    ("affiliate", "ecommerce"): 0.12,
}

_NICHE_AFFINITY: dict[str, dict[str, float]] = {
    "tech": {"saas": 1.3, "course": 1.1, "consulting": 1.1, "licensing": 1.2},
    "finance": {"saas": 1.2, "consulting": 1.3, "course": 1.2, "high_ticket_service": 1.2},
    "health": {"membership": 1.3, "course": 1.2, "community": 1.2, "digital_product": 1.1},
    "fitness": {"membership": 1.3, "course": 1.2, "community": 1.2, "ecommerce": 1.1, "sponsor": 1.1},
    "lifestyle": {"sponsor": 1.3, "affiliate": 1.2, "ad_revenue": 1.2, "ecommerce": 1.1},
    "education": {"course": 1.4, "membership": 1.2, "community": 1.2, "digital_product": 1.2},
    "business": {"saas": 1.2, "consulting": 1.3, "high_ticket_service": 1.2, "course": 1.1},
    "creative": {"digital_product": 1.3, "course": 1.2, "community": 1.1, "sponsor": 1.2},
    "gaming": {"ad_revenue": 1.3, "sponsor": 1.3, "community": 1.2, "ecommerce": 1.1},
    "marketing": {"saas": 1.2, "course": 1.2, "consulting": 1.2, "affiliate": 1.2},
}

_AVENUE_NEXT_STEPS: dict[str, list[str]] = {
    "saas": [
        "Define core value proposition and MVP feature set",
        "Build landing page with waitlist",
        "Validate with 10 pilot customers at discounted rate",
        "Implement billing with Stripe/Paddle",
        "Set up onboarding flow and usage analytics",
    ],
    "digital_product": [
        "Identify highest-demand topic from audience signals",
        "Create outline and production timeline",
        "Build sales page with compelling copy",
        "Set up delivery platform (Gumroad, Lemon Squeezy)",
        "Launch with limited-time intro pricing",
    ],
    "membership": [
        "Define exclusive value members receive monthly",
        "Choose platform (Circle, Skool, custom)",
        "Create founding-member offer with annual discount",
        "Build 30 days of content runway before launch",
        "Set up welcome sequence and community rituals",
    ],
    "consulting": [
        "Package expertise into 3 tiers (audit, strategy, done-for-you)",
        "Create intake questionnaire and scope template",
        "Set up scheduling and payment (Calendly + Stripe)",
        "Publish case studies or testimonials",
        "Outreach to warm network for first 5 clients",
    ],
    "high_ticket_service": [
        "Define premium offer with clear deliverables and timeline",
        "Create application funnel to qualify leads",
        "Build proposal template with ROI projection",
        "Set up onboarding process for new clients",
        "Develop referral incentive for existing clients",
    ],
    "course": [
        "Validate topic with pre-sale or survey",
        "Outline curriculum with clear learning outcomes",
        "Record and produce first module as proof of concept",
        "Choose platform (Teachable, Kajabi, self-hosted)",
        "Plan launch sequence with email + social campaign",
    ],
    "affiliate": [
        "Audit tools and products you already use and love",
        "Apply to affiliate programs with highest commissions",
        "Create honest review/comparison content",
        "Add affiliate links to high-traffic existing content",
        "Track conversions and double down on top performers",
    ],
    "sponsor": [
        "Build a media kit with audience demographics and engagement",
        "Research brands spending on creator sponsorships in niche",
        "Set rate card (CPM-based or flat fee per placement)",
        "Reach out to 20 potential sponsors with pitch deck",
        "Deliver first sponsored content and share results with brand",
    ],
    "ad_revenue": [
        "Ensure content meets monetization thresholds (YPP, etc.)",
        "Optimize content for watch time and session duration",
        "Experiment with mid-roll placement for longer content",
        "Diversify across platforms (YouTube, blog, podcast)",
        "Track RPM trends and adjust content strategy accordingly",
    ],
    "licensing": [
        "Identify IP assets suitable for licensing (frameworks, data, code)",
        "Research potential licensees in adjacent industries",
        "Create licensing terms and pricing structure",
        "Build a licensing pitch deck with ROI for licensee",
        "Negotiate first licensing deal with a pilot partner",
    ],
    "community": [
        "Define the transformation or identity the community provides",
        "Choose platform and pricing (free tier + paid tier)",
        "Recruit 20 founding members from most engaged followers",
        "Establish weekly rituals (AMAs, challenges, co-working)",
        "Build moderation guidelines and member success metrics",
    ],
    "ecommerce": [
        "Identify product-market fit with audience demand signals",
        "Source or create initial product line (3-5 SKUs)",
        "Set up store (Shopify, WooCommerce) with brand theming",
        "Plan inventory and fulfillment logistics",
        "Launch with limited edition or bundle to drive urgency",
    ],
}

_AVENUE_DEPENDENCIES: dict[str, list[str]] = {
    "saas": ["audience_validation", "technical_capability", "billing_infrastructure"],
    "digital_product": ["content_expertise", "sales_page"],
    "membership": ["content_pipeline", "community_platform"],
    "consulting": ["domain_expertise", "scheduling_system"],
    "high_ticket_service": ["proven_results", "sales_process"],
    "course": ["teaching_ability", "production_setup"],
    "affiliate": ["audience_trust", "content_distribution"],
    "sponsor": ["media_kit", "audience_metrics"],
    "ad_revenue": ["monetizable_content", "platform_eligibility"],
    "licensing": ["intellectual_property", "legal_framework"],
    "community": ["engaged_audience", "community_platform"],
    "ecommerce": ["product_sourcing", "fulfillment_logistics"],
}


@dataclass
class AvenueRecommendation:
    avenue: str
    priority_rank: int
    composite_score: float
    expected_monthly_revenue: float
    expected_annual_revenue: float
    margin: float
    time_to_revenue: str
    effort_level: str
    reasoning: str
    next_steps: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)


def _estimate_avenue_revenue(
    avenue: str,
    profile: dict,
    audience_size: int,
    engagement_rate: float,
    existing_revenue: float,
    growth_rate: float,
) -> float:
    """Estimate realistic monthly revenue for a revenue avenue given audience metrics."""
    engaged = audience_size * engagement_rate

    if avenue == "saas":
        trial_rate = 0.02
        convert_rate = 0.25
        avg_mrr = 49.0
        return engaged * trial_rate * convert_rate * avg_mrr
    if avenue == "digital_product":
        buy_rate = 0.015
        avg_price = 47.0
        return engaged * buy_rate * avg_price
    if avenue == "membership":
        join_rate = 0.01
        avg_monthly = 29.0
        return engaged * join_rate * avg_monthly
    if avenue == "consulting":
        inquiry_rate = 0.002
        close_rate = 0.30
        avg_deal = 3000.0
        return engaged * inquiry_rate * close_rate * avg_deal
    if avenue == "high_ticket_service":
        inquiry_rate = 0.001
        close_rate = 0.20
        avg_deal = 7500.0
        return engaged * inquiry_rate * close_rate * avg_deal
    if avenue == "course":
        buy_rate = 0.008
        avg_price = 197.0
        return engaged * buy_rate * avg_price
    if avenue == "affiliate":
        click_rate = 0.03
        conv_rate = 0.04
        avg_commission = 35.0
        return engaged * click_rate * conv_rate * avg_commission
    if avenue == "sponsor":
        cpm = 25.0
        placements_per_month = 4
        return (audience_size / 1000) * cpm * placements_per_month
    if avenue == "ad_revenue":
        rpm = 6.0
        views_per_month = audience_size * 2.5
        return (views_per_month / 1000) * rpm
    if avenue == "licensing":
        deals_per_year = 2
        avg_deal = 10000.0
        return (deals_per_year * avg_deal) / 12
    if avenue == "community":
        join_rate = 0.008
        avg_monthly = 19.0
        return engaged * join_rate * avg_monthly
    if avenue == "ecommerce":
        buy_rate = 0.01
        avg_order = 42.0
        return engaged * buy_rate * avg_order

    return existing_revenue if existing_revenue else 0.0


def prioritize_revenue_avenues(
    current_avenues: dict[str, dict],
    audience_size: int,
    audience_engagement_rate: float,
    niche: str,
    monthly_content_capacity: int,
    operator_skill_level: str,
) -> list[AvenueRecommendation]:
    """Rank all revenue avenues by expected ROI for this specific creator/brand.

    Scoring algorithm:
    1. Opportunity score based on audience fit, niche, and scale
    2. Operator capability filter
    3. ROI-weighted ranking: expected_revenue * margin * scalability / effort
    4. Portfolio diversification bonus
    5. Cross-avenue synergy multipliers
    """

    operator_level = _SKILL_LEVEL_NUMERIC.get(operator_skill_level, 2)
    niche_lower = niche.lower()
    niche_boosts = _NICHE_AFFINITY.get(niche_lower, {})
    active_avenues = set(current_avenues.keys())

    scored: list[tuple[str, float, float, str]] = []

    for avenue, profile in REVENUE_AVENUE_PROFILES.items():
        required_level = _SKILL_LEVEL_NUMERIC.get(_SKILL_REQUIREMENTS.get(avenue, "intermediate"), 2)
        if operator_level < required_level - 1:
            continue

        existing = current_avenues.get(avenue, {})
        existing_rev = float(existing.get("revenue", 0))
        growth_rate = float(existing.get("growth_rate", 0))

        estimated_rev = _estimate_avenue_revenue(
            avenue, profile, audience_size, audience_engagement_rate,
            existing_rev, growth_rate,
        )
        if existing_rev > 0:
            estimated_rev = max(estimated_rev, existing_rev * (1 + growth_rate))

        margin = float(profile["avg_margin"])
        scalability = float(profile["scalability"])
        effort_num = _EFFORT_NUMERIC.get(profile["setup_effort"], 2.0)

        content_capacity_factor = 1.0
        if effort_num >= 3.0 and monthly_content_capacity < 10:
            content_capacity_factor = 0.7
        elif effort_num >= 2.0 and monthly_content_capacity < 5:
            content_capacity_factor = 0.6

        niche_mult = niche_boosts.get(avenue, 1.0)

        base_score = (estimated_rev * margin * scalability) / max(effort_num, 0.5)
        base_score *= content_capacity_factor * niche_mult

        if profile["recurring"]:
            base_score *= 1.25

        ltv_mult = float(profile["ltv_multiple"])
        if ltv_mult > 12:
            base_score *= 1.0 + (ltv_mult - 12) / 48

        synergy_bonus = 0.0
        for existing_av in active_avenues:
            synergy = _SYNERGY_PAIRS.get((avenue, existing_av), 0.0)
            synergy_bonus += synergy
        base_score *= (1.0 + synergy_bonus)

        concentration_penalty = 0.0
        if avenue in active_avenues and len(active_avenues) == 1:
            concentration_penalty = 0.0
        elif avenue not in active_avenues and len(active_avenues) >= 4:
            base_score *= 0.85
        if avenue in active_avenues:
            total_rev = sum(float(v.get("revenue", 0)) for v in current_avenues.values())
            if total_rev > 0:
                share = existing_rev / total_rev
                if share > 0.70:
                    concentration_penalty = 0.15
                elif share > 0.50:
                    concentration_penalty = 0.08
        base_score *= (1.0 - concentration_penalty)

        skill_gap = max(0, required_level - operator_level)
        if skill_gap > 0:
            base_score *= (1.0 - skill_gap * 0.25)

        ttr = float(profile["time_to_revenue_months"])
        time_label = (
            "immediate" if ttr == 0
            else f"{ttr:.0f} month{'s' if ttr != 1 else ''}" if ttr <= 2
            else f"{ttr:.0f} months"
        )

        reasoning_parts = []
        if avenue in active_avenues:
            reasoning_parts.append(f"Already active with ${existing_rev:,.0f}/mo revenue")
            if growth_rate > 0.10:
                reasoning_parts.append(f"growing at {growth_rate:.0%}")
        else:
            reasoning_parts.append("New opportunity")

        if niche_mult > 1.0:
            reasoning_parts.append(f"strong niche fit for {niche} ({niche_mult:.0%} boost)")
        if synergy_bonus > 0:
            reasoning_parts.append(f"synergizes with existing avenues (+{synergy_bonus:.0%})")
        if profile["recurring"]:
            reasoning_parts.append("recurring revenue compounds over time")
        if ltv_mult > 12:
            reasoning_parts.append(f"high LTV multiple ({ltv_mult}x)")
        if scalability > 0.85:
            reasoning_parts.append("highly scalable")
        if concentration_penalty > 0:
            reasoning_parts.append("slight penalty for over-concentration")

        reasoning = "; ".join(reasoning_parts) + "."

        scored.append((avenue, base_score, estimated_rev, reasoning))

    scored.sort(key=lambda x: -x[1])

    recommendations: list[AvenueRecommendation] = []
    for rank, (avenue, score, est_rev, reasoning) in enumerate(scored, 1):
        profile = REVENUE_AVENUE_PROFILES[avenue]
        margin = float(profile["avg_margin"])
        recommendations.append(AvenueRecommendation(
            avenue=avenue,
            priority_rank=rank,
            composite_score=round(score, 2),
            expected_monthly_revenue=round(est_rev, 2),
            expected_annual_revenue=round(est_rev * 12, 2),
            margin=margin,
            time_to_revenue=f"{profile['time_to_revenue_months']} months" if profile["time_to_revenue_months"] > 0 else "immediate",
            effort_level=profile["setup_effort"],
            reasoning=reasoning,
            next_steps=_AVENUE_NEXT_STEPS.get(avenue, []),
            dependencies=_AVENUE_DEPENDENCIES.get(avenue, []),
        ))

    return recommendations


# ══════════════════════════════════════════════════════════════════════════════
# 7. UNIFIED REVENUE INTELLIGENCE REPORT
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class RevenueIntelligenceReport:
    """Top-level output combining all engines into a single actionable report."""
    generated_at: str
    saas_metrics: Optional[SaaSMetrics] = None
    churn_analysis: Optional[dict] = None
    expansion_opportunities: list[ExpansionOpportunity] = field(default_factory=list)
    pricing_recommendations: list[PricingRecommendation] = field(default_factory=list)
    cohort_analysis: list[CohortMetrics] = field(default_factory=list)
    revenue_projections: list[dict] = field(default_factory=list)
    avenue_recommendations: list[AvenueRecommendation] = field(default_factory=list)
    top_actions: list[dict] = field(default_factory=list)
    health_grade: str = "B"
    health_score: float = 0.0


def _grade_health(score: float) -> str:
    if score >= 90:
        return "A+"
    if score >= 85:
        return "A"
    if score >= 80:
        return "A-"
    if score >= 75:
        return "B+"
    if score >= 70:
        return "B"
    if score >= 65:
        return "B-"
    if score >= 60:
        return "C+"
    if score >= 55:
        return "C"
    if score >= 50:
        return "C-"
    if score >= 40:
        return "D"
    return "F"


def generate_revenue_intelligence_report(
    subscriptions: list[dict],
    customers: list[CustomerHealthSignals],
    plan_ladder: list[dict],
    usage_data: list[dict],
    price_history: list[dict],
    pricing_segments: list[dict],
    cost_structure: dict,
    current_avenues: dict[str, dict],
    audience_size: int = 10000,
    audience_engagement_rate: float = 0.05,
    niche: str = "tech",
    monthly_content_capacity: int = 20,
    operator_skill_level: str = "advanced",
    period_start: str = "",
    period_end: str = "",
    prior_period_sales_spend: float = 0.0,
    total_costs: float = 0.0,
    cohort_granularity: str = "monthly",
    target_margin: float = 0.80,
    projection_months: int = 24,
) -> RevenueIntelligenceReport:
    """Run every engine and compile a unified revenue intelligence report."""

    now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    saas_metrics = None
    if subscriptions and period_start and period_end:
        saas_metrics = compute_saas_metrics(
            subscriptions, period_start, period_end,
            prior_period_sales_spend, total_costs,
        )

    churn_analysis = None
    if customers:
        churn_analysis = batch_churn_analysis(customers)

    expansion_opps: list[ExpansionOpportunity] = []
    if customers and plan_ladder:
        expansion_opps = identify_expansion_opportunities(customers, plan_ladder, usage_data)

    pricing_recs: list[PricingRecommendation] = []
    if pricing_segments:
        pricing_recs = optimize_pricing_tiers(pricing_segments, cost_structure, target_margin)

    cohorts: list[CohortMetrics] = []
    projections: list[dict] = []
    if subscriptions:
        cohorts = analyze_cohorts(subscriptions, cohort_granularity)
        if cohorts:
            latest_cohort = cohorts[-1]
            projections = project_cohort_revenue(latest_cohort, projection_months)

    avenue_recs: list[AvenueRecommendation] = []
    if current_avenues is not None:
        avenue_recs = prioritize_revenue_avenues(
            current_avenues, audience_size, audience_engagement_rate,
            niche, monthly_content_capacity, operator_skill_level,
        )

    top_actions: list[dict] = []

    if churn_analysis:
        crit_count = churn_analysis.get("tier_summary", {}).get("critical", {}).get("count", 0)
        crit_rev = churn_analysis.get("tier_summary", {}).get("critical", {}).get("revenue_at_risk", 0)
        if crit_count > 0:
            top_actions.append({
                "action": f"Address {crit_count} critical churn-risk customers (${crit_rev:,.0f} at risk)",
                "impact": "high",
                "category": "retention",
            })

    if expansion_opps:
        total_exp = sum(o.expected_value for o in expansion_opps[:10])
        top_actions.append({
            "action": f"Pursue top {min(10, len(expansion_opps))} expansion opportunities (${total_exp:,.0f} expected value)",
            "impact": "high",
            "category": "growth",
        })

    if pricing_recs:
        best_pricing = max(pricing_recs, key=lambda r: r.expected_revenue_impact, default=None)
        if best_pricing and best_pricing.expected_revenue_impact > 0:
            top_actions.append({
                "action": f"Adjust {best_pricing.segment} pricing to ${best_pricing.recommended_price:.2f} (+${best_pricing.expected_revenue_impact:,.0f} revenue)",
                "impact": "medium",
                "category": "pricing",
            })

    if avenue_recs:
        new_avs = [a for a in avenue_recs if a.avenue not in current_avenues]
        if new_avs:
            best_new = new_avs[0]
            top_actions.append({
                "action": f"Launch {best_new.avenue} revenue stream (est. ${best_new.expected_monthly_revenue:,.0f}/mo)",
                "impact": "medium",
                "category": "diversification",
            })

    health_score = 50.0
    if saas_metrics:
        if saas_metrics.net_revenue_retention >= 1.2:
            health_score += 15
        elif saas_metrics.net_revenue_retention >= 1.0:
            health_score += 10
        elif saas_metrics.net_revenue_retention >= 0.9:
            health_score += 5
        else:
            health_score -= 10

        if saas_metrics.quick_ratio >= 4:
            health_score += 10
        elif saas_metrics.quick_ratio >= 2:
            health_score += 5
        elif saas_metrics.quick_ratio < 1:
            health_score -= 10

        if saas_metrics.ltv_cac_ratio >= 3:
            health_score += 10
        elif saas_metrics.ltv_cac_ratio >= 1:
            health_score += 5

        if saas_metrics.rule_of_40_score >= 40:
            health_score += 10
        elif saas_metrics.rule_of_40_score >= 20:
            health_score += 5

        if saas_metrics.gross_churn_rate < 0.02:
            health_score += 5
        elif saas_metrics.gross_churn_rate > 0.10:
            health_score -= 10

    if churn_analysis:
        risk_dist = churn_analysis.get("risk_distribution", {})
        safe_pct = risk_dist.get("safe", 0) + risk_dist.get("low", 0)
        if safe_pct > 0.80:
            health_score += 10
        elif safe_pct > 0.60:
            health_score += 5
        elif safe_pct < 0.40:
            health_score -= 10

    health_score = _clamp(health_score, 0, 100)
    health_grade = _grade_health(health_score)

    return RevenueIntelligenceReport(
        generated_at=now_str,
        saas_metrics=saas_metrics,
        churn_analysis=churn_analysis,
        expansion_opportunities=expansion_opps,
        pricing_recommendations=pricing_recs,
        cohort_analysis=cohorts,
        revenue_projections=projections,
        avenue_recommendations=avenue_recs,
        top_actions=top_actions,
        health_grade=health_grade,
        health_score=round(health_score, 1),
    )
