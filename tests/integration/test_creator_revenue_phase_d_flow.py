"""DB-backed integration tests for Creator Revenue Avenues Phase D — Hub."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def db(db_session):
    yield db_session


@pytest_asyncio.fixture
async def seed_brand(db: AsyncSession):
    from packages.db.enums import ContentType, MonetizationMethod
    from packages.db.models.content import ContentItem
    from packages.db.models.core import Brand, Organization
    from packages.db.models.offers import Offer

    org_id = uuid.uuid4()
    brand_id = uuid.uuid4()
    db.add(Organization(id=org_id, name=f"TestOrg-{org_id.hex[:8]}", slug=f"testorg-{org_id.hex[:8]}"))
    await db.flush()
    db.add(Brand(id=brand_id, organization_id=org_id, name="CRPhaseDTestBrand", slug=f"crd-{brand_id.hex[:8]}", niche="tech"))
    await db.flush()
    for i in range(25):
        db.add(ContentItem(brand_id=brand_id, title=f"TestContent-{i}", content_type=ContentType.SHORT_VIDEO, status="approved"))
    db.add(Offer(brand_id=brand_id, name="TestOffer", monetization_method=MonetizationMethod.PRODUCT))
    await db.flush()
    return brand_id


@pytest.mark.asyncio
async def test_hub_get_returns_all_9_avenues(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import get_hub
    hub = await get_hub(db, seed_brand)
    assert len(hub["entries"]) == 9
    avenues = {e["avenue_type"] for e in hub["entries"]}
    assert "ugc_services" in avenues
    assert "merch" in avenues
    assert "live_events" in avenues
    assert "owned_affiliate_program" in avenues
    assert "licensing" in avenues


@pytest.mark.asyncio
async def test_hub_entries_have_required_fields(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import get_hub
    hub = await get_hub(db, seed_brand)
    for e in hub["entries"]:
        assert "avenue_type" in e
        assert "avenue_display_name" in e
        assert "truth_state" in e
        assert "total_expected_value" in e
        assert "avg_confidence" in e
        assert "hub_score" in e
        assert "operator_next_action" in e
        assert "missing_integrations" in e


@pytest.mark.asyncio
async def test_hub_summary_totals(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import get_hub
    hub = await get_hub(db, seed_brand)
    assert "total_expected_value" in hub
    assert "total_revenue_to_date" in hub
    assert "total_blockers" in hub
    assert "event_rollup" in hub
    assert hub["avenues_live"] + hub["avenues_blocked"] + hub["avenues_executing"] + hub["avenues_queued"] + hub["avenues_recommended"] == 9


@pytest.mark.asyncio
async def test_hub_recompute_persists_truth(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import list_truth, recompute_hub
    result = await recompute_hub(db, seed_brand)
    assert result["created"] == 9
    truth = await list_truth(db, seed_brand)
    assert len(truth) == 9
    avenues = {t.avenue_type for t in truth}
    assert len(avenues) == 9


@pytest.mark.asyncio
async def test_hub_recompute_idempotent(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import list_truth, recompute_hub
    await recompute_hub(db, seed_brand)
    first = await list_truth(db, seed_brand)
    await recompute_hub(db, seed_brand)
    second = await list_truth(db, seed_brand)
    assert len(second) == 9
    assert {t.id for t in first}.isdisjoint({t.id for t in second})


@pytest.mark.asyncio
async def test_hub_with_actions_shows_counts(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import get_hub, recompute_live_events, recompute_merch
    await recompute_merch(db, seed_brand)
    await recompute_live_events(db, seed_brand)
    hub = await get_hub(db, seed_brand)
    merch_entry = next(e for e in hub["entries"] if e["avenue_type"] == "merch")
    events_entry = next(e for e in hub["entries"] if e["avenue_type"] == "live_events")
    assert merch_entry["total_actions"] >= 1
    assert events_entry["total_actions"] >= 1


@pytest.mark.asyncio
async def test_blocker_aggregation_in_hub(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import get_hub, recompute_blockers
    await recompute_blockers(db, seed_brand)
    hub = await get_hub(db, seed_brand)
    assert hub["total_blockers"] >= 1
    has_blocker_entry = any(e["blocker_count"] > 0 for e in hub["entries"])
    assert has_blocker_entry


@pytest.mark.asyncio
async def test_event_rollup_in_hub(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import get_hub
    from packages.db.models.creator_revenue import CreatorRevenueEvent
    db.add(CreatorRevenueEvent(
        brand_id=seed_brand,
        avenue_type="consulting",
        event_type="deal_closed",
        revenue=3000,
        cost=500,
        profit=2500,
        client_name="TestClient",
    ))
    await db.flush()
    hub = await get_hub(db, seed_brand)
    assert hub["event_rollup"]["total_revenue"] == 3000
    assert hub["event_rollup"]["total_profit"] == 2500
    assert "consulting" in hub["event_rollup"]["by_avenue"]


@pytest.mark.asyncio
async def test_truth_state_reflects_revenue(db: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import get_hub, recompute_merch
    from packages.db.models.creator_revenue import CreatorRevenueEvent
    await recompute_merch(db, seed_brand)
    db.add(CreatorRevenueEvent(
        brand_id=seed_brand,
        avenue_type="merch",
        event_type="order_completed",
        revenue=100,
        cost=30,
        profit=70,
    ))
    await db.flush()
    hub = await get_hub(db, seed_brand)
    merch = next(e for e in hub["entries"] if e["avenue_type"] == "merch")
    assert merch["truth_state"] == "live"
    assert merch["revenue_to_date"] == 100
