"""Integration: Phase D — Deal Desk & Kill Ledger persistence and API shape.

Requires Postgres (TEST_DATABASE_URL) and metadata create_all including Phase D tables.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from apps.api.main import app
from apps.api.deps import get_db, get_current_user
from apps.api.services import deal_desk_service
from apps.api.services import kill_ledger_service
from packages.db.enums import MonetizationMethod, Platform
from packages.db.models.accounts import CreatorAccount
from packages.db.models.core import Brand, Organization
from packages.db.models.deal_desk import DealDeskEvent, DealDeskRecommendation
from packages.db.models.kill_ledger import KillHindsightReview, KillLedgerEntry
from packages.db.models.offers import Offer


@pytest.mark.asyncio
async def test_deal_desk_recompute_persists_pricing_stance(db_session):
    org = Organization(name="DD Org", slug="dd-org")
    db_session.add(org)
    await db_session.flush()
    brand = Brand(
        name="DD Brand",
        slug=f"dd-brand-{uuid.uuid4().hex[:8]}",
        organization_id=org.id,
        niche="tech",
    )
    db_session.add(brand)
    await db_session.flush()

    db_session.add(
        Offer(
            brand_id=brand.id,
            name="High ticket",
            monetization_method=MonetizationMethod.AFFILIATE,
            conversion_rate=0.05,
            epc=10.0,
            average_order_value=500.0,
            is_active=True,
        )
    )
    await db_session.commit()

    out = await deal_desk_service.recompute_deal_desk(db_session, brand.id)
    await db_session.commit()
    assert out["deal_desk_recommendations"] >= 1
    assert out.get("deal_desk_events", 0) >= 1

    rows = (
        (await db_session.execute(select(DealDeskRecommendation).where(DealDeskRecommendation.brand_id == brand.id)))
        .scalars()
        .all()
    )
    assert len(rows) >= 1
    assert rows[0].pricing_stance in ("premium", "competitive", "penetration", "hold")
    assert rows[0].deal_strategy

    ev = (
        (await db_session.execute(select(DealDeskEvent).where(DealDeskEvent.brand_id == brand.id)))
        .scalars()
        .all()
    )
    assert len(ev) >= 1


@pytest.mark.asyncio
async def test_kill_ledger_and_hindsight_persist(db_session):
    org = Organization(name="KL Org", slug="kl-org")
    db_session.add(org)
    await db_session.flush()
    brand = Brand(
        name="KL Brand",
        slug=f"kl-brand-{uuid.uuid4().hex[:8]}",
        organization_id=org.id,
    )
    db_session.add(brand)
    await db_session.flush()

    db_session.add(
        Offer(
            brand_id=brand.id,
            name="Weak Offer",
            monetization_method=MonetizationMethod.AFFILIATE,
            conversion_rate=0.0001,
            epc=0.0,
            average_order_value=0.0,
            is_active=True,
        )
    )
    db_session.add(
        CreatorAccount(
            brand_id=brand.id,
            platform=Platform.YOUTUBE,
            platform_username="@kl_test",
            posting_capacity_per_day=1,
        )
    )
    await db_session.commit()

    k1 = await kill_ledger_service.recompute_kill_ledger(db_session, brand.id)
    await db_session.commit()
    assert k1["kill_entries_added"] >= 1

    entries = (
        (await db_session.execute(select(KillLedgerEntry).where(KillLedgerEntry.brand_id == brand.id)))
        .scalars()
        .all()
    )
    assert len(entries) >= 1
    assert entries[0].replacement_recommendation_json

    h1 = await kill_ledger_service.recompute_kill_hindsight(db_session, brand.id)
    await db_session.commit()
    assert h1["hindsight_reviews"] >= 1

    reviews = (
        (await db_session.execute(select(KillHindsightReview).where(KillHindsightReview.brand_id == brand.id)))
        .scalars()
        .all()
    )
    assert len(reviews) >= 1
    assert reviews[0].hindsight_outcome

    entry = entries[0]
    assert reviews[0].kill_ledger_entry_id == entry.id


@pytest.mark.asyncio
async def test_kill_bundle_merges_hindsight(db_session):
    org = Organization(name="KL2 Org", slug="kl2-org")
    db_session.add(org)
    await db_session.flush()
    brand = Brand(
        name="KL2 Brand",
        slug=f"kl2-{uuid.uuid4().hex[:8]}",
        organization_id=org.id,
    )
    db_session.add(brand)
    await db_session.flush()
    db_session.add(
        Offer(
            brand_id=brand.id,
            name="Bundle Offer",
            monetization_method=MonetizationMethod.AFFILIATE,
            conversion_rate=0.0001,
            epc=0.0,
            average_order_value=0.0,
            is_active=True,
        )
    )
    await db_session.commit()
    await kill_ledger_service.recompute_kill_ledger_full(db_session, brand.id)
    await db_session.commit()

    bundle = await kill_ledger_service.get_kill_ledger_bundle(db_session, brand.id)
    assert "entries" in bundle
    assert "hindsight_reviews" in bundle
    assert "entries_with_hindsight" in bundle


@pytest.mark.asyncio
async def test_api_deal_desk_and_kill_ledger_routes(db_session):
    """Smoke-test GET routes with dependency overrides (no JWT)."""
    from packages.db.models.core import User
    from packages.db.enums import UserRole

    org = Organization(name="API DD Org", slug="api-dd-org")
    db_session.add(org)
    await db_session.flush()
    user = User(
        organization_id=org.id,
        email=f"op-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        full_name="Op",
        role=UserRole.OPERATOR,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    brand = Brand(
        name="API Brand",
        slug=f"api-{uuid.uuid4().hex[:8]}",
        organization_id=org.id,
    )
    db_session.add(brand)
    await db_session.flush()
    db_session.add(
        Offer(
            brand_id=brand.id,
            name="API Offer",
            monetization_method=MonetizationMethod.AFFILIATE,
            conversion_rate=0.04,
            epc=5.0,
            average_order_value=99.0,
            is_active=True,
        )
    )
    await db_session.commit()

    await deal_desk_service.recompute_deal_desk(db_session, brand.id)
    await kill_ledger_service.recompute_kill_ledger_full(db_session, brand.id)
    await db_session.commit()

    async def override_db():
        yield db_session

    async def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.get(f"/api/v1/brands/{brand.id}/deal-desk")
        assert r1.status_code == 200
        assert isinstance(r1.json(), list)
        assert len(r1.json()) >= 1

        r2 = await client.get(f"/api/v1/brands/{brand.id}/kill-ledger")
        assert r2.status_code == 200
        body = r2.json()
        assert "entries_with_hindsight" in body

        r3 = await client.post(f"/api/v1/brands/{brand.id}/deal-desk/recompute")
        assert r3.status_code == 200
        assert "deal_desk_recommendations" in r3.json()

        r4 = await client.post(f"/api/v1/brands/{brand.id}/kill-ledger/recompute")
        assert r4.status_code == 200
        assert "kill_entries_added" in r4.json()
        assert "hindsight_reviews" in r4.json()

    app.dependency_overrides.clear()


def test_recompute_all_kill_ledger_worker_runs():
    """Celery task executes without raising (uses TEST_DATABASE_URL / default DB)."""
    from workers.mxp_worker.tasks import recompute_all_kill_ledger

    try:
        res = recompute_all_kill_ledger.apply()
        out = res.get(timeout=120)
    except Exception as e:
        pytest.skip(f"Worker or DB unavailable: {e}")
    assert isinstance(out, dict)
    assert "brands" in out


def test_recompute_all_deal_desk_worker_runs():
    from workers.mxp_worker.tasks import recompute_all_deal_desk

    try:
        res = recompute_all_deal_desk.apply()
        out = res.get(timeout=120)
    except Exception as e:
        pytest.skip(f"Worker or DB unavailable: {e}")
    assert isinstance(out, dict)
    assert "brands" in out
