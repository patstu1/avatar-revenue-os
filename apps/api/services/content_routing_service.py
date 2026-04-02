"""Content Routing service — classify tasks, route to providers, track costs."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.content_routing import ContentRoutingDecision, ContentRoutingCostReport
from packages.scoring.tiered_routing_engine import (
    route_content_task,
    compute_monthly_projection,
    check_budget_remaining,
)


async def route_task(db: AsyncSession, brand_id: uuid.UUID, task_description: str, platform: str, content_type: str = "text", is_promoted: bool = False, campaign_type: str = "organic") -> dict[str, Any]:
    from packages.db.models.pattern_memory import WinningPatternCluster
    hero_override = False
    try:
        top_cluster = (await db.execute(
            select(WinningPatternCluster)
            .where(WinningPatternCluster.brand_id == brand_id, WinningPatternCluster.platform == platform, WinningPatternCluster.is_active.is_(True))
            .order_by(WinningPatternCluster.avg_win_score.desc())
            .limit(1)
        )).scalar_one_or_none()
        if top_cluster and top_cluster.avg_win_score >= 0.6:
            hero_override = True
    except Exception:
        pass

    try:
        from apps.api.services.capital_allocator_service import get_allocation_for_target
        alloc = await get_allocation_for_target(db, brand_id, "platform", platform)
        if alloc.get("provider_tier") == "hero":
            hero_override = True
        if alloc.get("starved"):
            hero_override = False
    except Exception:
        pass

    try:
        from packages.db.models.account_state_intel import AccountStateReport
        state_report = (await db.execute(
            select(AccountStateReport)
            .where(AccountStateReport.brand_id == brand_id, AccountStateReport.is_active.is_(True))
            .order_by(AccountStateReport.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        if state_report:
            if state_report.current_state in ("newborn", "warming", "weak", "suppressed", "blocked"):
                hero_override = False
            if state_report.posting_cadence == "paused":
                hero_override = False
    except Exception:
        pass

    result = route_content_task(task_description, platform, content_type, is_promoted or hero_override, campaign_type)
    if hero_override and not is_promoted:
        result["explanation"] = result.get("explanation", "") + " [upgraded to hero by allocation/pattern]"
    decision = ContentRoutingDecision(
        brand_id=brand_id,
        content_type=result["content_type"],
        quality_tier=result["quality_tier"],
        routed_provider=result["routed_provider"],
        platform=result["platform"],
        is_promoted=result["is_promoted"],
        estimated_cost=result["estimated_cost"],
        explanation=result["explanation"],
    )
    db.add(decision)
    await db.flush()
    return result


async def list_routing_decisions(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(
        select(ContentRoutingDecision).where(ContentRoutingDecision.brand_id == brand_id, ContentRoutingDecision.is_active.is_(True)).order_by(ContentRoutingDecision.created_at.desc()).limit(100)
    )).scalars().all())


async def get_cost_reports(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(
        select(ContentRoutingCostReport).where(ContentRoutingCostReport.brand_id == brand_id, ContentRoutingCostReport.is_active.is_(True)).order_by(ContentRoutingCostReport.created_at.desc()).limit(30)
    )).scalars().all())


async def recompute_cost_report(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    decisions = list((await db.execute(
        select(ContentRoutingDecision).where(ContentRoutingDecision.brand_id == brand_id, ContentRoutingDecision.is_active.is_(True))
    )).scalars().all())

    by_provider: dict[str, float] = {}
    by_tier: dict[str, float] = {}
    by_ct: dict[str, float] = {}
    total_cost = 0.0

    for d in decisions:
        cost = d.actual_cost if d.actual_cost is not None else d.estimated_cost
        by_provider[d.routed_provider] = by_provider.get(d.routed_provider, 0) + cost
        by_tier[d.quality_tier] = by_tier.get(d.quality_tier, 0) + cost
        by_ct[d.content_type] = by_ct.get(d.content_type, 0) + cost
        total_cost += cost

    await db.execute(delete(ContentRoutingCostReport).where(ContentRoutingCostReport.brand_id == brand_id, ContentRoutingCostReport.report_date == today))
    db.add(ContentRoutingCostReport(
        brand_id=brand_id, report_date=today, total_cost=round(total_cost, 4),
        total_decisions=len(decisions),
        by_provider={k: round(v, 4) for k, v in by_provider.items()},
        by_tier={k: round(v, 4) for k, v in by_tier.items()},
        by_content_type={k: round(v, 4) for k, v in by_ct.items()},
    ))
    await db.flush()
    return {"rows_processed": 1, "status": "completed"}


async def get_monthly_projection() -> dict[str, Any]:
    return compute_monthly_projection()
