"""DB-backed integration tests for Content Form Selection."""
import pytest

import workers.content_form_worker.tasks  # noqa: F401 — register @app.task names under pytest
from workers.celery_app import app


async def _auth_brand(api_client, sample_org_data):
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": sample_org_data["email"], "password": sample_org_data["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    brand = await api_client.post(
        "/api/v1/brands/",
        json={"name": "CF Brand", "slug": "cf-brand", "niche": "fitness"},
        headers=headers,
    )
    bid = brand.json()["id"]
    await api_client.post(
        "/api/v1/accounts/",
        json={
            "brand_id": bid,
            "platform": "youtube",
            "platform_username": "@cf_yt",
            "niche_focus": "fitness",
            "posting_capacity_per_day": 2,
            "scale_role": "flagship",
        },
        headers=headers,
    )
    await api_client.post(
        "/api/v1/offers/",
        json={
            "brand_id": bid,
            "name": "CF Offer",
            "monetization_method": "affiliate",
            "epc": 2.0,
            "conversion_rate": 0.03,
        },
        headers=headers,
    )
    return headers, bid


@pytest.mark.asyncio
async def test_empty_before_recompute(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.get(f"/api/v1/brands/{bid}/content-forms", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_recompute_recommendations(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.post(f"/api/v1/brands/{bid}/content-forms/recompute", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["rows_processed"] > 0
    assert body.get("status") == "completed"


@pytest.mark.asyncio
async def test_get_recommendations_after_recompute(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/content-forms/recompute", headers=headers)
    r = await api_client.get(f"/api/v1/brands/{bid}/content-forms", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_recommendation_has_fields(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/content-forms/recompute", headers=headers)
    data = (await api_client.get(f"/api/v1/brands/{bid}/content-forms", headers=headers)).json()
    for entry in data:
        assert "recommended_content_form" in entry
        assert "avatar_mode" in entry
        assert "confidence" in entry


@pytest.mark.asyncio
async def test_mix_recompute_and_get(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/content-forms/recompute", headers=headers)
    pr = await api_client.post(f"/api/v1/brands/{bid}/content-form-mix/recompute", headers=headers)
    assert pr.status_code == 200
    assert pr.json()["rows_processed"] > 0
    gr = await api_client.get(f"/api/v1/brands/{bid}/content-form-mix", headers=headers)
    assert gr.status_code == 200
    assert len(gr.json()) >= 1


@pytest.mark.asyncio
async def test_blockers_get(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/content-forms/recompute", headers=headers)
    r = await api_client.get(f"/api/v1/brands/{bid}/content-form-blockers", headers=headers)
    assert r.status_code == 200
    blockers = r.json()
    assert isinstance(blockers, list)
    assert len(blockers) >= 1


@pytest.mark.asyncio
async def test_recompute_idempotent(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/content-forms/recompute", headers=headers)
    count1 = len((await api_client.get(f"/api/v1/brands/{bid}/content-forms", headers=headers)).json())
    await api_client.post(f"/api/v1/brands/{bid}/content-forms/recompute", headers=headers)
    count2 = len((await api_client.get(f"/api/v1/brands/{bid}/content-forms", headers=headers)).json())
    assert count1 == count2


def test_celery_tasks_registered():
    expected = {
        "workers.content_form_worker.tasks.recompute_content_forms",
        "workers.content_form_worker.tasks.recompute_content_form_mix",
        "workers.content_form_worker.tasks.recompute_content_form_blockers",
    }
    for name in expected:
        assert name in app.tasks, f"Missing Celery task: {name}"
