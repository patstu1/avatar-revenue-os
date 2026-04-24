"""DB-backed integration tests for Provider Registry APIs."""
import pytest


async def _auth_brand(api_client, sample_org_data):
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": sample_org_data["email"], "password": sample_org_data["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    brand = await api_client.post(
        "/api/v1/brands/",
        json={"name": "ProvReg Brand", "slug": "provreg-brand", "niche": "tech"},
        headers=headers,
    )
    bid = brand.json()["id"]
    return headers, bid


@pytest.mark.asyncio
async def test_providers_empty_before_audit(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.get(f"/api/v1/brands/{bid}/providers", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_audit_populates_registry(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    audit = await api_client.post(f"/api/v1/brands/{bid}/providers/audit", headers=headers)
    assert audit.status_code == 200
    r = await api_client.get(f"/api/v1/brands/{bid}/providers", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 20


@pytest.mark.asyncio
async def test_readiness_populated_after_audit(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/providers/audit", headers=headers)
    r = await api_client.get(f"/api/v1/brands/{bid}/providers/readiness", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1


@pytest.mark.asyncio
async def test_dependencies_populated_after_audit(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/providers/audit", headers=headers)
    r = await api_client.get(f"/api/v1/brands/{bid}/providers/dependencies", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1


@pytest.mark.asyncio
async def test_blockers_populated_after_audit(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/providers/audit", headers=headers)
    r = await api_client.get(f"/api/v1/brands/{bid}/providers/blockers", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1


@pytest.mark.asyncio
async def test_audit_is_idempotent(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/providers/audit", headers=headers)
    r1 = await api_client.get(f"/api/v1/brands/{bid}/providers", headers=headers)
    count1 = len(r1.json())

    await api_client.post(f"/api/v1/brands/{bid}/providers/audit", headers=headers)
    r2 = await api_client.get(f"/api/v1/brands/{bid}/providers", headers=headers)
    count2 = len(r2.json())

    assert count1 == count2


@pytest.mark.asyncio
async def test_claude_in_registry_as_primary(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/providers/audit", headers=headers)
    r = await api_client.get(f"/api/v1/brands/{bid}/providers", headers=headers)
    providers = r.json()
    claude = next((p for p in providers if p["provider_key"] == "claude"), None)
    assert claude is not None, "claude should be in the registry after audit"
    assert claude["is_primary"] is True
