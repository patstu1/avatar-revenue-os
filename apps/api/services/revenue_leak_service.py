"""Revenue Leak Detector Service — detect, cluster, estimate, persist."""
from __future__ import annotations
import uuid
from typing import Any
from datetime import datetime, timezone
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from packages.db.models.accounts import CreatorAccount
from packages.db.models.account_state_intel import AccountStateReport
from packages.db.models.content import ContentItem
from packages.db.models.offer_lab import OfferLabOffer
from packages.db.models.provider_registry import ProviderBlocker
from packages.db.models.publishing import PerformanceMetric
from packages.db.models.revenue_leak_detector import (
    RevenueLeakReport, RevenueLeakEvent, LeakCluster,
    LeakCorrectionAction, RevenueLossEstimate,
)
from packages.scoring.revenue_leak_engine import detect_leaks, cluster_leaks, estimate_total_loss, generate_corrections


async def recompute_leaks(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(delete(LeakCorrectionAction).where(LeakCorrectionAction.brand_id == brand_id))
    await db.execute(delete(LeakCluster).where(LeakCluster.brand_id == brand_id))
    await db.execute(delete(RevenueLeakEvent).where(RevenueLeakEvent.brand_id == brand_id))
    await db.execute(delete(RevenueLeakReport).where(RevenueLeakReport.brand_id == brand_id))
    await db.execute(delete(RevenueLossEstimate).where(RevenueLossEstimate.brand_id == brand_id))

    system_data = await _gather_system_data(db, brand_id)
    leaks = detect_leaks(system_data)
    clusters = cluster_leaks(leaks)
    loss = estimate_total_loss(leaks)
    corrections = generate_corrections(leaks)

    critical = sum(1 for l in leaks if l.get("severity") == "critical")
    top_type = clusters[0]["cluster_type"] if clusters else None
    summary = f"{len(leaks)} leaks detected, ${loss['total_estimated_loss']:.0f} estimated loss, {critical} critical"

    report = RevenueLeakReport(brand_id=brand_id, total_leaks=len(leaks), total_estimated_loss=loss["total_estimated_loss"], critical_count=critical, top_leak_type=top_type, summary=summary)
    db.add(report); await db.flush()

    event_map = {}
    for l in leaks:
        aid = None
        if l.get("affected_id"):
            try: aid = uuid.UUID(str(l["affected_id"]))
            except: pass
        ev = RevenueLeakEvent(brand_id=brand_id, report_id=report.id, leak_type=l["leak_type"], severity=l["severity"], affected_scope=l["affected_scope"], affected_id=aid, estimated_revenue_loss=l["estimated_revenue_loss"], confidence=l["confidence"], evidence_json=l.get("evidence_json", {}), next_best_action=l["next_best_action"], truth_label=l.get("truth_label", "measured"))
        db.add(ev); await db.flush()
        event_map[id(l)] = ev.id

    for c in clusters:
        db.add(LeakCluster(brand_id=brand_id, cluster_type=c["cluster_type"], event_count=c["event_count"], total_loss=c["total_loss"], priority_score=c["priority_score"], recommended_action=c["recommended_action"]))

    for i, corr in enumerate(corrections):
        leak_ev_id = list(event_map.values())[i] if i < len(event_map) else list(event_map.values())[0] if event_map else None
        if leak_ev_id:
            db.add(LeakCorrectionAction(brand_id=brand_id, leak_event_id=leak_ev_id, action_type=corr["action_type"], action_detail=corr["action_detail"], target_system=corr["target_system"], priority=corr["priority"]))

    db.add(RevenueLossEstimate(brand_id=brand_id, period=datetime.now(timezone.utc).strftime("%Y-%m"), total_estimated_loss=loss["total_estimated_loss"], by_leak_type=loss["by_leak_type"], by_scope=loss["by_scope"]))

    await db.flush()
    return {"rows_processed": len(leaks), "clusters": len(clusters), "total_loss": loss["total_estimated_loss"], "status": "completed"}


async def _gather_system_data(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    data: dict[str, Any] = {"content_items": [], "landing_pages": [], "offers": [], "accounts": [], "provider_blockers": []}

    perfs = list((await db.execute(select(PerformanceMetric).where(PerformanceMetric.brand_id == brand_id).limit(200))).scalars().all())
    ci_perf: dict[uuid.UUID, dict] = {}
    for p in perfs:
        ci_perf.setdefault(p.content_item_id, {"impressions": 0, "clicks": 0, "revenue": 0, "engagement_rate": 0, "n": 0})
        agg = ci_perf[p.content_item_id]
        agg["impressions"] += float(p.impressions or 0)
        agg["clicks"] += float(p.clicks or 0)
        agg["revenue"] += float(p.revenue or 0)
        agg["engagement_rate"] += float(p.engagement_rate or 0)
        agg["n"] += 1

    for cid, agg in ci_perf.items():
        n = max(1, agg["n"])
        cvr = agg["clicks"] / max(agg["impressions"], 1) if agg["impressions"] > 0 else 0
        data["content_items"].append({"id": str(cid), "impressions": agg["impressions"], "clicks": agg["clicks"], "revenue": agg["revenue"], "engagement_rate": agg["engagement_rate"] / n, "conversion_rate": cvr})

    offers = list((await db.execute(select(OfferLabOffer).where(OfferLabOffer.brand_id == brand_id, OfferLabOffer.is_active.is_(True)))).scalars().all())
    for o in offers:
        data["offers"].append({"id": str(o.id), "rank_score": float(o.rank_score), "usage_count": 0})

    states = list((await db.execute(select(AccountStateReport).where(AccountStateReport.brand_id == brand_id, AccountStateReport.is_active.is_(True)))).scalars().all())
    for s in states:
        data["accounts"].append({"id": str(s.account_id), "state": s.current_state, "revenue": 0})

    blockers = list((await db.execute(select(ProviderBlocker).where(ProviderBlocker.brand_id == brand_id, ProviderBlocker.is_active.is_(True)))).scalars().all())
    for b in blockers:
        data["provider_blockers"].append({"id": str(b.id), "name": b.provider_key})

    return data


async def list_reports(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(RevenueLeakReport).where(RevenueLeakReport.brand_id == brand_id).order_by(RevenueLeakReport.created_at.desc()).limit(10))).scalars().all())

async def list_events(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(RevenueLeakEvent).where(RevenueLeakEvent.brand_id == brand_id, RevenueLeakEvent.is_active.is_(True)).order_by(RevenueLeakEvent.estimated_revenue_loss.desc()).limit(50))).scalars().all())

async def list_clusters(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(LeakCluster).where(LeakCluster.brand_id == brand_id, LeakCluster.is_active.is_(True)).order_by(LeakCluster.priority_score.desc()))).scalars().all())

async def list_corrections(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(LeakCorrectionAction).where(LeakCorrectionAction.brand_id == brand_id, LeakCorrectionAction.is_active.is_(True)).order_by(LeakCorrectionAction.priority))).scalars().all())

async def get_leak_summary(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    """Downstream: quick leak summary for copilot."""
    report = (await db.execute(select(RevenueLeakReport).where(RevenueLeakReport.brand_id == brand_id).order_by(RevenueLeakReport.created_at.desc()).limit(1))).scalar_one_or_none()
    if not report:
        return {"total_leaks": 0, "total_loss": 0}
    return {"total_leaks": report.total_leaks, "total_loss": report.total_estimated_loss, "critical": report.critical_count, "top_type": report.top_leak_type, "summary": report.summary}
