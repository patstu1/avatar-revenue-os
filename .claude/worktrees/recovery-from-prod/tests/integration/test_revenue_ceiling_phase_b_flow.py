"""Integration tests for Revenue Ceiling Phase B APIs."""

import uuid

import pytest

from packages.db.enums import ContentType
from packages.db.models.content import ContentItem


async def _auth_brand_two_offers(api_client, sample_org_data):
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": sample_org_data["email"], "password": sample_org_data["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    brand = await api_client.post(
        "/api/v1/brands/",
        json={"name": "RC B Brand", "slug": "rc-b-brand", "niche": "fitness coaching"},
        headers=headers,
    )
    bid = brand.json()["id"]
    await api_client.post(
        "/api/v1/offers/",
        json={
            "brand_id": bid,
            "name": "Starter Affiliate",
            "monetization_method": "affiliate",
            "epc": 1.5,
            "conversion_rate": 0.02,
            "payout_amount": 30.0,
        },
        headers=headers,
    )
    await api_client.post(
        "/api/v1/offers/",
        json={
            "brand_id": bid,
            "name": "VIP Coaching Program",
            "monetization_method": "course",
            "epc": 4.0,
            "conversion_rate": 0.015,
            "payout_amount": 500.0,
            "average_order_value": 2000.0,
        },
        headers=headers,
    )
    return headers, bid


@pytest.mark.asyncio
async def test_phase_b_gets_empty_before_recompute(api_client, sample_org_data):
    headers, bid = await _auth_brand_two_offers(api_client, sample_org_data)
    for path in [
        f"/api/v1/brands/{bid}/high-ticket-opportunities",
        f"/api/v1/brands/{bid}/product-opportunities",
        f"/api/v1/brands/{bid}/revenue-density",
        f"/api/v1/brands/{bid}/upsell-recommendations",
    ]:
        r = await api_client.get(path, headers=headers)
        assert r.status_code == 200, path
        assert r.json() == [], path


@pytest.mark.asyncio
async def test_phase_b_recompute_and_get(api_client, sample_org_data):
    headers, bid = await _auth_brand_two_offers(api_client, sample_org_data)

    r1 = await api_client.post(f"/api/v1/brands/{bid}/high-ticket-opportunities/recompute", headers=headers)
    assert r1.status_code == 200
    ht = await api_client.get(f"/api/v1/brands/{bid}/high-ticket-opportunities", headers=headers)
    assert ht.status_code == 200
    assert len(ht.json()) >= 1
    assert "eligibility_score" in ht.json()[0]

    r2 = await api_client.post(f"/api/v1/brands/{bid}/product-opportunities/recompute", headers=headers)
    assert r2.status_code == 200
    po = await api_client.get(f"/api/v1/brands/{bid}/product-opportunities", headers=headers)
    assert po.status_code == 200
    assert len(po.json()) >= 1

    r3 = await api_client.post(f"/api/v1/brands/{bid}/revenue-density/recompute", headers=headers)
    assert r3.status_code == 200
    assert r3.json().get("revenue_density_rows", -1) == 0

    r4 = await api_client.post(f"/api/v1/brands/{bid}/upsell-recommendations/recompute", headers=headers)
    assert r4.status_code == 200
    up = await api_client.get(f"/api/v1/brands/{bid}/upsell-recommendations", headers=headers)
    assert up.status_code == 200
    assert len(up.json()) >= 1


def test_phase_b_celery_tasks_registered():
    import workers.revenue_ceiling_worker.tasks  # noqa: F401

    from workers.celery_app import app

    for name in (
        "workers.revenue_ceiling_worker.tasks.recompute_all_high_ticket",
        "workers.revenue_ceiling_worker.tasks.recompute_all_product_opportunities",
        "workers.revenue_ceiling_worker.tasks.recompute_all_revenue_density",
        "workers.revenue_ceiling_worker.tasks.refresh_all_upsell_recommendations",
    ):
        assert name in app.tasks


@pytest.mark.asyncio
async def test_phase_b_revenue_density_includes_content_title(api_client, db_session, sample_org_data):
    headers, bid = await _auth_brand_two_offers(api_client, sample_org_data)
    bid_uuid = uuid.UUID(bid)
    ci = ContentItem(
        brand_id=bid_uuid,
        title="Density Test Clip",
        content_type=ContentType.SHORT_VIDEO,
    )
    db_session.add(ci)
    await db_session.commit()

    rc = await api_client.post(f"/api/v1/brands/{bid}/revenue-density/recompute", headers=headers)
    assert rc.status_code == 200
    assert rc.json().get("revenue_density_rows", 0) >= 1

    rows = await api_client.get(f"/api/v1/brands/{bid}/revenue-density", headers=headers)
    assert rows.status_code == 200
    data = rows.json()
    assert len(data) >= 1
    assert data[0].get("content_title") == "Density Test Clip"
