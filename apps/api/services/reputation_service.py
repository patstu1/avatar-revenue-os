"""Reputation service — brand reputation risk assessment and event tracking."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.offers import SponsorProfile
from packages.db.models.publishing import PerformanceMetric
from packages.db.models.reputation import ReputationEvent, ReputationReport
from packages.scoring.reputation_engine import REPUTATION, assess_reputation


def _strip_meta(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k != REPUTATION}


# ---------------------------------------------------------------------------
# Recompute
# ---------------------------------------------------------------------------


async def recompute_reputation(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    # Delete active reports and events
    await db.execute(delete(ReputationEvent).where(ReputationEvent.brand_id == brand_id))
    await db.execute(
        delete(ReputationReport).where(
            ReputationReport.brand_id == brand_id,
            ReputationReport.is_active.is_(True),
        )
    )

    # Brand-level data
    aud_scalar = (
        await db.execute(
            select(func.coalesce(func.sum(CreatorAccount.follower_count), 0)).where(CreatorAccount.brand_id == brand_id)
        )
    ).scalar()
    audience_size = int(aud_scalar or 0)

    avg_eng = (
        await db.execute(
            select(func.coalesce(func.avg(PerformanceMetric.engagement_rate), 0.04)).where(
                PerformanceMetric.brand_id == brand_id
            )
        )
    ).scalar()
    avg_engagement = float(avg_eng or 0.04)

    sponsor_rows = list(
        (
            await db.execute(
                select(SponsorProfile).where(
                    SponsorProfile.brand_id == brand_id,
                    SponsorProfile.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    sponsor_names = [sp.sponsor_name for sp in sponsor_rows]

    brand_data: dict[str, Any] = {
        "niche": brand.niche or "general",
        "platform_warnings": 0,
        "disclosure_policy": True,
        "sponsor_names": sponsor_names,
        "audience_size": audience_size,
        "avg_engagement_rate": avg_engagement,
    }

    # Account-level signals
    accounts = list(
        (await db.execute(select(CreatorAccount).where(CreatorAccount.brand_id == brand_id))).scalars().all()
    )
    account_signals: list[dict[str, Any]] = []
    for acc in accounts:
        account_signals.append(
            {
                "platform": getattr(acc.platform, "value", str(acc.platform)),
                "follower_delta": int(acc.follower_count * acc.follower_growth_rate) if acc.follower_growth_rate else 0,
                "unfollow_rate": max(0.0, -float(acc.follower_growth_rate)) if acc.follower_growth_rate < 0 else 0.0,
                "strike_count": 0,
                "engagement_rate": float(acc.conversion_rate or 0),
                "bot_follower_pct": float(acc.fatigue_score or 0) * 0.1,
                "comment_texts": [],
            }
        )

    # Content-level signals
    items = list(
        (await db.execute(select(ContentItem).where(ContentItem.brand_id == brand_id).limit(100))).scalars().all()
    )
    perf_rows = (
        await db.execute(
            select(
                PerformanceMetric.content_item_id,
                func.coalesce(func.avg(PerformanceMetric.engagement_rate), 0.04).label("eng"),
            )
            .where(PerformanceMetric.brand_id == brand_id)
            .group_by(PerformanceMetric.content_item_id)
        )
    ).all()
    perf_eng_map: dict[uuid.UUID, float] = {row[0]: float(row[1]) for row in perf_rows}

    content_signals: list[dict[str, Any]] = []
    for ci in items:
        content_signals.append(
            {
                "title": ci.title or "",
                "description": "",
                "has_disclosure": False,
                "claims": [],
                "engagement_rate": perf_eng_map.get(ci.id, 0.04),
                "comment_sentiment": 0.6,
                "generic_comment_pct": 0.2,
                "sponsor_name": None,
            }
        )

    # Call engine — single brand-wide assessment
    result = assess_reputation(brand_data, account_signals, content_signals)
    r = _strip_meta(result)

    db.add(
        ReputationReport(
            brand_id=brand_id,
            scope_type="brand",
            scope_id=None,
            reputation_risk_score=float(r["reputation_risk_score"]),
            primary_risks_json=r.get("primary_risks", []),
            recommended_mitigation_json=r.get("recommended_mitigation", []),
            expected_impact_if_unresolved=float(r["expected_impact_if_unresolved"]),
            confidence_score=float(r["confidence"]),
        )
    )

    # Create events for each primary risk identified
    event_count = 0
    for risk in r.get("primary_risks", []):
        severity = (
            "high"
            if float(risk.get("score", 0)) >= 0.6
            else ("medium" if float(risk.get("score", 0)) >= 0.3 else "low")
        )
        db.add(
            ReputationEvent(
                brand_id=brand_id,
                event_type=risk.get("risk_type", "unknown"),
                severity=severity,
                scope_type="brand",
                scope_id=None,
                details_json={
                    "score": risk.get("score"),
                    "detail": risk.get("detail"),
                },
            )
        )
        event_count += 1

    await db.flush()
    return {"reputation_reports": 1, "reputation_events": event_count}


# ---------------------------------------------------------------------------
# Dict helpers
# ---------------------------------------------------------------------------


def _report_dict(x: ReputationReport) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "scope_type": x.scope_type,
        "scope_id": str(x.scope_id) if x.scope_id else None,
        "reputation_risk_score": x.reputation_risk_score,
        "primary_risks_json": x.primary_risks_json,
        "recommended_mitigation_json": x.recommended_mitigation_json,
        "expected_impact_if_unresolved": x.expected_impact_if_unresolved,
        "confidence_score": x.confidence_score,
        "is_active": x.is_active,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


# ---------------------------------------------------------------------------
# Getter
# ---------------------------------------------------------------------------


async def get_reputation_reports(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(ReputationReport)
                .where(
                    ReputationReport.brand_id == brand_id,
                    ReputationReport.is_active.is_(True),
                )
                .order_by(ReputationReport.reputation_risk_score.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_report_dict(r) for r in rows]


def _event_dict(x: ReputationEvent) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "event_type": x.event_type,
        "severity": x.severity,
        "scope_type": x.scope_type,
        "scope_id": str(x.scope_id) if x.scope_id else None,
        "details_json": x.details_json,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


async def get_reputation_events(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(ReputationEvent)
                .where(ReputationEvent.brand_id == brand_id)
                .order_by(ReputationEvent.created_at.desc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    return [_event_dict(r) for r in rows]
