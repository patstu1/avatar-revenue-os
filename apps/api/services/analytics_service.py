"""Analytics service: ingestion, attribution, rollups, winners, suppression, memory.

Core Phase 4 orchestration. All business logic in service layer.
"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.enums import (
    ActorType,
    ConfidenceLevel,
    DecisionMode,
    DecisionType,
    JobStatus,
    Platform,
    RecommendedAction,
    SuppressionReason,
)
from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.decisions import SuppressionDecision
from packages.db.models.experiments import WinnerCloneJob
from packages.db.models.learning import MemoryEntry
from packages.db.models.publishing import AttributionEvent, PerformanceMetric
from packages.db.models.system import SuppressionAction
from packages.scoring.bottleneck import BottleneckInput, classify_bottleneck
from packages.scoring.winner import ContentPerformance, detect_winners

# ── Performance Ingestion ────────────────────────────────────────────────────

async def ingest_performance(
    db: AsyncSession, brand_id: uuid.UUID, content_item_id: uuid.UUID,
    creator_account_id: uuid.UUID, platform: str, metrics: dict,
) -> PerformanceMetric:
    impressions = metrics.get("impressions", 0)
    views = metrics.get("views", 0)
    clicks = metrics.get("clicks", 0)
    ctr = clicks / impressions if impressions > 0 else 0.0
    revenue = metrics.get("revenue", 0.0)
    rpm = (revenue / impressions * 1000) if impressions > 0 else 0.0

    pm = PerformanceMetric(
        content_item_id=content_item_id,
        creator_account_id=creator_account_id,
        brand_id=brand_id,
        platform=Platform(platform),
        impressions=impressions,
        views=views,
        likes=metrics.get("likes", 0),
        comments=metrics.get("comments", 0),
        shares=metrics.get("shares", 0),
        saves=metrics.get("saves", 0),
        clicks=clicks,
        ctr=round(ctr, 4),
        watch_time_seconds=metrics.get("watch_time_seconds", 0),
        avg_watch_pct=metrics.get("avg_watch_pct", 0.0),
        followers_gained=metrics.get("followers_gained", 0),
        revenue=revenue,
        revenue_source=metrics.get("revenue_source"),
        rpm=round(rpm, 2),
        engagement_rate=metrics.get("engagement_rate", 0.0),
        raw_data=metrics,
    )
    db.add(pm)
    await db.flush()
    await db.refresh(pm)
    return pm


# ── Attribution Events ───────────────────────────────────────────────────────

async def track_click(db: AsyncSession, data: dict) -> AttributionEvent:
    event = AttributionEvent(
        brand_id=uuid.UUID(data["brand_id"]),
        content_item_id=uuid.UUID(data["content_item_id"]) if data.get("content_item_id") else None,
        offer_id=uuid.UUID(data["offer_id"]) if data.get("offer_id") else None,
        creator_account_id=uuid.UUID(data["creator_account_id"]) if data.get("creator_account_id") else None,
        event_type="click",
        event_value=0.0,
        platform=data.get("platform"),
        source_url=data.get("source_url"),
        tracking_id=data.get("tracking_id"),
        raw_event=data,
    )
    db.add(event)
    await db.flush()
    await db.refresh(event)
    return event


async def track_conversion(db: AsyncSession, data: dict) -> AttributionEvent:
    event = AttributionEvent(
        brand_id=uuid.UUID(data["brand_id"]),
        content_item_id=uuid.UUID(data["content_item_id"]) if data.get("content_item_id") else None,
        offer_id=uuid.UUID(data["offer_id"]) if data.get("offer_id") else None,
        creator_account_id=uuid.UUID(data["creator_account_id"]) if data.get("creator_account_id") else None,
        event_type=data.get("event_type", "purchase"),
        event_value=data.get("event_value", 0.0),
        currency=data.get("currency", "USD"),
        platform=data.get("platform"),
        attribution_model=data.get("attribution_model", "last_click"),
        source_url=data.get("source_url"),
        tracking_id=data.get("tracking_id"),
        raw_event=data,
    )
    db.add(event)
    await db.flush()
    await db.refresh(event)
    return event


# ── Revenue Rollups ──────────────────────────────────────────────────────────

async def get_revenue_dashboard(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    gross = (await db.execute(
        select(func.coalesce(func.sum(PerformanceMetric.revenue), 0.0))
        .where(PerformanceMetric.brand_id == brand_id)
    )).scalar() or 0.0

    total_cost = (await db.execute(
        select(func.coalesce(func.sum(ContentItem.total_cost), 0.0))
        .where(ContentItem.brand_id == brand_id)
    )).scalar() or 0.0

    total_impressions = (await db.execute(
        select(func.coalesce(func.sum(PerformanceMetric.impressions), 0))
        .where(PerformanceMetric.brand_id == brand_id)
    )).scalar() or 0

    total_clicks = (await db.execute(
        select(func.coalesce(func.sum(PerformanceMetric.clicks), 0))
        .where(PerformanceMetric.brand_id == brand_id)
    )).scalar() or 0

    total_conversions = (await db.execute(
        select(func.count()).select_from(AttributionEvent)
        .where(AttributionEvent.brand_id == brand_id, AttributionEvent.event_type != "click")
    )).scalar() or 0

    attribution_revenue = (await db.execute(
        select(func.coalesce(func.sum(AttributionEvent.event_value), 0.0))
        .where(AttributionEvent.brand_id == brand_id, AttributionEvent.event_type != "click")
    )).scalar() or 0.0

    net_profit = float(gross) + float(attribution_revenue) - float(total_cost)
    rpm = (float(gross) / total_impressions * 1000) if total_impressions > 0 else 0.0
    avg_ctr = (total_clicks / total_impressions) if total_impressions > 0 else 0.0
    epc = (float(attribution_revenue) / total_clicks) if total_clicks > 0 else 0.0
    cr = (total_conversions / total_clicks) if total_clicks > 0 else 0.0

    by_platform = {}
    platform_q = await db.execute(
        select(PerformanceMetric.platform, func.sum(PerformanceMetric.revenue), func.sum(PerformanceMetric.impressions))
        .where(PerformanceMetric.brand_id == brand_id)
        .group_by(PerformanceMetric.platform)
    )
    for row in platform_q.all():
        by_platform[row[0].value if hasattr(row[0], 'value') else str(row[0])] = {
            "revenue": float(row[1] or 0), "impressions": int(row[2] or 0),
        }

    return {
        "gross_revenue": round(float(gross), 2),
        "attribution_revenue": round(float(attribution_revenue), 2),
        "total_revenue": round(float(gross) + float(attribution_revenue), 2),
        "total_cost": round(float(total_cost), 2),
        "net_profit": round(net_profit, 2),
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "total_conversions": total_conversions,
        "rpm": round(rpm, 2),
        "avg_ctr": round(avg_ctr, 4),
        "epc": round(epc, 2),
        "conversion_rate": round(cr, 4),
        "revenue_by_platform": by_platform,
    }


# ── Content Performance ──────────────────────────────────────────────────────

async def get_content_performance(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    items = (await db.execute(
        select(ContentItem).where(ContentItem.brand_id == brand_id).order_by(ContentItem.created_at.desc()).limit(50)
    )).scalars().all()

    results = []
    for item in items:
        metrics = (await db.execute(
            select(
                func.coalesce(func.sum(PerformanceMetric.impressions), 0),
                func.coalesce(func.sum(PerformanceMetric.views), 0),
                func.coalesce(func.sum(PerformanceMetric.clicks), 0),
                func.coalesce(func.sum(PerformanceMetric.revenue), 0.0),
                func.coalesce(func.avg(PerformanceMetric.ctr), 0.0),
                func.coalesce(func.avg(PerformanceMetric.engagement_rate), 0.0),
                func.coalesce(func.avg(PerformanceMetric.avg_watch_pct), 0.0),
            ).where(PerformanceMetric.content_item_id == item.id)
        )).one()

        attr_rev = (await db.execute(
            select(func.coalesce(func.sum(AttributionEvent.event_value), 0.0))
            .where(AttributionEvent.content_item_id == item.id, AttributionEvent.event_type != "click")
        )).scalar() or 0.0

        imps = int(metrics[0])
        revenue = float(metrics[3]) + float(attr_rev)
        profit = revenue - item.total_cost

        results.append({
            "content_id": str(item.id), "title": item.title,
            "status": item.status, "platform": item.platform,
            "impressions": imps, "views": int(metrics[1]), "clicks": int(metrics[2]),
            "revenue": round(revenue, 2), "cost": round(item.total_cost, 2),
            "profit": round(profit, 2),
            "rpm": round((revenue / imps * 1000) if imps > 0 else 0, 2),
            "ctr": round(float(metrics[4]), 4),
            "engagement_rate": round(float(metrics[5]), 4),
            "avg_watch_pct": round(float(metrics[6]), 4),
        })

    return sorted(results, key=lambda x: -x["profit"])


# ── Winner Detection + Clone ─────────────────────────────────────────────────

async def detect_and_clone_winners(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    perf = await get_content_performance(db, brand_id)

    accounts = (await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )).scalars().all()
    available_platforms = list({a.platform.value for a in accounts})

    items = [ContentPerformance(
        content_id=p["content_id"], title=p["title"],
        impressions=p["impressions"], revenue=p["revenue"], profit=p["profit"],
        rpm=p["rpm"], ctr=p["ctr"], engagement_rate=p["engagement_rate"],
        conversion_rate=0.0, platform=p["platform"] or "", account_id="",
    ) for p in perf]

    signals = detect_winners(items, available_platforms)
    winners = [s for s in signals if s.is_winner]
    losers = [s for s in signals if s.is_loser]

    clone_jobs = []
    for w in winners:
        if w.clone_recommended:
            cid = uuid.UUID(w.content_id)
            dup = (
                await db.execute(
                    select(WinnerCloneJob.id).where(
                        WinnerCloneJob.brand_id == brand_id,
                        WinnerCloneJob.source_content_item_id == cid,
                        WinnerCloneJob.status.in_([JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.RETRYING]),
                    ).limit(1)
                )
            ).scalar_one_or_none()
            if dup:
                continue
            job = WinnerCloneJob(
                brand_id=brand_id,
                source_content_item_id=cid,
                target_platforms=[{"platform": p} for p in w.clone_targets],
                clone_strategy="adapt",
                status=JobStatus.PENDING,
                explanation=w.explanation,
            )
            db.add(job)
            clone_jobs.append(w.content_id)

    for w in winners:
        await _update_memory(db, brand_id, f"winner:{w.content_id}",
                           "content_performance", "winner",
                           w.explanation, {"win_score": w.win_score, "title": w.title})

    for l in losers:
        await _update_memory(db, brand_id, f"loser:{l.content_id}",
                           "content_performance", "loser",
                           l.explanation, {"title": l.title})

    await db.flush()
    return {
        "total_analyzed": len(signals),
        "winners": [{"content_id": s.content_id, "title": s.title, "win_score": s.win_score,
                     "clone_recommended": s.clone_recommended, "explanation": s.explanation} for s in winners],
        "losers": [{"content_id": s.content_id, "title": s.title, "explanation": s.explanation} for s in losers],
        "clone_jobs_created": len(clone_jobs),
    }


# ── Suppression Engine ───────────────────────────────────────────────────────

async def evaluate_suppressions(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    perf = await get_content_performance(db, brand_id)
    results = []

    for p in perf:
        should_suppress = False
        reason = None
        detail = ""

        if p["impressions"] > 500 and p["profit"] < -5:
            should_suppress = True
            reason = SuppressionReason.LOW_PROFIT
            detail = f"Negative profit ${p['profit']:.2f} after {p['impressions']} impressions"

        elif p["impressions"] > 1000 and p["rpm"] < 1.0:
            should_suppress = True
            reason = SuppressionReason.LOW_PROFIT
            detail = f"RPM ${p['rpm']:.2f} — below minimum viable threshold"

        elif p["impressions"] > 5000 and p.get("engagement_rate", 0) < 0.005:
            should_suppress = True
            reason = SuppressionReason.FATIGUE
            detail = f"Engagement {p.get('engagement_rate', 0):.3%} after {p['impressions']} impressions — audience fatigue"

        elif p.get("saturation_score", 0) > 0.85:
            should_suppress = True
            reason = SuppressionReason.SATURATION
            detail = f"Saturation score {p.get('saturation_score', 0):.2f} — niche oversaturated"

        elif p.get("originality_score", 1.0) < 0.25:
            should_suppress = True
            reason = SuppressionReason.ORIGINALITY_LOW
            detail = f"Originality {p.get('originality_score', 1.0):.2f} — too similar to existing content"

        elif p.get("compliance_risk", False):
            should_suppress = True
            reason = SuppressionReason.COMPLIANCE_RISK
            detail = "Compliance risk flagged on this content"

        elif p.get("cannibalization_score", 0) > 0.75:
            should_suppress = True
            reason = SuppressionReason.CANNIBALIZATION
            detail = f"Cannibalization score {p.get('cannibalization_score', 0):.2f} — competing with own content"

        if should_suppress and reason:
            cid = uuid.UUID(p["content_id"])
            already = (
                await db.execute(
                    select(SuppressionAction.id).where(
                        SuppressionAction.brand_id == brand_id,
                        SuppressionAction.target_entity_type == "content_item",
                        SuppressionAction.target_entity_id == cid,
                        SuppressionAction.is_lifted.is_(False),
                    ).limit(1)
                )
            ).scalar_one_or_none()
            if already:
                continue

            action = SuppressionAction(
                brand_id=brand_id,
                target_entity_type="content_item",
                target_entity_id=cid,
                reason=reason,
                reason_detail=detail,
                suppressed_by="system",
            )
            db.add(action)

            decision = SuppressionDecision(
                brand_id=brand_id,
                decision_type=DecisionType.SUPPRESSION,
                decision_mode=DecisionMode.GUARDED_AUTO,
                actor_type=ActorType.SYSTEM,
                target_entity_type="content_item",
                target_entity_id=cid,
                suppression_reason=reason.value,
                composite_score=0.0,
                confidence=ConfidenceLevel.MEDIUM,
                recommended_action=RecommendedAction.SUPPRESS,
                explanation=detail,
                input_snapshot=p,
            )
            db.add(decision)

            results.append({
                "content_id": p["content_id"], "title": p["title"],
                "reason": reason.value, "detail": detail,
            })

    await db.flush()
    return results


# ── Bottleneck Classification ────────────────────────────────────────────────

async def classify_bottlenecks(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    accounts = (await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )).scalars().all()

    results = []
    for acct in accounts:
        metrics = (await db.execute(
            select(
                func.coalesce(func.sum(PerformanceMetric.impressions), 0),
                func.coalesce(func.sum(PerformanceMetric.clicks), 0),
                func.coalesce(func.avg(PerformanceMetric.ctr), 0.0),
                func.coalesce(func.avg(PerformanceMetric.avg_watch_pct), 0.0),
                func.coalesce(func.avg(PerformanceMetric.engagement_rate), 0.0),
                func.coalesce(func.sum(PerformanceMetric.revenue), 0.0),
            ).where(PerformanceMetric.creator_account_id == acct.id)
        )).one()

        conversions = (await db.execute(
            select(func.count()).select_from(AttributionEvent)
            .where(AttributionEvent.creator_account_id == acct.id, AttributionEvent.event_type != "click")
        )).scalar() or 0

        inp = BottleneckInput(
            impressions=int(metrics[0]),
            clicks=int(metrics[1]),
            ctr=float(metrics[2]),
            avg_watch_pct=float(metrics[3]),
            engagement_rate=float(metrics[4]),
            revenue=float(metrics[5]),
            conversions=conversions,
            conversion_rate=(conversions / int(metrics[1])) if int(metrics[1]) > 0 else 0,
            fatigue_score=acct.fatigue_score,
            posting_capacity_used_pct=0.5,
        )
        result = classify_bottleneck(inp)
        results.append({
            "account_id": str(acct.id),
            "username": acct.platform_username,
            "platform": acct.platform.value,
            "primary_bottleneck": result.primary_bottleneck,
            "severity": result.severity,
            "explanation": result.explanation,
            "recommended_actions": result.recommended_actions,
            "all_bottlenecks": result.all_bottlenecks,
        })

    return results


# ── Funnel View ──────────────────────────────────────────────────────────────

async def get_funnel_data(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    impressions = (await db.execute(
        select(func.coalesce(func.sum(PerformanceMetric.impressions), 0))
        .where(PerformanceMetric.brand_id == brand_id)
    )).scalar() or 0

    clicks = (await db.execute(
        select(func.count()).select_from(AttributionEvent)
        .where(AttributionEvent.brand_id == brand_id, AttributionEvent.event_type == "click")
    )).scalar() or 0

    event_types = ["click", "opt_in", "lead", "booked_call", "purchase",
                   "coupon_redemption", "affiliate_conversion", "assisted_conversion"]
    funnel = {}
    for et in event_types:
        count = (await db.execute(
            select(func.count()).select_from(AttributionEvent)
            .where(AttributionEvent.brand_id == brand_id, AttributionEvent.event_type == et)
        )).scalar() or 0
        value = (await db.execute(
            select(func.coalesce(func.sum(AttributionEvent.event_value), 0.0))
            .where(AttributionEvent.brand_id == brand_id, AttributionEvent.event_type == et)
        )).scalar() or 0.0
        funnel[et] = {"count": count, "value": round(float(value), 2)}

    return {
        "impressions": impressions, "total_clicks": clicks,
        "funnel_stages": funnel,
    }


# ── Revenue Leaks ────────────────────────────────────────────────────────────

async def preview_revenue_leaks(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    """Read-only leak list for dashboards (no suppression persistence)."""
    bottlenecks = await classify_bottlenecks(db, brand_id)
    leaks = []
    for b in bottlenecks:
        if b["severity"] in ("critical", "warning"):
            leaks.append({
                "type": "bottleneck",
                "entity": f"{b['username']} ({b['platform']})",
                "issue": b["primary_bottleneck"],
                "severity": b["severity"],
                "detail": b["explanation"],
                "actions": b["recommended_actions"],
            })
    perf = await get_content_performance(db, brand_id)
    for p in perf:
        if p["impressions"] > 500 and p["profit"] < -5:
            leaks.append({
                "type": "performance",
                "entity": p["title"],
                "issue": "low_profit",
                "severity": "critical",
                "detail": f"Negative profit ${p['profit']:.2f} after {p['impressions']} impressions",
                "actions": ["Suppress or rework content", "Check offer fit"],
            })
    return leaks


async def get_revenue_leaks(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    bottlenecks = await classify_bottlenecks(db, brand_id)
    suppressions = await evaluate_suppressions(db, brand_id)
    leaks = []

    for b in bottlenecks:
        if b["severity"] in ("critical", "warning"):
            leaks.append({
                "type": "bottleneck",
                "entity": f"{b['username']} ({b['platform']})",
                "issue": b["primary_bottleneck"],
                "severity": b["severity"],
                "detail": b["explanation"],
                "actions": b["recommended_actions"],
            })

    for s in suppressions:
        leaks.append({
            "type": "suppression",
            "entity": s["title"],
            "issue": s["reason"],
            "severity": "critical",
            "detail": s["detail"],
            "actions": ["Suppress content", "Rewrite", "Change offer"],
        })

    return leaks


# ── Memory Engine ────────────────────────────────────────────────────────────

async def _update_memory(
    db: AsyncSession, brand_id: uuid.UUID, key: str,
    memory_type: str, category: str, value: str, structured: dict,
):
    existing = (await db.execute(
        select(MemoryEntry).where(MemoryEntry.brand_id == brand_id, MemoryEntry.key == key)
    )).scalar_one_or_none()

    if existing:
        existing.value = value
        existing.structured_value = structured
        existing.times_reinforced += 1
    else:
        entry = MemoryEntry(
            brand_id=brand_id, memory_type=memory_type,
            category=category, key=key, value=value,
            structured_value=structured, confidence=0.7,
            source_type="analytics_service",
        )
        db.add(entry)
