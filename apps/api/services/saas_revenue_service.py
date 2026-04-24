"""SaaS & High-Ticket Revenue Service — bridges scoring engines to database."""
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.creator_revenue import CreatorRevenueOpportunity
from packages.db.models.publishing import PerformanceMetric
from packages.db.models.saas_metrics import (
    HighTicketDeal,
    ProductLaunch,
    Subscription,
    SubscriptionEvent,
)

logger = structlog.get_logger()

PIPELINE_STAGES = ["awareness", "interest", "consideration", "proposal", "negotiation", "closed_won", "closed_lost"]
STAGE_WEIGHTS = {"awareness": 0.05, "interest": 0.15, "consideration": 0.30, "proposal": 0.50, "negotiation": 0.75, "closed_won": 1.0, "closed_lost": 0.0}

REVENUE_AVENUES = [
    {"key": "saas_subscription", "label": "SaaS / Subscriptions", "type": "recurring", "setup_effort": "high", "time_to_revenue_days": 90},
    {"key": "high_ticket_consulting", "label": "High-Ticket Consulting", "type": "one_time", "setup_effort": "medium", "time_to_revenue_days": 30},
    {"key": "digital_products", "label": "Digital Products / Courses", "type": "mixed", "setup_effort": "high", "time_to_revenue_days": 60},
    {"key": "affiliate", "label": "Affiliate Revenue", "type": "recurring", "setup_effort": "low", "time_to_revenue_days": 14},
    {"key": "sponsorships", "label": "Sponsorships / Brand Deals", "type": "one_time", "setup_effort": "medium", "time_to_revenue_days": 30},
    {"key": "ad_revenue", "label": "Ad Revenue (AdSense / RPM)", "type": "recurring", "setup_effort": "low", "time_to_revenue_days": 7},
    {"key": "community_membership", "label": "Community / Membership", "type": "recurring", "setup_effort": "medium", "time_to_revenue_days": 45},
    {"key": "ugc_services", "label": "UGC & Creative Services", "type": "one_time", "setup_effort": "low", "time_to_revenue_days": 14},
    {"key": "licensing", "label": "Licensing / Syndication", "type": "recurring", "setup_effort": "medium", "time_to_revenue_days": 60},
    {"key": "live_events", "label": "Live Events / Workshops", "type": "one_time", "setup_effort": "high", "time_to_revenue_days": 45},
]


