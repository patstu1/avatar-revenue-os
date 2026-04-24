"""Executive Intelligence Service — KPI rollup, forecast, cost, uptime, oversight, alerts."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.campaigns import Campaign
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.creator_revenue import CreatorRevenueEvent
from packages.db.models.executive_intel import (
    ExecutiveAlert,
    ExecutiveForecast,
    ExecutiveKPIReport,
    OversightModeReport,
    ProviderUptimeReport,
    UsageCostReport,
)
from packages.db.models.publishing import PerformanceMetric
from packages.db.models.workflow_builder import WorkflowApproval, WorkflowOverride
from packages.scoring.executive_intel_engine import (
    evaluate_oversight,
    forecast_metric,
    generate_executive_alerts,
    rollup_kpis,
)


async def recompute_executive_intel(db: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    period = now.strftime("%Y-%m")

    await db.execute(delete(ExecutiveAlert).where(ExecutiveAlert.organization_id == org_id))
    await db.execute(
        delete(ExecutiveKPIReport).where(
            ExecutiveKPIReport.organization_id == org_id, ExecutiveKPIReport.period == period
        )
    )
    await db.execute(delete(ExecutiveForecast).where(ExecutiveForecast.organization_id == org_id))
    await db.execute(delete(OversightModeReport).where(OversightModeReport.organization_id == org_id))

    brands = list((await db.execute(select(Brand.id).where(Brand.organization_id == org_id))).scalars().all())

    rev = (
        (
            await db.execute(
                select(
                    func.sum(CreatorRevenueEvent.revenue),
                    func.sum(CreatorRevenueEvent.profit),
                    func.sum(CreatorRevenueEvent.cost),
                ).where(CreatorRevenueEvent.brand_id.in_(brands))
            )
        ).one_or_none()
        if brands
        else None
    )
    revenue_data = {
        "total_revenue": float(rev[0] or 0) if rev else 0,
        "total_profit": float(rev[1] or 0) if rev else 0,
        "total_spend": float(rev[2] or 0) if rev else 0,
    }

    produced = (
        (
            await db.execute(select(func.count()).select_from(ContentItem).where(ContentItem.brand_id.in_(brands)))
        ).scalar()
        if brands
        else 0
    )
    published = (
        (
            await db.execute(
                select(func.count())
                .select_from(ContentItem)
                .where(ContentItem.brand_id.in_(brands), ContentItem.status == "published")
            )
        ).scalar()
        if brands
        else 0
    )
    content_data = {"produced": produced or 0, "published": published or 0}

    perf = (
        (
            await db.execute(
                select(
                    func.sum(PerformanceMetric.impressions),
                    func.avg(PerformanceMetric.engagement_rate),
                    func.avg(PerformanceMetric.ctr),
                ).where(PerformanceMetric.brand_id.in_(brands))
            )
        ).one_or_none()
        if brands
        else None
    )
    performance_data = {
        "total_impressions": float(perf[0] or 0) if perf else 0,
        "avg_engagement_rate": float(perf[1] or 0) if perf else 0,
        "avg_conversion_rate": float(perf[2] or 0) if perf else 0,
    }

    acct_count = (
        (
            await db.execute(
                select(func.count())
                .select_from(CreatorAccount)
                .where(CreatorAccount.brand_id.in_(brands), CreatorAccount.is_active.is_(True))
            )
        ).scalar()
        if brands
        else 0
    )
    camp_count = (
        (
            await db.execute(
                select(func.count())
                .select_from(Campaign)
                .where(Campaign.brand_id.in_(brands), Campaign.is_active.is_(True))
            )
        ).scalar()
        if brands
        else 0
    )

    kpis = rollup_kpis(
        revenue_data,
        content_data,
        performance_data,
        {"active_count": acct_count or 0},
        {"active_count": camp_count or 0},
    )
    db.add(ExecutiveKPIReport(organization_id=org_id, period=period, **kpis))

    rev_forecast = forecast_metric([revenue_data["total_revenue"]])
    db.add(
        ExecutiveForecast(
            organization_id=org_id,
            forecast_type="revenue",
            forecast_period=f"{period}_next",
            predicted_value=rev_forecast["predicted_value"],
            confidence=rev_forecast["confidence"],
            risk_factors=rev_forecast["risk_factors"],
            opportunity_factors=rev_forecast["opportunity_factors"],
            explanation=f"Revenue forecast: ${rev_forecast['predicted_value']:.0f}",
        )
    )

    auto_count = (await db.execute(select(func.count()).select_from(WorkflowApproval))).scalar() or 0
    override_count = (await db.execute(select(func.count()).select_from(WorkflowOverride))).scalar() or 0
    oversight = evaluate_oversight(auto_count, max(1, produced or 1) - auto_count, override_count)
    db.add(OversightModeReport(organization_id=org_id, **oversight))

    forecasts = [rev_forecast]
    uptimes: list[dict] = []
    alerts = generate_executive_alerts(kpis, forecasts, uptimes, oversight)
    for a in alerts:
        db.add(ExecutiveAlert(organization_id=org_id, **a))

    await db.flush()
    return {"rows_processed": 1 + len(alerts), "status": "completed"}


async def list_kpis(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(ExecutiveKPIReport)
                .where(ExecutiveKPIReport.organization_id == org_id, ExecutiveKPIReport.is_active.is_(True))
                .order_by(ExecutiveKPIReport.created_at.desc())
                .limit(12)
            )
        )
        .scalars()
        .all()
    )


async def list_forecasts(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(ExecutiveForecast).where(
                    ExecutiveForecast.organization_id == org_id, ExecutiveForecast.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )


async def list_usage_cost(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(UsageCostReport).where(
                    UsageCostReport.organization_id == org_id, UsageCostReport.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )


async def list_uptime(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(ProviderUptimeReport).where(
                    ProviderUptimeReport.organization_id == org_id, ProviderUptimeReport.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )


async def list_oversight(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(OversightModeReport).where(
                    OversightModeReport.organization_id == org_id, OversightModeReport.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )


async def list_alerts(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(ExecutiveAlert)
                .where(ExecutiveAlert.organization_id == org_id, ExecutiveAlert.is_active.is_(True))
                .order_by(ExecutiveAlert.severity)
            )
        )
        .scalars()
        .all()
    )


async def get_executive_summary(db: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    """Downstream: quick executive summary for copilot/command center."""
    kpi = (
        await db.execute(
            select(ExecutiveKPIReport)
            .where(ExecutiveKPIReport.organization_id == org_id)
            .order_by(ExecutiveKPIReport.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    alerts = list(
        (
            await db.execute(
                select(ExecutiveAlert)
                .where(
                    ExecutiveAlert.organization_id == org_id,
                    ExecutiveAlert.is_active.is_(True),
                    ExecutiveAlert.severity.in_(("critical", "high")),
                )
                .limit(3)
            )
        )
        .scalars()
        .all()
    )
    if not kpi:
        return {"status": "no_data"}
    return {
        "revenue": kpi.total_revenue,
        "profit": kpi.total_profit,
        "spend": kpi.total_spend,
        "content_produced": kpi.content_produced,
        "content_published": kpi.content_published,
        "accounts": kpi.active_accounts,
        "campaigns": kpi.active_campaigns,
        "critical_alerts": [{"title": a.title, "severity": a.severity} for a in alerts],
    }
