"""System Command Center — aggregates all real data for the control room."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

from packages.db.models.account_state_intel import AccountStateReport
from packages.db.models.accounts import CreatorAccount
from packages.db.models.creator_revenue import CreatorRevenueEvent
from packages.db.models.failure_family import SuppressionRule
from packages.db.models.offers import Offer
from packages.db.models.opportunity_cost import RankedAction
from packages.db.models.provider_registry import ProviderBlocker, ProviderReadinessReport, ProviderRegistryEntry
from packages.db.models.publishing import PerformanceMetric
from packages.db.models.quality_governor import QualityBlock
from packages.db.models.scale_alerts import OperatorAlert


async def get_command_center_data(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    now = datetime.now(timezone.utc)

    revenue = await _revenue_section(db, brand_id, now)
    providers = await _provider_health(db, brand_id)
    platforms = await _platform_health(db, brand_id)
    accounts = await _account_ops(db, brand_id)
    alerts = await _alert_layer(db, brand_id)

    return {
        "revenue": revenue,
        "providers": providers,
        "platforms": platforms,
        "accounts": accounts,
        "alerts": alerts,
        "generated_at": now.isoformat(),
    }


async def _revenue_section(db: AsyncSession, brand_id: uuid.UUID, now: datetime) -> dict[str, Any]:
    lifetime = (await db.execute(
        select(func.sum(CreatorRevenueEvent.revenue), func.sum(CreatorRevenueEvent.profit), func.sum(CreatorRevenueEvent.cost))
        .where(CreatorRevenueEvent.brand_id == brand_id)
    )).one_or_none()
    total_rev = float(lifetime[0] or 0) if lifetime else 0
    total_profit = float(lifetime[1] or 0) if lifetime else 0
    total_spend = float(lifetime[2] or 0) if lifetime else 0

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day7 = now - timedelta(days=7)
    day30 = now - timedelta(days=30)

    today_rev = float((await db.execute(
        select(func.coalesce(func.sum(CreatorRevenueEvent.revenue), 0)).where(CreatorRevenueEvent.brand_id == brand_id, CreatorRevenueEvent.created_at >= today_start)
    )).scalar() or 0)
    week_rev = float((await db.execute(
        select(func.coalesce(func.sum(CreatorRevenueEvent.revenue), 0)).where(CreatorRevenueEvent.brand_id == brand_id, CreatorRevenueEvent.created_at >= day7)
    )).scalar() or 0)
    month_rev = float((await db.execute(
        select(func.coalesce(func.sum(CreatorRevenueEvent.revenue), 0)).where(CreatorRevenueEvent.brand_id == brand_id, CreatorRevenueEvent.created_at >= day30)
    )).scalar() or 0)

    by_platform = dict((await db.execute(
        select(PerformanceMetric.platform, func.sum(PerformanceMetric.revenue))
        .where(PerformanceMetric.brand_id == brand_id)
        .group_by(PerformanceMetric.platform)
    )).all() or [])

    by_offer = {}
    offer_rows = (await db.execute(
        select(Offer.name, func.sum(CreatorRevenueEvent.revenue))
        .join(CreatorRevenueEvent, CreatorRevenueEvent.opportunity_id == Offer.id, isouter=True)
        .where(Offer.brand_id == brand_id)
        .group_by(Offer.name)
    )).all()
    for name, rev in offer_rows:
        by_offer[name] = float(rev or 0)

    acct_rev = {}
    acct_rows = list((await db.execute(
        select(CreatorAccount.platform_username, func.sum(PerformanceMetric.revenue))
        .join(PerformanceMetric, PerformanceMetric.creator_account_id == CreatorAccount.id)
        .where(CreatorAccount.brand_id == brand_id)
        .group_by(CreatorAccount.platform_username)
    )).all())
    for username, rev in acct_rows:
        acct_rev[username] = float(rev or 0)

    strongest = max(acct_rev, key=acct_rev.get) if acct_rev else None
    weakest = min(acct_rev, key=acct_rev.get) if acct_rev else None

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    mtd_rev = float((await db.execute(
        select(func.coalesce(func.sum(CreatorRevenueEvent.revenue), 0)).where(CreatorRevenueEvent.brand_id == brand_id, CreatorRevenueEvent.created_at >= month_start)
    )).scalar() or 0)

    mtd_perf_rev = float((await db.execute(
        select(func.coalesce(func.sum(PerformanceMetric.revenue), 0)).where(PerformanceMetric.brand_id == brand_id, PerformanceMetric.measured_at >= month_start)
    )).scalar() or 0)

    forecast_data = {}
    try:
        from packages.scoring.revenue_forecast_engine import forecast_revenue, generate_forecast_summary
        daily_revs = [
            float(r[0]) for r in (await db.execute(
                select(func.coalesce(func.sum(PerformanceMetric.revenue), 0.0))
                .where(PerformanceMetric.brand_id == brand_id, PerformanceMetric.measured_at >= day30)
                .group_by(func.date(PerformanceMetric.measured_at))
                .order_by(func.date(PerformanceMetric.measured_at))
            )).all()
        ]
        if daily_revs and len(daily_revs) >= 7:
            fc = forecast_revenue(daily_revs)
            forecast_data = {"forecast_30d": fc["forecast_revenue_30d"], "trend": fc["trend_direction"], "confidence": fc["confidence"], "summary": generate_forecast_summary(fc)}
    except Exception:
        logger.debug("revenue_forecast_enrichment_failed", exc_info=True)

    fleet_data = {}
    try:
        from packages.db.models.autonomous_farm import FleetStatusReport
        fleet = (await db.execute(select(FleetStatusReport).where(FleetStatusReport.is_active.is_(True)).order_by(FleetStatusReport.created_at.desc()).limit(1))).scalar_one_or_none()
        if fleet:
            fleet_data = {"total": fleet.total_accounts, "warming": fleet.accounts_warming, "scaling": fleet.accounts_scaling, "plateaued": fleet.accounts_plateaued, "suspended": fleet.accounts_suspended, "expansion_recommended": fleet.expansion_recommended}
    except Exception:
        logger.debug("fleet_status_enrichment_failed", exc_info=True)

    return {
        "lifetime_revenue": round(total_rev, 2),
        "lifetime_profit": round(total_profit, 2),
        "lifetime_spend": round(total_spend, 2),
        "today_revenue": round(today_rev, 2),
        "week_revenue": round(week_rev, 2),
        "month_revenue": round(month_rev, 2),
        "mtd_revenue": round(mtd_rev + mtd_perf_rev, 2),
        "by_platform": {str(k): round(float(v or 0), 2) for k, v in by_platform.items()},
        "by_offer": by_offer,
        "by_account": acct_rev,
        "strongest_lane": strongest,
        "weakest_lane": weakest,
        "revenue_forecast": forecast_data,
        "fleet_status": fleet_data,
    }


async def _provider_health(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    entries = list((await db.execute(select(ProviderRegistryEntry))).scalars().all())
    readiness = list((await db.execute(
        select(ProviderReadinessReport).where(ProviderReadinessReport.brand_id == brand_id)
    )).scalars().all())
    blockers = list((await db.execute(
        select(ProviderBlocker).where(ProviderBlocker.brand_id == brand_id, ProviderBlocker.is_active.is_(True))
    )).scalars().all())

    readiness_map = {r.provider_key: r for r in readiness}
    blocker_map: dict[str, list] = {}
    for b in blockers:
        blocker_map.setdefault(b.provider_key, []).append(b)

    providers = []
    for e in entries:
        r = readiness_map.get(e.provider_key)
        bs = blocker_map.get(e.provider_key, [])

        if bs:
            status = "blocked"
        elif r and r.is_ready:
            status = "healthy"
        elif r and r.credential_status == "configured":
            status = "degraded"
        elif r and r.credential_status == "not_configured":
            status = "needs_attention"
        else:
            status = "inactive"

        providers.append({
            "provider_key": e.provider_key,
            "provider_name": e.provider_name if hasattr(e, "provider_name") else e.provider_key,
            "status": status,
            "credential_status": r.credential_status if r else "unknown",
            "integration_status": r.integration_status if r else "unknown",
            "is_ready": r.is_ready if r else False,
            "blockers": [{"type": b.blocker_type, "severity": b.severity, "action": b.operator_action_needed} for b in bs],
        })

    return sorted(providers, key=lambda p: {"blocked": 0, "needs_attention": 1, "degraded": 2, "healthy": 3, "inactive": 4}.get(p["status"], 5))


async def _platform_health(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    accounts = list((await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )).scalars().all())

    state_map = {}
    states = list((await db.execute(
        select(AccountStateReport).where(AccountStateReport.brand_id == brand_id, AccountStateReport.is_active.is_(True))
    )).scalars().all())
    for s in states:
        state_map[s.account_id] = s

    platform_data: dict[str, dict] = {}
    for a in accounts:
        plat = a.platform.value if hasattr(a.platform, "value") else str(a.platform)
        if plat not in platform_data:
            platform_data[plat] = {"accounts": 0, "healthy": 0, "weak": 0, "blocked": 0, "saturated": 0, "scaling": 0}
        pd = platform_data[plat]
        pd["accounts"] += 1

        sr = state_map.get(a.id)
        state = sr.current_state if sr else "unknown"
        if state in ("scaling", "monetizing"):
            pd["healthy"] += 1
            pd["scaling"] += 1
        elif state in ("weak", "cooling"):
            pd["weak"] += 1
        elif state in ("blocked", "suppressed"):
            pd["blocked"] += 1
        elif state == "saturated":
            pd["saturated"] += 1
        else:
            pd["healthy"] += 1

    platforms = []
    for plat, pd in platform_data.items():
        if pd["blocked"] > 0:
            status = "blocked"
        elif pd["weak"] > pd["healthy"]:
            status = "weak"
        elif pd["saturated"] > 0:
            status = "saturated"
        elif pd["scaling"] > 0:
            status = "healthy"
        else:
            status = "warming"

        platforms.append({"platform": plat, "status": status, **pd})

    return sorted(platforms, key=lambda p: {"blocked": 0, "weak": 1, "saturated": 2, "warming": 3, "healthy": 4}.get(p["status"], 5))


async def _account_ops(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    states = list((await db.execute(
        select(AccountStateReport).where(AccountStateReport.brand_id == brand_id, AccountStateReport.is_active.is_(True))
    )).scalars().all())

    groups: dict[str, int] = {}
    for s in states:
        groups[s.current_state] = groups.get(s.current_state, 0) + 1

    expansion_eligible = sum(1 for s in states if s.expansion_eligible)

    return {
        "total": len(states),
        "by_state": groups,
        "scaling": groups.get("scaling", 0) + groups.get("monetizing", 0),
        "weak": groups.get("weak", 0) + groups.get("cooling", 0),
        "saturated": groups.get("saturated", 0),
        "blocked": groups.get("blocked", 0) + groups.get("suppressed", 0),
        "expansion_eligible": expansion_eligible,
    }


async def _alert_layer(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    critical_alerts = list((await db.execute(
        select(OperatorAlert).where(OperatorAlert.brand_id == brand_id, OperatorAlert.urgency >= 0.8, OperatorAlert.is_active.is_(True)).order_by(OperatorAlert.urgency.desc()).limit(10)
    )).scalars().all())

    quality_blocks = list((await db.execute(
        select(QualityBlock).where(QualityBlock.brand_id == brand_id, QualityBlock.is_active.is_(True)).limit(5)
    )).scalars().all())

    suppressions = list((await db.execute(
        select(SuppressionRule).where(SuppressionRule.brand_id == brand_id, SuppressionRule.is_active.is_(True)).limit(5)
    )).scalars().all())

    top_actions = list((await db.execute(
        select(RankedAction).where(RankedAction.brand_id == brand_id, RankedAction.is_active.is_(True)).order_by(RankedAction.rank_position).limit(5)
    )).scalars().all())

    return {
        "critical_alerts": [{"title": a.title, "urgency": a.urgency, "action": a.recommended_action} for a in critical_alerts],
        "quality_blocks": [{"reason": b.block_reason, "severity": b.severity} for b in quality_blocks],
        "active_suppressions": [{"type": s.family_type, "key": s.family_key, "mode": s.suppression_mode} for s in suppressions],
        "top_actions": [{"rank": a.rank_position, "type": a.action_type, "key": a.action_key, "urgency": a.urgency, "delay_cost": a.cost_of_delay} for a in top_actions],
    }
