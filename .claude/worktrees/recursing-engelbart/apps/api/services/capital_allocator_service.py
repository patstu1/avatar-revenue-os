"""Portfolio Capital Allocator Service — gather inputs, solve, persist, rebalance."""
from __future__ import annotations
import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.capital_allocator import (
    CAAllocationConstraint, CAAllocationDecision, CAAllocationRebalance,
    AllocationTarget, CapitalAllocationReport,
)
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.offers import Offer
from packages.db.models.pattern_memory import WinningPatternCluster, WinningPatternMemory
from packages.db.models.promote_winner import ActiveExperiment, PromotedWinnerRule
from packages.db.models.publishing import PerformanceMetric
from packages.scoring.capital_allocator_engine import (
    rebalance as engine_rebalance,
    solve_allocation,
)

DEFAULT_BUDGET = 1000.0


async def _gather_targets(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    """Gather all allocation targets from accounts, offers, platforms, patterns, experiments."""
    targets: list[dict[str, Any]] = []

    accounts = list((await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id)
    )).scalars().all())
    for a in accounts:
        health_val = a.account_health.value if hasattr(a.account_health, "value") else str(a.account_health)
        health_num = {"healthy": 1.0, "warning": 0.6, "critical": 0.2, "suspended": 0.0}.get(health_val, 0.5)
        plat = a.platform.value if hasattr(a.platform, "value") else str(a.platform)
        perf_row = (await db.execute(
            select(func.avg(PerformanceMetric.engagement_rate)).where(PerformanceMetric.creator_account_id == a.id)
        )).scalar() or 0
        targets.append({
            "target_type": "account",
            "target_key": f"{plat}:{a.platform_username}",
            "target_id": str(a.id),
            "expected_return": float(perf_row) * 100,
            "expected_cost": 5.0,
            "confidence": 0.5 + health_num * 0.3,
            "account_health": health_num,
            "fatigue_score": 0.0,
            "pattern_win_score": 0.0,
        })

        targets.append({
            "target_type": "platform",
            "target_key": plat,
            "target_id": str(a.id),
            "expected_return": float(perf_row) * 80,
            "expected_cost": 3.0,
            "confidence": 0.5,
            "account_health": health_num,
            "fatigue_score": 0.0,
            "pattern_win_score": 0.0,
        })

    offers = list((await db.execute(
        select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
    )).scalars().all())
    for o in offers:
        epc = float(o.epc or 0)
        cvr = float(o.conversion_rate or 0)
        targets.append({
            "target_type": "offer",
            "target_key": o.name,
            "target_id": str(o.id),
            "expected_return": epc * 10,
            "expected_cost": float(o.payout_amount or 0) * 0.1,
            "confidence": min(1.0, cvr * 10),
            "account_health": 1.0,
            "fatigue_score": 0.0,
            "conversion_quality": cvr,
            "pattern_win_score": 0.0,
        })

    clusters = list((await db.execute(
        select(WinningPatternCluster).where(
            WinningPatternCluster.brand_id == brand_id,
            WinningPatternCluster.is_active.is_(True),
        )
    )).scalars().all())
    for c in clusters:
        targets.append({
            "target_type": "content_form",
            "target_key": f"{c.cluster_type}:{c.platform or 'all'}",
            "target_id": str(c.id),
            "expected_return": float(c.avg_win_score) * 50,
            "expected_cost": 2.0,
            "confidence": float(c.avg_win_score),
            "account_health": 1.0,
            "fatigue_score": 0.0,
            "pattern_win_score": float(c.avg_win_score),
        })

    experiments = list((await db.execute(
        select(ActiveExperiment).where(
            ActiveExperiment.brand_id == brand_id,
            ActiveExperiment.status == "active",
        )
    )).scalars().all())
    for e in experiments:
        targets.append({
            "target_type": "experiment",
            "target_key": f"exp:{e.experiment_name}",
            "target_id": str(e.id),
            "expected_return": 15.0,
            "expected_cost": 5.0,
            "confidence": 0.4,
            "account_health": 1.0,
            "fatigue_score": 0.0,
            "pattern_win_score": 0.0,
        })

    return targets


