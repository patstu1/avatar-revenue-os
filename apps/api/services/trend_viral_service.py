"""Trend / Viral Opportunity Service — scan, score, persist, suppress."""
from __future__ import annotations
import uuid
from typing import Any
from datetime import datetime, timezone
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from packages.db.models.accounts import CreatorAccount
from packages.db.models.core import Brand
from packages.db.models.discovery import TrendSignal as DiscoveryTrend
from packages.db.models.trend_viral import (
    TrendSignalEvent, TrendVelocityReport, ViralOpportunity, TrendOpportunityScore,
    TrendDuplicate, TrendSuppressionRule, TrendBlocker, TrendSourceHealth,
)
from packages.scoring.trend_viral_engine import (
    extract_signals, compute_velocity, check_duplicate, score_opportunity,
    classify_opportunity, should_suppress, detect_blockers,
)


async def light_scan(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    """60-second light scan: fetch signals, compute deltas, dedup."""
    now = datetime.now(timezone.utc)
    discovery = list((await db.execute(select(DiscoveryTrend).where(DiscoveryTrend.brand_id == brand_id).limit(50))).scalars().all())

    raw = [{"topic": d.keyword or str(d.id)[:8], "source": "discovery", "signal_strength": float(d.volume or 0), "velocity": float(d.velocity or 0), "truth_label": "internal_proxy"} for d in discovery]

    existing = list((await db.execute(select(TrendSignalEvent.topic).where(TrendSignalEvent.brand_id == brand_id, TrendSignalEvent.is_active.is_(True)))).scalars().all())
    signals = extract_signals(raw, existing)

    created = 0
    for s in signals:
        if s.get("is_new"):
            db.add(TrendSignalEvent(brand_id=brand_id, source=s["source"], topic=s["topic"], signal_strength=s["signal_strength"], velocity=s["velocity"], first_seen_at=now, last_seen_at=now, truth_label=s["truth_label"]))
            created += 1
        else:
            existing_sig = (await db.execute(select(TrendSignalEvent).where(TrendSignalEvent.brand_id == brand_id, TrendSignalEvent.topic == s["topic"], TrendSignalEvent.is_active.is_(True)).limit(1))).scalar_one_or_none()
            if existing_sig:
                existing_sig.last_seen_at = now
                existing_sig.velocity = s["velocity"]

    await db.flush()
    return {"signals_scanned": len(raw), "new_signals": created, "status": "completed"}


async def deep_analysis(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    """Deeper analysis on threshold-crossing signals — create opportunities."""
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    brand_ctx = {"niche": brand.niche if brand else "general"}
    has_accounts = (await db.execute(select(CreatorAccount.id).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True)).limit(1))).scalar() is not None

    signals = list((await db.execute(select(TrendSignalEvent).where(TrendSignalEvent.brand_id == brand_id, TrendSignalEvent.is_active.is_(True), TrendSignalEvent.velocity > 0.5))).scalars().all())
    suppressions = list((await db.execute(select(TrendSuppressionRule).where(TrendSuppressionRule.brand_id == brand_id, TrendSuppressionRule.is_active.is_(True)))).scalars().all())
    supp_dicts = [{"pattern": s.pattern, "reason": s.reason} for s in suppressions]

    existing_opps = list((await db.execute(select(ViralOpportunity.topic).where(ViralOpportunity.brand_id == brand_id, ViralOpportunity.is_active.is_(True)))).scalars().all())

    await db.execute(delete(TrendBlocker).where(TrendBlocker.brand_id == brand_id))
    now = datetime.now(timezone.utc)
    created = 0

    for sig in signals:
        dup = check_duplicate(sig.topic, existing_opps)
        if dup:
            db.add(TrendDuplicate(brand_id=brand_id, original_topic=dup, duplicate_topic=sig.topic, similarity=0.7))
            continue

        sig_dict = {"topic": sig.topic, "source": sig.source, "velocity": float(sig.velocity), "signal_strength": float(sig.signal_strength), "is_new": True, "truth_label": sig.truth_label}
        scores = score_opportunity(sig_dict, brand_ctx)
        suppressed = should_suppress(sig_dict, scores, supp_dicts)
        if suppressed:
            continue

        classification = classify_opportunity(scores)
        blockers = detect_blockers(sig_dict, {"has_accounts": has_accounts})

        vel = compute_velocity(float(sig.velocity), 0)
        db.add(TrendVelocityReport(brand_id=brand_id, topic=sig.topic, current_velocity=vel["current_velocity"], previous_velocity=vel["previous_velocity"], acceleration=vel["acceleration"], breakout=vel["breakout"]))

        opp = ViralOpportunity(brand_id=brand_id, topic=sig.topic, source=sig.source, first_seen_at=sig.first_seen_at, last_seen_at=now, **scores, **classification, explanation=f"{classification['opportunity_type']} opportunity — {sig.topic}", truth_label=sig.truth_label)
        db.add(opp); await db.flush()

        for dim in ["velocity", "novelty", "relevance", "revenue_potential", "platform_fit", "account_fit", "content_form_fit"]:
            db.add(TrendOpportunityScore(opportunity_id=opp.id, dimension=dim, score=scores.get(f"{dim}_score", 0)))

        for b in blockers:
            db.add(TrendBlocker(brand_id=brand_id, opportunity_id=opp.id, **b))

        existing_opps.append(sig.topic)
        created += 1

    db.add(TrendSourceHealth(brand_id=brand_id, source_name="discovery", status="healthy" if signals else "no_signals", last_signal_count=len(signals), truth_label="internal_proxy"))

    await db.flush()
    return {"rows_processed": len(signals), "opportunities_created": created, "status": "completed"}


async def list_signals(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(TrendSignalEvent).where(TrendSignalEvent.brand_id == brand_id, TrendSignalEvent.is_active.is_(True)).order_by(TrendSignalEvent.velocity.desc()).limit(50))).scalars().all())

async def list_velocity(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(TrendVelocityReport).where(TrendVelocityReport.brand_id == brand_id, TrendVelocityReport.is_active.is_(True)).order_by(TrendVelocityReport.current_velocity.desc()))).scalars().all())

async def list_opportunities(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(ViralOpportunity).where(ViralOpportunity.brand_id == brand_id, ViralOpportunity.is_active.is_(True)).order_by(ViralOpportunity.composite_score.desc()))).scalars().all())

async def list_blockers(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(TrendBlocker).where(TrendBlocker.brand_id == brand_id, TrendBlocker.is_active.is_(True)))).scalars().all())

async def list_source_health(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(TrendSourceHealth).where(TrendSourceHealth.brand_id == brand_id, TrendSourceHealth.is_active.is_(True)))).scalars().all())

async def get_top_opportunities(db: AsyncSession, brand_id: uuid.UUID, limit: int = 5) -> list[dict[str, Any]]:
    """Downstream: top trend opportunities for copilot/generation."""
    opps = list((await db.execute(select(ViralOpportunity).where(ViralOpportunity.brand_id == brand_id, ViralOpportunity.is_active.is_(True), ViralOpportunity.status == "active").order_by(ViralOpportunity.composite_score.desc()).limit(limit))).scalars().all())
    return [{"topic": o.topic, "score": o.composite_score, "type": o.opportunity_type, "platform": o.recommended_platform, "form": o.recommended_content_form, "monetization": o.recommended_monetization, "urgency": o.urgency} for o in opps]
