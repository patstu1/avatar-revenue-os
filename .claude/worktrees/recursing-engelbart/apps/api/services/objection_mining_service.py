"""Objection Mining Service — extract from comments, cluster, respond, persist."""
from __future__ import annotations
import uuid
from typing import Any

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

from packages.db.models.learning import CommentIngestion
from packages.db.models.objection_mining import (
    ObjectionCluster, ObjectionPriorityReport, ObjectionResponse, ObjectionSignal,
)
from packages.scoring.objection_mining_engine import (
    build_priority_report,
    cluster_objections,
    extract_objections,
    generate_responses,
)


async def recompute_objections(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    comments = list((await db.execute(
        select(CommentIngestion).where(CommentIngestion.brand_id == brand_id).limit(500)
    )).scalars().all())

    texts = []
    for c in comments:
        texts.append({
            "text": c.comment_text,
            "source_type": "comment",
            "source_id": str(c.id),
            "content_item_id": str(c.content_item_id) if c.content_item_id else None,
            "platform": c.platform,
        })

    await db.execute(delete(ObjectionResponse).where(ObjectionResponse.brand_id == brand_id))
    await db.execute(delete(ObjectionCluster).where(ObjectionCluster.brand_id == brand_id))
    await db.execute(delete(ObjectionSignal).where(ObjectionSignal.brand_id == brand_id))
    await db.execute(delete(ObjectionPriorityReport).where(ObjectionPriorityReport.brand_id == brand_id))

    signals = extract_objections(texts)
    for s in signals:
        ci_id = None
        if s.get("content_item_id"):
            try:
                ci_id = uuid.UUID(str(s["content_item_id"]))
            except (ValueError, TypeError):
                logger.debug("objection_signal_content_id_parse_failed", exc_info=True)
        oid = None
        if s.get("offer_id"):
            try:
                oid = uuid.UUID(str(s["offer_id"]))
            except (ValueError, TypeError):
                logger.debug("objection_signal_offer_id_parse_failed", exc_info=True)
        db.add(ObjectionSignal(
            brand_id=brand_id,
            source_type=s["source_type"],
            content_item_id=ci_id,
            offer_id=oid,
            objection_type=s["objection_type"],
            raw_text=s["raw_text"],
            extracted_objection=s["extracted_objection"],
            severity=s["severity"],
            monetization_impact=s["monetization_impact"],
            platform=s.get("platform"),
        ))
    await db.flush()

    clusters = cluster_objections(signals)
    cluster_map = {}
    for c in clusters:
        oc = ObjectionCluster(
            brand_id=brand_id,
            objection_type=c["objection_type"],
            cluster_label=c["cluster_label"],
            signal_count=c["signal_count"],
            avg_severity=c["avg_severity"],
            avg_monetization_impact=c["avg_monetization_impact"],
            representative_texts=c["representative_texts"],
            recommended_response_angle=c.get("recommended_response_angle"),
        )
        db.add(oc)
        await db.flush()
        cluster_map[c["objection_type"]] = oc.id

    responses = generate_responses(clusters)
    for r in responses:
        cid = cluster_map.get(r["objection_type"])
        if not cid:
            continue
        db.add(ObjectionResponse(
            brand_id=brand_id,
            cluster_id=cid,
            response_type=r["response_type"],
            response_angle=r["response_angle"],
            target_channel=r["target_channel"],
            priority=r["priority"],
        ))

    report_data = build_priority_report(clusters, len(signals))
    db.add(ObjectionPriorityReport(
        brand_id=brand_id,
        top_objections=report_data["top_objections"],
        total_signals=report_data["total_signals"],
        total_clusters=report_data["total_clusters"],
        highest_impact_type=report_data.get("highest_impact_type"),
        summary=report_data.get("summary"),
    ))

    await db.flush()
    return {"rows_processed": len(signals), "clusters": len(clusters), "status": "completed"}


async def list_signals(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(
        select(ObjectionSignal).where(ObjectionSignal.brand_id == brand_id, ObjectionSignal.is_active.is_(True)).order_by(ObjectionSignal.monetization_impact.desc()).limit(100)
    )).scalars().all())


async def list_clusters(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(
        select(ObjectionCluster).where(ObjectionCluster.brand_id == brand_id, ObjectionCluster.is_active.is_(True)).order_by(ObjectionCluster.avg_monetization_impact.desc())
    )).scalars().all())


async def list_responses(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(
        select(ObjectionResponse).where(ObjectionResponse.brand_id == brand_id, ObjectionResponse.is_active.is_(True)).order_by(ObjectionResponse.priority)
    )).scalars().all())


async def get_priority_report(db: AsyncSession, brand_id: uuid.UUID):
    return (await db.execute(
        select(ObjectionPriorityReport).where(ObjectionPriorityReport.brand_id == brand_id).order_by(ObjectionPriorityReport.created_at.desc()).limit(1)
    )).scalar_one_or_none()


async def get_objections_for_brief(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    """Downstream: return top objection clusters for content brief injection."""
    clusters = list((await db.execute(
        select(ObjectionCluster).where(ObjectionCluster.brand_id == brand_id, ObjectionCluster.is_active.is_(True)).order_by(ObjectionCluster.avg_monetization_impact.desc()).limit(5)
    )).scalars().all())
    return [{"type": c.objection_type, "label": c.cluster_label, "impact": c.avg_monetization_impact, "angle": c.recommended_response_angle} for c in clusters]
