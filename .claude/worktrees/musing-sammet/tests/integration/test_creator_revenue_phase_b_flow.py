"""DB-backed integration tests for Creator Revenue Avenues Phase B."""
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
    from packages.db.enums import ContentType

    org_id = uuid.uuid4()
    brand_id = uuid.uuid4()
    db.add(Organization(id=org_id, name=f"TestOrg-{org_id.hex[:8]}", slug=f"testorg-{org_id.hex[:8]}"))
    await db.flush()
    db.add(Brand(id=brand_id, organization_id=org_id, name="CRPhaseBTestBrand", slug=f"crb-{brand_id.hex[:8]}", niche="tech"))
    await db.flush()
    for i in range(25):
        db.add(ContentItem(brand_id=brand_id, title=f"TestContent-{i}", content_type=ContentType.SHORT_VIDEO, status="approved"))
    await db.flush()
    return brand_id


@pytest.mark.asyncio
async def test_licensing_recompute(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import recompute_licensing, list_licensing
    result = await recompute_licensing(db, seed_brand)
    assert result["created"] >= 1
    items = await list_licensing(db, seed_brand)
    assert len(items) >= 1
    assert items[0].asset_type is not None
    assert items[0].is_active is True


@pytest.mark.asyncio
async def test_licensing_idempotent(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import recompute_licensing, list_licensing
    await recompute_licensing(db, seed_brand)
    first = await list_licensing(db, seed_brand)
    await recompute_licensing(db, seed_brand)
    second = await list_licensing(db, seed_brand)
    assert len(second) >= 1
    first_ids = {i.id for i in first}
    second_ids = {i.id for i in second}
    assert first_ids.isdisjoint(second_ids)


@pytest.mark.asyncio
async def test_syndication_recompute(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import recompute_syndication, list_syndication
    result = await recompute_syndication(db, seed_brand)
    assert result["created"] >= 1
    items = await list_syndication(db, seed_brand)
    assert len(items) >= 1
    assert items[0].syndication_format is not None
    assert items[0].is_active is True


@pytest.mark.asyncio
async def test_syndication_idempotent(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import recompute_syndication, list_syndication
    await recompute_syndication(db, seed_brand)
    first = await list_syndication(db, seed_brand)
    await recompute_syndication(db, seed_brand)
    second = await list_syndication(db, seed_brand)
    assert len(second) >= 1
    assert {i.id for i in first}.isdisjoint({i.id for i in second})


@pytest.mark.asyncio
async def test_data_products_recompute(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import recompute_data_products, list_data_products
    result = await recompute_data_products(db, seed_brand)
    assert result["created"] >= 1
    items = await list_data_products(db, seed_brand)
    assert len(items) >= 1
    assert items[0].product_type is not None
    assert items[0].is_active is True


@pytest.mark.asyncio
async def test_data_products_idempotent(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import recompute_data_products, list_data_products
    await recompute_data_products(db, seed_brand)
    first = await list_data_products(db, seed_brand)
    await recompute_data_products(db, seed_brand)
    second = await list_data_products(db, seed_brand)
    assert len(second) >= 1
    assert {i.id for i in first}.isdisjoint({i.id for i in second})


@pytest.mark.asyncio
async def test_blockers_include_phase_b(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import recompute_blockers, list_blockers
    result = await recompute_blockers(db, seed_brand)
    assert result["created"] >= 1
    items = await list_blockers(db, seed_brand)
    types = {b.avenue_type for b in items}
    assert "licensing" in types or "syndication" in types or "data_products" in types or "all" in types


@pytest.mark.asyncio
async def test_revenue_event_persistence(db: AsyncSession, seed_brand):
    from packages.db.models.creator_revenue import CreatorRevenueEvent
    event = CreatorRevenueEvent(
        brand_id=seed_brand,
        avenue_type="licensing",
        event_type="deal_closed",
        revenue=5000.0,
        cost=500.0,
        profit=4500.0,
        client_name="TestClient",
    )
    db.add(event)
    await db.flush()
    q = await db.execute(
        select(CreatorRevenueEvent).where(
            CreatorRevenueEvent.brand_id == seed_brand,
            CreatorRevenueEvent.avenue_type == "licensing",
        )
    )
    found = q.scalars().first()
    assert found is not None
    assert found.profit == 4500.0
