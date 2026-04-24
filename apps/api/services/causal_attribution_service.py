"""Causal Attribution Service — detect changes, attribute causes, persist."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.causal_attribution import (
    CausalAttributionReport,
    CausalConfidenceReport,
    CausalCreditAllocation,
    CausalHypothesis,
    CausalSignal,
)
from packages.db.models.promote_winner import PWExperimentWinner
from packages.db.models.publishing import PerformanceMetric
from packages.scoring.causal_attribution_engine import (
    allocate_credit,
    build_confidence_summary,
    detect_change_points,
    extract_candidate_causes,
    score_causal_confidence,
)


async def recompute_attribution(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(
        delete(CausalCreditAllocation).where(
            CausalCreditAllocation.report_id.in_(
                select(CausalAttributionReport.id).where(CausalAttributionReport.brand_id == brand_id)
            )
        )
    )
    await db.execute(
        delete(CausalConfidenceReport).where(
            CausalConfidenceReport.report_id.in_(
                select(CausalAttributionReport.id).where(CausalAttributionReport.brand_id == brand_id)
            )
        )
    )
    await db.execute(
        delete(CausalHypothesis).where(
            CausalHypothesis.report_id.in_(
                select(CausalAttributionReport.id).where(CausalAttributionReport.brand_id == brand_id)
            )
        )
    )
    await db.execute(delete(CausalSignal).where(CausalSignal.brand_id == brand_id))
    await db.execute(delete(CausalAttributionReport).where(CausalAttributionReport.brand_id == brand_id))

    perf_rows = list(
        (
            await db.execute(
                select(PerformanceMetric)
                .where(PerformanceMetric.brand_id == brand_id)
                .order_by(PerformanceMetric.created_at)
                .limit(100)
            )
        )
        .scalars()
        .all()
    )

    system_events: list[dict] = []
    winners = list(
        (await db.execute(select(PWExperimentWinner).where(PWExperimentWinner.brand_id == brand_id).limit(10)))
        .scalars()
        .all()
    )
    for i, w in enumerate(winners):
        system_events.append(
            {
                "index": max(1, len(perf_rows) - len(winners) + i),
                "driver_type": "experiment_result",
                "driver_name": f"Experiment winner {str(w.variant_id)[:8]}",
                "confidence": float(w.confidence),
            }
        )

    for metric_name in ("engagement_rate", "revenue"):
        if metric_name == "engagement_rate":
            series = [float(p.engagement_rate or 0) for p in perf_rows]
        else:
            series = [float(p.revenue or 0) for p in perf_rows]

        if len(series) < 3:
            continue

        changes = detect_change_points(series)
        if not changes:
            continue

        candidates = extract_candidate_causes(changes, system_events)
        if not candidates and changes:
            for ch in changes:
                candidates.append(
                    {
                        "change": ch,
                        "driver_type": "content_change",
                        "driver_name": f"Performance shift at period {ch['index']}",
                        "temporal_proximity": 0,
                    }
                )

        hypotheses = [score_causal_confidence(c) for c in candidates]
        credits = allocate_credit(hypotheses)
        conf_summary = build_confidence_summary(hypotheses)

        top_change = changes[0]
        top_driver = hypotheses[0]["driver_name"] if hypotheses else None

        report = CausalAttributionReport(
            brand_id=brand_id,
            target_metric=metric_name,
            direction=top_change["direction"],
            magnitude=abs(top_change["change_pct"]),
            top_driver=top_driver,
            total_hypotheses=len(hypotheses),
            summary=f"{len(hypotheses)} hypotheses for {metric_name} {top_change['direction']} of {abs(top_change['change_pct']):.0f}%",
        )
        db.add(report)
        await db.flush()

        for ch in changes:
            db.add(
                CausalSignal(
                    brand_id=brand_id,
                    report_id=report.id,
                    signal_type="change_point",
                    scope=metric_name,
                    before_value=ch["before"],
                    after_value=ch["after"],
                    change_pct=ch["change_pct"],
                )
            )

        for h in hypotheses:
            db.add(
                CausalHypothesis(
                    report_id=report.id,
                    driver_type=h["driver_type"],
                    driver_name=h["driver_name"],
                    estimated_lift_pct=h["estimated_lift_pct"],
                    confidence=h["confidence"],
                    competing_explanations=h["competing_explanations"],
                    evidence_json=h.get("event_data", {}),
                    recommended_action=h["recommended_action"],
                )
            )

        db.add(CausalConfidenceReport(report_id=report.id, **conf_summary))

        for cr in credits:
            db.add(CausalCreditAllocation(report_id=report.id, **cr))

    await db.flush()
    return {"rows_processed": len(perf_rows), "status": "completed"}


async def list_reports(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(CausalAttributionReport)
                .where(CausalAttributionReport.brand_id == brand_id, CausalAttributionReport.is_active.is_(True))
                .order_by(CausalAttributionReport.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def list_hypotheses(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(CausalHypothesis)
                .join(CausalAttributionReport)
                .where(CausalAttributionReport.brand_id == brand_id, CausalHypothesis.is_active.is_(True))
                .order_by(CausalHypothesis.confidence.desc())
            )
        )
        .scalars()
        .all()
    )


async def list_credits(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(CausalCreditAllocation)
                .join(CausalAttributionReport)
                .where(CausalAttributionReport.brand_id == brand_id, CausalCreditAllocation.is_active.is_(True))
                .order_by(CausalCreditAllocation.credit_pct.desc())
            )
        )
        .scalars()
        .all()
    )


async def list_confidence(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(CausalConfidenceReport)
                .join(CausalAttributionReport)
                .where(CausalAttributionReport.brand_id == brand_id, CausalConfidenceReport.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )


async def get_attribution_summary(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    """Downstream: quick attribution summary for copilot."""
    reports = list(
        (
            await db.execute(
                select(CausalAttributionReport)
                .where(CausalAttributionReport.brand_id == brand_id, CausalAttributionReport.is_active.is_(True))
                .order_by(CausalAttributionReport.created_at.desc())
                .limit(3)
            )
        )
        .scalars()
        .all()
    )
    return {
        "reports": [
            {"metric": r.target_metric, "direction": r.direction, "magnitude": r.magnitude, "driver": r.top_driver}
            for r in reports
        ]
    }
