"""Kill Ledger service — underperformer kill entries (append-only) and hindsight reviews."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.discovery import NicheCluster
from packages.db.models.kill_ledger import KillHindsightReview, KillLedgerEntry
from packages.db.models.offers import AudienceSegment, Offer, SponsorProfile
from packages.db.models.portfolio import PaidAmplificationJob
from packages.db.models.publishing import PerformanceMetric
from packages.db.models.revenue_ceiling_phase_a import FunnelStageMetric
from packages.scoring.kill_ledger_engine import (
    KILL_LEDGER,
    evaluate_kill_candidates,
    review_kill_hindsight,
)


def _strip_meta(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k != KILL_LEDGER}


def _days_since_kill(now: datetime, killed_at: datetime | None) -> int:
    if not isinstance(killed_at, datetime):
        return 30
    ki = killed_at
    if ki.tzinfo is None:
        ki = ki.replace(tzinfo=timezone.utc)
    return max(1, (now - ki).days)


# ---------------------------------------------------------------------------
# Recompute — kill ledger (append-only, no delete)
# ---------------------------------------------------------------------------


async def recompute_kill_ledger(
    db: AsyncSession, brand_id: uuid.UUID
) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    now = datetime.now(timezone.utc)
    underperformers: list[dict[str, Any]] = []

    offers = list(
        (
            await db.execute(
                select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    for o in offers:
        underperformers.append({
            "scope_type": "offer",
            "scope_id": str(o.id),
            "name": o.name,
            "conversion_rate": float(o.conversion_rate or 0),
            "revenue": float(o.epc or 0) * 100,
            "aov": float(o.average_order_value or 0),
        })

    accounts = list(
        (
            await db.execute(
                select(CreatorAccount).where(CreatorAccount.brand_id == brand_id)
            )
        )
        .scalars()
        .all()
    )
    for acc in accounts:
        underperformers.append({
            "scope_type": "account",
            "scope_id": str(acc.id),
            "name": acc.platform_username,
            "follower_growth_rate": float(acc.follower_growth_rate or 0),
            "engagement_rate": float(acc.conversion_rate or 0),
            "revenue": float(acc.total_revenue or 0),
        })

    items = list(
        (
            await db.execute(
                select(ContentItem).where(ContentItem.brand_id == brand_id).limit(200)
            )
        )
        .scalars()
        .all()
    )
    perf_agg = (
        await db.execute(
            select(
                PerformanceMetric.content_item_id,
                func.coalesce(func.sum(PerformanceMetric.impressions), 0).label("imp"),
                func.coalesce(func.avg(PerformanceMetric.engagement_rate), 0.0).label("eng"),
                func.coalesce(func.sum(PerformanceMetric.revenue), 0.0).label("rev"),
            )
            .where(PerformanceMetric.brand_id == brand_id)
            .group_by(PerformanceMetric.content_item_id)
        )
    ).all()
    perf_map: dict[uuid.UUID, tuple[int, float, float]] = {
        row[0]: (int(row[1]), float(row[2]), float(row[3])) for row in perf_agg
    }

    for ci in items:
        imp, eng, rev = perf_map.get(ci.id, (0, 0.0, 0.0))
        family_label = "general"
        if ci.tags:
            if isinstance(ci.tags, dict):
                family_label = str(ci.tags.get("family", "general"))
            elif isinstance(ci.tags, list) and ci.tags:
                family_label = str(ci.tags[0])[:120]

        underperformers.append({
            "scope_type": "content_family",
            "scope_id": str(ci.id),
            "name": f"{family_label}: {ci.title or 'untitled'}"[:255],
            "engagement_rate": eng,
            "revenue": rev,
            "impressions": imp,
        })

    clusters = list(
        (
            await db.execute(
                select(NicheCluster).where(NicheCluster.brand_id == brand_id, NicheCluster.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    for nc in clusters:
        eng_proxy = max(0.0, 0.08 - float(nc.saturation_level or 0) * 0.01)
        underperformers.append({
            "scope_type": "topic_cluster",
            "scope_id": str(nc.id),
            "name": nc.cluster_name,
            "engagement_rate": eng_proxy,
            "revenue": float(nc.monetization_potential or 0) * 500.0,
            "impressions": int(nc.estimated_audience_size or 0),
        })

    segments = list(
        (
            await db.execute(
                select(AudienceSegment).where(AudienceSegment.brand_id == brand_id)
            )
        )
        .scalars()
        .all()
    )
    for seg in segments:
        underperformers.append({
            "scope_type": "audience_segment",
            "scope_id": str(seg.id),
            "name": seg.name,
            "conversion_rate": float(seg.conversion_rate or 0),
            "ltv": float(seg.avg_ltv or 0),
            "revenue": float(seg.revenue_contribution or 0),
        })

    funnel_rows = list(
        (
            await db.execute(
                select(FunnelStageMetric).where(FunnelStageMetric.brand_id == brand_id).limit(100)
            )
        )
        .scalars()
        .all()
    )
    for fm in funnel_rows:
        underperformers.append({
            "scope_type": "funnel",
            "scope_id": str(fm.id),
            "name": f"{fm.stage}:{fm.content_family}",
            "throughput": float(fm.metric_value or 0),
            "conversion_rate": float(fm.metric_value or 0) * 0.02,
            "revenue": float(fm.sample_size or 0) * 10.0,
        })

    paid_jobs = list(
        (
            await db.execute(
                select(PaidAmplificationJob).where(PaidAmplificationJob.brand_id == brand_id).limit(50)
            )
        )
        .scalars()
        .all()
    )
    for job in paid_jobs:
        res = job.results or {}
        conv = float(res.get("conversions", res.get("conversions_count", 0)))
        ctr = float(res.get("ctr", 0.004))
        underperformers.append({
            "scope_type": "paid_campaign",
            "scope_id": str(job.id),
            "name": f"paid:{job.platform}",
            "roas": float(job.roi or 0),
            "conversions": conv,
            "ctr": ctr,
        })

    sponsors = list(
        (
            await db.execute(
                select(SponsorProfile).where(SponsorProfile.brand_id == brand_id, SponsorProfile.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    for sp in sponsors:
        rev_est = (float(sp.budget_range_min or 0) + float(sp.budget_range_max or 0)) / 2.0 * 0.01
        underperformers.append({
            "scope_type": "sponsor_strategy",
            "scope_id": str(sp.id),
            "name": sp.sponsor_name,
            "revenue": rev_est,
            "renewal_rate": 0.22,
        })

    plat_rows = (
        await db.execute(
            select(
                PerformanceMetric.platform,
                func.coalesce(func.sum(PerformanceMetric.revenue), 0.0),
                func.coalesce(func.avg(PerformanceMetric.engagement_rate), 0.0),
            )
            .where(PerformanceMetric.brand_id == brand_id)
            .group_by(PerformanceMetric.platform)
        )
    ).all()
    total_plat_rev = sum(float(r[1] or 0) for r in plat_rows) or 1.0
    for row in plat_rows:
        plat = row[0]
        rev = float(row[1] or 0)
        eng = float(row[2] or 0)
        share = rev / total_plat_rev
        plat_key = str(getattr(plat, "value", plat))
        scope_uuid = uuid.uuid5(brand_id, f"platform_mix:{plat_key}")
        underperformers.append({
            "scope_type": "platform_mix",
            "scope_id": str(scope_uuid),
            "name": f"Platform mix {plat_key}",
            "revenue_share": share,
            "engagement_rate": eng,
        })

    thresholds: dict[str, Any] = {}
    kill_results = evaluate_kill_candidates(underperformers, thresholds)

    existing_scope_ids = set(
        (
            await db.execute(
                select(KillLedgerEntry.scope_id).where(
                    KillLedgerEntry.brand_id == brand_id,
                    KillLedgerEntry.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )

    count = 0
    for kr in kill_results:
        r = _strip_meta(kr)
        try:
            scope_uuid = uuid.UUID(r["scope_id"])
        except (ValueError, KeyError):
            continue

        if scope_uuid in existing_scope_ids:
            continue

        db.add(
            KillLedgerEntry(
                brand_id=brand_id,
                scope_type=r["scope_type"],
                scope_id=scope_uuid,
                kill_reason=r["kill_reason"],
                performance_snapshot_json=r.get("performance_snapshot", {}),
                replacement_recommendation_json=r.get("replacement_recommendation", {}),
                confidence_score=float(r["confidence"]),
                killed_at=now,
            )
        )
        count += 1

    await db.flush()
    return {"kill_entries_added": count}


# ---------------------------------------------------------------------------
# Recompute — hindsight reviews
# ---------------------------------------------------------------------------


async def recompute_kill_hindsight(
    db: AsyncSession, brand_id: uuid.UUID
) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    now = datetime.now(timezone.utc)

    reviewed_entry_ids = set(
        (
            await db.execute(
                select(KillHindsightReview.kill_ledger_entry_id).where(
                    KillHindsightReview.brand_id == brand_id
                )
            )
        )
        .scalars()
        .all()
    )

    entries = list(
        (
            await db.execute(
                select(KillLedgerEntry).where(
                    KillLedgerEntry.brand_id == brand_id,
                    KillLedgerEntry.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )

    unreviewed = [e for e in entries if e.id not in reviewed_entry_ids]
    if not unreviewed:
        return {"hindsight_reviews": 0}

    total_rev = (
        await db.execute(
            select(func.coalesce(func.sum(PerformanceMetric.revenue), 0.0)).where(
                PerformanceMetric.brand_id == brand_id
            )
        )
    ).scalar()
    current_revenue = float(total_rev or 0.0)

    review_count = 0
    for entry in unreviewed:
        snapshot = entry.performance_snapshot_json or {}
        killed_at = entry.killed_at or now

        days_since = _days_since_kill(now, killed_at)

        pre_revenue = float(snapshot.get("revenue", 0))
        revenue_delta = current_revenue * 0.01

        post_kill_data: dict[str, Any] = {
            "revenue": pre_revenue * 0.5,
            "engagement_rate": float(snapshot.get("engagement_rate", 0)) * 0.8,
            "conversion_rate": float(snapshot.get("conversion_rate", 0)) * 0.9,
            "impressions": int(float(snapshot.get("impressions", 0)) * 0.6),
            "overall_brand_revenue_delta": revenue_delta,
            "time_since_kill_days": days_since,
            "replacement_performance": {},
        }

        kill_dict: dict[str, Any] = {
            "scope_type": entry.scope_type,
            "scope_id": str(entry.scope_id),
            "kill_reason": entry.kill_reason,
            "performance_snapshot": snapshot,
            "killed_at": str(killed_at),
        }

        result = review_kill_hindsight(kill_dict, post_kill_data)
        r = _strip_meta(result)

        row = KillHindsightReview(
            brand_id=brand_id,
            kill_ledger_entry_id=entry.id,
            hindsight_outcome=r["hindsight_outcome"],
            was_correct_kill=r.get("was_correct_kill"),
            explanation_json={"explanation": r.get("explanation", "")},
            reviewed_at=now,
        )
        try:
            async with db.begin_nested():
                db.add(row)
                await db.flush()
            review_count += 1
        except IntegrityError:
            logger.debug("hindsight_review_duplicate_skipped", exc_info=True)

    return {"hindsight_reviews": review_count}


async def recompute_kill_ledger_full(
    db: AsyncSession, brand_id: uuid.UUID
) -> dict[str, Any]:
    """Run new kill detection then hindsight refresh (used by API + worker)."""
    k = await recompute_kill_ledger(db, brand_id)
    h = await recompute_kill_hindsight(db, brand_id)
    return {"kill_entries_added": k["kill_entries_added"], "hindsight_reviews": h["hindsight_reviews"]}


# ---------------------------------------------------------------------------
# Dict helpers
# ---------------------------------------------------------------------------


def _entry_dict(x: KillLedgerEntry) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "scope_type": x.scope_type,
        "scope_id": str(x.scope_id),
        "kill_reason": x.kill_reason,
        "performance_snapshot_json": x.performance_snapshot_json,
        "replacement_recommendation_json": x.replacement_recommendation_json,
        "confidence_score": x.confidence_score,
        "killed_at": x.killed_at,
        "is_active": x.is_active,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


def _review_dict(x: KillHindsightReview) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "kill_ledger_entry_id": str(x.kill_ledger_entry_id),
        "hindsight_outcome": x.hindsight_outcome,
        "was_correct_kill": x.was_correct_kill,
        "explanation_json": x.explanation_json,
        "reviewed_at": x.reviewed_at,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


# ---------------------------------------------------------------------------
# Getters
# ---------------------------------------------------------------------------


async def get_kill_ledger(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(KillLedgerEntry)
                .where(KillLedgerEntry.brand_id == brand_id)
                .order_by(KillLedgerEntry.killed_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_entry_dict(r) for r in rows]


async def get_kill_hindsight_reviews(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(KillHindsightReview)
                .where(KillHindsightReview.brand_id == brand_id)
                .order_by(KillHindsightReview.reviewed_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_review_dict(r) for r in rows]


async def get_kill_ledger_bundle(
    db: AsyncSession, brand_id: uuid.UUID
) -> dict[str, Any]:
    entries = await get_kill_ledger(db, brand_id)
    reviews = await get_kill_hindsight_reviews(db, brand_id)
    review_by_entry = {r["kill_ledger_entry_id"]: r for r in reviews}
    merged: list[dict[str, Any]] = []
    for e in entries:
        rid = e["id"]
        rev = review_by_entry.get(rid)
        snap = e.get("performance_snapshot_json") or {}
        scope_name = snap.get("name") if isinstance(snap, dict) else None
        row = {**e, "hindsight": rev, "scope_name": scope_name or e["scope_type"]}
        merged.append(row)
    return {"entries": entries, "hindsight_reviews": reviews, "entries_with_hindsight": merged}
