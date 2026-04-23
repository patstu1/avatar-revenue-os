"""DB-backed integration tests for Executive Intelligence."""
from __future__ import annotations
import uuid
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from packages.db.models.core import Organization, Brand
from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.publishing import PerformanceMetric
from packages.db.models.executive_intel import ExecutiveKPIReport, ExecutiveForecast, OversightModeReport, ExecutiveAlert
from packages.db.enums import Platform, ContentType
from apps.api.services.executive_intel_service import recompute_executive_intel, list_kpis, list_forecasts, list_alerts, list_oversight, get_executive_summary


@pytest_asyncio.fixture
async def org_with_data(db_session: AsyncSession):
    slug = f"ei-{uuid.uuid4().hex[:6]}"
    org = Organization(name="EI Org", slug=f"org-{slug}")
    db_session.add(org); await db_session.flush()
    brand = Brand(organization_id=org.id, name="EI Brand", slug=slug, niche="tech")
    db_session.add(brand); await db_session.flush()
    acct = CreatorAccount(brand_id=brand.id, platform=Platform.TIKTOK, platform_username=f"@ei_{slug}")
    db_session.add(acct); await db_session.flush()
    ci = ContentItem(brand_id=brand.id, creator_account_id=acct.id, title="EI content", content_type=ContentType.SHORT_VIDEO, platform="tiktok", status="published")
    db_session.add(ci); await db_session.flush()
    db_session.add(PerformanceMetric(brand_id=brand.id, content_item_id=ci.id, creator_account_id=acct.id, platform=Platform.TIKTOK, impressions=10000, engagement_rate=0.08, revenue=50.0))
    await db_session.flush()
    return org, brand


@pytest.mark.asyncio
async def test_recompute(db_session, org_with_data):
    org, _ = org_with_data
    result = await recompute_executive_intel(db_session, org.id)
    await db_session.commit()
    assert result["status"] == "completed"

    kpis = (await db_session.execute(select(ExecutiveKPIReport).where(ExecutiveKPIReport.organization_id == org.id))).scalars().all()
    assert len(kpis) == 1
    assert kpis[0].content_published >= 1
    assert kpis[0].active_accounts >= 1


@pytest.mark.asyncio
async def test_forecast_created(db_session, org_with_data):
    org, _ = org_with_data
    await recompute_executive_intel(db_session, org.id); await db_session.commit()
    forecasts = (await db_session.execute(select(ExecutiveForecast).where(ExecutiveForecast.organization_id == org.id))).scalars().all()
    assert len(forecasts) >= 1
    assert forecasts[0].forecast_type == "revenue"


@pytest.mark.asyncio
async def test_oversight_created(db_session, org_with_data):
    org, _ = org_with_data
    await recompute_executive_intel(db_session, org.id); await db_session.commit()
    oversight = (await db_session.execute(select(OversightModeReport).where(OversightModeReport.organization_id == org.id))).scalars().all()
    assert len(oversight) == 1
    assert oversight[0].mode in ("full_auto", "hybrid", "human_primary", "human_only")


@pytest.mark.asyncio
async def test_alerts_generated(db_session, org_with_data):
    org, _ = org_with_data
    await recompute_executive_intel(db_session, org.id); await db_session.commit()
    alerts = (await db_session.execute(select(ExecutiveAlert).where(ExecutiveAlert.organization_id == org.id))).scalars().all()
    assert isinstance(alerts, list)


@pytest.mark.asyncio
async def test_list_kpis(db_session, org_with_data):
    org, _ = org_with_data
    await recompute_executive_intel(db_session, org.id); await db_session.commit()
    kpis = await list_kpis(db_session, org.id)
    assert len(kpis) == 1


@pytest.mark.asyncio
async def test_list_forecasts(db_session, org_with_data):
    org, _ = org_with_data
    await recompute_executive_intel(db_session, org.id); await db_session.commit()
    f = await list_forecasts(db_session, org.id)
    assert len(f) >= 1


@pytest.mark.asyncio
async def test_list_alerts(db_session, org_with_data):
    org, _ = org_with_data
    await recompute_executive_intel(db_session, org.id); await db_session.commit()
    a = await list_alerts(db_session, org.id)
    assert isinstance(a, list)


@pytest.mark.asyncio
async def test_list_oversight(db_session, org_with_data):
    org, _ = org_with_data
    await recompute_executive_intel(db_session, org.id); await db_session.commit()
    o = await list_oversight(db_session, org.id)
    assert len(o) == 1


@pytest.mark.asyncio
async def test_executive_summary(db_session, org_with_data):
    org, _ = org_with_data
    await recompute_executive_intel(db_session, org.id); await db_session.commit()
    s = await get_executive_summary(db_session, org.id)
    assert "revenue" in s
    assert "content_produced" in s


@pytest.mark.asyncio
async def test_idempotent(db_session, org_with_data):
    org, _ = org_with_data
    await recompute_executive_intel(db_session, org.id); await db_session.commit()
    await recompute_executive_intel(db_session, org.id); await db_session.commit()
    kpis = (await db_session.execute(select(ExecutiveKPIReport).where(ExecutiveKPIReport.organization_id == org.id))).scalars().all()
    assert len(kpis) == 1


def test_executive_intel_worker_registered():
    from workers.celery_app import app
    import workers.executive_intel_worker.tasks  # noqa: F401
    assert "workers.executive_intel_worker.tasks.recompute_executive_intel" in app.tasks
