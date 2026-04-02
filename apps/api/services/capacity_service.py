"""Capacity service — production throughput analysis, bottleneck detection, queue allocation."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.capacity import CapacityReport, QueueAllocationDecision
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.system import SystemJob
from packages.scoring.capacity_engine import (
    CAP,
    CAPACITY_TYPES,
    allocate_queues,
    compute_capacity_reports,
)


def _strip_meta(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k != CAP}


# ---------------------------------------------------------------------------
# Recompute
# ---------------------------------------------------------------------------


async def recompute_capacity(
    db: AsyncSession, brand_id: uuid.UUID
) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    account_count = (
        await db.execute(
            select(func.count(CreatorAccount.id)).where(CreatorAccount.brand_id == brand_id)
        )
    ).scalar() or 0

    job_counts_rows = (
        await db.execute(
            select(SystemJob.queue, func.count(SystemJob.id))
            .where(SystemJob.brand_id == brand_id)
            .group_by(SystemJob.queue)
        )
    ).all()
    job_counts: dict[str, int] = {row[0]: int(row[1]) for row in job_counts_rows}

    content_count = (
        await db.execute(
            select(func.count(ContentItem.id)).where(ContentItem.brand_id == brand_id)
        )
    ).scalar() or 0

    posting_cap = max(account_count * 30, 50)

    capacity_data: list[dict[str, Any]] = []
    for cap_type in CAPACITY_TYPES:
        if cap_type == "content_generation":
            current = float(posting_cap)
            used = float(min(content_count, posting_cap))
        elif cap_type == "publishing":
            current = float(posting_cap)
            used = float(job_counts.get("publish", 0))
        elif cap_type == "qa_review":
            current = float(max(posting_cap * 0.5, 20))
            used = float(job_counts.get("qa", 0))
        elif cap_type == "media_render":
            current = float(max(posting_cap * 0.8, 30))
            used = float(job_counts.get("render", job_counts.get("media", 0)))
        elif cap_type == "paid_test":
            current = 20.0
            used = float(job_counts.get("paid_test", 0))
        elif cap_type == "sponsor_sales":
            current = 10.0
            used = float(job_counts.get("sponsor", 0))
        elif cap_type == "operator_bandwidth":
            current = 40.0
            total_jobs = sum(job_counts.values())
            used = float(min(total_jobs, 40))
        else:
            current = 50.0
            used = 0.0

        capacity_data.append({
            "capacity_type": cap_type,
            "current_capacity": current,
            "used_capacity": used,
            "unit_cost": 1.0,
            "revenue_per_unit": 2.0,
        })

    cost_ceilings: dict[str, Any] = {ct: 10000.0 for ct in CAPACITY_TYPES}
    reports = compute_capacity_reports(capacity_data, cost_ceilings)

    queue_priorities: list[dict[str, Any]] = []
    for cap_type in CAPACITY_TYPES:
        queue_priorities.append({
            "queue_name": f"{cap_type}_queue",
            "capacity_type": cap_type,
            "requested_capacity": 10.0,
            "expected_roi": 0.5,
            "priority_tier": 2,
        })
    allocations = allocate_queues(reports, queue_priorities)

    await db.execute(
        delete(QueueAllocationDecision).where(QueueAllocationDecision.brand_id == brand_id)
    )
    await db.execute(
        delete(CapacityReport).where(
            CapacityReport.brand_id == brand_id,
            CapacityReport.is_active.is_(True),
        )
    )

    report_count = 0
    for item in reports:
        r = _strip_meta(item)
        db.add(
            CapacityReport(
                brand_id=brand_id,
                capacity_type=r.get("capacity_type", "unknown"),
                current_capacity=float(r.get("current_capacity", 0)),
                used_capacity=float(r.get("used_capacity", 0)),
                constrained_scope_json=r.get("constrained_scope"),
                recommended_volume=float(r.get("recommended_volume", 0)),
                recommended_throttle=r.get("recommended_throttle"),
                expected_profit_impact=float(r.get("expected_profit_impact", 0)),
                confidence_score=float(r.get("confidence", 0)),
                explanation_json={"explanation": r.get("explanation", "")},
                is_active=True,
            )
        )
        report_count += 1

    alloc_count = 0
    for item in allocations:
        a = _strip_meta(item)
        db.add(
            QueueAllocationDecision(
                brand_id=brand_id,
                queue_name=a.get("queue_name", "unknown"),
                priority_score=float(a.get("priority_score", 0)),
                allocated_capacity=float(a.get("allocated_capacity", 0)),
                deferred_capacity=float(a.get("deferred_capacity", 0)),
                reason_json={"reason": a.get("reason", ""), "explanation": a.get("explanation", "")},
            )
        )
        alloc_count += 1

    await db.flush()
    return {"capacity_reports": report_count, "queue_allocations": alloc_count}


# ---------------------------------------------------------------------------
# Dict helpers
# ---------------------------------------------------------------------------


def _cap_dict(x: CapacityReport) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "capacity_type": x.capacity_type,
        "current_capacity": x.current_capacity,
        "used_capacity": x.used_capacity,
        "constrained_scope_json": x.constrained_scope_json,
        "recommended_volume": x.recommended_volume,
        "recommended_throttle": x.recommended_throttle,
        "expected_profit_impact": x.expected_profit_impact,
        "confidence_score": x.confidence_score,
        "explanation_json": x.explanation_json,
        "is_active": x.is_active,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


def _qa_dict(x: QueueAllocationDecision) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "queue_name": x.queue_name,
        "priority_score": x.priority_score,
        "allocated_capacity": x.allocated_capacity,
        "deferred_capacity": x.deferred_capacity,
        "reason_json": x.reason_json,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


# ---------------------------------------------------------------------------
# Getters
# ---------------------------------------------------------------------------


async def get_capacity_reports(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(CapacityReport)
                .where(
                    CapacityReport.brand_id == brand_id,
                    CapacityReport.is_active.is_(True),
                )
                .order_by(CapacityReport.created_at.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    return [_cap_dict(r) for r in rows]


async def get_queue_allocations(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(QueueAllocationDecision)
                .where(QueueAllocationDecision.brand_id == brand_id)
                .order_by(QueueAllocationDecision.priority_score.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    return [_qa_dict(r) for r in rows]
