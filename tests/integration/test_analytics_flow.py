"""Integration tests for Phase 4 analytics, attribution, and intelligence."""

import pytest


async def _setup_analytics(api_client, sample_org_data):
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post("/api/v1/auth/login", json={
        "email": sample_org_data["email"], "password": sample_org_data["password"],
    })
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    brand = await api_client.post("/api/v1/brands/", json={
        "name": "Analytics Brand", "slug": "analytics-brand", "niche": "finance",
    }, headers=headers)
    bid = brand.json()["id"]

    offer = await api_client.post("/api/v1/offers/", json={
        "brand_id": bid, "name": "Analytics Offer", "monetization_method": "affiliate",
        "payout_amount": 30, "epc": 2.0, "conversion_rate": 0.04,
    }, headers=headers)

    account = await api_client.post("/api/v1/accounts/", json={
        "brand_id": bid, "platform": "youtube", "platform_username": "@analytics_test",
    }, headers=headers)

    return headers, bid, account.json()["id"], offer.json()["id"]


@pytest.mark.asyncio
async def test_click_tracking(api_client, sample_org_data):
    headers, bid, acct_id, offer_id = await _setup_analytics(api_client, sample_org_data)
    response = await api_client.post("/api/v1/analytics/events/track-click", json={
        "brand_id": bid, "offer_id": offer_id, "platform": "youtube",
        "tracking_id": "utm_test_click",
    }, headers=headers)
    assert response.status_code == 200
    assert response.json()["event_type"] == "click"


@pytest.mark.asyncio
async def test_conversion_tracking(api_client, sample_org_data):
    headers, bid, acct_id, offer_id = await _setup_analytics(api_client, sample_org_data)
    response = await api_client.post("/api/v1/analytics/events/track-conversion", json={
        "brand_id": bid, "offer_id": offer_id, "event_type": "purchase",
        "event_value": 49.99, "tracking_id": "conv_test",
    }, headers=headers)
    assert response.status_code == 200
    assert response.json()["event_type"] == "purchase"
    assert response.json()["event_value"] == 49.99


@pytest.mark.asyncio
async def test_revenue_dashboard(api_client, sample_org_data):
    headers, bid, acct_id, offer_id = await _setup_analytics(api_client, sample_org_data)
    response = await api_client.get(f"/api/v1/analytics/dashboard/revenue?brand_id={bid}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "gross_revenue" in data
    assert "net_profit" in data
    assert "rpm" in data
    assert "total_impressions" in data


@pytest.mark.asyncio
async def test_content_performance_dashboard(api_client, sample_org_data):
    headers, bid, acct_id, offer_id = await _setup_analytics(api_client, sample_org_data)
    response = await api_client.get(f"/api/v1/analytics/dashboard/content-performance?brand_id={bid}", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_funnel_dashboard(api_client, sample_org_data):
    headers, bid, acct_id, offer_id = await _setup_analytics(api_client, sample_org_data)

    await api_client.post("/api/v1/analytics/events/track-click", json={
        "brand_id": bid, "platform": "youtube", "tracking_id": "funnel_click",
    })
    await api_client.post("/api/v1/analytics/events/track-conversion", json={
        "brand_id": bid, "event_type": "purchase", "event_value": 25.0,
    })

    response = await api_client.get(f"/api/v1/analytics/dashboard/funnel?brand_id={bid}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "funnel_stages" in data
    assert "click" in data["funnel_stages"]
    assert "purchase" in data["funnel_stages"]


@pytest.mark.asyncio
async def test_bottleneck_classification(api_client, sample_org_data):
    headers, bid, acct_id, offer_id = await _setup_analytics(api_client, sample_org_data)
    response = await api_client.get(f"/api/v1/analytics/dashboard/bottlenecks?brand_id={bid}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        assert "primary_bottleneck" in data[0]
        assert "severity" in data[0]
        assert "recommended_actions" in data[0]


@pytest.mark.asyncio
async def test_winner_detection(api_client, sample_org_data):
    headers, bid, acct_id, offer_id = await _setup_analytics(api_client, sample_org_data)
    response = await api_client.post(f"/api/v1/analytics/winners/detect?brand_id={bid}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_analyzed" in data
    assert "winners" in data
    assert "losers" in data
    assert "clone_jobs_created" in data


@pytest.mark.asyncio
async def test_suppression_evaluation(api_client, sample_org_data):
    headers, bid, acct_id, offer_id = await _setup_analytics(api_client, sample_org_data)
    response = await api_client.post(f"/api/v1/analytics/suppressions/evaluate?brand_id={bid}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "suppressions" in data
    assert "count" in data


@pytest.mark.asyncio
async def test_revenue_leaks(api_client, sample_org_data):
    headers, bid, acct_id, offer_id = await _setup_analytics(api_client, sample_org_data)
    response = await api_client.get(f"/api/v1/analytics/dashboard/leaks?brand_id={bid}", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
