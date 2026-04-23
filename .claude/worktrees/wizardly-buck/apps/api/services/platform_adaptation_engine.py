"""Platform Adaptation Engine — detects what's gaining traction and adapts.

Analyzes platform-specific performance trends and recommends format/timing/routing
adjustments. Does not bypass algorithms — adapts to them.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_action
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.publishing import PerformanceMetric

logger = structlog.get_logger()


async def analyze_platform_traction(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    """Detect what's gaining traction on each platform and recommend adaptations."""
    now = datetime.now(timezone.utc)
    day_14 = now - timedelta(days=14)
    day_30 = now - timedelta(days=30)

    # Performance by platform + content_type (last 14 days vs prior 14 days)
    recent_q = await db.execute(
        select(ContentItem.platform, ContentItem.content_type,
               func.sum(PerformanceMetric.impressions),
               func.sum(PerformanceMetric.revenue),
               func.avg(PerformanceMetric.engagement_rate),
               func.count())
        .outerjoin(PerformanceMetric, PerformanceMetric.content_item_id == ContentItem.id)
        .where(ContentItem.brand_id == brand_id, ContentItem.created_at >= day_14)
        .group_by(ContentItem.platform, ContentItem.content_type)
    )
    recent = {}
    for row in recent_q.all():
        key = f"{row[0]}:{row[1].value if hasattr(row[1], 'value') else row[1]}" if row[0] else None
        if key:
            recent[key] = {"impressions": int(row[2] or 0), "revenue": float(row[3] or 0),
                            "engagement": float(row[4] or 0), "count": row[5]}

    prior_q = await db.execute(
        select(ContentItem.platform, ContentItem.content_type,
               func.sum(PerformanceMetric.impressions),
               func.sum(PerformanceMetric.revenue),
               func.avg(PerformanceMetric.engagement_rate),
               func.count())
        .outerjoin(PerformanceMetric, PerformanceMetric.content_item_id == ContentItem.id)
        .where(ContentItem.brand_id == brand_id,
               ContentItem.created_at >= day_30, ContentItem.created_at < day_14)
        .group_by(ContentItem.platform, ContentItem.content_type)
    )
    prior = {}
    for row in prior_q.all():
        key = f"{row[0]}:{row[1].value if hasattr(row[1], 'value') else row[1]}" if row[0] else None
        if key:
            prior[key] = {"impressions": int(row[2] or 0), "revenue": float(row[3] or 0),
                           "engagement": float(row[4] or 0), "count": row[5]}

    # Compute traction signals
    traction_signals = []
    for key, r in recent.items():
        p = prior.get(key, {"impressions": 0, "revenue": 0, "engagement": 0, "count": 0})
        platform, content_type = key.split(":", 1)

        if p["impressions"] > 0:
            impression_growth = (r["impressions"] - p["impressions"]) / p["impressions"]
        else:
            impression_growth = 1.0 if r["impressions"] > 0 else 0

        if p["revenue"] > 0:
            revenue_growth = (r["revenue"] - p["revenue"]) / p["revenue"]
        else:
            revenue_growth = 1.0 if r["revenue"] > 0 else 0

        engagement_delta = r["engagement"] - p["engagement"]

        traction_score = (
            0.40 * min(1.0, max(-1.0, impression_growth)) +
            0.35 * min(1.0, max(-1.0, revenue_growth)) +
            0.25 * min(1.0, max(-1.0, engagement_delta * 10))
        )

        if abs(traction_score) > 0.1:  # Only surface meaningful changes
            traction_signals.append({
                "platform": platform,
                "content_type": content_type,
                "traction_score": round(traction_score, 3),
                "direction": "gaining" if traction_score > 0 else "losing",
                "impression_growth": round(impression_growth * 100, 1),
                "revenue_growth": round(revenue_growth * 100, 1),
                "engagement_delta": round(engagement_delta, 4),
                "recent_count": r["count"],
                "recommendation": _get_adaptation_recommendation(traction_score, platform, content_type),
            })

    traction_signals.sort(key=lambda x: abs(x["traction_score"]), reverse=True)

    # Identify best-performing platform/format combinations
    best_combos = sorted(recent.items(), key=lambda x: x[1]["revenue"], reverse=True)[:3]

    return {
        "traction_signals": traction_signals,
        "gaining_traction": [s for s in traction_signals if s["direction"] == "gaining"],
        "losing_traction": [s for s in traction_signals if s["direction"] == "losing"],
        "best_performing": [
            {"combo": k, "revenue": v["revenue"], "impressions": v["impressions"]}
            for k, v in best_combos if v["revenue"] > 0
        ],
        "adaptation_count": len(traction_signals),
    }


async def surface_adaptation_actions(
    db: AsyncSession, org_id: uuid.UUID, brand_id: uuid.UUID,
) -> list[dict]:
    """Create operator actions from platform traction analysis."""
    data = await analyze_platform_traction(db, brand_id)
    created = []

    # Gaining traction → scale up
    for signal in data.get("gaining_traction", [])[:2]:
        a = await emit_action(
            db, org_id=org_id, action_type="scale_winning_segment",
            title=f"Gaining traction: {signal['platform']}/{signal['content_type']} (+{signal['impression_growth']:.0f}%)",
            description=signal.get("recommendation", "Increase content frequency for this format/platform."),
            category="opportunity", priority="high" if signal["traction_score"] > 0.5 else "medium",
            brand_id=brand_id, source_module="platform_adaptation",
        )
        created.append({"type": "gaining_traction", "action_id": str(a.id)})

    # Losing traction → reduce or adapt
    for signal in data.get("losing_traction", [])[:2]:
        a = await emit_action(
            db, org_id=org_id, action_type="adapt_content_strategy",
            title=f"Losing traction: {signal['platform']}/{signal['content_type']} ({signal['impression_growth']:.0f}%)",
            description=signal.get("recommendation", "Consider reducing frequency or changing format."),
            category="monetization", priority="medium",
            brand_id=brand_id, source_module="platform_adaptation",
        )
        created.append({"type": "losing_traction", "action_id": str(a.id)})

    return created


def _get_adaptation_recommendation(traction_score: float, platform: str, content_type: str) -> str:
    if traction_score > 0.5:
        return f"Strong traction on {platform}/{content_type}. Double content frequency. Attach best offers. Test packaging variants."
    elif traction_score > 0.2:
        return f"Growing on {platform}/{content_type}. Maintain frequency. Optimize hooks and CTAs based on winning patterns."
    elif traction_score > -0.2:
        return f"Stable on {platform}/{content_type}. Maintain current approach. Monitor for changes."
    elif traction_score > -0.5:
        return f"Declining on {platform}/{content_type}. Reduce frequency. Experiment with different formats or topics."
    else:
        return f"Significant decline on {platform}/{content_type}. Pause or pivot. Reallocate effort to gaining platforms."
