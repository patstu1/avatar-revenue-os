"""DB-backed integration tests for Creator Revenue Avenues Phase C."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def db(db_session):
    yield db_session


@pytest_asyncio.fixture
async def seed_brand(db: AsyncSession):
    from packages.db.models.core import Brand, Organization
    from packages.db.models.content import ContentItem
    from packages.db.models.offers import Offer
    from packages.db.enums import ContentType, MonetizationMethod

    org_id = uuid.uuid4()
    brand_id = uuid.uuid4()
    db.add(Organization(id=org_id, name=f"TestOrg-{org_id.hex[:8]}", slug=f"testorg-{org_id.hex[:8]}"))
    await db.flush()
    db.add(Brand(id=brand_id, organization_id=org_id, name="CRPhaseCTestBrand", slug=f"crc-{brand_id.hex[:8]}", niche="tech"))
    await db.flush()
    for i in range(25):
        db.add(ContentItem(brand_id=brand_id, title=f"TestContent-{i}", content_type=ContentType.SHORT_VIDEO, status="approved"))
    db.add(Offer(brand_id=brand_id, name="TestOffer", monetization_method=MonetizationMethod.PRODUCT))
    await db.flush()
    return brand_id


@pytest.mark.asyncio
async def test_merch_recompute(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import recompute_merch, list_merch
    result = await recompute_merch(db, seed_brand)
    assert result["created"] >= 1
    items = await list_merch(db, seed_brand)
    assert len(items) >= 1
    assert items[0].product_class is not None
    assert items[0].truth_label in ("recommended", "queued", "blocked", "live")
    assert items[0].is_active is True


@pytest.mark.asyncio
async def test_merch_idempotent(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import recompute_merch, list_merch
    await recompute_merch(db, seed_brand)
    first = await list_merch(db, seed_brand)
    await recompute_merch(db, seed_brand)
    second = await list_merch(db, seed_brand)
    assert len(second) >= 1
    assert {i.id for i in first}.isdisjoint({i.id for i in second})


@pytest.mark.asyncio
async def test_live_events_recompute(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import recompute_live_events, list_live_events
    result = await recompute_live_events(db, seed_brand)
    assert result["created"] >= 1
    items = await list_live_events(db, seed_brand)
    assert len(items) >= 1
    assert items[0].event_type is not None
    assert items[0].truth_label in ("recommended", "queued", "blocked", "live")


@pytest.mark.asyncio
async def test_live_events_idempotent(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import recompute_live_events, list_live_events
    await recompute_live_events(db, seed_brand)
    first = await list_live_events(db, seed_brand)
    await recompute_live_events(db, seed_brand)
    second = await list_live_events(db, seed_brand)
    assert len(second) >= 1
    assert {i.id for i in first}.isdisjoint({i.id for i in second})


@pytest.mark.asyncio
async def test_owned_affiliate_program_recompute(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import recompute_owned_affiliate_program, list_owned_affiliate_program
    result = await recompute_owned_affiliate_program(db, seed_brand)
    assert result["created"] >= 1
    items = await list_owned_affiliate_program(db, seed_brand)
    assert len(items) >= 1
    assert items[0].program_type is not None
    assert items[0].truth_label in ("recommended", "queued", "blocked", "live")


@pytest.mark.asyncio
async def test_owned_affiliate_idempotent(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import recompute_owned_affiliate_program, list_owned_affiliate_program
    await recompute_owned_affiliate_program(db, seed_brand)
    first = await list_owned_affiliate_program(db, seed_brand)
    await recompute_owned_affiliate_program(db, seed_brand)
    second = await list_owned_affiliate_program(db, seed_brand)
    assert len(second) >= 1
    assert {i.id for i in first}.isdisjoint({i.id for i in second})


@pytest.mark.asyncio
async def test_blockers_include_phase_c(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import recompute_blockers, list_blockers
    result = await recompute_blockers(db, seed_brand)
    assert result["created"] >= 1
    items = await list_blockers(db, seed_brand)
    types = {b.blocker_type for b in items}
    assert "no_payment_processor" in types


@pytest.mark.asyncio
async def test_revenue_event_for_phase_c(db: AsyncSession, seed_brand):
    from packages.db.models.creator_revenue import CreatorRevenueEvent
    event = CreatorRevenueEvent(
        brand_id=seed_brand,
        avenue_type="merch",
        event_type="order_completed",
        revenue=150.0,
        cost=40.0,
        profit=110.0,
        client_name="MerchBuyer",
    )
    db.add(event)
    await db.flush()
    q = await db.execute(
        select(CreatorRevenueEvent).where(
            CreatorRevenueEvent.brand_id == seed_brand,
            CreatorRevenueEvent.avenue_type == "merch",
        )
    )
    found = q.scalars().first()
    assert found is not None
    assert found.profit == 110.0
