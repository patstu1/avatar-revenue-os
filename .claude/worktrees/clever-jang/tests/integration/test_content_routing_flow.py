"""DB-backed integration tests for Content Routing."""
import pytest


async def _auth_brand(api_client, sample_org_data):
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post("/api/v1/auth/login", json={"email": sample_org_data["email"], "password": sample_org_data["password"]})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    brand = await api_client.post("/api/v1/brands/", json={"name": "Routing Brand", "slug": "routing-brand", "niche": "tech"}, headers=headers)
    bid = brand.json()["id"]
    return headers, bid


@pytest.mark.asyncio
async def test_decisions_empty_before_routing(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.get(f"/api/v1/brands/{bid}/content-routing/decisions", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_route_task_returns_provider(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.post(f"/api/v1/brands/{bid}/content-routing/route", json={
        "task_description": "Write a product review", "platform": "instagram", "content_type": "text",
    }, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["routed_provider"] in ("claude", "gemini_flash", "deepseek")
    assert body["quality_tier"] in ("hero", "standard", "bulk")


@pytest.mark.asyncio
async def test_decision_persisted_after_route(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/content-routing/route", json={
        "task_description": "Generate thumbnail", "platform": "youtube", "content_type": "image",
    }, headers=headers)
    r = await api_client.get(f"/api/v1/brands/{bid}/content-routing/decisions", headers=headers)
    assert len(r.json()) >= 1


@pytest.mark.asyncio
async def test_cost_report_recompute(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/content-routing/route", json={
        "task_description": "test", "platform": "x", "content_type": "text",
    }, headers=headers)
    r = await api_client.post(f"/api/v1/brands/{bid}/content-routing/cost-reports/recompute", headers=headers)
    assert r.status_code == 200
    reports = await api_client.get(f"/api/v1/brands/{bid}/content-routing/cost-reports", headers=headers)
    assert len(reports.json()) >= 1


@pytest.mark.asyncio
async def test_monthly_projection(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.get(f"/api/v1/brands/{bid}/content-routing/monthly-projection", headers=headers)
    assert r.status_code == 200
    assert r.json()["total_estimated_usd"] > 0


@pytest.mark.asyncio
async def test_promoted_routes_to_hero(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.post(f"/api/v1/brands/{bid}/content-routing/route", json={
        "task_description": "Ad creative for paid campaign", "platform": "instagram",
        "content_type": "text", "is_promoted": True,
    }, headers=headers)
    assert r.json()["quality_tier"] == "hero"
    assert r.json()["routed_provider"] == "claude"


def test_celery_task_registered():
    import workers.content_routing_worker.tasks
    from workers.celery_app import app
    assert "workers.content_routing_worker.tasks.daily_cost_rollup" in app.tasks
