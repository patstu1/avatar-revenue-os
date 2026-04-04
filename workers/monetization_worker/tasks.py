"""Monetization Machine Worker — Scheduled tasks for the revenue machine."""
import asyncio
from datetime import datetime, timedelta, timezone

from celery import shared_task

from workers.base_task import TrackedTask
from packages.db.session import get_async_session_factory


def _run(coro):
    """Run an async coroutine from a synchronous Celery task."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Credit Replenishment
# ---------------------------------------------------------------------------
@shared_task(name="workers.monetization_worker.tasks.replenish_credits", base=TrackedTask)
def replenish_credits():
    """Monthly credit replenishment for all active plan subscriptions."""
    return _run(_do_replenish_credits())


async def _do_replenish_credits():
    from sqlalchemy import select
    from packages.db.models.monetization import PlanSubscription, CreditLedger, CreditTransaction

    factory = get_async_session_factory()
    async with factory() as db:
        subs = (await db.execute(
            select(PlanSubscription).where(
                PlanSubscription.is_active.is_(True),
                PlanSubscription.status == "active",
                PlanSubscription.plan_tier != "free",
            )
        )).scalars().all()

        replenished = 0
        for sub in subs:
            ledger = (await db.execute(
                select(CreditLedger).where(
                    CreditLedger.organization_id == sub.organization_id,
                    CreditLedger.is_active.is_(True),
                )
            )).scalar_one_or_none()

            if ledger and sub.included_credits > 0:
                ledger.total_credits += sub.included_credits
                ledger.remaining_credits += sub.included_credits

                db.add(CreditTransaction(
                    organization_id=sub.organization_id,
                    transaction_type="earn",
                    amount=sub.included_credits,
                    balance_after=ledger.remaining_credits,
                    description=f"Monthly replenishment: {sub.plan_name}",
                ))
                replenished += 1

        await db.commit()
    return {"replenished": replenished}


# ---------------------------------------------------------------------------
# Credit Exhaustion Check
# ---------------------------------------------------------------------------
@shared_task(name="workers.monetization_worker.tasks.check_credit_exhaustion", base=TrackedTask)
def check_credit_exhaustion():
    """Predict which orgs will exhaust credits and create alerts."""
    return _run(_do_check_credit_exhaustion())


async def _do_check_credit_exhaustion():
    from sqlalchemy import select
    from packages.db.models.monetization import CreditLedger, MonetizationTelemetryEvent

    factory = get_async_session_factory()
    async with factory() as db:
        ledgers = (await db.execute(
            select(CreditLedger).where(CreditLedger.is_active.is_(True))
        )).scalars().all()

        alerts_created = 0
        for ledger in ledgers:
            if ledger.total_credits == 0:
                continue

            utilization = (ledger.used_credits / ledger.total_credits) if ledger.total_credits else 0
            if utilization >= 0.80 or ledger.remaining_credits <= (ledger.replenishment_rate * 2):
                severity = "critical" if utilization >= 0.95 else "warning"
                db.add(MonetizationTelemetryEvent(
                    organization_id=ledger.organization_id,
                    user_id=None,
                    event_name=f"credit_exhaustion_{severity}",
                    event_value=utilization,
                    event_properties={
                        "remaining": ledger.remaining_credits,
                        "total": ledger.total_credits,
                        "utilization_pct": round(utilization * 100, 1),
                        "severity": severity,
                    },
                ))
                alerts_created += 1

        await db.commit()
    return {"ledgers_checked": len(ledgers), "alerts_created": alerts_created}


# ---------------------------------------------------------------------------
# Ascension Profiles
# ---------------------------------------------------------------------------
@shared_task(name="workers.monetization_worker.tasks.compute_ascension_profiles", base=TrackedTask)
def compute_ascension_profiles():
    """Compute upgrade-readiness profiles for all active organizations."""
    return _run(_do_compute_ascension_profiles())


async def _do_compute_ascension_profiles():
    from sqlalchemy import select, func as sa_func
    from packages.db.models.monetization import (
        PlanSubscription, CreditLedger, CreditTransaction, MonetizationTelemetryEvent,
    )

    factory = get_async_session_factory()
    async with factory() as db:
        subs = (await db.execute(
            select(PlanSubscription).where(
                PlanSubscription.is_active.is_(True),
                PlanSubscription.status == "active",
            )
        )).scalars().all()

        profiles_computed = 0
        for sub in subs:
            ledger = (await db.execute(
                select(CreditLedger).where(
                    CreditLedger.organization_id == sub.organization_id,
                    CreditLedger.is_active.is_(True),
                )
            )).scalar_one_or_none()

            recent_txn_count = (await db.execute(
                select(sa_func.count(CreditTransaction.id)).where(
                    CreditTransaction.organization_id == sub.organization_id,
                    CreditTransaction.transacted_at >= datetime.now(timezone.utc) - timedelta(days=30),
                )
            )).scalar() or 0

            utilization = (ledger.used_credits / ledger.total_credits) if ledger and ledger.total_credits else 0
            ascension_score = min(1.0, (utilization * 0.4) + (min(recent_txn_count, 100) / 100 * 0.3) + 0.3)

            if ascension_score >= 0.7:
                db.add(MonetizationTelemetryEvent(
                    organization_id=sub.organization_id,
                    user_id=None,
                    event_name="ascension_profile_computed",
                    event_value=ascension_score,
                    event_properties={
                        "current_tier": sub.plan_tier,
                        "utilization": round(utilization, 3),
                        "txn_velocity": recent_txn_count,
                        "ready_for_upgrade": ascension_score >= 0.85,
                    },
                ))
                profiles_computed += 1

        await db.commit()
    return {"subscriptions_analyzed": len(subs), "profiles_flagged": profiles_computed}


# ---------------------------------------------------------------------------
# Monetization Health
# ---------------------------------------------------------------------------
@shared_task(name="workers.monetization_worker.tasks.compute_monetization_health", base=TrackedTask)
def compute_monetization_health():
    """Compute aggregate monetization health metrics per organization."""
    return _run(_do_compute_monetization_health())


async def _do_compute_monetization_health():
    from sqlalchemy import select, func as sa_func
    from packages.db.models.monetization import (
        CreditLedger, CreditTransaction, PlanSubscription, MultiplicationEvent,
        MonetizationTelemetryEvent,
    )

    factory = get_async_session_factory()
    async with factory() as db:
        subs = (await db.execute(
            select(PlanSubscription).where(
                PlanSubscription.is_active.is_(True),
                PlanSubscription.status == "active",
            )
        )).scalars().all()

        computed = 0
        for sub in subs:
            org_id = sub.organization_id
            ledger = (await db.execute(
                select(CreditLedger).where(
                    CreditLedger.organization_id == org_id,
                    CreditLedger.is_active.is_(True),
                )
            )).scalar_one_or_none()

            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

            revenue_from_multiplications = (await db.execute(
                select(sa_func.coalesce(sa_func.sum(MultiplicationEvent.revenue), 0)).where(
                    MultiplicationEvent.organization_id == org_id,
                    MultiplicationEvent.converted.is_(True),
                    MultiplicationEvent.converted_at >= thirty_days_ago,
                )
            )).scalar() or 0.0

            spend_txns = (await db.execute(
                select(sa_func.coalesce(sa_func.sum(CreditTransaction.amount), 0)).where(
                    CreditTransaction.organization_id == org_id,
                    CreditTransaction.transaction_type == "spend",
                    CreditTransaction.transacted_at >= thirty_days_ago,
                )
            )).scalar() or 0

            credit_util = (ledger.used_credits / ledger.total_credits) if ledger and ledger.total_credits else 0
            health_score = min(1.0, credit_util * 0.3 + min(revenue_from_multiplications / 10000, 1.0) * 0.4 + 0.3)

            db.add(MonetizationTelemetryEvent(
                organization_id=org_id,
                user_id=None,
                event_name="monetization_health_snapshot",
                event_value=health_score,
                event_properties={
                    "credit_utilization": round(credit_util, 3),
                    "multiplication_revenue_30d": float(revenue_from_multiplications),
                    "credit_spend_30d": int(spend_txns),
                    "plan_tier": sub.plan_tier,
                },
            ))
            computed += 1

        await db.commit()
    return {"orgs_computed": computed}


# ---------------------------------------------------------------------------
# Multiplication Opportunity Scan
# ---------------------------------------------------------------------------
@shared_task(name="workers.monetization_worker.tasks.scan_multiplication_opportunities", base=TrackedTask)
def scan_multiplication_opportunities():
    """Scan all active users for premium upgrade / upsell moments."""
    return _run(_do_scan_multiplication_opportunities())


async def _do_scan_multiplication_opportunities():
    from sqlalchemy import select, func as sa_func
    from packages.db.models.monetization import (
        PlanSubscription, CreditLedger, MultiplicationEvent, MonetizationTelemetryEvent,
    )

    factory = get_async_session_factory()
    async with factory() as db:
        subs = (await db.execute(
            select(PlanSubscription).where(
                PlanSubscription.is_active.is_(True),
                PlanSubscription.status == "active",
            )
        )).scalars().all()

        opportunities_found = 0
        for sub in subs:
            org_id = sub.organization_id
            ledger = (await db.execute(
                select(CreditLedger).where(
                    CreditLedger.organization_id == org_id,
                    CreditLedger.is_active.is_(True),
                )
            )).scalar_one_or_none()

            if not ledger:
                continue

            recent_mult_count = (await db.execute(
                select(sa_func.count(MultiplicationEvent.id)).where(
                    MultiplicationEvent.organization_id == org_id,
                    MultiplicationEvent.offered_at >= datetime.now(timezone.utc) - timedelta(days=7),
                )
            )).scalar() or 0

            utilization = (ledger.used_credits / ledger.total_credits) if ledger.total_credits else 0

            triggers = []
            if utilization >= 0.75:
                triggers.append("high_utilization")
            if sub.plan_tier in ("free", "starter") and utilization >= 0.5:
                triggers.append("tier_upgrade_candidate")
            if recent_mult_count == 0 and utilization >= 0.4:
                triggers.append("no_recent_offers")

            if triggers:
                db.add(MultiplicationEvent(
                    organization_id=org_id,
                    user_id=None,
                    event_type="system_scan",
                    trigger_context=", ".join(triggers),
                    offered=False,
                    converted=False,
                ))
                opportunities_found += 1

        await db.commit()
    return {"scanned": len(subs), "opportunities_found": opportunities_found}


# ---------------------------------------------------------------------------
# SaaS Metrics Snapshot
# ---------------------------------------------------------------------------
@shared_task(name="workers.monetization_worker.tasks.snapshot_saas_metrics", base=TrackedTask)
def snapshot_saas_metrics():
    """Take daily SaaS metric snapshot for each brand."""
    return _run(_do_snapshot_saas_metrics())


async def _do_snapshot_saas_metrics():
    from sqlalchemy import select, func as sa_func
    from packages.db.models.saas_metrics import Subscription, SubscriptionEvent, SaaSMetricSnapshot

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    factory = get_async_session_factory()
    async with factory() as db:
        brand_ids = (await db.execute(
            select(Subscription.brand_id).where(Subscription.is_active.is_(True)).distinct()
        )).scalars().all()

        snapshots_created = 0
        for brand_id in brand_ids:
            active_subs = (await db.execute(
                select(Subscription).where(
                    Subscription.brand_id == brand_id,
                    Subscription.status == "active",
                    Subscription.is_active.is_(True),
                )
            )).scalars().all()

            mrr = sum(s.mrr for s in active_subs)

            new_events = (await db.execute(
                select(sa_func.coalesce(sa_func.sum(SubscriptionEvent.mrr_delta), 0)).where(
                    SubscriptionEvent.brand_id == brand_id,
                    SubscriptionEvent.event_type == "new",
                    SubscriptionEvent.event_at >= thirty_days_ago,
                )
            )).scalar() or 0.0

            churned_events = (await db.execute(
                select(sa_func.coalesce(sa_func.sum(SubscriptionEvent.mrr_delta), 0)).where(
                    SubscriptionEvent.brand_id == brand_id,
                    SubscriptionEvent.event_type == "churn",
                    SubscriptionEvent.event_at >= thirty_days_ago,
                )
            )).scalar() or 0.0

            expansion_events = (await db.execute(
                select(sa_func.coalesce(sa_func.sum(SubscriptionEvent.mrr_delta), 0)).where(
                    SubscriptionEvent.brand_id == brand_id,
                    SubscriptionEvent.event_type == "expansion",
                    SubscriptionEvent.event_at >= thirty_days_ago,
                )
            )).scalar() or 0.0

            contraction_events = (await db.execute(
                select(sa_func.coalesce(sa_func.sum(SubscriptionEvent.mrr_delta), 0)).where(
                    SubscriptionEvent.brand_id == brand_id,
                    SubscriptionEvent.event_type == "contraction",
                    SubscriptionEvent.event_at >= thirty_days_ago,
                )
            )).scalar() or 0.0

            churned_count = (await db.execute(
                select(sa_func.count(Subscription.id)).where(
                    Subscription.brand_id == brand_id,
                    Subscription.status == "cancelled",
                    Subscription.cancelled_at >= thirty_days_ago,
                )
            )).scalar() or 0

            new_count = (await db.execute(
                select(sa_func.count(SubscriptionEvent.id)).where(
                    SubscriptionEvent.brand_id == brand_id,
                    SubscriptionEvent.event_type == "new",
                    SubscriptionEvent.event_at >= thirty_days_ago,
                )
            )).scalar() or 0

            prev_mrr = mrr - float(new_events) + abs(float(churned_events))
            gross_churn = abs(float(churned_events)) / prev_mrr if prev_mrr > 0 else 0.0
            net_retention = (prev_mrr + float(expansion_events) + float(contraction_events) - abs(float(churned_events))) / prev_mrr if prev_mrr > 0 else 1.0

            db.add(SaaSMetricSnapshot(
                brand_id=brand_id,
                period="daily",
                snapshot_date=today,
                mrr=mrr,
                arr=mrr * 12,
                new_mrr=float(new_events),
                churned_mrr=abs(float(churned_events)),
                expansion_mrr=float(expansion_events),
                contraction_mrr=abs(float(contraction_events)),
                net_new_mrr=float(new_events) + float(expansion_events) + float(contraction_events) - abs(float(churned_events)),
                active_subscriptions=len(active_subs),
                churned_subscriptions=churned_count,
                new_subscriptions=new_count,
                gross_churn_rate=round(gross_churn, 4),
                net_revenue_retention=round(net_retention, 4),
            ))
            snapshots_created += 1

        await db.commit()
    return {"brands_processed": len(brand_ids), "snapshots_created": snapshots_created}


# ---------------------------------------------------------------------------
# Churn Prediction
# ---------------------------------------------------------------------------
@shared_task(name="workers.monetization_worker.tasks.run_churn_prediction", base=TrackedTask)
def run_churn_prediction():
    """Predict churn risk for all active subscribers."""
    return _run(_do_run_churn_prediction())


async def _do_run_churn_prediction():
    from sqlalchemy import select, func as sa_func
    from packages.db.models.saas_metrics import Subscription, SubscriptionEvent, SaaSMetricSnapshot

    factory = get_async_session_factory()
    async with factory() as db:
        subs = (await db.execute(
            select(Subscription).where(
                Subscription.status == "active",
                Subscription.is_active.is_(True),
            )
        )).scalars().all()

        high_risk = 0
        for sub in subs:
            days_active = (datetime.now(timezone.utc) - sub.started_at).days if sub.started_at else 0

            event_count = (await db.execute(
                select(sa_func.count(SubscriptionEvent.id)).where(
                    SubscriptionEvent.subscription_id == sub.id,
                    SubscriptionEvent.event_at >= datetime.now(timezone.utc) - timedelta(days=30),
                )
            )).scalar() or 0

            had_downgrade = (await db.execute(
                select(sa_func.count(SubscriptionEvent.id)).where(
                    SubscriptionEvent.subscription_id == sub.id,
                    SubscriptionEvent.event_type == "contraction",
                )
            )).scalar() or 0

            risk_score = 0.0
            if days_active < 30:
                risk_score += 0.2
            if event_count == 0:
                risk_score += 0.3
            if had_downgrade > 0:
                risk_score += 0.3
            if sub.trial_ends_at and sub.trial_ends_at <= datetime.now(timezone.utc) + timedelta(days=3):
                risk_score += 0.2

            risk_score = min(risk_score, 1.0)
            if risk_score >= 0.5:
                sub.metadata_json = {**(sub.metadata_json or {}), "churn_risk": round(risk_score, 2)}
                high_risk += 1

        await db.commit()
    return {"subscribers_analyzed": len(subs), "high_risk_flagged": high_risk}


# ---------------------------------------------------------------------------
# Expansion Opportunity Scan
# ---------------------------------------------------------------------------
@shared_task(name="workers.monetization_worker.tasks.scan_expansion_opportunities", base=TrackedTask)
def scan_expansion_opportunities():
    """Find expansion / upsell opportunities among active subscribers."""
    return _run(_do_scan_expansion_opportunities())


async def _do_scan_expansion_opportunities():
    from sqlalchemy import select, func as sa_func
    from packages.db.models.saas_metrics import Subscription, SubscriptionEvent

    factory = get_async_session_factory()
    async with factory() as db:
        subs = (await db.execute(
            select(Subscription).where(
                Subscription.status == "active",
                Subscription.is_active.is_(True),
            )
        )).scalars().all()

        opportunities = 0
        for sub in subs:
            days_active = (datetime.now(timezone.utc) - sub.started_at).days if sub.started_at else 0
            if days_active < 14:
                continue

            expansion_count = (await db.execute(
                select(sa_func.count(SubscriptionEvent.id)).where(
                    SubscriptionEvent.subscription_id == sub.id,
                    SubscriptionEvent.event_type == "expansion",
                )
            )).scalar() or 0

            is_low_tier = sub.plan_tier in ("free", "starter", "basic", "standard")
            is_long_tenured = days_active > 90
            no_expansion_yet = expansion_count == 0

            if is_low_tier and is_long_tenured and no_expansion_yet:
                sub.metadata_json = {
                    **(sub.metadata_json or {}),
                    "expansion_opportunity": True,
                    "days_active": days_active,
                    "current_tier": sub.plan_tier,
                }
                opportunities += 1

        await db.commit()
    return {"subscribers_scanned": len(subs), "expansion_opportunities": opportunities}


# ---------------------------------------------------------------------------
# Revenue Avenue Rankings
# ---------------------------------------------------------------------------
@shared_task(name="workers.monetization_worker.tasks.recompute_avenue_rankings", base=TrackedTask)
def recompute_avenue_rankings():
    """Re-rank revenue avenues for all brands based on performance signals."""
    return _run(_do_recompute_avenue_rankings())


async def _do_recompute_avenue_rankings():
    from sqlalchemy import select, func as sa_func
    from packages.db.models.saas_metrics import Subscription, HighTicketDeal, ProductLaunch, SaaSMetricSnapshot

    factory = get_async_session_factory()
    async with factory() as db:
        brand_ids_from_subs = (await db.execute(
            select(Subscription.brand_id).where(Subscription.is_active.is_(True)).distinct()
        )).scalars().all()

        brand_ids_from_deals = (await db.execute(
            select(HighTicketDeal.brand_id).where(HighTicketDeal.is_active.is_(True)).distinct()
        )).scalars().all()

        all_brand_ids = set(brand_ids_from_subs) | set(brand_ids_from_deals)
        rankings_computed = 0

        for brand_id in all_brand_ids:
            sub_mrr = (await db.execute(
                select(sa_func.coalesce(sa_func.sum(Subscription.mrr), 0)).where(
                    Subscription.brand_id == brand_id,
                    Subscription.status == "active",
                )
            )).scalar() or 0.0

            deal_pipeline = (await db.execute(
                select(sa_func.coalesce(sa_func.sum(HighTicketDeal.deal_value * HighTicketDeal.probability), 0)).where(
                    HighTicketDeal.brand_id == brand_id,
                    HighTicketDeal.is_active.is_(True),
                    HighTicketDeal.stage != "closed_lost",
                )
            )).scalar() or 0.0

            launch_revenue = (await db.execute(
                select(sa_func.coalesce(sa_func.sum(ProductLaunch.total_revenue), 0)).where(
                    ProductLaunch.brand_id == brand_id,
                    ProductLaunch.is_active.is_(True),
                )
            )).scalar() or 0.0

            avenues = []
            if sub_mrr > 0:
                avenues.append({"avenue": "subscriptions", "mrr": float(sub_mrr), "arr": float(sub_mrr) * 12})
            if deal_pipeline > 0:
                avenues.append({"avenue": "high_ticket", "weighted_pipeline": float(deal_pipeline)})
            if launch_revenue > 0:
                avenues.append({"avenue": "product_launches", "total_revenue": float(launch_revenue)})

            avenues.sort(key=lambda a: a.get("arr", 0) + a.get("weighted_pipeline", 0) + a.get("total_revenue", 0), reverse=True)

            latest_snapshot = (await db.execute(
                select(SaaSMetricSnapshot).where(
                    SaaSMetricSnapshot.brand_id == brand_id,
                ).order_by(SaaSMetricSnapshot.created_at.desc()).limit(1)
            )).scalar_one_or_none()

            if latest_snapshot:
                latest_snapshot.details_json = {
                    **(latest_snapshot.details_json or {}),
                    "avenue_rankings": avenues,
                    "ranked_at": datetime.now(timezone.utc).isoformat(),
                }

            rankings_computed += 1

        await db.commit()
    return {"brands_ranked": rankings_computed}


# ---------------------------------------------------------------------------
# Revenue Maximizer Cycle (scheduled)
# ---------------------------------------------------------------------------
@shared_task(name="workers.monetization_worker.tasks.run_revenue_cycle", base=TrackedTask)
def run_revenue_cycle():
    """Run the full revenue maximizer cycle: surface actions + dispatch autonomous."""
    return _run(_do_run_revenue_cycle())


async def _do_run_revenue_cycle():
    from sqlalchemy import select
    from packages.db.models.core import Brand, Organization

    factory = get_async_session_factory()
    async with factory() as db:
        # Get all active orgs with brands
        orgs = (await db.execute(
            select(Organization.id).where(Organization.is_active.is_(True))
        )).scalars().all()

        total_actions = 0
        total_executed = 0

        for org_id in orgs:
            brands = (await db.execute(
                select(Brand.id).where(Brand.organization_id == org_id)
            )).scalars().all()

            for brand_id in brands:
                try:
                    # Phase 1: Surface revenue actions from intelligence
                    from apps.api.services.revenue_maximizer import auto_surface_revenue_actions
                    actions = await auto_surface_revenue_actions(db, org_id, brand_id)
                    total_actions += len(actions)
                except Exception as e:
                    import structlog
                    structlog.get_logger().warning("revenue_cycle.surface_failed", brand_id=str(brand_id), error=str(e))

            try:
                # Phase 2: Dispatch autonomous actions for this org
                from apps.api.services.action_dispatcher import dispatch_autonomous_actions
                dispatch_result = await dispatch_autonomous_actions(db, org_id)
                total_executed += len(dispatch_result.get("executed", []))
            except Exception as e:
                import structlog
                structlog.get_logger().warning("revenue_cycle.dispatch_failed", org_id=str(org_id), error=str(e))

        await db.commit()

    return {
        "orgs_processed": len(orgs),
        "actions_surfaced": total_actions,
        "actions_auto_executed": total_executed,
    }


# ---------------------------------------------------------------------------
# Pipeline Deal Scoring
# ---------------------------------------------------------------------------
@shared_task(name="workers.monetization_worker.tasks.score_pipeline_deals", base=TrackedTask)
def score_pipeline_deals():
    """Score all active high-ticket deals based on engagement signals."""
    return _run(_do_score_pipeline_deals())


async def _do_score_pipeline_deals():
    from sqlalchemy import select
    from packages.db.models.saas_metrics import HighTicketDeal

    factory = get_async_session_factory()
    async with factory() as db:
        deals = (await db.execute(
            select(HighTicketDeal).where(
                HighTicketDeal.is_active.is_(True),
                HighTicketDeal.stage.notin_(["closed_won", "closed_lost"]),
            )
        )).scalars().all()

        scored = 0
        for deal in deals:
            stage_scores = {
                "awareness": 0.1, "interest": 0.2, "consideration": 0.4,
                "intent": 0.6, "evaluation": 0.75, "negotiation": 0.85,
            }
            stage_score = stage_scores.get(deal.stage, 0.1)

            days_since_activity = (datetime.now(timezone.utc) - deal.last_activity_at).days if deal.last_activity_at else 999
            recency_score = max(0, 1.0 - (days_since_activity / 60))

            interaction_score = min(1.0, deal.interactions / 20) if deal.interactions else 0

            deal.score = round(
                stage_score * 0.4 + recency_score * 0.3 + interaction_score * 0.3,
                3,
            )
            deal.probability = round(deal.score * 0.9, 2)
            scored += 1

        await db.commit()
    return {"deals_scored": scored}
