"""Integration tests for the brand management flow."""
import pytest


async def get_auth_headers(api_client, sample_org_data) -> dict:
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    response = await api_client.post("/api/v1/auth/login", json={
        "email": sample_org_data["email"],
        "password": sample_org_data["password"],
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_and_list_brands(api_client, sample_org_data):
    headers = await get_auth_headers(api_client, sample_org_data)

    # Create brand
    response = await api_client.post("/api/v1/brands", json={
        "name": "Test Brand",
        "slug": "test-brand",
        "niche": "finance",
        "decision_mode": "guarded_auto",
    }, headers=headers)
    assert response.status_code == 201
    brand = response.json()
    assert brand["name"] == "Test Brand"
    assert brand["decision_mode"] == "guarded_auto"

    # List brands
    response = await api_client.get("/api/v1/brands", headers=headers)
    assert response.status_code == 200
    brands = response.json()
    assert len(brands) >= 1
    assert any(b["slug"] == "test-brand" for b in brands)

    # Get brand by ID
    response = await api_client.get(f"/api/v1/brands/{brand['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == brand["id"]


@pytest.mark.asyncio
async def test_create_avatar_for_brand(api_client, sample_org_data):
    headers = await get_auth_headers(api_client, sample_org_data)

    brand_resp = await api_client.post("/api/v1/brands", json={
        "name": "Avatar Test Brand",
        "slug": "avatar-test-brand",
    }, headers=headers)
    brand_id = brand_resp.json()["id"]

    response = await api_client.post("/api/v1/avatars", json={
        "brand_id": brand_id,
        "name": "Test Avatar",
        "persona_description": "A friendly finance educator",
        "voice_style": "warm and authoritative",
    }, headers=headers)
    assert response.status_code == 201
    avatar = response.json()
    assert avatar["name"] == "Test Avatar"
    assert avatar["brand_id"] == brand_id


@pytest.mark.asyncio
async def test_create_offer_for_brand(api_client, sample_org_data):
    headers = await get_auth_headers(api_client, sample_org_data)

    brand_resp = await api_client.post("/api/v1/brands", json={
        "name": "Offer Test Brand",
        "slug": "offer-test-brand",
    }, headers=headers)
    brand_id = brand_resp.json()["id"]

    response = await api_client.post("/api/v1/offers", json={
        "brand_id": brand_id,
        "name": "Test Affiliate Offer",
        "monetization_method": "affiliate",
        "payout_amount": 25.0,
        "epc": 1.50,
        "conversion_rate": 0.03,
    }, headers=headers)
    assert response.status_code == 201
    offer = response.json()
    assert offer["name"] == "Test Affiliate Offer"
    assert offer["payout_amount"] == 25.0
