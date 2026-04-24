"""DB-backed integration tests for Offer Lab."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.offer_lab_service import (
    get_best_offer,
    list_offers,
    list_variants,
    recompute_offer_lab,
)
from packages.db.models.core import Brand, Organization
from packages.db.models.offer_lab import (
    OfferLabBundle,
    OfferLabOffer,
    OfferLabPricingTest,
    OfferLabVariant,
)
from packages.db.models.offers import Offer


@pytest_asyncio.fixture
async def brand_with_offers(db_session: AsyncSession):
    slug = f"ol-{uuid.uuid4().hex[:6]}"
    org = Organization(name="OL Org", slug=f"org-{slug}")
    db_session.add(org)
    await db_session.flush()
    brand = Brand(organization_id=org.id, name="OL Brand", slug=slug, niche="tech")
    db_session.add(brand)
    await db_session.flush()

    o1 = Offer(
        brand_id=brand.id,
        name="Premium Course",
        monetization_method="product",
        payout_amount=97,
        epc=4.0,
        conversion_rate=0.05,
    )
    o2 = Offer(
        brand_id=brand.id,
        name="Budget Tool",
        monetization_method="affiliate",
        payout_amount=19,
        epc=1.5,
        conversion_rate=0.08,
    )
    db_session.add_all([o1, o2])
    await db_session.flush()
    return brand


@pytest.mark.asyncio
async def test_recompute(db_session, brand_with_offers):
    brand = brand_with_offers
    result = await recompute_offer_lab(db_session, brand.id)
    await db_session.commit()
    assert result["status"] == "completed"
    assert result["rows_processed"] == 2


@pytest.mark.asyncio
async def test_offers_created(db_session, brand_with_offers):
    brand = brand_with_offers
    await recompute_offer_lab(db_session, brand.id)
    await db_session.commit()
    offers = (await db_session.execute(select(OfferLabOffer).where(OfferLabOffer.brand_id == brand.id))).scalars().all()
    assert len(offers) == 2
    assert all(o.rank_score > 0 for o in offers)


@pytest.mark.asyncio
async def test_variants_created(db_session, brand_with_offers):
    brand = brand_with_offers
    await recompute_offer_lab(db_session, brand.id)
    await db_session.commit()
    variants = (
        (
            await db_session.execute(
                select(OfferLabVariant).join(OfferLabOffer).where(OfferLabOffer.brand_id == brand.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(variants) == 16


@pytest.mark.asyncio
async def test_pricing_tests(db_session, brand_with_offers):
    brand = brand_with_offers
    await recompute_offer_lab(db_session, brand.id)
    await db_session.commit()
    tests = (
        (
            await db_session.execute(
                select(OfferLabPricingTest).join(OfferLabOffer).where(OfferLabOffer.brand_id == brand.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(tests) == 2


@pytest.mark.asyncio
async def test_bundles_created(db_session, brand_with_offers):
    brand = brand_with_offers
    await recompute_offer_lab(db_session, brand.id)
    await db_session.commit()
    bundles = (
        (await db_session.execute(select(OfferLabBundle).where(OfferLabBundle.brand_id == brand.id))).scalars().all()
    )
    assert len(bundles) == 1


@pytest.mark.asyncio
async def test_list_offers(db_session, brand_with_offers):
    brand = brand_with_offers
    await recompute_offer_lab(db_session, brand.id)
    await db_session.commit()
    offers = await list_offers(db_session, brand.id)
    assert len(offers) == 2
    assert offers[0].rank_score >= offers[1].rank_score


@pytest.mark.asyncio
async def test_list_variants(db_session, brand_with_offers):
    brand = brand_with_offers
    await recompute_offer_lab(db_session, brand.id)
    await db_session.commit()
    v = await list_variants(db_session, brand.id)
    assert len(v) == 16


@pytest.mark.asyncio
async def test_get_best_offer(db_session, brand_with_offers):
    brand = brand_with_offers
    await recompute_offer_lab(db_session, brand.id)
    await db_session.commit()
    best = await get_best_offer(db_session, brand.id)
    assert best["offer_id"] is not None
    assert best["truth_label"] == "recommendation_only"


@pytest.mark.asyncio
async def test_idempotent(db_session, brand_with_offers):
    brand = brand_with_offers
    r1 = await recompute_offer_lab(db_session, brand.id)
    await db_session.commit()
    r2 = await recompute_offer_lab(db_session, brand.id)
    await db_session.commit()
    assert r1["rows_processed"] == r2["rows_processed"]


def test_offer_lab_worker_registered():
    import workers.offer_lab_worker.tasks  # noqa: F401
    from workers.celery_app import app

    assert "workers.offer_lab_worker.tasks.recompute_offer_lab" in app.tasks
