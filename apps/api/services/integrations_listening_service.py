"""Integrations + Listening Service — sync, cluster, route, persist."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.integrations_listening import (
    CompetitorSignalEvent,
    EnterpriseConnector,
    EnterpriseConnectorSync,
    IntegrationBlocker,
    InternalBusinessSignal,
    ListeningCluster,
    SignalResponseRecommendation,
    SocialListeningEvent,
)
from packages.scoring.integrations_listening_engine import (
    cluster_listening_signals,
    evaluate_connector_sync,
    extract_competitor_signals,
    generate_response_recommendations,
)


async def recompute_listening(db: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(delete(SignalResponseRecommendation).where(SignalResponseRecommendation.organization_id == org_id))
    await db.execute(delete(ListeningCluster).where(ListeningCluster.organization_id == org_id))
    await db.execute(delete(IntegrationBlocker).where(IntegrationBlocker.organization_id == org_id))

    connectors = list(
        (
            await db.execute(
                select(EnterpriseConnector).where(
                    EnterpriseConnector.organization_id == org_id, EnterpriseConnector.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    for c in connectors:
        last_sync = (
            await db.execute(
                select(EnterpriseConnectorSync)
                .where(EnterpriseConnectorSync.connector_id == c.id)
                .order_by(EnterpriseConnectorSync.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        sync_dict = {"sync_status": last_sync.sync_status, "detail": last_sync.detail} if last_sync else None
        eval_r = evaluate_connector_sync(
            {"status": c.status, "credential_env_key": c.credential_env_key, "endpoint_url": c.endpoint_url}, sync_dict
        )
        if not eval_r["healthy"]:
            db.add(
                IntegrationBlocker(
                    organization_id=org_id,
                    connector_id=c.id,
                    blocker_type=eval_r.get("blocker", "unknown"),
                    description=eval_r["reason"],
                )
            )

    social = list(
        (
            await db.execute(
                select(SocialListeningEvent)
                .where(SocialListeningEvent.organization_id == org_id, SocialListeningEvent.is_active.is_(True))
                .limit(500)
            )
        )
        .scalars()
        .all()
    )
    signal_dicts = [
        {
            "signal_type": s.signal_type,
            "raw_text": s.raw_text,
            "sentiment": float(s.sentiment),
            "relevance_score": float(s.relevance_score),
        }
        for s in social
    ]

    business = list(
        (
            await db.execute(
                select(InternalBusinessSignal)
                .where(InternalBusinessSignal.organization_id == org_id, InternalBusinessSignal.is_active.is_(True))
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    for b in business:
        signal_dicts.append(
            {"signal_type": b.signal_type, "raw_text": str(b.data_json), "sentiment": 0, "relevance_score": 0.5}
        )

    clusters = cluster_listening_signals(signal_dicts)
    cluster_map = {}
    for c in clusters:
        lc = ListeningCluster(
            organization_id=org_id,
            cluster_type=c["cluster_type"],
            cluster_label=c["cluster_label"],
            signal_count=c["signal_count"],
            avg_sentiment=c["avg_sentiment"],
            avg_relevance=c["avg_relevance"],
            representative_texts=c["representative_texts"],
            recommended_action=c["recommended_action"],
        )
        db.add(lc)
        await db.flush()
        c["id"] = str(lc.id)
        cluster_map[c["cluster_type"]] = lc.id

    recs = generate_response_recommendations(clusters)
    for r in recs:
        cid = cluster_map.get(r.get("cluster_type"))
        if not cid:
            continue
        db.add(
            SignalResponseRecommendation(
                organization_id=org_id,
                cluster_id=cid,
                response_type=r["response_type"],
                response_action=r["response_action"],
                target_system=r["target_system"],
                priority=r["priority"],
            )
        )

    comp_signals = list(
        (
            await db.execute(
                select(CompetitorSignalEvent)
                .where(CompetitorSignalEvent.organization_id == org_id, CompetitorSignalEvent.is_active.is_(True))
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    comp_dicts = [
        {
            "competitor_name": c.competitor_name,
            "signal_type": c.signal_type,
            "raw_text": c.raw_text,
            "sentiment": float(c.sentiment),
        }
        for c in comp_signals
    ]
    scored_comp = extract_competitor_signals(comp_dicts)
    for i, sc in enumerate(scored_comp):
        if i < len(comp_signals):
            comp_signals[i].opportunity_score = sc["opportunity_score"]

    await db.flush()
    return {"rows_processed": len(signal_dicts) + len(comp_dicts), "clusters": len(clusters), "status": "completed"}


async def list_connectors(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(EnterpriseConnector).where(
                    EnterpriseConnector.organization_id == org_id, EnterpriseConnector.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )


async def list_listening(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(SocialListeningEvent)
                .where(SocialListeningEvent.organization_id == org_id, SocialListeningEvent.is_active.is_(True))
                .order_by(SocialListeningEvent.created_at.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )


async def list_competitor_signals(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(CompetitorSignalEvent)
                .where(CompetitorSignalEvent.organization_id == org_id, CompetitorSignalEvent.is_active.is_(True))
                .order_by(CompetitorSignalEvent.opportunity_score.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )


async def list_clusters(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(ListeningCluster)
                .where(ListeningCluster.organization_id == org_id, ListeningCluster.is_active.is_(True))
                .order_by(ListeningCluster.signal_count.desc())
            )
        )
        .scalars()
        .all()
    )


async def list_blockers(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(IntegrationBlocker).where(
                    IntegrationBlocker.organization_id == org_id, IntegrationBlocker.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )


async def get_listening_summary(db: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    """Downstream: quick summary for copilot."""
    clusters = list(
        (
            await db.execute(
                select(ListeningCluster)
                .where(ListeningCluster.organization_id == org_id, ListeningCluster.is_active.is_(True))
                .order_by(ListeningCluster.signal_count.desc())
                .limit(5)
            )
        )
        .scalars()
        .all()
    )
    return {
        "top_clusters": [
            {"type": c.cluster_type, "count": c.signal_count, "action": c.recommended_action} for c in clusters
        ]
    }