async def get_saas_metrics(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    """Compute current SaaS metrics from active subscriptions and events."""
    active_subs = (
        await db.execute(
            select(Subscription).where(
                Subscription.brand_id == brand_id,
                Subscription.status.in_(["active", "past_due", "trial"]),
                Subscription.is_active.is_(True),
            )
        )
    ).scalars().all()

    total_mrr = sum(s.mrr for s in active_subs)
    arr = total_mrr * 12

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    recent_events = (
        await db.execute(
            select(SubscriptionEvent).where(
                SubscriptionEvent.brand_id == brand_id,
                SubscriptionEvent.event_at >= thirty_days_ago,
                SubscriptionEvent.is_active.is_(True),
            )
        )
    ).scalars().all()

    new_mrr = sum(e.new_mrr for e in recent_events if e.event_type == "new")
    churned_mrr = sum(abs(e.mrr_delta) for e in recent_events if e.event_type == "churn")
    expansion_mrr = sum(e.mrr_delta for e in recent_events if e.event_type == "upgrade" and e.mrr_delta > 0)
    contraction_mrr = sum(abs(e.mrr_delta) for e in recent_events if e.event_type == "downgrade")
    net_new = new_mrr + expansion_mrr - churned_mrr - contraction_mrr

    prev_mrr = total_mrr - net_new if total_mrr - net_new > 0 else total_mrr
    gross_churn_rate = churned_mrr / prev_mrr if prev_mrr > 0 else 0.0
    nrr = (prev_mrr + expansion_mrr - churned_mrr - contraction_mrr) / prev_mrr if prev_mrr > 0 else 1.0

    new_count = len([e for e in recent_events if e.event_type == "new"])
    churn_count = len([e for e in recent_events if e.event_type == "churn"])

    avg_mrr = total_mrr / len(active_subs) if active_subs else 0
    avg_lifespan_months = 1.0 / gross_churn_rate if gross_churn_rate > 0 else 36.0
    ltv = avg_mrr * avg_lifespan_months

    quick_ratio = (new_mrr + expansion_mrr) / (churned_mrr + contraction_mrr) if (churned_mrr + contraction_mrr) > 0 else 10.0

    plan_breakdown = defaultdict(lambda: {"count": 0, "mrr": 0.0})
    for s in active_subs:
        plan_breakdown[s.plan_name]["count"] += 1
        plan_breakdown[s.plan_name]["mrr"] += s.mrr

    return {
        "mrr": round(total_mrr, 2),
        "arr": round(arr, 2),
        "net_new_mrr": round(net_new, 2),
        "new_mrr": round(new_mrr, 2),
        "churned_mrr": round(churned_mrr, 2),
        "expansion_mrr": round(expansion_mrr, 2),
        "contraction_mrr": round(contraction_mrr, 2),
        "active_subscriptions": len(active_subs),
        "new_subscriptions_30d": new_count,
        "churned_subscriptions_30d": churn_count,
        "gross_churn_rate": round(gross_churn_rate, 4),
        "net_revenue_retention": round(nrr, 4),
        "ltv": round(ltv, 2),
        "quick_ratio": round(min(quick_ratio, 10.0), 2),
        "avg_mrr_per_customer": round(avg_mrr, 2),
        "plan_breakdown": dict(plan_breakdown),
        "status": "active" if active_subs else "no_subscriptions",
    }


async def get_churn_analysis(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    """Run churn prediction on all active subscribers."""
    active_subs = (
        await db.execute(
            select(Subscription).where(
                Subscription.brand_id == brand_id,
                Subscription.status.in_(["active", "past_due", "trial"]),
                Subscription.is_active.is_(True),
            )
        )
    ).scalars().all()

    if not active_subs:
        return {"status": "no_subscriptions", "at_risk": [], "summary": {}}

    now = datetime.now(timezone.utc)
    at_risk = []
    risk_buckets = {"critical": 0, "high": 0, "medium": 0, "low": 0}

    for sub in active_subs:
        signals = []
        risk_score = 0.0

        if sub.status == "past_due":
            risk_score += 0.4
            signals.append("payment_past_due")

        tenure_days = (now - sub.started_at).days if sub.started_at else 0
        if tenure_days < 30:
            risk_score += 0.15
            signals.append("new_subscriber_risk")

        if sub.trial_ends_at and sub.trial_ends_at > now:
            days_left = (sub.trial_ends_at - now).days
            if days_left < 3:
                risk_score += 0.3
                signals.append("trial_expiring_soon")

        recent_events = (
            await db.execute(
                select(func.count()).select_from(SubscriptionEvent).where(
                    SubscriptionEvent.subscription_id == sub.id,
                    SubscriptionEvent.event_type == "payment_failed",
                    SubscriptionEvent.event_at >= now - timedelta(days=30),
                )
            )
        ).scalar() or 0

        if recent_events > 0:
            risk_score += 0.2 * min(recent_events, 3)
            signals.append(f"payment_failures_{recent_events}")

        risk_score = min(risk_score, 1.0)

        if risk_score >= 0.6:
            bucket = "critical"
        elif risk_score >= 0.4:
            bucket = "high"
        elif risk_score >= 0.2:
            bucket = "medium"
        else:
            bucket = "low"

        risk_buckets[bucket] += 1

        if risk_score >= 0.2:
            at_risk.append({
                "subscription_id": str(sub.id),
                "customer_id": sub.customer_id,
                "customer_name": sub.customer_name,
                "plan_name": sub.plan_name,
                "mrr": sub.mrr,
                "risk_score": round(risk_score, 3),
                "risk_level": bucket,
                "signals": signals,
                "tenure_days": tenure_days,
                "recommended_action": _churn_recommendation(bucket, signals),
            })

    at_risk.sort(key=lambda x: x["risk_score"], reverse=True)
    mrr_at_risk = sum(r["mrr"] for r in at_risk)

    return {
        "status": "analyzed",
        "total_analyzed": len(active_subs),
        "at_risk_count": len(at_risk),
        "mrr_at_risk": round(mrr_at_risk, 2),
        "risk_distribution": risk_buckets,
        "at_risk": at_risk[:50],
    }


def _churn_recommendation(level: str, signals: list[str]) -> str:
    if "payment_past_due" in signals or any("payment_failures" in s for s in signals):
        return "Send dunning email sequence and offer payment method update"
    if "trial_expiring_soon" in signals:
        return "Trigger conversion sequence with limited-time offer"
    if level == "critical":
        return "Schedule personal outreach call within 24 hours"
    if level == "high":
        return "Send retention offer (discount or feature unlock)"
    return "Monitor engagement patterns"


async def get_expansion_opportunities(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    """Identify upsell/cross-sell opportunities from active subscribers."""
    active_subs = (
        await db.execute(
            select(Subscription).where(
                Subscription.brand_id == brand_id,
                Subscription.status == "active",
                Subscription.is_active.is_(True),
            )
        )
    ).scalars().all()

    if not active_subs:
        return {"status": "no_subscriptions", "opportunities": []}

    now = datetime.now(timezone.utc)
    opportunities = []

    tier_order = ["free", "starter", "standard", "pro", "enterprise"]

    for sub in active_subs:
        tenure_days = (now - sub.started_at).days if sub.started_at else 0
        current_tier_idx = next((i for i, t in enumerate(tier_order) if t == sub.plan_tier.lower()), 1)

        opp_score = 0.0
        opp_type = None
        expected_delta = 0.0

        if tenure_days >= 60 and current_tier_idx < len(tier_order) - 1:
            opp_score = min(0.3 + (tenure_days / 365) * 0.3, 0.8)
            opp_type = "tier_upgrade"
            expected_delta = sub.mrr * 0.5

        if sub.billing_interval == "monthly" and tenure_days >= 90:
            annual_score = 0.4 + (tenure_days / 365) * 0.2
            if annual_score > opp_score:
                opp_score = annual_score
                opp_type = "annual_conversion"
                expected_delta = sub.mrr * 2

        if opp_score >= 0.25:
            opportunities.append({
                "subscription_id": str(sub.id),
                "customer_id": sub.customer_id,
                "customer_name": sub.customer_name,
                "current_plan": sub.plan_name,
                "current_mrr": sub.mrr,
                "opportunity_type": opp_type,
                "expected_mrr_delta": round(expected_delta, 2),
                "probability": round(opp_score, 3),
                "expected_value": round(expected_delta * opp_score * 12, 2),
                "tenure_days": tenure_days,
            })

    opportunities.sort(key=lambda x: x["expected_value"], reverse=True)
    total_expansion = sum(o["expected_value"] for o in opportunities)

    return {
        "status": "analyzed",
        "total_opportunities": len(opportunities),
        "total_expected_expansion": round(total_expansion, 2),
        "opportunities": opportunities[:30],
    }


async def get_pipeline_analysis(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    """Analyze high-ticket deal pipeline with velocity and bottleneck detection."""
    deals = (
        await db.execute(
            select(HighTicketDeal).where(
                HighTicketDeal.brand_id == brand_id,
                HighTicketDeal.is_active.is_(True),
            )
        )
    ).scalars().all()

    if not deals:
        return {"status": "empty_pipeline", "stages": {}, "deals": []}

    now = datetime.now(timezone.utc)
    stage_data = {}
    for stage in PIPELINE_STAGES:
        stage_deals = [d for d in deals if d.stage == stage]
        stage_data[stage] = {
            "count": len(stage_deals),
            "total_value": round(sum(d.deal_value for d in stage_deals), 2),
            "weighted_value": round(sum(d.deal_value * STAGE_WEIGHTS.get(stage, 0) for d in stage_deals), 2),
            "avg_days_in_stage": round(
                sum((now - d.last_activity_at).days for d in stage_deals) / max(len(stage_deals), 1), 1
            ),
        }

    open_deals = [d for d in deals if d.stage not in ("closed_won", "closed_lost")]
    weighted_pipeline = sum(d.deal_value * STAGE_WEIGHTS.get(d.stage, 0) for d in open_deals)
    total_pipeline = sum(d.deal_value for d in open_deals)

    bottleneck_stage = max(
        [(s, data) for s, data in stage_data.items() if s not in ("closed_won", "closed_lost") and data["count"] > 0],
        key=lambda x: x[1]["avg_days_in_stage"],
        default=(None, None),
    )

    thirty_days_ago = now - timedelta(days=30)
    won_30d = [d for d in deals if d.stage == "closed_won" and d.last_activity_at >= thirty_days_ago]
    velocity_30d = sum(d.deal_value for d in won_30d)

    deal_list = []
    for d in open_deals:
        stale_days = (now - d.last_activity_at).days
        deal_list.append({
            "id": str(d.id),
            "customer_name": d.customer_name,
            "deal_value": d.deal_value,
            "stage": d.stage,
            "product_type": d.product_type,
            "probability": d.probability,
            "weighted_value": round(d.deal_value * d.probability, 2),
            "score": d.score,
            "days_stale": stale_days,
            "interactions": d.interactions,
            "expected_close": d.expected_close_date.isoformat() if d.expected_close_date else None,
            "needs_attention": stale_days > 7,
        })

    deal_list.sort(key=lambda x: x["weighted_value"], reverse=True)

    return {
        "status": "analyzed",
        "summary": {
            "total_open_deals": len(open_deals),
            "total_pipeline_value": round(total_pipeline, 2),
            "weighted_pipeline_value": round(weighted_pipeline, 2),
            "velocity_30d": round(velocity_30d, 2),
            "avg_deal_size": round(total_pipeline / max(len(open_deals), 1), 2),
            "win_rate_30d": round(len(won_30d) / max(len([d for d in deals if d.last_activity_at >= thirty_days_ago]), 1), 3),
        },
        "bottleneck": {
            "stage": bottleneck_stage[0],
            "avg_days": bottleneck_stage[1]["avg_days_in_stage"] if bottleneck_stage[1] else 0,
            "deals_stuck": bottleneck_stage[1]["count"] if bottleneck_stage[1] else 0,
        } if bottleneck_stage[0] else None,
        "stages": stage_data,
        "deals": deal_list[:50],
    }


async def get_revenue_avenue_rankings(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    """Rank all revenue avenues by expected ROI, effort, and current performance."""
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    saas_mrr = (
        await db.execute(
            select(func.coalesce(func.sum(Subscription.mrr), 0.0)).where(
                Subscription.brand_id == brand_id,
                Subscription.status.in_(["active", "past_due"]),
                Subscription.is_active.is_(True),
            )
        )
    ).scalar() or 0.0

    pipeline_value = (
        await db.execute(
            select(func.coalesce(func.sum(HighTicketDeal.deal_value * HighTicketDeal.probability), 0.0)).where(
                HighTicketDeal.brand_id == brand_id,
                HighTicketDeal.stage.notin_(["closed_won", "closed_lost"]),
                HighTicketDeal.is_active.is_(True),
            )
        )
    ).scalar() or 0.0

    launch_revenue = (
        await db.execute(
            select(func.coalesce(func.sum(ProductLaunch.total_revenue), 0.0)).where(
                ProductLaunch.brand_id == brand_id,
                ProductLaunch.is_active.is_(True),
            )
        )
    ).scalar() or 0.0

    ad_revenue_30d = (
        await db.execute(
            select(func.coalesce(func.sum(PerformanceMetric.revenue), 0.0)).where(
                PerformanceMetric.brand_id == brand_id,
                PerformanceMetric.measured_at >= thirty_days_ago,
            )
        )
    ).scalar() or 0.0

    opportunity_data = (
        await db.execute(
            select(
                CreatorRevenueOpportunity.avenue_type,
                func.sum(CreatorRevenueOpportunity.expected_value).label("total_expected"),
                func.avg(CreatorRevenueOpportunity.expected_margin).label("avg_margin"),
                func.count().label("cnt"),
            ).where(
                CreatorRevenueOpportunity.brand_id == brand_id,
                CreatorRevenueOpportunity.status == "active",
                CreatorRevenueOpportunity.is_active.is_(True),
            ).group_by(CreatorRevenueOpportunity.avenue_type)
        )
    ).all()

    opp_map = {r.avenue_type: {"expected": float(r.total_expected), "margin": float(r.avg_margin), "count": r.cnt} for r in opportunity_data}

    revenue_map = {
        "saas_subscription": float(saas_mrr),
        "high_ticket_consulting": float(pipeline_value) / 12,
        "digital_products": float(launch_revenue) / max((now - thirty_days_ago).days, 1) * 30,
        "ad_revenue": float(ad_revenue_30d),
    }

    rankings = []
    for avenue in REVENUE_AVENUES:
        key = avenue["key"]
        current_monthly = revenue_map.get(key, 0.0)
        opp = opp_map.get(key, {})
        potential = opp.get("expected", current_monthly * 1.5) if opp else current_monthly * 1.5
        margin = opp.get("margin", 0.7)

        effort_multiplier = {"low": 1.0, "medium": 0.7, "high": 0.4}[avenue["setup_effort"]]
        time_decay = 1.0 / (1.0 + avenue["time_to_revenue_days"] / 90)
        roi_score = (potential * margin * effort_multiplier * time_decay)
        roi_score = round(min(roi_score / 1000, 100), 1) if roi_score > 0 else 0

        rankings.append({
            "avenue_key": key,
            "label": avenue["label"],
            "type": avenue["type"],
            "current_monthly_revenue": round(current_monthly, 2),
            "potential_monthly_revenue": round(potential, 2),
            "margin": round(margin, 3),
            "setup_effort": avenue["setup_effort"],
            "time_to_revenue_days": avenue["time_to_revenue_days"],
            "roi_score": roi_score,
            "active_opportunities": opp.get("count", 0),
        })

    rankings.sort(key=lambda x: x["roi_score"], reverse=True)

    for i, r in enumerate(rankings):
        if i < 3:
            r["tier"] = "gold"
        elif i < 6:
            r["tier"] = "silver"
        else:
            r["tier"] = "standard"

    return {
        "status": "ranked",
        "total_avenues": len(rankings),
        "rankings": rankings,
    }


async def get_cohort_analysis(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    """Run monthly cohort retention analysis on subscriptions."""
    subs = (
        await db.execute(
            select(Subscription).where(
                Subscription.brand_id == brand_id,
                Subscription.is_active.is_(True),
            )
        )
    ).scalars().all()

    if not subs:
        return {"status": "no_data", "cohorts": []}

    now = datetime.now(timezone.utc)
    cohort_map: dict[str, list] = defaultdict(list)

    for s in subs:
        if s.started_at:
            cohort_key = s.started_at.strftime("%Y-%m")
            cohort_map[cohort_key].append(s)

    cohorts = []
    for cohort_month in sorted(cohort_map.keys(), reverse=True)[:12]:
        members = cohort_map[cohort_month]
        initial_count = len(members)
        initial_mrr = sum(m.mrr for m in members)
        still_active = [m for m in members if m.status in ("active", "past_due")]
        current_mrr = sum(m.mrr for m in still_active)

        retention_rate = len(still_active) / initial_count if initial_count > 0 else 0
        revenue_retention = current_mrr / initial_mrr if initial_mrr > 0 else 0

        months_since = max(
            (now.year - int(cohort_month[:4])) * 12 + (now.month - int(cohort_month[5:])),
            1,
        )

        cohorts.append({
            "cohort_month": cohort_month,
            "initial_count": initial_count,
            "initial_mrr": round(initial_mrr, 2),
            "current_active": len(still_active),
            "current_mrr": round(current_mrr, 2),
            "retention_rate": round(retention_rate, 4),
            "revenue_retention": round(revenue_retention, 4),
            "months_since_start": months_since,
        })

    return {
        "status": "analyzed",
        "total_cohorts": len(cohorts),
        "cohorts": cohorts,
    }


async def get_revenue_stack(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    """Compute full revenue stack with diversification scoring."""
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    saas_mrr = (
        await db.execute(
            select(func.coalesce(func.sum(Subscription.mrr), 0.0)).where(
                Subscription.brand_id == brand_id,
                Subscription.status.in_(["active", "past_due"]),
                Subscription.is_active.is_(True),
            )
        )
    ).scalar() or 0.0

    pipeline_weighted = (
        await db.execute(
            select(func.coalesce(func.sum(HighTicketDeal.deal_value * HighTicketDeal.probability), 0.0)).where(
                HighTicketDeal.brand_id == brand_id,
                HighTicketDeal.stage.notin_(["closed_won", "closed_lost"]),
                HighTicketDeal.is_active.is_(True),
            )
        )
    ).scalar() or 0.0

    launch_rev = (
        await db.execute(
            select(func.coalesce(func.sum(ProductLaunch.total_revenue), 0.0)).where(
                ProductLaunch.brand_id == brand_id,
                ProductLaunch.is_active.is_(True),
            )
        )
    ).scalar() or 0.0

    ad_rev = (
        await db.execute(
            select(func.coalesce(func.sum(PerformanceMetric.revenue), 0.0)).where(
                PerformanceMetric.brand_id == brand_id,
                PerformanceMetric.measured_at >= thirty_days_ago,
            )
        )
    ).scalar() or 0.0

    opp_rows = (
        await db.execute(
            select(
                CreatorRevenueOpportunity.avenue_type,
                func.sum(CreatorRevenueOpportunity.expected_value).label("total"),
            ).where(
                CreatorRevenueOpportunity.brand_id == brand_id,
                CreatorRevenueOpportunity.status == "active",
                CreatorRevenueOpportunity.is_active.is_(True),
            ).group_by(CreatorRevenueOpportunity.avenue_type)
        )
    ).all()
    opp_rev = {r.avenue_type: float(r.total) for r in opp_rows}

    stack = {
        "saas_subscription": {"monthly": round(float(saas_mrr), 2), "type": "recurring"},
        "high_ticket_consulting": {"monthly": round(float(pipeline_weighted) / 12, 2), "type": "one_time"},
        "digital_products": {"monthly": round(float(launch_rev) / 6, 2), "type": "mixed"},
        "ad_revenue": {"monthly": round(float(ad_rev), 2), "type": "recurring"},
    }

    for avenue_type, total in opp_rev.items():
        if avenue_type not in stack:
            stack[avenue_type] = {"monthly": round(total / 12, 2), "type": "mixed"}

    total_monthly = sum(v["monthly"] for v in stack.values())
    recurring_monthly = sum(v["monthly"] for v in stack.values() if v["type"] == "recurring")
    one_time_monthly = sum(v["monthly"] for v in stack.values() if v["type"] in ("one_time", "mixed"))

    active_streams = [k for k, v in stack.items() if v["monthly"] > 0]
    n = len(active_streams)

    if n <= 1:
        diversification_score = 0.0
    else:
        shares = [stack[k]["monthly"] / total_monthly for k in active_streams] if total_monthly > 0 else []
        hhi = sum(s ** 2 for s in shares)
        diversification_score = round(1.0 - hhi, 3) if shares else 0.0

    max_share = max((v["monthly"] / total_monthly for v in stack.values() if total_monthly > 0), default=0)
    vulnerability = "critical" if max_share > 0.8 else "high" if max_share > 0.6 else "moderate" if max_share > 0.4 else "healthy"

    return {
        "status": "computed",
        "total_monthly_revenue": round(total_monthly, 2),
        "recurring_monthly": round(recurring_monthly, 2),
        "one_time_monthly": round(one_time_monthly, 2),
        "recurring_pct": round(recurring_monthly / max(total_monthly, 1) * 100, 1),
        "active_streams": n,
        "diversification_score": diversification_score,
        "vulnerability": vulnerability,
        "stack": stack,
    }


async def get_launch_analysis(db: AsyncSession, brand_id: uuid.UUID, launch_id: uuid.UUID) -> dict:
    """Analyze a specific product launch funnel and performance."""
    launch = (
        await db.execute(
            select(ProductLaunch).where(
                ProductLaunch.id == launch_id,
                ProductLaunch.brand_id == brand_id,
                ProductLaunch.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()

    if not launch:
        return {"status": "not_found"}

    conversion_rate = launch.sales / max(launch.registrations, 1)
    roas = launch.total_revenue / max(launch.ad_spend, 1)
    revenue_per_sale = launch.total_revenue / max(launch.sales, 1)
    cost_per_registration = launch.ad_spend / max(launch.registrations, 1)

    now = datetime.now(timezone.utc)
    days_since_launch = (now - launch.launch_date).days if launch.launch_date else 0
    daily_run_rate = launch.total_revenue / max(days_since_launch, 1)

    health = "strong"
    issues = []
    if conversion_rate < 0.02:
        health = "weak"
        issues.append("Conversion rate below 2% — review offer positioning and urgency triggers")
    elif conversion_rate < 0.05:
        health = "moderate"
        issues.append("Conversion rate below 5% — test price point and guarantee")

    if roas < 2.0 and launch.ad_spend > 0:
        health = "weak" if health != "weak" else health
        issues.append(f"ROAS of {roas:.1f}x is below 2x target — optimize ad creative or pause low performers")

    if launch.registrations > 0 and launch.sales == 0 and days_since_launch > 3:
        health = "critical"
        issues.append("Zero sales with registrations — cart page or checkout may have issues")

    return {
        "status": "analyzed",
        "launch": {
            "id": str(launch.id),
            "product_name": launch.product_name,
            "product_type": launch.product_type,
            "price": launch.price,
            "launch_phase": launch.launch_phase,
            "launch_date": launch.launch_date.isoformat() if launch.launch_date else None,
        },
        "metrics": {
            "registrations": launch.registrations,
            "sales": launch.sales,
            "total_revenue": round(launch.total_revenue, 2),
            "ad_spend": round(launch.ad_spend, 2),
            "conversion_rate": round(conversion_rate, 4),
            "roas": round(roas, 2),
            "revenue_per_sale": round(revenue_per_sale, 2),
            "cost_per_registration": round(cost_per_registration, 2),
            "daily_run_rate": round(daily_run_rate, 2),
            "days_since_launch": days_since_launch,
        },
        "health": health,
        "issues": issues,
        "funnel_metrics": launch.funnel_metrics_json or {},
    }


async def score_pipeline_deals(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    """Score all open pipeline deals using engagement, recency, and value signals."""
    deals = (
        await db.execute(
            select(HighTicketDeal).where(
                HighTicketDeal.brand_id == brand_id,
                HighTicketDeal.stage.notin_(["closed_won", "closed_lost"]),
                HighTicketDeal.is_active.is_(True),
            )
        )
    ).scalars().all()

    if not deals:
        return {"status": "empty_pipeline", "scored": []}

    now = datetime.now(timezone.utc)
    scored = []

    for d in deals:
        stale_days = (now - d.last_activity_at).days
        recency_score = max(0, 1.0 - stale_days / 30)
        interaction_score = min(d.interactions / 10, 1.0)
        stage_score = STAGE_WEIGHTS.get(d.stage, 0.1)
        value_score = 0.75 if d.deal_value > 0 else 0.0  # Any deal has value — no fixed ceiling

        composite = round(
            recency_score * 0.3 + interaction_score * 0.2 + stage_score * 0.3 + value_score * 0.2,
            3,
        )

        d.score = composite
        scored.append({
            "deal_id": str(d.id),
            "customer_name": d.customer_name,
            "deal_value": d.deal_value,
            "stage": d.stage,
            "score": composite,
            "recency_score": round(recency_score, 3),
            "interaction_score": round(interaction_score, 3),
            "stage_score": round(stage_score, 3),
            "value_score": round(value_score, 3),
            "recommended_action": _deal_action(composite, stale_days, d.stage),
        })

    await db.flush()
    scored.sort(key=lambda x: x["score"], reverse=True)

    return {"status": "scored", "total": len(scored), "scored": scored}


def _deal_action(score: float, stale_days: int, stage: str) -> str:
    if stale_days > 14:
        return "Re-engage: send value-add follow-up or case study"
    if stage == "proposal" and score > 0.5:
        return "Push for close: schedule decision call"
    if stage == "negotiation":
        return "Finalize terms: send agreement for review"
    if score < 0.3:
        return "Qualify: verify budget and timeline"
    return "Nurture: share relevant content"


async def plan_launch(db: AsyncSession, brand_id: uuid.UUID, launch_id: uuid.UUID) -> dict:
    """Generate a phased launch plan for a product launch."""
    launch = (
        await db.execute(
            select(ProductLaunch).where(
                ProductLaunch.id == launch_id,
                ProductLaunch.brand_id == brand_id,
                ProductLaunch.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()

    if not launch:
        return {"status": "not_found"}

    plan = {
        "planning": {
            "duration_days": 14,
            "tasks": [
                "Define offer positioning and unique mechanism",
                "Build sales page wireframe",
                "Create lead magnet for list building",
                "Set up payment processing and delivery",
            ],
        },
        "pre_launch": {
            "duration_days": 21,
            "tasks": [
                "Run lead magnet ads to build waitlist",
                "Publish 3-5 authority content pieces",
                "Send email warm-up sequence (3 emails)",
                "Host free workshop or webinar for leads",
                "Collect testimonials and social proof",
            ],
        },
        "cart_open": {
            "duration_days": 5,
            "tasks": [
                "Send cart-open email with bonuses",
                "Publish launch video / live stream",
                "Daily email sequence with objection handling",
                "Run retargeting ads to engaged audience",
                "Fast-action bonus for first 24h buyers",
            ],
        },
        "cart_close": {
            "duration_days": 2,
            "tasks": [
                "48-hour final countdown sequence",
                "Last-chance bonuses email",
                "Live Q&A session",
                "Cart close deadline enforcement",
            ],
        },
        "post_launch": {
            "duration_days": 7,
            "tasks": [
                "Onboard new customers",
                "Collect launch debrief data",
                "Survey non-buyers for insights",
                "Repurpose launch content for evergreen",
                "Plan evergreen funnel conversion",
            ],
        },
    }

    launch.launch_plan_json = plan
    await db.flush()

    revenue_targets = {
        "conservative": round(launch.price * launch.registrations * 0.02, 2),
        "moderate": round(launch.price * launch.registrations * 0.05, 2),
        "optimistic": round(launch.price * launch.registrations * 0.10, 2),
    }

    return {
        "status": "planned",
        "launch_id": str(launch.id),
        "product_name": launch.product_name,
        "current_phase": launch.launch_phase,
        "plan": plan,
        "revenue_targets": revenue_targets,
        "total_timeline_days": sum(p["duration_days"] for p in plan.values()),
    }
