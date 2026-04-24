"""Integration tests for brand CRUD and audit logging."""

import pytest


async def _register_and_get_headers(api_client, sample_org_data) -> dict:
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    resp = await api_client.post(
        "/api/v1/auth/login",
        json={
            "email": sample_org_data["email"],
            "password": sample_org_data["password"],
        },
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_create_brand(api_client, sample_org_data):
    headers = await _register_and_get_headers(api_client, sample_org_data)
    response = await api_client.post(
        "/api/v1/brands/",
        json={
            "name": "Test Brand",
            "slug": "test-brand",
            "niche": "finance",
            "decision_mode": "guarded_auto",
        },
        headers=headers,
    )
    assert response.status_code == 201
    brand = response.json()
    assert brand["name"] == "Test Brand"
    assert brand["niche"] == "finance"
    assert brand["decision_mode"] == "guarded_auto"


@pytest.mark.asyncio
async def test_list_brands(api_client, sample_org_data):
    headers = await _register_and_get_headers(api_client, sample_org_data)
    await api_client.post("/api/v1/brands/", json={"name": "B1", "slug": "b1"}, headers=headers)
    await api_client.post("/api/v1/brands/", json={"name": "B2", "slug": "b2"}, headers=headers)

    response = await api_client.get("/api/v1/brands/", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) >= 2


@pytest.mark.asyncio
async def test_get_brand_by_id(api_client, sample_org_data):
    headers = await _register_and_get_headers(api_client, sample_org_data)
    create_resp = await api_client.post(
        "/api/v1/brands/", json={"name": "Get Test", "slug": "get-test"}, headers=headers
    )
    brand_id = create_resp.json()["id"]

    response = await api_client.get(f"/api/v1/brands/{brand_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == brand_id


@pytest.mark.asyncio
async def test_brand_creation_creates_audit_log(api_client, sample_org_data):
    headers = await _register_and_get_headers(api_client, sample_org_data)
    await api_client.post("/api/v1/brands/", json={"name": "Audit Test", "slug": "audit-test"}, headers=headers)

    response = await api_client.get("/api/v1/jobs/audit/logs", headers=headers)
    assert response.status_code == 200
    data = response.json()
    actions = [item["action"] for item in data["items"]]
    assert "brand.created" in actions
