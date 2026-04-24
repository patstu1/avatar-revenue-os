import pytest
from httpx import AsyncClient
from sqlalchemy import select

from packages.db.models.core import Brand, Organization
from packages.db.models.offers import Offer
from packages.db.enums import MonetizationMethod
from packages.db.models.expansion_pack2_phase_b import (
    PricingRecommendation,
    BundleRecommendation,
    ReactivationCampaign,
)
from tests.conftest import make_operator_user, create_access_token_for_user


@pytest.fixture
async def brand_with_offer(async_session):
    organization = Organization(name="Test Org", slug="ep2b-test")
    async_session.add(organization)
    await async_session.flush()

    brand = Brand(name="Test Brand", slug="ep2b-brand", organization_id=organization.id)
    async_session.add(brand)
    await async_session.flush()

    offer = Offer(
        brand_id=brand.id,
        name="Test Offer",
        description="A test offer",
        monetization_method=MonetizationMethod.AFFILIATE,
        payout_amount=100.0,
        is_active=True,
    )
    async_session.add(offer)
    await async_session.commit()
    return brand, offer


@pytest.fixture
async def operator_user(async_session, brand_with_offer):
    brand, _ = brand_with_offer
    user = make_operator_user(brand.organization_id)
    async_session.add(user)
    await async_session.commit()
    return user


@pytest.mark.asyncio
async def test_recompute_pricing_recommendations(client: AsyncClient, operator_user, brand_with_offer):
    brand, offer = brand_with_offer
    token = create_access_token_for_user(operator_user)
    response = await client.post(
        f"/api/v1/brands/{brand.id}/pricing-recommendations/recompute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["pricing_recommendations_count"] == 1


@pytest.mark.asyncio
async def test_list_pricing_recommendations(client: AsyncClient, operator_user, brand_with_offer):
    brand, offer = brand_with_offer
    token = create_access_token_for_user(operator_user)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/brands/{brand.id}/pricing-recommendations/recompute", headers=headers)

    response = await client.get(f"/api/v1/brands/{brand.id}/pricing-recommendations", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["offer_id"] == str(offer.id)


@pytest.mark.asyncio
async def test_recompute_bundle_recommendations(client: AsyncClient, operator_user, brand_with_offer):
    brand, offer = brand_with_offer
    token = create_access_token_for_user(operator_user)
    response = await client.post(
        f"/api/v1/brands/{brand.id}/bundle-recommendations/recompute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["bundle_recommendations_count"] == 1


@pytest.mark.asyncio
async def test_list_bundle_recommendations(client: AsyncClient, operator_user, brand_with_offer):
    brand, offer = brand_with_offer
    token = create_access_token_for_user(operator_user)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/brands/{brand.id}/bundle-recommendations/recompute", headers=headers)

    response = await client.get(f"/api/v1/brands/{brand.id}/bundle-recommendations", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["brand_id"] == str(brand.id)
    assert isinstance(data[0]["offer_ids"], list)


@pytest.mark.asyncio
async def test_list_retention_recommendations(client: AsyncClient, operator_user, brand_with_offer):
    brand, _ = brand_with_offer
    token = create_access_token_for_user(operator_user)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/brands/{brand.id}/retention-recommendations/recompute", headers=headers)

    response = await client.get(f"/api/v1/brands/{brand.id}/retention-recommendations", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["brand_id"] == str(brand.id)


@pytest.mark.asyncio
async def test_recompute_reactivation_campaigns(client: AsyncClient, operator_user, brand_with_offer):
    brand, _ = brand_with_offer
    token = create_access_token_for_user(operator_user)
    response = await client.post(
        f"/api/v1/brands/{brand.id}/reactivation-campaigns/recompute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["reactivation_campaigns_count"] == 1


@pytest.mark.asyncio
async def test_list_reactivation_campaigns(client: AsyncClient, operator_user, brand_with_offer):
    brand, _ = brand_with_offer
    token = create_access_token_for_user(operator_user)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/brands/{brand.id}/reactivation-campaigns/recompute", headers=headers)

    response = await client.get(f"/api/v1/brands/{brand.id}/reactivation-campaigns", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["brand_id"] == str(brand.id)
