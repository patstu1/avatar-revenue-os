"""Integration tests for Phase 7 APIs and persistence."""

import pytest


async def _auth_brand(api_client, sample_org_data):
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post("/api/v1/auth/login", json={"email": sample_org_data["email"], "password": sample_org_data["password"]})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    brand = await api_client.post("/api/v1/brands/", json={"name": "P7 Brand", "slug": "p7-brand", "niche": "personal finance"}, headers=headers)
    bid = brand.json()["id"]
    await api_client.post("/api/v1/accounts/", json={"brand_id": bid, "platform": "youtube", "platform_username": "@p7yt", "niche_focus": "finance", "posting_capacity_per_day": 2, "scale_role": "flagship"}, headers=headers)
    await api_client.post("/api/v1/offers/", json={"brand_id": bid, "name": "P7 Offer", "monetization_method": "affiliate", "epc": 2.5, "conversion_rate": 0.03}, headers=headers)
    return headers, bid


@pytest.mark.asyncio
async def test_recompute_then_read_roadmap(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    rc = await api_client.post(f"/api/v1/brands/{bid}/phase7/recompute", headers=headers)
    assert rc.status_code == 200
    summary = rc.json()
    assert summary["roadmap_items"] >= 1
    assert summary["capital_allocations"] >= 7

    r = await api_client.get(f"/api/v1/brands/{bid}/roadmap", headers=headers)
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 1


@pytest.mark.asyncio
async def test_gets_are_side_effect_free(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.get(f"/api/v1/brands/{bid}/roadmap", headers=headers)
    assert r.status_code == 200
    assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_capital_allocation_and_cockpit(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/phase7/recompute", headers=headers)

    r = await api_client.get(f"/api/v1/brands/{bid}/capital-allocation", headers=headers)
    assert r.status_code == 200
    assert len(r.json()["allocations"]) >= 7

    r2 = await api_client.get(f"/api/v1/brands/{bid}/operator-cockpit", headers=headers)
    assert r2.status_code == 200
    d = r2.json()
    assert d["brand_id"] == bid
    assert "top_roadmap_items" in d
    assert "capital_allocation" in d
    assert "scale_action" in d
    assert "growth_blockers" in d


@pytest.mark.asyncio
async def test_sponsor_and_knowledge_graph(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/phase7/recompute", headers=headers)

    r = await api_client.get(f"/api/v1/brands/{bid}/sponsor-opportunities", headers=headers)
    assert r.status_code == 200
    assert "packages" in r.json()

    r2 = await api_client.get(f"/api/v1/brands/{bid}/knowledge-graph", headers=headers)
    assert r2.status_code == 200
    assert len(r2.json()["nodes"]) >= 1
