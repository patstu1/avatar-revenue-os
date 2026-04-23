"""DB-backed integration tests for Account-State Intelligence."""
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
from packages.db.models.account_state_intel import (
    AccountStateReport, AccountStateTransition, AccountStateAction,
)
from packages.db.enums import Platform, ContentType
from apps.api.services.account_state_intel_service import (
    recompute_account_states, list_reports, list_transitions,
    list_actions, get_state_for_account,
)


@pytest_asyncio.fixture
async def brand_with_accounts(db_session: AsyncSession):
    slug = f"asi-{uuid.uuid4().hex[:6]}"
    org = Organization(name="ASI Test Org", slug=f"org-{slug}")
    db_session.add(org)
    await db_session.flush()

    brand = Brand(organization_id=org.id, name="ASI Brand", slug=slug, niche="tech")
    db_session.add(brand)
    await db_session.flush()

    acct_new = CreatorAccount(brand_id=brand.id, platform=Platform.TIKTOK, platform_username=f"@new_{slug}")
    acct_scaling = CreatorAccount(brand_id=brand.id, platform=Platform.INSTAGRAM, platform_username=f"@scale_{slug}", total_revenue=200, total_profit=50, conversion_rate=0.05)
    db_session.add_all([acct_new, acct_scaling])
    await db_session.flush()

    for i in range(20):
        ci = ContentItem(brand_id=brand.id, creator_account_id=acct_scaling.id, title=f"Scaling content {i}", content_type=ContentType.SHORT_VIDEO, platform="instagram")
        db_session.add(ci)
    await db_session.flush()

    scaling_items = (await db_session.execute(
        select(ContentItem).where(ContentItem.creator_account_id == acct_scaling.id)
    )).scalars().all()
    for ci in scaling_items:
        db_session.add(PerformanceMetric(brand_id=brand.id, content_item_id=ci.id, creator_account_id=acct_scaling.id, platform=Platform.INSTAGRAM, impressions=5000, engagement_rate=0.08, revenue=15.0))
    await db_session.flush()

    return brand, acct_new, acct_scaling


@pytest.mark.asyncio
async def test_recompute_creates_reports(db_session, brand_with_accounts):
    brand, acct_new, acct_scaling = brand_with_accounts
    result = await recompute_account_states(db_session, brand.id)
    await db_session.commit()

    assert result["status"] == "completed"
    assert result["rows_processed"] == 2

    reports = (await db_session.execute(
        select(AccountStateReport).where(AccountStateReport.brand_id == brand.id)
    )).scalars().all()
    assert len(reports) == 2
    states = {r.account_id: r.current_state for r in reports}
    assert acct_new.id in states
    assert acct_scaling.id in states


@pytest.mark.asyncio
async def test_newborn_classified_correctly(db_session, brand_with_accounts):
    brand, acct_new, _ = brand_with_accounts
    await recompute_account_states(db_session, brand.id)
    await db_session.commit()

    report = (await db_session.execute(
        select(AccountStateReport).where(AccountStateReport.account_id == acct_new.id)
    )).scalar_one_or_none()
    assert report is not None
    assert report.current_state in ("newborn", "warming")
    assert report.monetization_intensity in ("none", "low")
    assert report.expansion_eligible is False


@pytest.mark.asyncio
async def test_scaling_account_classified(db_session, brand_with_accounts):
    brand, _, acct_scaling = brand_with_accounts
    await recompute_account_states(db_session, brand.id)
    await db_session.commit()

    report = (await db_session.execute(
        select(AccountStateReport).where(AccountStateReport.account_id == acct_scaling.id)
    )).scalar_one_or_none()
    assert report is not None
    assert report.current_state in ("scaling", "monetizing", "early_signal", "authority_building")


@pytest.mark.asyncio
async def test_actions_created(db_session, brand_with_accounts):
    brand, _, _ = brand_with_accounts
    await recompute_account_states(db_session, brand.id)
    await db_session.commit()

    actions = (await db_session.execute(
        select(AccountStateAction).where(AccountStateAction.brand_id == brand.id)
    )).scalars().all()
    assert len(actions) >= 2


@pytest.mark.asyncio
async def test_transitions_on_recompute(db_session, brand_with_accounts):
    brand, _, _ = brand_with_accounts
    await recompute_account_states(db_session, brand.id)
    await db_session.commit()

    transitions = (await db_session.execute(
        select(AccountStateTransition).where(AccountStateTransition.brand_id == brand.id)
    )).scalars().all()
    assert isinstance(transitions, list)


@pytest.mark.asyncio
async def test_list_reports(db_session, brand_with_accounts):
    brand, _, _ = brand_with_accounts
    await recompute_account_states(db_session, brand.id)
    await db_session.commit()
    reports = await list_reports(db_session, brand.id)
    assert len(reports) == 2


@pytest.mark.asyncio
async def test_list_transitions(db_session, brand_with_accounts):
    brand, _, _ = brand_with_accounts
    await recompute_account_states(db_session, brand.id)
    await db_session.commit()
    assert isinstance(await list_transitions(db_session, brand.id), list)


@pytest.mark.asyncio
async def test_list_actions(db_session, brand_with_accounts):
    brand, _, _ = brand_with_accounts
    await recompute_account_states(db_session, brand.id)
    await db_session.commit()
    actions = await list_actions(db_session, brand.id)
    assert len(actions) >= 2


@pytest.mark.asyncio
async def test_get_state_for_account(db_session, brand_with_accounts):
    brand, acct_new, _ = brand_with_accounts
    await recompute_account_states(db_session, brand.id)
    await db_session.commit()

    state = await get_state_for_account(db_session, acct_new.id)
    assert "current_state" in state
    assert "monetization_intensity" in state
    assert "posting_cadence" in state
    assert "suitable_content_forms" in state


@pytest.mark.asyncio
async def test_idempotent(db_session, brand_with_accounts):
    brand, _, _ = brand_with_accounts
    r1 = await recompute_account_states(db_session, brand.id)
    await db_session.commit()
    r2 = await recompute_account_states(db_session, brand.id)
    await db_session.commit()
    assert r1["rows_processed"] == r2["rows_processed"]

    reports = (await db_session.execute(
        select(AccountStateReport).where(AccountStateReport.brand_id == brand.id)
    )).scalars().all()
    assert len(reports) == 2


def test_account_state_intel_worker_registered():
    from workers.celery_app import app
    import workers.account_state_intel_worker.tasks  # noqa: F401
    assert "workers.account_state_intel_worker.tasks.recompute_account_state_intel" in app.tasks
