"""Market Timing service — timing reports per category and macro signal events."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.core import Brand
from packages.db.models.market_timing import MacroSignalEvent, MarketTimingReport
from packages.db.models.offers import Offer
from packages.scoring.market_timing_engine import MARKET_TIMING, evaluate_market_timing


def _strip_meta(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k != MARKET_TIMING}


# ---------------------------------------------------------------------------
# Recompute
# ---------------------------------------------------------------------------


async def recompute_market_timing(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    # Delete active reports (keep macro signal events as historical record)
    await db.execute(
        delete(MarketTimingReport).where(
            MarketTimingReport.brand_id == brand_id,
            MarketTimingReport.is_active.is_(True),
        )
    )

    # Brand context
    aud_scalar = (
        await db.execute(
            select(func.coalesce(func.sum(CreatorAccount.follower_count), 0)).where(CreatorAccount.brand_id == brand_id)
        )
    ).scalar()
    audience_size = int(aud_scalar or 0)

    from packages.db.models.publishing import PerformanceMetric

    total_rev = (
        await db.execute(
            select(func.coalesce(func.sum(PerformanceMetric.revenue), 0.0)).where(
                PerformanceMetric.brand_id == brand_id
            )
        )
    ).scalar()
    avg_monthly_revenue = float(total_rev or 0.0) / 12.0

    active_offers = (
        await db.execute(
            select(func.count()).select_from(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
        )
    ).scalar()
    offer_count = int(active_offers or 0)

    now = datetime.now(timezone.utc)
    current_month = now.month

    brand_context: dict[str, Any] = {
        "niche": brand.niche or "general",
        "month": current_month,
        "audience_size": audience_size,
        "avg_monthly_revenue": avg_monthly_revenue,
        "content_types": [],
        "active_offer_count": offer_count,
    }

    # Load existing macro signal events for this brand
    existing_signals = list(
        (await db.execute(select(MacroSignalEvent).where(MacroSignalEvent.brand_id == brand_id))).scalars().all()
    )

    macro_signals: list[dict[str, Any]] = []
    for sig in existing_signals:
        meta = sig.signal_metadata_json or {}
        macro_signals.append(
            {
                "signal_type": sig.signal_type,
                "value": float(meta.get("value", 0.5)),
                "source": sig.source_name,
            }
        )

    # If no macro signals exist, synthesize baseline signals
    if not macro_signals:
        baseline_signals = [
            {"signal_type": "recession_indicator", "value": 0.3, "source": "synthetic_baseline"},
            {"signal_type": "ad_spend_trend", "value": 0.6, "source": "synthetic_baseline"},
            {"signal_type": "cpm_index", "value": 0.5, "source": "synthetic_baseline"},
        ]
        macro_signals = baseline_signals

        for bs in baseline_signals:
            db.add(
                MacroSignalEvent(
                    brand_id=brand_id,
                    signal_type=bs["signal_type"],
                    source_name=bs["source"],
                    signal_metadata_json={"value": bs["value"]},
                    observed_at=now,
                )
            )

    # Call engine
    results = evaluate_market_timing(brand_context, macro_signals)

    count = 0
    for entry in results:
        r = _strip_meta(entry)
        db.add(
            MarketTimingReport(
                brand_id=brand_id,
                market_category=r["market_category"],
                timing_score=float(r["timing_score"]),
                active_window=r.get("active_window"),
                recommendation=r.get("recommendation", ""),
                expected_uplift=float(r.get("expected_uplift", 0)),
                confidence_score=float(r["confidence"]),
                explanation_json={"explanation": r.get("explanation", "")},
            )
        )
        count += 1

    await db.flush()
    return {"market_timing_reports": count}


# ---------------------------------------------------------------------------
# Dict helpers
# ---------------------------------------------------------------------------


def _report_dict(x: MarketTimingReport) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "market_category": x.market_category,
        "timing_score": x.timing_score,
        "active_window": x.active_window,
        "recommendation": x.recommendation,
        "expected_uplift": x.expected_uplift,
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


async def get_market_timing_reports(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(MarketTimingReport)
                .where(
                    MarketTimingReport.brand_id == brand_id,
                    MarketTimingReport.is_active.is_(True),
                )
                .order_by(MarketTimingReport.timing_score.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_report_dict(r) for r in rows]


def _macro_dict(x: MacroSignalEvent) -> dict[str, Any]:
    source = x.source_name or ""
    ds = "synthetic_proxy" if "synthetic" in source or "baseline" in source or "seed" in source else "live_import"
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id) if x.brand_id else None,
        "signal_type": x.signal_type,
        "source_name": x.source_name,
        "signal_metadata_json": x.signal_metadata_json,
        "observed_at": x.observed_at,
        "data_source": ds,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


async def get_macro_signal_events(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(MacroSignalEvent)
                .where(MacroSignalEvent.brand_id == brand_id)
                .order_by(MacroSignalEvent.created_at.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    return [_macro_dict(r) for r in rows]