async def recompute_allocation(
    db: AsyncSession, brand_id: uuid.UUID, total_budget: float = DEFAULT_BUDGET,
) -> dict[str, Any]:
    await db.execute(delete(CAAllocationDecision).where(CAAllocationDecision.brand_id == brand_id))
    await db.execute(delete(AllocationTarget).where(AllocationTarget.brand_id == brand_id))
    await db.execute(delete(CapitalAllocationReport).where(CapitalAllocationReport.brand_id == brand_id))

    targets = await _gather_targets(db, brand_id)
    constraints = list((await db.execute(
        select(CAAllocationConstraint).where(CAAllocationConstraint.brand_id == brand_id, CAAllocationConstraint.is_active.is_(True))
    )).scalars().all())
    constraint_dicts = [{"constraint_type": c.constraint_type, "constraint_key": c.constraint_key, "min_value": c.min_value, "max_value": c.max_value} for c in constraints]

    result = solve_allocation(targets, total_budget, constraint_dicts)
    report_data = result["report"]

    report = CapitalAllocationReport(
        brand_id=brand_id,
        total_budget=report_data["total_budget"],
        allocated_budget=report_data["allocated_budget"],
        experiment_reserve=report_data["experiment_reserve"],
        hero_spend=report_data["hero_spend"],
        bulk_spend=report_data["bulk_spend"],
        target_count=report_data["target_count"],
        starved_count=report_data["starved_count"],
        summary_json=report_data,
    )
    db.add(report)
    await db.flush()

    for dec in result["decisions"]:
        tid_raw = dec.get("target_id")
        try:
            tid = uuid.UUID(str(tid_raw)) if tid_raw else None
        except (ValueError, TypeError):
            tid = None

        at = AllocationTarget(
            brand_id=brand_id, report_id=report.id,
            target_type=dec["target_type"], target_key=dec["target_key"], target_id=tid,
            expected_return=dec.get("return_score", 0), expected_cost=0,
            confidence=dec.get("return_score", 0),
            pattern_win_score=dec.get("return_score", 0),
            provider_tier=dec["provider_tier"],
        )
        db.add(at)
        await db.flush()

        db.add(CAAllocationDecision(
            brand_id=brand_id, report_id=report.id, target_id=at.id,
            allocated_budget=dec["allocated_budget"],
            allocated_volume=dec["allocated_volume"],
            provider_tier=dec["provider_tier"],
            allocation_pct=dec["allocation_pct"],
            starved=dec["starved"],
            explanation=dec["explanation"],
        ))

    await db.flush()
    return {"rows_processed": len(result["decisions"]), "status": "completed"}


async def list_reports(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(
        select(CapitalAllocationReport).where(CapitalAllocationReport.brand_id == brand_id).order_by(CapitalAllocationReport.created_at.desc()).limit(20)
    )).scalars().all())


async def list_decisions(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(
        select(CAAllocationDecision).where(CAAllocationDecision.brand_id == brand_id, CAAllocationDecision.is_active.is_(True)).order_by(CAAllocationDecision.allocation_pct.desc())
    )).scalars().all())


async def list_rebalances(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(
        select(CAAllocationRebalance).where(CAAllocationRebalance.brand_id == brand_id).order_by(CAAllocationRebalance.created_at.desc()).limit(20)
    )).scalars().all())


async def get_allocation_for_target(db: AsyncSession, brand_id: uuid.UUID, target_type: str, target_key: str) -> dict[str, Any]:
    """Downstream query: get allocation decision for a specific target."""
    at = (await db.execute(
        select(AllocationTarget).where(
            AllocationTarget.brand_id == brand_id,
            AllocationTarget.target_type == target_type,
            AllocationTarget.target_key == target_key,
            AllocationTarget.is_active.is_(True),
        ).order_by(AllocationTarget.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if not at:
        return {"provider_tier": "bulk", "allocated_budget": 0, "starved": False}
    dec = (await db.execute(
        select(CAAllocationDecision).where(CAAllocationDecision.target_id == at.id, CAAllocationDecision.is_active.is_(True))
    )).scalar_one_or_none()
    if not dec:
        return {"provider_tier": at.provider_tier, "allocated_budget": 0, "starved": False}
    return {"provider_tier": dec.provider_tier, "allocated_budget": dec.allocated_budget, "allocation_pct": dec.allocation_pct, "starved": dec.starved}
