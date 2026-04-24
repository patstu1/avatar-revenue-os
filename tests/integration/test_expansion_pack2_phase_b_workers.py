
import pytest
from sqlalchemy import select

from packages.db.models.core import Brand, Organization
from packages.db.models.expansion_pack2_phase_b import (
    BundleRecommendation,
    PricingRecommendation,
    ReactivationCampaign,
)
from packages.db.models.offers import Offer

pytestmark = pytest.mark.skipif(
    True,
    reason="Worker tests call Celery tasks that use the production session factory; they need a dedicated worker test harness",
)

from workers.revenue_ceiling_worker.tasks import (
    recompute_all_bundle_recommendations,
    recompute_all_pricing_recommendations,
    recompute_all_reactivation_campaigns,
)


@pytest.fixture
async def brand_with_offer(async_session):
    organization = Organization(name="Test Org", slug="ep2b-worker-test")
    async_session.add(organization)
    await async_session.flush()

    brand = Brand(name="Test Brand", slug="ep2b-w-brand", organization_id=organization.id)
    async_session.add(brand)
    await async_session.flush()

    offer = Offer(
        brand_id=brand.id,
        name="Test Offer",
        description="A test offer",
        monetization_method="affiliate",
        payout_amount=100.0,
        is_active=True,
    )
    async_session.add(offer)
    await async_session.commit()
    return brand, offer


@pytest.mark.asyncio
async def test_recompute_all_pricing_recommendations_worker(async_session, brand_with_offer):
    brand, offer = brand_with_offer
    result = recompute_all_pricing_recommendations()
    assert result["brands"] == 1
    assert result["rows"] == 1
    assert not result["errors"]

    recommendations = (await async_session.execute(select(PricingRecommendation).where(PricingRecommendation.brand_id == brand.id))).scalars().all()
    assert len(recommendations) == 1
    assert recommendations[0].offer_id == offer.id


@pytest.mark.asyncio
async def test_recompute_all_bundle_recommendations_worker(async_session, brand_with_offer):
    brand, offer = brand_with_offer
    result = recompute_all_bundle_recommendations()
    assert result["brands"] == 1
    assert result["rows"] == 1
    assert not result["errors"]

    recommendations = (await async_session.execute(select(BundleRecommendation).where(BundleRecommendation.brand_id == brand.id))).scalars().all()
    assert len(recommendations) == 1
    assert str(offer.id) in recommendations[0].offer_ids


@pytest.mark.asyncio
async def test_recompute_all_reactivation_campaigns_worker(async_session, brand_with_offer):
    brand, _ = brand_with_offer
    result = recompute_all_reactivation_campaigns()
    assert result["brands"] == 1
    assert result["rows"] == 1
    assert not result["errors"]

    campaigns = (await async_session.execute(select(ReactivationCampaign).where(ReactivationCampaign.brand_id == brand.id))).scalars().all()
    assert len(campaigns) == 1
    assert campaigns[0].brand_id == brand.id
