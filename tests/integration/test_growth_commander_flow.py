"""Integration tests for Growth Commander APIs."""

import pytest


async def _auth_brand(api_client, sample_org_data):
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post(
        "/api/v1/auth/login", json={"email": sample_org_data["email"], "password": sample_org_data["password"]}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    brand = await api_client.post(
        "/api/v1/brands/", json={"name": "GC Brand", "slug": "gc-brand", "niche": "finance"}, headers=headers
    )
    bid = brand.json()["id"]
    await api_client.post(
        "/api/v1/accounts/",
        json={
            "brand_id": bid,
            "platform": "youtube",
            "platform_username": "@gc_yt",
            "niche_focus": "finance",
            "posting_capacity_per_day": 2,
            "scale_role": "flagship",
        },
        headers=headers,
    )
    await api_client.post(
        "/api/v1/offers/",
        json={
            "brand_id": bid,
            "name": "GC Offer",
            "monetization_method": "affiliate",
            "epc": 2.5,
            "conversion_rate": 0.03,
        },
        headers=headers,
    )
    return headers, bid


@pytest.mark.asyncio
async def test_recompute_then_read(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    rc = await api_client.post(f"/api/v1/brands/{bid}/growth-commands/recompute", headers=headers)
    assert rc.status_code == 200
    body = rc.json()
    assert body["commands_generated"] >= 1
    assert "last_run_id" in body
    r = await api_client.get(f"/api/v1/brands/{bid}/growth-commands", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    runs = await api_client.get(f"/api/v1/brands/{bid}/growth-command-runs", headers=headers)
    assert runs.status_code == 200
    assert len(runs.json()) >= 1
    assert runs.json()[0]["id"] == body["last_run_id"]


@pytest.mark.asyncio
async def test_gets_side_effect_free(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.get(f"/api/v1/brands/{bid}/growth-commands", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_portfolio_assessment(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/growth-commands/recompute", headers=headers)
    r = await api_client.get(f"/api/v1/brands/{bid}/portfolio-assessment", headers=headers)
    assert r.status_code == 200
    d = r.json()
    assert "balance" in d
    assert "whitespace" in d
    assert "latest_portfolio_directive" in d
    assert d["latest_portfolio_directive"] is not None
    assert "recommended_account_count" in d["latest_portfolio_directive"]
