"""Integration tests for Phase 5 scale APIs and persistence."""
import pytest


async def _headers_brand_two_accounts(api_client, sample_org_data):
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": sample_org_data["email"], "password": sample_org_data["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    brand = await api_client.post(
        "/api/v1/brands/",
        json={"name": "Scale Brand", "slug": "scale-brand", "niche": "personal finance tips"},
        headers=headers,
    )
    bid = brand.json()["id"]

    for i, uname, plat in [
        (0, "@scale_flagship", "youtube"),
        (1, "@scale_exp", "tiktok"),
    ]:
        await api_client.post(
            "/api/v1/accounts/",
            json={
                "brand_id": bid,
                "platform": plat,
                "platform_username": uname,
                "niche_focus": "personal finance",
                "posting_capacity_per_day": 2 + i,
                "scale_role": "flagship" if i == 0 else "experimental",
            },
            headers=headers,
        )

    for i in range(2):
        await api_client.post(
            "/api/v1/offers/",
            json={
                "brand_id": bid,
                "name": f"Offer {i}",
                "monetization_method": "affiliate",
                "epc": 2.0 + i * 0.1,
                "conversion_rate": 0.03 + i * 0.005,
            },
            headers=headers,
        )

    return headers, bid


@pytest.mark.asyncio
async def test_scale_recommendations_recompute_persists(api_client, sample_org_data):
    headers, bid = await _headers_brand_two_accounts(api_client, sample_org_data)
    r = await api_client.post(f"/api/v1/brands/{bid}/scale-recommendations/recompute", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "recommendation_key" in data[0]
    assert "scale_readiness_score" in data[0]
    assert "incremental_profit_new_account" in data[0]
    assert "incremental_profit_existing_push" in data[0]
    assert "comparison_ratio" in data[0]
    assert isinstance(data[0].get("score_components"), dict)


@pytest.mark.asyncio
async def test_scale_recommendations_list(api_client, sample_org_data):
    headers, bid = await _headers_brand_two_accounts(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/scale-recommendations/recompute", headers=headers)
    r = await api_client.get(f"/api/v1/brands/{bid}/scale-recommendations", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1


@pytest.mark.asyncio
async def test_portfolio_allocations_recompute(api_client, sample_org_data):
    headers, bid = await _headers_brand_two_accounts(api_client, sample_org_data)
    r = await api_client.post(f"/api/v1/brands/{bid}/portfolio-allocations/recompute", headers=headers)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2
    pct_sum = sum(float(x["allocation_pct"]) for x in rows)
    assert 99.0 <= pct_sum <= 101.0


@pytest.mark.asyncio
async def test_scale_command_center_dashboard(api_client, sample_org_data):
    headers, bid = await _headers_brand_two_accounts(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/scale-recommendations/recompute", headers=headers)
    await api_client.post(f"/api/v1/brands/{bid}/portfolio-allocations/recompute", headers=headers)

    r = await api_client.get(
        "/api/v1/dashboard/scale-command-center",
        params={"brand_id": bid},
        headers=headers,
    )
    assert r.status_code == 200
    d = r.json()
    assert str(d["brand_id"]) == str(bid)
    assert "portfolio_overview" in d
    assert "totals" in d["portfolio_overview"]
    assert "incremental_tradeoff" in d
    assert d["incremental_tradeoff"].get("interpretation")
    assert "audit" in d
    assert d["audit"].get("formula_constants", {}).get("expansion_beats_existing_ratio") == pytest.approx(1.15)
    assert "ai_recommendations" in d
    assert "weekly_action_plan" in d
    assert "growth_blockers" in d
    assert "revenue_leak_alerts" in d
    assert "platform_allocation" in d
    assert "niche_expansion" in d
    primary = next(
        (r for r in d["ai_recommendations"] if r.get("recommendation_key") != "reduce_or_suppress_weak_account"),
        d["ai_recommendations"][0] if d["ai_recommendations"] else None,
    )
    assert primary is not None
    assert primary.get("recommendation_key") != "reduce_or_suppress_weak_account"
