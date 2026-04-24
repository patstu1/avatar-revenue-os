"""Integration tests for revenue ceiling APIs and persistence."""

import pytest


async def _auth_brand(api_client, sample_org_data):
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post("/api/v1/auth/login", json={"email": sample_org_data["email"], "password": sample_org_data["password"]})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    brand = await api_client.post("/api/v1/brands/", json={"name": "RevIntel Brand", "slug": "revintel-brand", "niche": "personal finance"}, headers=headers)
    bid = brand.json()["id"]
    await api_client.post("/api/v1/accounts/", json={"brand_id": bid, "platform": "youtube", "platform_username": "@rev_yt", "niche_focus": "finance", "posting_capacity_per_day": 2, "scale_role": "flagship"}, headers=headers)
    await api_client.post("/api/v1/offers/", json={"brand_id": bid, "name": "Affiliate Offer", "monetization_method": "affiliate", "epc": 2.5, "conversion_rate": 0.03, "payout_amount": 40.0}, headers=headers)
    await api_client.post("/api/v1/offers/", json={"brand_id": bid, "name": "Course Offer", "monetization_method": "course", "epc": 1.5, "conversion_rate": 0.02, "payout_amount": 97.0}, headers=headers)
    return headers, bid


@pytest.mark.asyncio
async def test_recompute_then_read_offer_stacks(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    rc = await api_client.post(f"/api/v1/brands/{bid}/revenue-intel/recompute", headers=headers)
    assert rc.status_code == 200
    summary = rc.json()
    assert "monetization_decisions" in summary

    r = await api_client.get(f"/api/v1/brands/{bid}/offer-stacks", headers=headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_gets_are_side_effect_free(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.get(f"/api/v1/brands/{bid}/offer-stacks", headers=headers)
    assert r.status_code == 200
    assert r.json() == []

    r2 = await api_client.get(f"/api/v1/brands/{bid}/productization", headers=headers)
    assert r2.status_code == 200
    assert r2.json() == []


@pytest.mark.asyncio
async def test_dashboard_bundled_read(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/revenue-intel/recompute", headers=headers)

    r = await api_client.get("/api/v1/dashboard/revenue-intel", params={"brand_id": bid}, headers=headers)
    assert r.status_code == 200
    d = r.json()
    assert d["brand_id"] == bid
    assert "offer_stacks" in d
    assert "funnel_paths" in d
    assert "owned_audience" in d
    assert "productization" in d
    assert "density_improvements" in d


@pytest.mark.asyncio
async def test_all_revenue_intel_endpoints(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/revenue-intel/recompute", headers=headers)

    for path in ["offer-stacks", "funnel-paths", "owned-audience-value", "productization", "monetization-density"]:
        r = await api_client.get(f"/api/v1/brands/{bid}/{path}", headers=headers)
        assert r.status_code == 200, f"Failed: {path}"
