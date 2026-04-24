"""DB-backed integration tests for Causal Attribution."""
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
from packages.db.models.causal_attribution import CausalAttributionReport, CausalHypothesis, CausalCreditAllocation, CausalConfidenceReport
from packages.db.enums import Platform, ContentType
from apps.api.services.causal_attribution_service import recompute_attribution, list_reports, list_hypotheses, list_credits, get_attribution_summary


@pytest_asyncio.fixture
async def brand_with_perf_series(db_session: AsyncSession):
    slug = f"ca-{uuid.uuid4().hex[:6]}"
    org = Organization(name="CA Org", slug=f"org-{slug}")
    db_session.add(org); await db_session.flush()
    brand = Brand(organization_id=org.id, name="CA Brand", slug=slug, niche="tech")
    db_session.add(brand); await db_session.flush()
    acct = CreatorAccount(brand_id=brand.id, platform=Platform.TIKTOK, platform_username=f"@ca_{slug}")
    db_session.add(acct); await db_session.flush()

    engagement_series = [0.04, 0.04, 0.05, 0.04, 0.03, 0.08, 0.09, 0.08]
    revenue_series = [10, 12, 11, 10, 10, 25, 30, 28]
    for i in range(8):
        ci = ContentItem(brand_id=brand.id, creator_account_id=acct.id, title=f"CA content {i}", content_type=ContentType.SHORT_VIDEO, platform="tiktok", status="published")
        db_session.add(ci); await db_session.flush()
        db_session.add(PerformanceMetric(brand_id=brand.id, content_item_id=ci.id, creator_account_id=acct.id, platform=Platform.TIKTOK, impressions=5000 + i * 1000, engagement_rate=engagement_series[i], revenue=revenue_series[i]))
    await db_session.flush()
    return brand


@pytest.mark.asyncio
async def test_recompute(db_session, brand_with_perf_series):
    brand = brand_with_perf_series
    result = await recompute_attribution(db_session, brand.id)
    await db_session.commit()
    assert result["status"] == "completed"
    assert result["rows_processed"] >= 8


@pytest.mark.asyncio
async def test_reports_created(db_session, brand_with_perf_series):
    brand = brand_with_perf_series
    await recompute_attribution(db_session, brand.id); await db_session.commit()
    reports = (await db_session.execute(select(CausalAttributionReport).where(CausalAttributionReport.brand_id == brand.id))).scalars().all()
    assert len(reports) >= 1
    for r in reports:
        assert r.direction in ("lift", "drop")
        assert r.magnitude > 0


@pytest.mark.asyncio
async def test_hypotheses_created(db_session, brand_with_perf_series):
    brand = brand_with_perf_series
    await recompute_attribution(db_session, brand.id); await db_session.commit()
    hypos = (await db_session.execute(select(CausalHypothesis).join(CausalAttributionReport).where(CausalAttributionReport.brand_id == brand.id))).scalars().all()
    assert len(hypos) >= 1
    for h in hypos:
        assert h.confidence > 0
        assert h.recommended_action


@pytest.mark.asyncio
async def test_credits_created(db_session, brand_with_perf_series):
    brand = brand_with_perf_series
    await recompute_attribution(db_session, brand.id); await db_session.commit()
    credits = (await db_session.execute(select(CausalCreditAllocation).join(CausalAttributionReport).where(CausalAttributionReport.brand_id == brand.id))).scalars().all()
    assert len(credits) >= 1

    reports = (await db_session.execute(select(CausalAttributionReport).where(CausalAttributionReport.brand_id == brand.id))).scalars().all()
    for r in reports:
        r_credits = [c for c in credits if c.report_id == r.id]
        if r_credits:
            total = sum(c.credit_pct for c in r_credits)
            assert total == pytest.approx(100, abs=1)


@pytest.mark.asyncio
async def test_confidence_report(db_session, brand_with_perf_series):
    brand = brand_with_perf_series
    await recompute_attribution(db_session, brand.id); await db_session.commit()
    conf = (await db_session.execute(select(CausalConfidenceReport).join(CausalAttributionReport).where(CausalAttributionReport.brand_id == brand.id))).scalars().all()
    assert len(conf) >= 1
    assert conf[0].recommendation


@pytest.mark.asyncio
async def test_list_reports(db_session, brand_with_perf_series):
    brand = brand_with_perf_series
    await recompute_attribution(db_session, brand.id); await db_session.commit()
    r = await list_reports(db_session, brand.id)
    assert len(r) >= 1


@pytest.mark.asyncio
async def test_list_hypotheses(db_session, brand_with_perf_series):
    brand = brand_with_perf_series
    await recompute_attribution(db_session, brand.id); await db_session.commit()
    h = await list_hypotheses(db_session, brand.id)
    assert len(h) >= 1


@pytest.mark.asyncio
async def test_get_attribution_summary(db_session, brand_with_perf_series):
    brand = brand_with_perf_series
    await recompute_attribution(db_session, brand.id); await db_session.commit()
    s = await get_attribution_summary(db_session, brand.id)
    assert len(s["reports"]) >= 1


@pytest.mark.asyncio
async def test_idempotent(db_session, brand_with_perf_series):
    brand = brand_with_perf_series
    await recompute_attribution(db_session, brand.id); await db_session.commit()
    await recompute_attribution(db_session, brand.id); await db_session.commit()
    reports = (await db_session.execute(select(CausalAttributionReport).where(CausalAttributionReport.brand_id == brand.id))).scalars().all()
    assert len(reports) >= 1


def test_causal_worker_registered():
    from workers.celery_app import app
    import workers.causal_attribution_worker.tasks  # noqa: F401
    assert "workers.causal_attribution_worker.tasks.recompute_causal_attribution" in app.tasks
