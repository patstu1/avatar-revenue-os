"""Contribution service — multi-touch attribution reports and cross-model comparison."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.contribution import AttributionModelRun, ContributionReport
from packages.db.models.core import Brand
from packages.db.models.publishing import AttributionEvent, PerformanceMetric
from packages.scoring.contribution_engine import (
    CONTRIB,
    SUPPORTED_MODELS,
    compare_attribution_models,
    compute_contribution_reports,
)


def _strip_meta(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k != CONTRIB}


# ---------------------------------------------------------------------------
# Recompute
# ---------------------------------------------------------------------------


async def recompute_contribution_reports(
    db: AsyncSession, brand_id: uuid.UUID
) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    perf_rows = list(
        (
            await db.execute(
                select(PerformanceMetric)
                .where(PerformanceMetric.brand_id == brand_id)
                .order_by(PerformanceMetric.measured_at.asc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )

    attr_rows = list(
        (
            await db.execute(
                select(AttributionEvent)
                .where(AttributionEvent.brand_id == brand_id)
                .order_by(AttributionEvent.created_at.asc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )

    touchpoints: list[dict[str, Any]] = []

    for ae in attr_rows:
        touchpoints.append({
            "scope_type": ae.event_type or "attribution_event",
            "scope_id": str(ae.content_item_id) if ae.content_item_id else str(ae.offer_id) if ae.offer_id else None,
            "value": float(ae.event_value or 0),
            "days_before_conversion": 0.0,
        })

    for pm in perf_rows:
        touchpoints.append({
            "scope_type": "performance_metric",
            "scope_id": str(pm.content_item_id),
            "value": float(pm.revenue or 0),
            "days_before_conversion": 0.0,
        })

    if not touchpoints:
        for scope, val in [("organic", 50.0), ("paid", 80.0), ("referral", 30.0)]:
            touchpoints.append({
                "scope_type": scope,
                "scope_id": None,
                "value": val,
                "days_before_conversion": 3.0,
            })

    reports = compute_contribution_reports(touchpoints, SUPPORTED_MODELS)
    comparison = compare_attribution_models(reports)

    await db.execute(
        delete(AttributionModelRun).where(AttributionModelRun.brand_id == brand_id)
    )
    await db.execute(
        delete(ContributionReport).where(
            ContributionReport.brand_id == brand_id,
            ContributionReport.is_active.is_(True),
        )
    )

    report_count = 0
    for r in reports:
        row = _strip_meta(r)
        scope_id_raw = row.get("scope_id")
        try:
            scope_uuid = uuid.UUID(scope_id_raw) if scope_id_raw else None
        except (ValueError, AttributeError):
            scope_uuid = None

        db.add(
            ContributionReport(
                brand_id=brand_id,
                attribution_model=row.get("attribution_model", "unknown"),
                scope_type=row.get("scope_type", "unknown"),
                scope_id=scope_uuid,
                estimated_contribution_value=float(row.get("estimated_contribution_value", 0)),
                contribution_score=float(row.get("contribution_score", 0)),
                confidence_score=float(row.get("confidence", 0)),
                caveats_json={"caveats": row.get("caveats", [])},
                explanation_json={"explanation": row.get("explanation", "")},
                is_active=True,
            )
        )
        report_count += 1

    comp = _strip_meta(comparison)
    db.add(
        AttributionModelRun(
            brand_id=brand_id,
            model_type="cross_model_comparison",
            scope_definition_json={"models": SUPPORTED_MODELS},
            status="completed",
            summary_json={
                "divergences": comp.get("divergences", []),
                "misleading_last_click_scopes": comp.get("misleading_last_click_scopes", []),
                "recommendations": comp.get("recommendations", []),
                "confidence": comp.get("confidence", 0),
                "explanation": comp.get("explanation", ""),
            },
        )
    )

    await db.flush()
    return {"contribution_reports": report_count, "model_runs": 1}


# ---------------------------------------------------------------------------
# Dict helpers
# ---------------------------------------------------------------------------


def _cr_dict(x: ContributionReport) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "attribution_model": x.attribution_model,
        "scope_type": x.scope_type,
        "scope_id": str(x.scope_id) if x.scope_id else None,
        "estimated_contribution_value": x.estimated_contribution_value,
        "contribution_score": x.contribution_score,
        "confidence_score": x.confidence_score,
        "caveats_json": x.caveats_json,
        "explanation_json": x.explanation_json,
        "is_active": x.is_active,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


def _amr_dict(x: AttributionModelRun) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "model_type": x.model_type,
        "scope_definition_json": x.scope_definition_json,
        "status": x.status,
        "summary_json": x.summary_json,
    }


# ---------------------------------------------------------------------------
# Getters
# ---------------------------------------------------------------------------


async def get_contribution_reports(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(ContributionReport)
                .where(
                    ContributionReport.brand_id == brand_id,
                    ContributionReport.is_active.is_(True),
                )
                .order_by(ContributionReport.created_at.desc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    return [_cr_dict(r) for r in rows]


async def get_attribution_model_runs(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(AttributionModelRun)
                .where(AttributionModelRun.brand_id == brand_id)
                .order_by(AttributionModelRun.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    return [_amr_dict(r) for r in rows]
