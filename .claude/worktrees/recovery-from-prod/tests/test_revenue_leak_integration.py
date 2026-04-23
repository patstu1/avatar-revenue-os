"""DB-backed integration tests for Revenue Leak Detector."""
from __future__ import annotations
import uuid
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from packages.db.models.core import Brand, Organization
from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.publishing import PerformanceMetric
from packages.db.models.account_state_intel import AccountStateReport
from packages.db.models.revenue_leak_detector import RevenueLeakReport, RevenueLeakEvent, LeakCluster, LeakCorrectionAction
from packages.db.enums import Platform, ContentType
from apps.api.services.revenue_leak_service import recompute_leaks, list_reports, list_events, list_clusters, list_corrections, get_leak_summary


@pytest_asyncio.fixture
async def brand_with_perf(db_session: AsyncSession):
    slug = f"rld-{uuid.uuid4().hex[:6]}"
    org = Organization(name="RLD Org", slug=f"org-{slug}")
    db_session.add(org); await db_session.flush()
    brand = Brand(organization_id=org.id, name="RLD Brand", slug=slug, niche="tech")
    db_session.add(brand); await db_session.flush()
    acct = CreatorAccount(brand_id=brand.id, platform=Platform.TIKTOK, platform_username=f"@rld_{slug}")
    db_session.add(acct); await db_session.flush()

    ci_good = ContentItem(brand_id=brand.id, creator_account_id=acct.id, title="Good content", content_type=ContentType.SHORT_VIDEO, platform="tiktok", status="published")
    ci_leak = ContentItem(brand_id=brand.id, creator_account_id=acct.id, title="Leaking content", content_type=ContentType.SHORT_VIDEO, platform="tiktok", status="published")
    db_session.add_all([ci_good, ci_leak]); await db_session.flush()

    db_session.add(PerformanceMetric(brand_id=brand.id, content_item_id=ci_good.id, creator_account_id=acct.id, platform=Platform.TIKTOK, impressions=5000, clicks=300, engagement_rate=0.06, revenue=80.0))
    db_session.add(PerformanceMetric(brand_id=brand.id, content_item_id=ci_leak.id, creator_account_id=acct.id, platform=Platform.TIKTOK, impressions=20000, clicks=50, engagement_rate=0.08, revenue=2.0))
    db_session.add(AccountStateReport(brand_id=brand.id, account_id=acct.id, current_state="scaling", confidence=0.8, monetization_intensity="medium", posting_cadence="aggressive", expansion_eligible=True))
    await db_session.flush()
    return brand


@pytest.mark.asyncio
async def test_recompute_detects_leaks(db_session, brand_with_perf):
    brand = brand_with_perf
    result = await recompute_leaks(db_session, brand.id)
    await db_session.commit()
    assert result["status"] == "completed"
    assert result["rows_processed"] >= 1
    assert result["total_loss"] > 0


@pytest.mark.asyncio
async def test_report_created(db_session, brand_with_perf):
    brand = brand_with_perf
    await recompute_leaks(db_session, brand.id); await db_session.commit()
    reports = (await db_session.execute(select(RevenueLeakReport).where(RevenueLeakReport.brand_id == brand.id))).scalars().all()
    assert len(reports) == 1
    assert reports[0].total_leaks >= 1


@pytest.mark.asyncio
async def test_events_created(db_session, brand_with_perf):
    brand = brand_with_perf
    await recompute_leaks(db_session, brand.id); await db_session.commit()
    events = (await db_session.execute(select(RevenueLeakEvent).where(RevenueLeakEvent.brand_id == brand.id))).scalars().all()
    assert len(events) >= 1
    types = {e.leak_type for e in events}
    assert len(types) >= 1


@pytest.mark.asyncio
async def test_clusters_created(db_session, brand_with_perf):
    brand = brand_with_perf
    await recompute_leaks(db_session, brand.id); await db_session.commit()
    clusters = (await db_session.execute(select(LeakCluster).where(LeakCluster.brand_id == brand.id))).scalars().all()
    assert len(clusters) >= 1


@pytest.mark.asyncio
async def test_corrections_created(db_session, brand_with_perf):
    brand = brand_with_perf
    await recompute_leaks(db_session, brand.id); await db_session.commit()
    corrs = (await db_session.execute(select(LeakCorrectionAction).where(LeakCorrectionAction.brand_id == brand.id))).scalars().all()
    assert len(corrs) >= 1


@pytest.mark.asyncio
async def test_list_reports(db_session, brand_with_perf):
    brand = brand_with_perf
    await recompute_leaks(db_session, brand.id); await db_session.commit()
    r = await list_reports(db_session, brand.id)
    assert len(r) == 1


@pytest.mark.asyncio
async def test_get_leak_summary(db_session, brand_with_perf):
    brand = brand_with_perf
    await recompute_leaks(db_session, brand.id); await db_session.commit()
    s = await get_leak_summary(db_session, brand.id)
    assert s["total_leaks"] >= 1
    assert s["total_loss"] > 0


@pytest.mark.asyncio
async def test_idempotent(db_session, brand_with_perf):
    brand = brand_with_perf
    r1 = await recompute_leaks(db_session, brand.id); await db_session.commit()
    r2 = await recompute_leaks(db_session, brand.id); await db_session.commit()
    assert r1["rows_processed"] == r2["rows_processed"]


def test_revenue_leak_worker_registered():
    from workers.celery_app import app
    import workers.revenue_leak_worker.tasks  # noqa: F401
    assert "workers.revenue_leak_worker.tasks.recompute_revenue_leaks" in app.tasks
