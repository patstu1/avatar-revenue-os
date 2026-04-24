"""Integration tests for offer CRUD and creator account CRUD."""

import pytest


async def _setup(api_client, sample_org_data) -> tuple[dict, str]:
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post(
        "/api/v1/auth/login",
        json={
            "email": sample_org_data["email"],
            "password": sample_org_data["password"],
        },
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    brand = await api_client.post(
        "/api/v1/brands/",
        json={
            "name": "OA Test Brand",
            "slug": "oa-test",
        },
        headers=headers,
    )
    return headers, brand.json()["id"]


@pytest.mark.asyncio
async def test_create_offer(api_client, sample_org_data):
    headers, brand_id = await _setup(api_client, sample_org_data)
    response = await api_client.post(
        "/api/v1/offers/",
        json={
            "brand_id": brand_id,
            "name": "Test Affiliate",
            "monetization_method": "affiliate",
            "payout_amount": 25.0,
            "epc": 1.50,
            "conversion_rate": 0.03,
        },
        headers=headers,
    )
    assert response.status_code == 201
    offer = response.json()
    assert offer["name"] == "Test Affiliate"
    assert offer["payout_amount"] == 25.0


@pytest.mark.asyncio
async def test_list_offers(api_client, sample_org_data):
    headers, brand_id = await _setup(api_client, sample_org_data)
    await api_client.post(
        "/api/v1/offers/",
        json={
            "brand_id": brand_id,
            "name": "Offer 1",
            "monetization_method": "affiliate",
        },
        headers=headers,
    )
    await api_client.post(
        "/api/v1/offers/",
        json={
            "brand_id": brand_id,
            "name": "Offer 2",
            "monetization_method": "product",
        },
        headers=headers,
    )

    response = await api_client.get(f"/api/v1/offers/?brand_id={brand_id}", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) >= 2


@pytest.mark.asyncio
async def test_delete_offer(api_client, sample_org_data):
    headers, brand_id = await _setup(api_client, sample_org_data)
    create = await api_client.post(
        "/api/v1/offers/",
        json={
            "brand_id": brand_id,
            "name": "To Delete",
            "monetization_method": "affiliate",
        },
        headers=headers,
    )
    offer_id = create.json()["id"]

    response = await api_client.delete(f"/api/v1/offers/{offer_id}", headers=headers)
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_create_creator_account(api_client, sample_org_data):
    headers, brand_id = await _setup(api_client, sample_org_data)
    response = await api_client.post(
        "/api/v1/accounts/",
        json={
            "brand_id": brand_id,
            "platform": "youtube",
            "platform_username": "@testchannel",
            "niche_focus": "finance",
            "posting_capacity_per_day": 2,
        },
        headers=headers,
    )
    assert response.status_code == 201
    account = response.json()
    assert account["platform"] == "youtube"
    assert account["platform_username"] == "@testchannel"
    assert account["account_health"] == "healthy"
    assert account["total_revenue"] == 0.0


@pytest.mark.asyncio
async def test_list_creator_accounts(api_client, sample_org_data):
    headers, brand_id = await _setup(api_client, sample_org_data)
    await api_client.post(
        "/api/v1/accounts/",
        json={
            "brand_id": brand_id,
            "platform": "youtube",
            "platform_username": "@ch1",
        },
        headers=headers,
    )
    await api_client.post(
        "/api/v1/accounts/",
        json={
            "brand_id": brand_id,
            "platform": "tiktok",
            "platform_username": "@ch2",
        },
        headers=headers,
    )

    response = await api_client.get(f"/api/v1/accounts/?brand_id={brand_id}", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) >= 2


@pytest.mark.asyncio
async def test_delete_creator_account(api_client, sample_org_data):
    headers, brand_id = await _setup(api_client, sample_org_data)
    create = await api_client.post(
        "/api/v1/accounts/",
        json={
            "brand_id": brand_id,
            "platform": "instagram",
            "platform_username": "@del",
        },
        headers=headers,
    )
    account_id = create.json()["id"]

    response = await api_client.delete(f"/api/v1/accounts/{account_id}", headers=headers)
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_offer_creation_creates_audit_log(api_client, sample_org_data):
    headers, brand_id = await _setup(api_client, sample_org_data)
    await api_client.post(
        "/api/v1/offers/",
        json={
            "brand_id": brand_id,
            "name": "Audit Offer",
            "monetization_method": "affiliate",
        },
        headers=headers,
    )

    audit = await api_client.get("/api/v1/jobs/audit/logs", headers=headers)
    actions = [e["action"] for e in audit.json()["items"]]
    assert "offer.created" in actions


@pytest.mark.asyncio
async def test_account_creation_creates_audit_log(api_client, sample_org_data):
    headers, brand_id = await _setup(api_client, sample_org_data)
    await api_client.post(
        "/api/v1/accounts/",
        json={
            "brand_id": brand_id,
            "platform": "youtube",
            "platform_username": "@auditchan",
        },
        headers=headers,
    )

    audit = await api_client.get("/api/v1/jobs/audit/logs", headers=headers)
    actions = [e["action"] for e in audit.json()["items"]]
    assert "creator_account.created" in actions
