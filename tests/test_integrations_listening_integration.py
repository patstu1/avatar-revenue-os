"""DB-backed integration tests for Integrations + Listening."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.integrations_listening_service import (
    get_listening_summary,
    list_blockers,
    list_clusters,
    list_connectors,
    list_listening,
    recompute_listening,
)
from packages.db.models.core import Brand, Organization
from packages.db.models.integrations_listening import (
    CompetitorSignalEvent,
    EnterpriseConnector,
    IntegrationBlocker,
    ListeningCluster,
    SignalResponseRecommendation,
    SocialListeningEvent,
)


@pytest_asyncio.fixture
async def org_with_signals(db_session: AsyncSession):
    slug = f"il-{uuid.uuid4().hex[:6]}"
    org = Organization(name="IL Org", slug=f"org-{slug}")
    db_session.add(org)
    await db_session.flush()
    brand = Brand(organization_id=org.id, name="IL Brand", slug=slug, niche="tech")
    db_session.add(brand)
    await db_session.flush()

    db_session.add(
        EnterpriseConnector(
            organization_id=org.id,
            connector_name="Salesforce CRM",
            connector_type="crm",
            endpoint_url="https://sf.example.com",
            credential_env_key="SF_KEY",
        )
    )
    db_session.add(EnterpriseConnector(organization_id=org.id, connector_name="Broken Connector", connector_type="erp"))

    db_session.add(
        SocialListeningEvent(
            organization_id=org.id,
            brand_id=brand.id,
            signal_type="brand_mention",
            raw_text="Love this product so much!",
            sentiment=0.8,
            relevance_score=0.9,
        )
    )
    db_session.add(
        SocialListeningEvent(
            organization_id=org.id,
            brand_id=brand.id,
            signal_type="demand_signal",
            raw_text="Need a feature for bulk scheduling",
            sentiment=0.3,
            relevance_score=0.8,
        )
    )
    db_session.add(
        SocialListeningEvent(
            organization_id=org.id,
            brand_id=brand.id,
            signal_type="demand_signal",
            raw_text="When will you add analytics?",
            sentiment=0.2,
            relevance_score=0.7,
        )
    )
    db_session.add(
        CompetitorSignalEvent(
            organization_id=org.id,
            brand_id=brand.id,
            competitor_name="Rival Co",
            signal_type="competitor_mention",
            raw_text="Disappointed with Rival, looking for alternative",
            sentiment=-0.6,
        )
    )
    await db_session.flush()
    return org, brand


@pytest.mark.asyncio
async def test_recompute_listening(db_session, org_with_signals):
    org, _ = org_with_signals
    result = await recompute_listening(db_session, org.id)
    await db_session.commit()
    assert result["status"] == "completed"
    assert result["rows_processed"] >= 3
    assert result["clusters"] >= 2


@pytest.mark.asyncio
async def test_clusters_created(db_session, org_with_signals):
    org, _ = org_with_signals
    await recompute_listening(db_session, org.id)
    await db_session.commit()
    clusters = (
        (await db_session.execute(select(ListeningCluster).where(ListeningCluster.organization_id == org.id)))
        .scalars()
        .all()
    )
    assert len(clusters) >= 2
    types = {c.cluster_type for c in clusters}
    assert "demand_signal" in types


@pytest.mark.asyncio
async def test_blockers_detected(db_session, org_with_signals):
    org, _ = org_with_signals
    await recompute_listening(db_session, org.id)
    await db_session.commit()
    blockers = (
        (await db_session.execute(select(IntegrationBlocker).where(IntegrationBlocker.organization_id == org.id)))
        .scalars()
        .all()
    )
    assert len(blockers) >= 1


@pytest.mark.asyncio
async def test_response_recs_created(db_session, org_with_signals):
    org, _ = org_with_signals
    await recompute_listening(db_session, org.id)
    await db_session.commit()
    recs = (
        (
            await db_session.execute(
                select(SignalResponseRecommendation).where(SignalResponseRecommendation.organization_id == org.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(recs) >= 2


@pytest.mark.asyncio
async def test_list_connectors(db_session, org_with_signals):
    org, _ = org_with_signals
    conns = await list_connectors(db_session, org.id)
    assert len(conns) == 2


@pytest.mark.asyncio
async def test_list_listening(db_session, org_with_signals):
    org, _ = org_with_signals
    events = await list_listening(db_session, org.id)
    assert len(events) == 3


@pytest.mark.asyncio
async def test_list_clusters(db_session, org_with_signals):
    org, _ = org_with_signals
    await recompute_listening(db_session, org.id)
    await db_session.commit()
    cl = await list_clusters(db_session, org.id)
    assert len(cl) >= 2


@pytest.mark.asyncio
async def test_list_blockers(db_session, org_with_signals):
    org, _ = org_with_signals
    await recompute_listening(db_session, org.id)
    await db_session.commit()
    bl = await list_blockers(db_session, org.id)
    assert len(bl) >= 1


@pytest.mark.asyncio
async def test_get_listening_summary(db_session, org_with_signals):
    org, _ = org_with_signals
    await recompute_listening(db_session, org.id)
    await db_session.commit()
    summary = await get_listening_summary(db_session, org.id)
    assert "top_clusters" in summary
    assert len(summary["top_clusters"]) >= 2


@pytest.mark.asyncio
async def test_idempotent(db_session, org_with_signals):
    org, _ = org_with_signals
    r1 = await recompute_listening(db_session, org.id)
    await db_session.commit()
    r2 = await recompute_listening(db_session, org.id)
    await db_session.commit()
    assert r1["clusters"] == r2["clusters"]


def test_listening_worker_registered():
    import workers.integrations_listening_worker.tasks  # noqa: F401
    from workers.celery_app import app

    assert "workers.integrations_listening_worker.tasks.recompute_listening" in app.tasks
