"""Audience State service — segment state inference, transition events, action recs."""
from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

from packages.db.models.audience_state import AudienceStateEvent, AudienceStateReport
from packages.db.models.core import Brand
from packages.db.models.offers import AudienceSegment
from packages.scoring.audience_state_engine import (
    AUDIENCE_STATE,
    infer_audience_states,
    recommend_state_actions,
)


def _strip_meta(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k != AUDIENCE_STATE}


# ---------------------------------------------------------------------------
# Recompute
# ---------------------------------------------------------------------------


async def recompute_audience_states(
    db: AsyncSession, brand_id: uuid.UUID
) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    # Capture previous reports for transition detection before deleting
    prev_rows = list(
        (
            await db.execute(
                select(AudienceStateReport).where(
                    AudienceStateReport.brand_id == brand_id,
                    AudienceStateReport.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    prev_states: dict[str, str] = {}
    for pr in prev_rows:
        seg_id = str(pr.audience_segment_id) if pr.audience_segment_id else ""
        prev_states[seg_id] = pr.state_name

    # Delete existing active reports and events
    await db.execute(
        delete(AudienceStateEvent).where(AudienceStateEvent.brand_id == brand_id)
    )
    await db.execute(
        delete(AudienceStateReport).where(
            AudienceStateReport.brand_id == brand_id,
            AudienceStateReport.is_active.is_(True),
        )
    )

    # Load audience segments
    segments = list(
        (
            await db.execute(
                select(AudienceSegment).where(
                    AudienceSegment.brand_id == brand_id,
                    AudienceSegment.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )

    if not segments:
        return {"audience_state_reports": 0, "transition_events": 0}

    # Build segment dicts and engagement data per segment
    segment_dicts: list[dict[str, Any]] = []
    engagement_data: dict[str, Any] = {}

    for seg in segments:
        seg_id_str = str(seg.id)
        segment_dicts.append({
            "segment_id": seg_id_str,
            "name": seg.name,
            "estimated_size": seg.estimated_size,
        })

        engagement_data[seg_id_str] = {
            "engagement_rate": float(seg.conversion_rate or 0) * 0.5,
            "purchase_count": max(0, int(float(seg.revenue_contribution or 0) / max(1, float(seg.avg_ltv or 1)))),
            "ltv": float(seg.avg_ltv or 0),
            "recency_days": 30,
            "frequency": min(1.0, float(seg.conversion_rate or 0) * 5),
            "feedback_sentiment": 0.6,
        }

    # Call engine
    state_results = infer_audience_states(segment_dicts, engagement_data)

    report_count = 0
    event_count = 0

    for sr in state_results:
        r = _strip_meta(sr)
        seg_uuid: uuid.UUID | None = None
        try:
            seg_uuid = uuid.UUID(r["segment_id"])
        except (ValueError, KeyError):
            logger.debug("segment_id_parse_failed", exc_info=True)

        db.add(
            AudienceStateReport(
                brand_id=brand_id,
                audience_segment_id=seg_uuid,
                state_name=r["state_name"],
                state_score=float(r["state_score"]),
                transition_probabilities_json=r.get("transition_probabilities", {}),
                best_next_action=r["best_next_action"][:255],
                confidence_score=float(r["confidence"]),
                explanation_json={"explanation": r.get("explanation", "")},
            )
        )
        report_count += 1

        # Detect transitions from previous state
        seg_key = str(seg_uuid) if seg_uuid else r.get("segment_id", "")
        old_state = prev_states.get(seg_key)
        new_state = r["state_name"]

        if old_state and old_state != new_state:
            action_rec = recommend_state_actions(r)
            action_clean = _strip_meta(action_rec)
            db.add(
                AudienceStateEvent(
                    brand_id=brand_id,
                    audience_segment_id=seg_uuid,
                    from_state=old_state,
                    to_state=new_state,
                    trigger_reason_json={
                        "reason": f"State transition detected: {old_state} → {new_state}",
                        "recommended_content_type": action_clean.get("recommended_content_type"),
                        "recommended_offer_approach": action_clean.get("recommended_offer_approach"),
                        "recommended_channel": action_clean.get("recommended_channel"),
                        "expected_conversion_lift": action_clean.get("expected_conversion_lift"),
                    },
                )
            )
            event_count += 1

    await db.flush()
    return {"audience_state_reports": report_count, "transition_events": event_count}


# ---------------------------------------------------------------------------
# Dict helpers
# ---------------------------------------------------------------------------


def _report_dict(x: AudienceStateReport) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "audience_segment_id": str(x.audience_segment_id) if x.audience_segment_id else None,
        "state_name": x.state_name,
        "state_score": x.state_score,
        "transition_probabilities_json": x.transition_probabilities_json,
        "best_next_action": x.best_next_action,
        "confidence_score": x.confidence_score,
        "explanation_json": x.explanation_json,
        "is_active": x.is_active,
        "data_source": "synthetic_proxy",
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


# ---------------------------------------------------------------------------
# Getter
# ---------------------------------------------------------------------------


async def get_audience_states(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(AudienceStateReport)
                .where(
                    AudienceStateReport.brand_id == brand_id,
                    AudienceStateReport.is_active.is_(True),
                )
                .order_by(AudienceStateReport.state_score.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_report_dict(r) for r in rows]
