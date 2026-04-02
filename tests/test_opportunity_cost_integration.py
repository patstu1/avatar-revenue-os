"""DB-backed integration tests for Opportunity-Cost Ranking."""
from __future__ import annotations
import uuid
import pytest
import pytest_asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.core import Brand, Organization
from packages.db.models.accounts import CreatorAccount
from packages.db.models.account_state_intel import AccountStateReport
from packages.db.models.opportunity_cost import OpportunityCostReport, RankedAction, CostOfDelayModel
from packages.db.enums import Platform
from apps.api.services.opportunity_cost_service import (
    recompute_ranking, list_reports, list_ranked_actions, get_top_actions,
)


@pytest_asyncio.fixture
async def brand_with_state(db_session: AsyncSession):
    slug = f"oc-{uuid.uuid4().hex[:6]}"
    org = Organization(name="OC Test Org", slug=f"org-{slug}")
    db_session.add(org)
    await db_session.flush()

    brand = Brand(organization_id=org.id, name="OC Brand", slug=slug, niche="tech")
    db_session.add(brand)
    await db_session.flush()

    acct1 = CreatorAccount(brand_id=brand.id, platform=Platform.TIKTOK, platform_username=f"@oc1_{slug}")
    acct2 = CreatorAccount(brand_id=brand.id, platform=Platform.INSTAGRAM, platform_username=f"@oc2_{slug}")
    db_session.add_all([acct1, acct2])
    await db_session.flush()

    db_session.add(AccountStateReport(brand_id=brand.id, account_id=acct1.id, current_state="scaling", confidence=0.8, monetization_intensity="medium", posting_cadence="aggressive", expansion_eligible=True))
    db_session.add(AccountStateReport(brand_id=brand.id, account_id=acct2.id, current_state="weak", confidence=0.7, monetization_intensity="none", posting_cadence="minimal", expansion_eligible=False))
    await db_session.flush()

    return brand


@pytest.mark.asyncio
async def test_recompute_creates_ranked_actions(db_session, brand_with_state):
    brand = brand_with_state
    result = await recompute_ranking(db_session, brand.id)
    await db_session.commit()

    assert result["status"] == "completed"
    assert result["rows_processed"] >= 2

    actions = (await db_session.execute(
        select(RankedAction).where(RankedAction.brand_id == brand.id)
    )).scalars().all()
    assert len(actions) >= 2
    assert actions[0].rank_position == 1 or any(a.rank_position == 1 for a in actions)


@pytest.mark.asyncio
async def test_report_created(db_session, brand_with_state):
    brand = brand_with_state
    await recompute_ranking(db_session, brand.id)
    await db_session.commit()

    reports = (await db_session.execute(
        select(OpportunityCostReport).where(OpportunityCostReport.brand_id == brand.id)
    )).scalars().all()
    assert len(reports) == 1
    assert reports[0].total_actions >= 2
    assert reports[0].total_opportunity_cost > 0


@pytest.mark.asyncio
async def test_cost_of_delay_persisted(db_session, brand_with_state):
    brand = brand_with_state
    await recompute_ranking(db_session, brand.id)
    await db_session.commit()

    delays = (await db_session.execute(
        select(CostOfDelayModel).where(CostOfDelayModel.brand_id == brand.id)
    )).scalars().all()
    assert len(delays) >= 2
    for d in delays:
        assert d.daily_cost > 0
        assert d.weekly_cost > 0


@pytest.mark.asyncio
async def test_ranking_order(db_session, brand_with_state):
    brand = brand_with_state
    await recompute_ranking(db_session, brand.id)
    await db_session.commit()

    actions = (await db_session.execute(
        select(RankedAction).where(RankedAction.brand_id == brand.id).order_by(RankedAction.rank_position)
    )).scalars().all()
    for i in range(1, len(actions)):
        assert actions[i - 1].composite_rank >= actions[i].composite_rank


@pytest.mark.asyncio
async def test_list_reports(db_session, brand_with_state):
    brand = brand_with_state
    await recompute_ranking(db_session, brand.id)
    await db_session.commit()
    reports = await list_reports(db_session, brand.id)
    assert len(reports) == 1


@pytest.mark.asyncio
async def test_list_ranked_actions(db_session, brand_with_state):
    brand = brand_with_state
    await recompute_ranking(db_session, brand.id)
    await db_session.commit()
    actions = await list_ranked_actions(db_session, brand.id)
    assert len(actions) >= 2


@pytest.mark.asyncio
async def test_get_top_actions(db_session, brand_with_state):
    brand = brand_with_state
    await recompute_ranking(db_session, brand.id)
    await db_session.commit()
    top = await get_top_actions(db_session, brand.id, limit=3)
    assert isinstance(top, list)
    assert len(top) >= 2
    for a in top:
        assert "rank" in a
        assert "type" in a
        assert "delay_cost" in a
        assert "safe_to_wait" in a


@pytest.mark.asyncio
async def test_idempotent(db_session, brand_with_state):
    brand = brand_with_state
    r1 = await recompute_ranking(db_session, brand.id)
    await db_session.commit()
    r2 = await recompute_ranking(db_session, brand.id)
    await db_session.commit()
    assert r1["rows_processed"] == r2["rows_processed"]


def test_opportunity_cost_worker_registered():
    from workers.celery_app import app
    import workers.opportunity_cost_worker.tasks  # noqa: F401
    assert "workers.opportunity_cost_worker.tasks.recompute_opportunity_cost" in app.tasks
