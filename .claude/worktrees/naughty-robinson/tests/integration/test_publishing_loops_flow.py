"""DB-backed integration tests for publishing loop + measured-data loop."""
import pytest


async def _auth_brand_with_content(api_client, sample_org_data):
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post("/api/v1/auth/login", json={"email": sample_org_data["email"], "password": sample_org_data["password"]})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    brand = await api_client.post("/api/v1/brands/", json={"name": "PubLoop Brand", "slug": "publoop-brand", "niche": "tech"}, headers=headers)
    bid = brand.json()["id"]
    await api_client.post("/api/v1/accounts/", json={
        "brand_id": bid, "platform": "youtube", "platform_username": "@pub_yt",
        "niche_focus": "tech", "posting_capacity_per_day": 2, "scale_role": "flagship",
    }, headers=headers)
    await api_client.post("/api/v1/offers/", json={
        "brand_id": bid, "name": "Test Offer", "monetization_method": "affiliate",
        "epc": 2.0, "conversion_rate": 0.03, "payout_amount": 40.0,
    }, headers=headers)
    return headers, bid


@pytest.mark.asyncio
async def test_expansion_advisor_creates_alert(api_client, sample_org_data):
    headers, bid = await _auth_brand_with_content(api_client, sample_org_data)
    r = await api_client.post(f"/api/v1/brands/{bid}/expansion-advisor/recompute", headers=headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_content_routing_persists_decision(api_client, sample_org_data):
    headers, bid = await _auth_brand_with_content(api_client, sample_org_data)
    r = await api_client.post(f"/api/v1/brands/{bid}/content-routing/route", json={
        "task_description": "Product review for YouTube", "platform": "youtube", "content_type": "text",
    }, headers=headers)
    assert r.status_code == 200
    assert r.json()["routed_provider"] in ("claude", "gemini_flash", "deepseek")

    decisions = await api_client.get(f"/api/v1/brands/{bid}/content-routing/decisions", headers=headers)
    assert len(decisions.json()) >= 1


@pytest.mark.asyncio
async def test_gatekeeper_creates_operator_alerts(api_client, sample_org_data):
    headers, bid = await _auth_brand_with_content(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/gatekeeper/completion/recompute", headers=headers)
    await api_client.post(f"/api/v1/brands/{bid}/gatekeeper/truth/recompute", headers=headers)


def test_auto_publish_task_exists():
    from workers.publishing_worker.auto_publish import auto_publish_approved_content
    from workers.celery_app import app
    assert "workers.publishing_worker.tasks.auto_publish_approved_content" in app.tasks


def test_measured_data_cascade_task_exists():
    from workers.publishing_worker.measured_data_cascade import run_measured_data_cascade
    from workers.celery_app import app
    assert "workers.publishing_worker.tasks.run_measured_data_cascade" in app.tasks


def test_brain_decision_executor_task_exists():
    from workers.action_executor_worker.tasks import execute_brain_decisions
    from workers.celery_app import app
    assert "workers.action_executor_worker.tasks.execute_brain_decisions" in app.tasks
