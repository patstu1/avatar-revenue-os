"""DB-backed integration tests for Trend / Viral Opportunity Engine."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.trend_viral_service import (
    deep_analysis,
    get_top_opportunities,
    light_scan,
    list_opportunities,
    list_signals,
)
from packages.db.enums import Platform, SignalStrength
from packages.db.models.accounts import CreatorAccount
from packages.db.models.core import Brand, Organization
from packages.db.models.discovery import TrendSignal as DiscoveryTrend
from packages.db.models.trend_viral import TrendSourceHealth, TrendVelocityReport, ViralOpportunity


@pytest_asyncio.fixture
async def brand_with_trends(db_session: AsyncSession):
    slug = f"tv-{uuid.uuid4().hex[:6]}"
    org = Organization(name="TV Org", slug=f"org-{slug}")
    db_session.add(org)
    await db_session.flush()
    brand = Brand(organization_id=org.id, name="TV Brand", slug=slug, niche="tech")
    db_session.add(brand)
    await db_session.flush()
    acct = CreatorAccount(brand_id=brand.id, platform=Platform.TIKTOK, platform_username=f"@tv_{slug}")
    db_session.add(acct)
    await db_session.flush()

    db_session.add(
        DiscoveryTrend(
            brand_id=brand.id,
            keyword="AI agents taking over",
            signal_type="trending_topic",
            strength=SignalStrength.STRONG,
            velocity=2.5,
            volume=5000,
        )
    )
    db_session.add(
        DiscoveryTrend(
            brand_id=brand.id,
            keyword="Budget productivity tools",
            signal_type="trending_topic",
            strength=SignalStrength.MODERATE,
            velocity=1.0,
            volume=1500,
        )
    )
    await db_session.flush()
    return brand


@pytest.mark.asyncio
async def test_light_scan(db_session, brand_with_trends):
    brand = brand_with_trends
    result = await light_scan(db_session, brand.id)
    await db_session.commit()
    assert result["status"] == "completed"
    assert result["new_signals"] >= 2


@pytest.mark.asyncio
async def test_deep_analysis_creates_opportunities(db_session, brand_with_trends):
    brand = brand_with_trends
    await light_scan(db_session, brand.id)
    await db_session.flush()
    result = await deep_analysis(db_session, brand.id)
    await db_session.commit()
    assert result["status"] == "completed"
    assert result["opportunities_created"] >= 1


@pytest.mark.asyncio
async def test_opportunities_have_scores(db_session, brand_with_trends):
    brand = brand_with_trends
    await light_scan(db_session, brand.id)
    await db_session.flush()
    await deep_analysis(db_session, brand.id)
    await db_session.commit()
    opps = (
        (await db_session.execute(select(ViralOpportunity).where(ViralOpportunity.brand_id == brand.id)))
        .scalars()
        .all()
    )
    assert len(opps) >= 1
    for o in opps:
        assert o.composite_score > 0
        assert o.recommended_platform
        assert o.recommended_content_form
        assert o.opportunity_type in (
            "monetization",
            "pure_reach",
            "authority_building",
            "growth",
            "community_engagement",
        )


@pytest.mark.asyncio
async def test_velocity_tracked(db_session, brand_with_trends):
    brand = brand_with_trends
    await light_scan(db_session, brand.id)
    await db_session.flush()
    await deep_analysis(db_session, brand.id)
    await db_session.commit()
    vel = (
        (await db_session.execute(select(TrendVelocityReport).where(TrendVelocityReport.brand_id == brand.id)))
        .scalars()
        .all()
    )
    assert len(vel) >= 1


@pytest.mark.asyncio
async def test_source_health_tracked(db_session, brand_with_trends):
    brand = brand_with_trends
    await light_scan(db_session, brand.id)
    await db_session.flush()
    await deep_analysis(db_session, brand.id)
    await db_session.commit()
    health = (
        (await db_session.execute(select(TrendSourceHealth).where(TrendSourceHealth.brand_id == brand.id)))
        .scalars()
        .all()
    )
    assert len(health) >= 1


@pytest.mark.asyncio
async def test_list_signals(db_session, brand_with_trends):
    brand = brand_with_trends
    await light_scan(db_session, brand.id)
    await db_session.commit()
    sigs = await list_signals(db_session, brand.id)
    assert len(sigs) >= 2


@pytest.mark.asyncio
async def test_list_opportunities(db_session, brand_with_trends):
    brand = brand_with_trends
    await light_scan(db_session, brand.id)
    await db_session.flush()
    await deep_analysis(db_session, brand.id)
    await db_session.commit()
    opps = await list_opportunities(db_session, brand.id)
    assert len(opps) >= 1


@pytest.mark.asyncio
async def test_get_top_opportunities(db_session, brand_with_trends):
    brand = brand_with_trends
    await light_scan(db_session, brand.id)
    await db_session.flush()
    await deep_analysis(db_session, brand.id)
    await db_session.commit()
    top = await get_top_opportunities(db_session, brand.id)
    assert len(top) >= 1
    for t in top:
        assert "topic" in t
        assert "monetization" in t
        assert "platform" in t


@pytest.mark.asyncio
async def test_dedup_prevents_duplicates(db_session, brand_with_trends):
    brand = brand_with_trends
    await light_scan(db_session, brand.id)
    await db_session.flush()
    await deep_analysis(db_session, brand.id)
    await db_session.flush()
    r1_count = len(
        (await db_session.execute(select(ViralOpportunity).where(ViralOpportunity.brand_id == brand.id)))
        .scalars()
        .all()
    )
    await deep_analysis(db_session, brand.id)
    await db_session.commit()
    r2_count = len(
        (await db_session.execute(select(ViralOpportunity).where(ViralOpportunity.brand_id == brand.id)))
        .scalars()
        .all()
    )
    assert r2_count == r1_count


def test_trend_workers_registered():
    import workers.trend_viral_worker.tasks  # noqa: F401
    from workers.celery_app import app

    assert "workers.trend_viral_worker.tasks.trend_light_scan" in app.tasks
    assert "workers.trend_viral_worker.tasks.trend_deep_analysis" in app.tasks
