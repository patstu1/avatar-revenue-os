"""DB-backed integration tests for Portfolio Capital Allocator."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.capital_allocator_service import (
    get_allocation_for_target,
    list_decisions,
    list_reports,
    recompute_allocation,
)
from packages.db.enums import ContentType, Platform
from packages.db.models.accounts import CreatorAccount
from packages.db.models.capital_allocator import (
    AllocationTarget,
    CAAllocationDecision,
    CapitalAllocationReport,
)
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand, Organization
from packages.db.models.offers import Offer
from packages.db.models.publishing import PerformanceMetric


@pytest_asyncio.fixture
async def brand_with_data(db_session: AsyncSession):
    slug = f"cap-{uuid.uuid4().hex[:6]}"
    org = Organization(name="Cap Test Org", slug=f"org-{slug}")
    db_session.add(org)
    await db_session.flush()

    brand = Brand(organization_id=org.id, name="Cap Brand", slug=slug, niche="tech")
    db_session.add(brand)
    await db_session.flush()

    acct = CreatorAccount(brand_id=brand.id, platform=Platform.TIKTOK, platform_username=f"@tt_{slug}")
    db_session.add(acct)
    await db_session.flush()

    offer = Offer(
        brand_id=brand.id,
        name="Test Offer",
        monetization_method="affiliate",
        payout_amount=30.0,
        epc=2.5,
        conversion_rate=0.05,
    )
    db_session.add(offer)
    await db_session.flush()

    ci = ContentItem(
        brand_id=brand.id,
        creator_account_id=acct.id,
        title="Test content",
        content_type=ContentType.SHORT_VIDEO,
        platform="tiktok",
    )
    db_session.add(ci)
    await db_session.flush()

    pm = PerformanceMetric(
        brand_id=brand.id,
        content_item_id=ci.id,
        creator_account_id=acct.id,
        platform=Platform.TIKTOK,
        impressions=10000,
        clicks=500,
        engagement_rate=0.08,
        revenue=50.0,
    )
    db_session.add(pm)
    await db_session.flush()

    return brand, acct, offer


@pytest.mark.asyncio
async def test_recompute_allocation(db_session, brand_with_data):
    brand, acct, offer = brand_with_data
    result = await recompute_allocation(db_session, brand.id, 1000.0)
    await db_session.commit()

    assert result["status"] == "completed"
    assert result["rows_processed"] > 0

    reports = (
        (await db_session.execute(select(CapitalAllocationReport).where(CapitalAllocationReport.brand_id == brand.id)))
        .scalars()
        .all()
    )
    assert len(reports) == 1
    assert reports[0].total_budget == 1000.0
    assert reports[0].target_count > 0


@pytest.mark.asyncio
async def test_decisions_created(db_session, brand_with_data):
    brand, _, _ = brand_with_data
    await recompute_allocation(db_session, brand.id, 500.0)
    await db_session.commit()

    decisions = (
        (await db_session.execute(select(CAAllocationDecision).where(CAAllocationDecision.brand_id == brand.id)))
        .scalars()
        .all()
    )
    assert len(decisions) > 0
    for d in decisions:
        assert d.allocated_budget >= 0
        assert d.provider_tier in ("hero", "bulk", "standard")


@pytest.mark.asyncio
async def test_hero_vs_bulk_assigned(db_session, brand_with_data):
    brand, _, _ = brand_with_data
    await recompute_allocation(db_session, brand.id, 2000.0)
    await db_session.commit()

    decisions = (
        (await db_session.execute(select(CAAllocationDecision).where(CAAllocationDecision.brand_id == brand.id)))
        .scalars()
        .all()
    )
    tiers = {d.provider_tier for d in decisions}
    assert len(tiers) >= 1


@pytest.mark.asyncio
async def test_targets_created(db_session, brand_with_data):
    brand, _, _ = brand_with_data
    await recompute_allocation(db_session, brand.id, 1000.0)
    await db_session.commit()

    targets = (
        (await db_session.execute(select(AllocationTarget).where(AllocationTarget.brand_id == brand.id)))
        .scalars()
        .all()
    )
    assert len(targets) > 0
    target_types = {t.target_type for t in targets}
    assert "account" in target_types
    assert "offer" in target_types


@pytest.mark.asyncio
async def test_list_reports(db_session, brand_with_data):
    brand, _, _ = brand_with_data
    await recompute_allocation(db_session, brand.id)
    await db_session.commit()
    reports = await list_reports(db_session, brand.id)
    assert isinstance(reports, list)
    assert len(reports) >= 1


@pytest.mark.asyncio
async def test_list_decisions(db_session, brand_with_data):
    brand, _, _ = brand_with_data
    await recompute_allocation(db_session, brand.id)
    await db_session.commit()
    decs = await list_decisions(db_session, brand.id)
    assert isinstance(decs, list)
    assert len(decs) >= 1


@pytest.mark.asyncio
async def test_get_allocation_for_target(db_session, brand_with_data):
    brand, acct, _ = brand_with_data
    await recompute_allocation(db_session, brand.id)
    await db_session.commit()
    result = await get_allocation_for_target(db_session, brand.id, "account", f"tiktok:{acct.platform_username}")
    assert "provider_tier" in result


@pytest.mark.asyncio
async def test_recompute_idempotent(db_session, brand_with_data):
    brand, _, _ = brand_with_data
    r1 = await recompute_allocation(db_session, brand.id, 1000.0)
    await db_session.commit()
    r2 = await recompute_allocation(db_session, brand.id, 1000.0)
    await db_session.commit()
    assert r1["rows_processed"] == r2["rows_processed"]

    reports = (
        (await db_session.execute(select(CapitalAllocationReport).where(CapitalAllocationReport.brand_id == brand.id)))
        .scalars()
        .all()
    )
    assert len(reports) == 1


def test_capital_allocator_worker_registered():
    import workers.capital_allocator_worker.tasks  # noqa: F401
    from workers.celery_app import app

    assert "workers.capital_allocator_worker.tasks.recompute_capital_allocation" in app.tasks
