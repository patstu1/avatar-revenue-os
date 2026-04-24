"""Winning-Pattern Memory — recompute, list, persist."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

import sqlalchemy as sa
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.experiments import Experiment
from packages.db.models.learning import CommentIngestion
from packages.db.models.pattern_memory import (
    LosingPatternMemory,
    PatternDecayReport,
    PatternReuseRecommendation,
    WinningPatternCluster,
    WinningPatternEvidence,
    WinningPatternMemory,
)
from packages.db.models.publishing import PerformanceMetric
from packages.scoring.pattern_memory_engine import (
    cluster_patterns,
    compute_pattern_allocation_weights,
    detect_decay,
    extract_patterns_from_content,
    recommend_reuse,
    score_pattern,
    suggest_experiments_from_patterns,
)

DEFAULT_TARGET_PLATFORMS = ("tiktok", "instagram", "youtube", "facebook", "linkedin", "twitter")


def _evidence_for_scoring(raw: dict[str, Any]) -> dict[str, float]:
    ev = raw.get("evidence") or {}
    return {
        "engagement_rate": float(ev.get("engagement_rate", 0) or 0),
        "conversion_rate": float(ev.get("conversion_rate", 0) or 0),
        "profit": float(ev.get("profit", 0) or 0),
        "impressions": float(ev.get("impressions", 0) or 0),
    }


async def _delete_pattern_memory_rows(db: AsyncSession, brand_id: uuid.UUID) -> None:
    await db.execute(delete(PatternDecayReport).where(PatternDecayReport.brand_id == brand_id))
    await db.execute(delete(PatternReuseRecommendation).where(PatternReuseRecommendation.brand_id == brand_id))
    await db.execute(delete(WinningPatternEvidence).where(WinningPatternEvidence.brand_id == brand_id))
    await db.execute(delete(WinningPatternCluster).where(WinningPatternCluster.brand_id == brand_id))
    await db.execute(delete(LosingPatternMemory).where(LosingPatternMemory.brand_id == brand_id))
    await db.execute(delete(WinningPatternMemory).where(WinningPatternMemory.brand_id == brand_id))


async def recompute_patterns(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    niche = (brand.niche or "general") if brand else "general"

    old_rows = (
        (await db.execute(select(WinningPatternMemory).where(WinningPatternMemory.brand_id == brand_id)))
        .scalars()
        .all()
    )
    prior_map = {p.pattern_signature: float(p.win_score) for p in old_rows}

    await _delete_pattern_memory_rows(db, brand_id)

    items = (await db.execute(select(ContentItem).where(ContentItem.brand_id == brand_id))).scalars().all()

    metrics_rows = (
        (await db.execute(select(PerformanceMetric).where(PerformanceMetric.brand_id == brand_id))).scalars().all()
    )

    perf_by_ci: dict[uuid.UUID, dict[str, float]] = {}
    for m in metrics_rows:
        cid = m.content_item_id
        if cid not in perf_by_ci:
            perf_by_ci[cid] = {
                "impressions": 0.0,
                "clicks": 0.0,
                "engagement_rate": 0.0,
                "revenue": 0.0,
                "conversion_rate": 0.0,
                "profit": 0.0,
                "n": 0.0,
            }
        agg = perf_by_ci[cid]
        agg["impressions"] += float(m.impressions or 0)
        agg["clicks"] += float(m.clicks or 0)
        agg["revenue"] += float(m.revenue or 0)
        agg["engagement_rate"] += float(m.engagement_rate or 0)
        agg["conversion_rate"] += float(m.ctr or 0) / 100.0 if (m.ctr or 0) > 1 else float(m.ctr or 0)
        agg["n"] += 1.0

    performance: dict[str, dict[str, float]] = {}
    for cid, agg in perf_by_ci.items():
        n = max(1.0, agg["n"])
        performance[str(cid)] = {
            "impressions": agg["impressions"],
            "clicks": agg["clicks"],
            "engagement_rate": agg["engagement_rate"] / n,
            "revenue": agg["revenue"],
            "conversion_rate": agg["conversion_rate"] / n,
            "profit": agg["revenue"],
        }

    ci_ids = [ci.id for ci in items]
    comment_data: dict[str, dict[str, float]] = {}
    if ci_ids:
        comment_rows = (
            await db.execute(
                select(
                    CommentIngestion.content_item_id,
                    func.avg(CommentIngestion.sentiment_score).label("avg_sentiment"),
                    func.avg(func.cast(CommentIngestion.is_purchase_intent, sa.Integer)).label("purchase_intent_pct"),
                    func.avg(func.cast(CommentIngestion.is_complaint, sa.Integer)).label("objection_pct"),
                )
                .where(CommentIngestion.content_item_id.in_(ci_ids))
                .group_by(CommentIngestion.content_item_id)
            )
        ).all()
        for row in comment_rows:
            comment_data[str(row.content_item_id)] = {
                "avg_sentiment": float(row.avg_sentiment or 0),
                "purchase_intent_pct": float(row.purchase_intent_pct or 0),
                "objection_pct": float(row.objection_pct or 0),
            }

    content_items: list[dict[str, Any]] = []
    for ci in items:
        ct = ci.content_type
        ctype_val = ct.value if hasattr(ct, "value") else str(ct)
        content_items.append(
            {
                "id": str(ci.id),
                "platform": ci.platform or "unknown",
                "content_form": ctype_val,
                "content_type": ctype_val,
                "title": ci.title or "",
                "tags": ci.tags if isinstance(ci.tags, dict) else {},
                "monetization_method": ci.monetization_method or "",
                "cta_type": getattr(ci, "cta_type", None),
                "offer_angle": getattr(ci, "offer_angle", None),
                "hook_type": getattr(ci, "hook_type", None),
                "creative_structure": getattr(ci, "creative_structure", None),
                "audience_response_profile": getattr(ci, "audience_response_profile", None) or {},
            }
        )

    raw_patterns = extract_patterns_from_content(content_items, performance, niche=niche, comment_data=comment_data)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in raw_patterns:
        grouped[p["pattern_signature"]].append(p)

    winners = 0
    losers = 0
    for sig, members in grouped.items():
        first = members[0]
        evidence_list = [_evidence_for_scoring(m) for m in members]
        scored = score_pattern(evidence_list)
        win_score = float(scored["win_score"])
        confidence = float(scored["confidence"])
        performance_band = str(scored["performance_band"])
        usage_count = len(members)

        explanation = f"{first['pattern_type']}:{first['pattern_name']} — score {win_score:.2f}, n={usage_count}"

        ev_json: dict[str, Any] = {}
        if sig in prior_map:
            ev_json["prior_win_score"] = prior_map[sig]

        if win_score >= 0.6:
            wpm = WinningPatternMemory(
                brand_id=brand_id,
                pattern_type=first["pattern_type"],
                pattern_name=first["pattern_name"],
                pattern_signature=sig,
                platform=first.get("platform"),
                niche=first.get("niche"),
                content_form=first.get("content_form"),
                monetization_method=first.get("monetization_method") or None,
                performance_band=performance_band,
                confidence=confidence,
                win_score=win_score,
                decay_score=0.0,
                usage_count=usage_count,
                explanation=explanation,
                evidence_json=ev_json,
            )
            db.add(wpm)
            await db.flush()

            seen_ci: set[uuid.UUID] = set()
            for m in members:
                ev = m.get("evidence") or {}
                ci_raw = ev.get("content_item_id") or ""
                if not ci_raw:
                    continue
                try:
                    ci_uuid = uuid.UUID(str(ci_raw))
                except (ValueError, TypeError):
                    continue
                if ci_uuid in seen_ci:
                    continue
                seen_ci.add(ci_uuid)
                db.add(
                    WinningPatternEvidence(
                        pattern_id=wpm.id,
                        brand_id=brand_id,
                        content_item_id=ci_uuid,
                        impressions=int(ev.get("impressions", 0) or 0),
                        clicks=int(ev.get("clicks", 0) or 0),
                        engagement_rate=float(ev.get("engagement_rate", 0) or 0),
                        conversion_rate=float(ev.get("conversion_rate", 0) or 0),
                        profit=float(ev.get("profit", 0) or 0),
                        details_json=dict(ev),
                    )
                )
            winners += 1
        elif win_score < 0.25:
            db.add(
                LosingPatternMemory(
                    brand_id=brand_id,
                    pattern_type=first["pattern_type"],
                    pattern_name=first["pattern_name"],
                    pattern_signature=sig,
                    platform=first.get("platform"),
                    fail_score=max(0.0, 1.0 - win_score),
                    usage_count=usage_count,
                    suppress_reason="win_score_below_0.25",
                    evidence_json={"win_score": win_score, "sample_size": usage_count},
                )
            )
            losers += 1

    return {
        "rows_processed": len(grouped),
        "winners": winners,
        "losers": losers,
        "status": "completed",
    }


async def recompute_clusters(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(delete(WinningPatternCluster).where(WinningPatternCluster.brand_id == brand_id))

    rows = (
        (
            await db.execute(
                select(WinningPatternMemory).where(
                    WinningPatternMemory.brand_id == brand_id,
                    WinningPatternMemory.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )

    pattern_dicts = [
        {
            "id": str(p.id),
            "pattern_type": p.pattern_type,
            "pattern_name": p.pattern_name,
            "platform": p.platform or "",
            "win_score": float(p.win_score),
            "content_form": p.content_form,
        }
        for p in rows
    ]
    clusters = cluster_patterns(pattern_dicts)
    for c in clusters:
        db.add(
            WinningPatternCluster(
                brand_id=brand_id,
                cluster_name=c["cluster_name"],
                cluster_type=c["cluster_type"],
                pattern_ids=list(c.get("pattern_ids") or []),
                avg_win_score=float(c["avg_win_score"]),
                pattern_count=int(c["pattern_count"]),
                platform=c.get("platform"),
                explanation=c.get("explanation"),
            )
        )
    return {"rows_processed": len(clusters), "status": "completed"}


async def recompute_decay(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(delete(PatternDecayReport).where(PatternDecayReport.brand_id == brand_id))

    patterns = (
        (
            await db.execute(
                select(WinningPatternMemory).where(
                    WinningPatternMemory.brand_id == brand_id,
                    WinningPatternMemory.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )

    count = 0
    for p in patterns:
        evidence_rows = (
            (await db.execute(select(WinningPatternEvidence).where(WinningPatternEvidence.pattern_id == p.id)))
            .scalars()
            .all()
        )
        evidence_list = [
            {
                "engagement_rate": float(e.engagement_rate or 0),
                "conversion_rate": float(e.conversion_rate or 0),
                "profit": float(e.profit or 0),
                "impressions": float(e.impressions or 0),
            }
            for e in evidence_rows
        ]
        evidence_win = float(score_pattern(evidence_list)["win_score"]) if evidence_list else float(p.win_score)
        prev = float(p.win_score)
        decay = detect_decay(prev, evidence_win, p.usage_count or 0)
        rec = decay.get("recommendation")
        db.add(
            PatternDecayReport(
                brand_id=brand_id,
                pattern_id=p.id,
                decay_rate=float(decay["decay_rate"]),
                decay_reason=str(decay["decay_reason"]),
                previous_win_score=prev,
                current_win_score=evidence_win,
                recommendation=str(rec) if rec else None,
            )
        )
        p.decay_score = float(decay["decay_rate"])
        count += 1

    return {"rows_processed": count, "status": "completed"}


async def recompute_reuse(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(delete(PatternReuseRecommendation).where(PatternReuseRecommendation.brand_id == brand_id))

    rows = (
        (
            await db.execute(
                select(WinningPatternMemory).where(
                    WinningPatternMemory.brand_id == brand_id,
                    WinningPatternMemory.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )

    platforms = {p.platform for p in rows if p.platform}
    target_platforms = sorted(set(DEFAULT_TARGET_PLATFORMS) | platforms)

    winning_patterns = [
        {
            "id": str(p.id),
            "pattern_type": p.pattern_type,
            "pattern_name": p.pattern_name,
            "platform": p.platform or "",
            "content_form": p.content_form,
            "win_score": float(p.win_score),
            "confidence": float(p.confidence or 0),
            "is_winner": float(p.win_score) >= 0.6,
        }
        for p in rows
    ]
    recs = recommend_reuse(winning_patterns, target_platforms)
    for r in recs:
        pid = r.get("pattern_id") or ""
        try:
            pattern_uuid = uuid.UUID(str(pid))
        except (ValueError, TypeError):
            continue
        db.add(
            PatternReuseRecommendation(
                brand_id=brand_id,
                pattern_id=pattern_uuid,
                target_platform=str(r["target_platform"]),
                target_content_form=r.get("target_content_form"),
                expected_uplift=float(r.get("expected_uplift", 0) or 0),
                confidence=float(r.get("confidence", 0) or 0),
                explanation=r.get("explanation"),
            )
        )
    return {"rows_processed": len(recs), "status": "completed"}


async def list_patterns(db: AsyncSession, brand_id: uuid.UUID) -> list[WinningPatternMemory]:
    r = await db.execute(
        select(WinningPatternMemory)
        .where(
            WinningPatternMemory.brand_id == brand_id,
            WinningPatternMemory.is_active.is_(True),
        )
        .order_by(WinningPatternMemory.win_score.desc())
    )
    return list(r.scalars().all())


async def list_clusters(db: AsyncSession, brand_id: uuid.UUID) -> list[WinningPatternCluster]:
    r = await db.execute(
        select(WinningPatternCluster)
        .where(
            WinningPatternCluster.brand_id == brand_id,
            WinningPatternCluster.is_active.is_(True),
        )
        .order_by(WinningPatternCluster.avg_win_score.desc())
    )
    return list(r.scalars().all())


async def list_losers(db: AsyncSession, brand_id: uuid.UUID) -> list[LosingPatternMemory]:
    r = await db.execute(
        select(LosingPatternMemory)
        .where(
            LosingPatternMemory.brand_id == brand_id,
            LosingPatternMemory.is_active.is_(True),
        )
        .order_by(LosingPatternMemory.fail_score.desc())
    )
    return list(r.scalars().all())


async def list_reuse(db: AsyncSession, brand_id: uuid.UUID) -> list[PatternReuseRecommendation]:
    r = await db.execute(
        select(PatternReuseRecommendation)
        .where(
            PatternReuseRecommendation.brand_id == brand_id,
            PatternReuseRecommendation.is_active.is_(True),
        )
        .order_by(PatternReuseRecommendation.expected_uplift.desc())
    )
    return list(r.scalars().all())


async def list_decay(db: AsyncSession, brand_id: uuid.UUID) -> list[PatternDecayReport]:
    r = await db.execute(
        select(PatternDecayReport)
        .where(
            PatternDecayReport.brand_id == brand_id,
            PatternDecayReport.is_active.is_(True),
        )
        .order_by(PatternDecayReport.decay_rate.desc())
    )
    return list(r.scalars().all())


async def get_experiment_suggestions(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    """Use pattern memory to suggest experiments worth running."""
    winners = (
        (
            await db.execute(
                select(WinningPatternMemory).where(
                    WinningPatternMemory.brand_id == brand_id, WinningPatternMemory.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    losers = (
        (
            await db.execute(
                select(LosingPatternMemory).where(
                    LosingPatternMemory.brand_id == brand_id, LosingPatternMemory.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    existing_exps = (
        (await db.execute(select(Experiment.experiment_type).where(Experiment.brand_id == brand_id).distinct()))
        .scalars()
        .all()
    )

    win_dicts = [
        {
            "pattern_type": w.pattern_type,
            "pattern_name": w.pattern_name,
            "win_score": float(w.win_score),
            "usage_count": w.usage_count,
        }
        for w in winners
    ]
    lose_dicts = [
        {"pattern_type": l.pattern_type, "pattern_name": l.pattern_name, "fail_score": float(l.fail_score)}
        for l in losers
    ]
    return suggest_experiments_from_patterns(win_dicts, lose_dicts, list(existing_exps))


async def get_allocation_weights(
    db: AsyncSession, brand_id: uuid.UUID, total_budget: float = 1000.0
) -> list[dict[str, Any]]:
    """Compute budget allocation weights from pattern cluster strength."""
    clusters = (
        (
            await db.execute(
                select(WinningPatternCluster).where(
                    WinningPatternCluster.brand_id == brand_id, WinningPatternCluster.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    cluster_dicts = [
        {
            "cluster_type": c.cluster_type,
            "platform": c.platform,
            "cluster_name": c.cluster_name,
            "avg_win_score": float(c.avg_win_score),
            "pattern_count": c.pattern_count,
        }
        for c in clusters
    ]
    return compute_pattern_allocation_weights(cluster_dicts, total_budget)


async def compute_niche_aggregate_patterns(db: AsyncSession, niche: str, limit: int = 10) -> dict[str, Any]:
    """Aggregate winning/losing patterns across ALL brands in the same niche.

    Cross-platform intelligence: if curiosity-gap hooks win on TikTok finance accounts,
    that insight flows to YouTube finance accounts too.
    """
    niche_brands = list(
        (await db.execute(select(Brand.id).where(Brand.niche == niche, Brand.is_active.is_(True)))).scalars().all()
    )

    if not niche_brands:
        return {"niche": niche, "winning_patterns": [], "losing_patterns": [], "brand_count": 0}

    all_winners = list(
        (
            await db.execute(
                select(WinningPatternMemory)
                .where(
                    WinningPatternMemory.brand_id.in_(niche_brands),
                    WinningPatternMemory.is_active.is_(True),
                )
                .order_by(WinningPatternMemory.win_score.desc())
                .limit(limit * 3)
            )
        )
        .scalars()
        .all()
    )

    all_losers = list(
        (
            await db.execute(
                select(LosingPatternMemory)
                .where(
                    LosingPatternMemory.brand_id.in_(niche_brands),
                    LosingPatternMemory.is_active.is_(True),
                )
                .order_by(LosingPatternMemory.fail_score.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    pattern_scores: dict[str, list[float]] = {}
    for w in all_winners:
        key = f"{w.pattern_type}:{w.pattern_name}"
        pattern_scores.setdefault(key, []).append(float(w.win_score))

    aggregated = []
    for key, scores in pattern_scores.items():
        ptype, pname = key.split(":", 1)
        aggregated.append(
            {
                "pattern_type": ptype,
                "pattern_name": pname,
                "avg_win_score": sum(scores) / len(scores),
                "brand_count": len(scores),
                "cross_validated": len(scores) >= 2,
            }
        )
    aggregated.sort(key=lambda x: x["avg_win_score"] * (1.2 if x["cross_validated"] else 1.0), reverse=True)

    return {
        "niche": niche,
        "winning_patterns": aggregated[:limit],
        "losing_patterns": [
            {"pattern_type": lp.pattern_type, "pattern_name": lp.pattern_name, "fail_score": float(lp.fail_score)}
            for lp in all_losers[:5]
        ],
        "brand_count": len(niche_brands),
    }
