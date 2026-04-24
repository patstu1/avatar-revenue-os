"""Offer lifecycle service — health tracking, decay detection, state transitions."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.core import Brand
from packages.db.models.offer_lifecycle import OfferLifecycleEvent, OfferLifecycleReport
from packages.db.models.offers import Offer
from packages.db.models.publishing import PerformanceMetric
from packages.scoring.offer_lifecycle_engine import (
    OLC,
    assess_offer_lifecycle,
    recommend_lifecycle_transition,
)


def _strip_meta(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k != OLC}


# ---------------------------------------------------------------------------
# Recompute
# ---------------------------------------------------------------------------


async def recompute_offer_lifecycle(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    offers = list(
        (await db.execute(select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True)))).scalars().all()
    )
    if not offers:
        return {"lifecycle_reports": 0, "lifecycle_events": 0}

    perf_agg = (
        await db.execute(
            select(
                PerformanceMetric.content_item_id,
                func.coalesce(func.sum(PerformanceMetric.revenue), 0.0).label("rev"),
                func.coalesce(func.avg(PerformanceMetric.engagement_rate), 0.0).label("eng"),
            )
            .where(PerformanceMetric.brand_id == brand_id)
            .group_by(PerformanceMetric.content_item_id)
        )
    ).all()
    perf_map: dict[str, tuple[float, float]] = {str(row[0]): (float(row[1]), float(row[2])) for row in perf_agg}

    existing_reports = list(
        (
            await db.execute(
                select(OfferLifecycleReport).where(
                    OfferLifecycleReport.brand_id == brand_id,
                    OfferLifecycleReport.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    current_state_map: dict[str, str] = {str(r.offer_id): r.lifecycle_state for r in existing_reports}

    offer_dicts: list[dict[str, Any]] = []
    for o in offers:
        revenue = float(getattr(o, "total_revenue", 0) or 0)
        conversions = int(getattr(o, "total_conversions", 0) or 0)
        age_days = int(getattr(o, "age_days", 30) or 30)
        growth_rate = float(getattr(o, "growth_rate", 0.05) or 0.05)

        offer_dicts.append(
            {
                "offer_id": str(o.id),
                "name": o.name,
                "age_days": age_days,
                "total_conversions": conversions,
                "revenue": revenue,
                "growth_rate": growth_rate,
                "is_paused": not o.is_active,
                "is_retired": False,
            }
        )

    performance_history: list[dict[str, Any]] = []
    for o in offers:
        oid = str(o.id)
        rev, eng = perf_map.get(oid, (0.0, 0.0))
        performance_history.append(
            {
                "offer_id": oid,
                "period_index": 0,
                "conversion_rate": float(o.conversion_rate or 0),
                "revenue": rev,
            }
        )
        performance_history.append(
            {
                "offer_id": oid,
                "period_index": 1,
                "conversion_rate": float(o.conversion_rate or 0) * 0.95,
                "revenue": rev * 0.95,
            }
        )

    assessments = assess_offer_lifecycle(offer_dicts, performance_history)

    await db.execute(
        delete(OfferLifecycleReport).where(
            OfferLifecycleReport.brand_id == brand_id,
            OfferLifecycleReport.is_active.is_(True),
        )
    )

    report_count = 0
    event_count = 0

    for assessment in assessments:
        r = _strip_meta(assessment)
        offer_id_str = r.get("offer_id")
        offer_id = uuid.UUID(offer_id_str) if offer_id_str else None
        if not offer_id:
            continue

        db.add(
            OfferLifecycleReport(
                brand_id=brand_id,
                offer_id=offer_id,
                lifecycle_state=r.get("lifecycle_state", "active"),
                health_score=float(r.get("health_score", 0)),
                dependency_risk_score=float(r.get("dependency_risk_score", 0)),
                decay_score=float(r.get("decay_score", 0)),
                recommended_next_action=r.get("recommended_action"),
                expected_impact_json=r.get("expected_impact"),
                confidence_score=float(r.get("confidence", 0)),
                explanation_json={"explanation": r.get("explanation", "")},
                is_active=True,
            )
        )
        report_count += 1

        current_db_state = current_state_map.get(offer_id_str)
        if current_db_state:
            assessment_with_state = {**r, "current_db_state": current_db_state}
            transition = recommend_lifecycle_transition(assessment_with_state)
            t = _strip_meta(transition)

            if t.get("event_type") != "no_change":
                db.add(
                    OfferLifecycleEvent(
                        brand_id=brand_id,
                        offer_id=offer_id,
                        event_type=t.get("event_type", "transition"),
                        from_state=t.get("from_state"),
                        to_state=t.get("to_state"),
                        reason_json={
                            "reason": t.get("reason", ""),
                            "confidence": t.get("confidence", 0),
                        },
                    )
                )
                event_count += 1

    await db.flush()
    return {"lifecycle_reports": report_count, "lifecycle_events": event_count}


# ---------------------------------------------------------------------------
# Dict helpers
# ---------------------------------------------------------------------------


def _olr_dict(x: OfferLifecycleReport) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "offer_id": str(x.offer_id),
        "lifecycle_state": x.lifecycle_state,
        "health_score": x.health_score,
        "dependency_risk_score": x.dependency_risk_score,
        "decay_score": x.decay_score,
        "recommended_next_action": x.recommended_next_action,
        "expected_impact_json": x.expected_impact_json,
        "confidence_score": x.confidence_score,
        "explanation_json": x.explanation_json,
        "is_active": x.is_active,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


def _ole_dict(x: OfferLifecycleEvent) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "offer_id": str(x.offer_id),
        "event_type": x.event_type,
        "from_state": x.from_state,
        "to_state": x.to_state,
        "reason_json": x.reason_json,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


# ---------------------------------------------------------------------------
# Getters
# ---------------------------------------------------------------------------


async def get_offer_lifecycle_reports(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(OfferLifecycleReport)
                .where(
                    OfferLifecycleReport.brand_id == brand_id,
                    OfferLifecycleReport.is_active.is_(True),
                )
                .order_by(OfferLifecycleReport.created_at.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    return [_olr_dict(r) for r in rows]


async def get_offer_lifecycle_events(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(OfferLifecycleEvent)
                .where(OfferLifecycleEvent.brand_id == brand_id)
                .order_by(OfferLifecycleEvent.created_at.desc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    return [_ole_dict(r) for r in rows]
