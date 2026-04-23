"""DB-backed integration tests for Affiliate Intelligence."""
from __future__ import annotations
import uuid
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from packages.db.models.core import Brand, Organization
from packages.db.models.affiliate_intel import AffiliateOffer, AffiliateLink, AffiliateLeak, AffiliateBlocker, AffiliateClickEvent, AffiliateConversionEvent
from apps.api.services.affiliate_intel_service import recompute_ranking, list_offers, list_links, list_leaks, list_blockers, get_best_offer_for_content


@pytest_asyncio.fixture
async def brand_with_affiliate(db_session: AsyncSession):
    slug = f"af-{uuid.uuid4().hex[:6]}"
    org = Organization(name="AF Org", slug=f"org-{slug}")
    db_session.add(org); await db_session.flush()
    brand = Brand(organization_id=org.id, name="AF Brand", slug=slug, niche="tech")
    db_session.add(brand); await db_session.flush()

    good = AffiliateOffer(brand_id=brand.id, product_name="Good Product", epc=3.5, conversion_rate=0.06, commission_rate=25, trust_score=0.8, affiliate_url="https://aff.com/good?ref=123")
    weak = AffiliateOffer(brand_id=brand.id, product_name="Weak Product", epc=0.2, conversion_rate=0.005, commission_rate=3, trust_score=0.3, refund_rate=0.20)
    no_url = AffiliateOffer(brand_id=brand.id, product_name="No URL Product", epc=1.0, commission_rate=10)
    db_session.add_all([good, weak, no_url]); await db_session.flush()

    link = AffiliateLink(brand_id=brand.id, offer_id=good.id, full_url="https://aff.com/good?ref=123", click_count=80, conversion_count=0)
    db_session.add(link); await db_session.flush()

    return brand, good, weak, no_url, link


@pytest.mark.asyncio
async def test_recompute_ranking(db_session, brand_with_affiliate):
    brand, good, weak, no_url, link = brand_with_affiliate
    result = await recompute_ranking(db_session, brand.id)
    await db_session.commit()
    assert result["status"] == "completed"
    assert result["rows_processed"] == 3

    offers = (await db_session.execute(select(AffiliateOffer).where(AffiliateOffer.brand_id == brand.id).order_by(AffiliateOffer.rank_score.desc()))).scalars().all()
    assert offers[0].product_name == "Good Product"
    assert offers[0].rank_score > offers[1].rank_score


@pytest.mark.asyncio
async def test_blockers_detected(db_session, brand_with_affiliate):
    brand, _, _, _, _ = brand_with_affiliate
    await recompute_ranking(db_session, brand.id); await db_session.commit()
    blockers = (await db_session.execute(select(AffiliateBlocker).where(AffiliateBlocker.brand_id == brand.id))).scalars().all()
    assert len(blockers) >= 1
    types = {b.blocker_type for b in blockers}
    assert "no_destination_url" in types


@pytest.mark.asyncio
async def test_leaks_detected(db_session, brand_with_affiliate):
    brand, _, _, _, _ = brand_with_affiliate
    await recompute_ranking(db_session, brand.id); await db_session.commit()
    leaks = (await db_session.execute(select(AffiliateLeak).where(AffiliateLeak.brand_id == brand.id))).scalars().all()
    assert len(leaks) >= 1
    types = {l.leak_type for l in leaks}
    assert "high_clicks_zero_conversions" in types or "high_refund_rate" in types


@pytest.mark.asyncio
async def test_best_offer(db_session, brand_with_affiliate):
    brand, _, _, _, _ = brand_with_affiliate
    await recompute_ranking(db_session, brand.id); await db_session.commit()
    best = await get_best_offer_for_content(db_session, brand.id)
    assert best["offer_id"] is not None
    assert best["product_name"] == "Good Product"


@pytest.mark.asyncio
async def test_list_offers(db_session, brand_with_affiliate):
    brand, _, _, _, _ = brand_with_affiliate
    await recompute_ranking(db_session, brand.id); await db_session.commit()
    offers = await list_offers(db_session, brand.id)
    assert len(offers) == 3


@pytest.mark.asyncio
async def test_list_links(db_session, brand_with_affiliate):
    brand, _, _, _, _ = brand_with_affiliate
    links = await list_links(db_session, brand.id)
    assert len(links) == 1


@pytest.mark.asyncio
async def test_list_leaks(db_session, brand_with_affiliate):
    brand, _, _, _, _ = brand_with_affiliate
    await recompute_ranking(db_session, brand.id); await db_session.commit()
    leaks = await list_leaks(db_session, brand.id)
    assert isinstance(leaks, list)


@pytest.mark.asyncio
async def test_list_blockers(db_session, brand_with_affiliate):
    brand, _, _, _, _ = brand_with_affiliate
    await recompute_ranking(db_session, brand.id); await db_session.commit()
    blockers = await list_blockers(db_session, brand.id)
    assert len(blockers) >= 1


@pytest.mark.asyncio
async def test_idempotent(db_session, brand_with_affiliate):
    brand, _, _, _, _ = brand_with_affiliate
    r1 = await recompute_ranking(db_session, brand.id); await db_session.commit()
    r2 = await recompute_ranking(db_session, brand.id); await db_session.commit()
    assert r1["rows_processed"] == r2["rows_processed"]


def test_affiliate_worker_registered():
    from workers.celery_app import app
    import workers.affiliate_intel_worker.tasks  # noqa: F401
    assert "workers.affiliate_intel_worker.tasks.recompute_affiliate_intel" in app.tasks
