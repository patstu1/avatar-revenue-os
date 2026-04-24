"""Integration tests for Revenue Ceiling Phase C APIs."""

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
        json={"name": "RC C Brand", "slug": "rc-c-brand", "niche": "fitness"},
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
            "name": "Membership Program",
            "monetization_method": "membership",
            "epc": 3.0,
            "conversion_rate": 0.015,
            "payout_amount": 99.0,
        },
        headers=headers,
    )
    return headers, bid


# ---------------------------------------------------------------------------
# GET — empty before recompute
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_phase_c_gets_empty_before_recompute(api_client, sample_org_data):
    headers, bid = await _auth_brand_two_offers(api_client, sample_org_data)
    for path in [
        f"/api/v1/brands/{bid}/recurring-revenue",
        f"/api/v1/brands/{bid}/sponsor-inventory",
        f"/api/v1/brands/{bid}/sponsor-package-recommendations",
        f"/api/v1/brands/{bid}/trust-conversion",
        f"/api/v1/brands/{bid}/monetization-mix",
        f"/api/v1/brands/{bid}/paid-promotion-candidates",
    ]:
        r = await api_client.get(path, headers=headers)
        assert r.status_code == 200, f"GET {path} returned {r.status_code}"
        assert r.json() == [] or r.json() == {}, f"Expected empty for {path}"


# ---------------------------------------------------------------------------
# Recompute + GET — recurring revenue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_phase_c_recurring_revenue_recompute_and_get(api_client, sample_org_data):
    headers, bid = await _auth_brand_two_offers(api_client, sample_org_data)

    rc = await api_client.post(f"/api/v1/brands/{bid}/recurring-revenue/recompute", headers=headers)
    assert rc.status_code == 200

    rows = await api_client.get(f"/api/v1/brands/{bid}/recurring-revenue", headers=headers)
    assert rows.status_code == 200
    data = rows.json()
    assert len(data) >= 1
    row = data[0]
    assert "recurring_potential_score" in row
    assert "best_recurring_offer_type" in row
    assert "audience_fit" in row
    assert "churn_risk_proxy" in row
    assert "expected_monthly_value" in row
    assert "expected_annual_value" in row
    assert "confidence" in row


# ---------------------------------------------------------------------------
# Recompute + GET — sponsor inventory
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_phase_c_sponsor_inventory_recompute_and_get(api_client, db_session, sample_org_data):
    headers, bid = await _auth_brand_two_offers(api_client, sample_org_data)
    bid_uuid = uuid.UUID(bid)

    ci = ContentItem(brand_id=bid_uuid, title="Sponsor Test Video", content_type=ContentType.SHORT_VIDEO)
    db_session.add(ci)
    await db_session.commit()

    rc = await api_client.post(f"/api/v1/brands/{bid}/sponsor-inventory/recompute", headers=headers)
    assert rc.status_code == 200

    inv = await api_client.get(f"/api/v1/brands/{bid}/sponsor-inventory", headers=headers)
    assert inv.status_code == 200
    assert len(inv.json()) >= 1
    item = inv.json()[0]
    assert "sponsor_fit_score" in item
    assert "estimated_package_price" in item
    assert "sponsor_category" in item

    pkg = await api_client.get(f"/api/v1/brands/{bid}/sponsor-package-recommendations", headers=headers)
    assert pkg.status_code == 200
    pkg_data = pkg.json()
    if isinstance(pkg_data, list):
        assert len(pkg_data) >= 1
        assert "recommended_package" in pkg_data[0]


# ---------------------------------------------------------------------------
# Recompute + GET — trust conversion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_phase_c_trust_conversion_recompute_and_get(api_client, sample_org_data):
    headers, bid = await _auth_brand_two_offers(api_client, sample_org_data)

    rc = await api_client.post(f"/api/v1/brands/{bid}/trust-conversion/recompute", headers=headers)
    assert rc.status_code == 200

    rows = await api_client.get(f"/api/v1/brands/{bid}/trust-conversion", headers=headers)
    assert rows.status_code == 200
    data = rows.json()
    assert len(data) >= 1
    row = data[0]
    assert "trust_deficit_score" in row
    assert "recommended_proof_blocks" in row
    assert "missing_trust_elements" in row
    assert "expected_uplift" in row
    assert "confidence" in row


# ---------------------------------------------------------------------------
# Recompute + GET — monetization mix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_phase_c_monetization_mix_recompute_and_get(api_client, sample_org_data):
    headers, bid = await _auth_brand_two_offers(api_client, sample_org_data)

    rc = await api_client.post(f"/api/v1/brands/{bid}/monetization-mix/recompute", headers=headers)
    assert rc.status_code == 200

    rows = await api_client.get(f"/api/v1/brands/{bid}/monetization-mix", headers=headers)
    assert rows.status_code == 200
    data = rows.json()
    assert len(data) >= 1
    row = data[0]
    assert "current_revenue_mix" in row
    assert "dependency_risk" in row
    assert "underused_monetization_paths" in row
    assert "next_best_mix" in row
    assert "expected_margin_uplift" in row
    assert "expected_ltv_uplift" in row
    assert "confidence" in row


# ---------------------------------------------------------------------------
# Recompute + GET — paid promotion candidates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_phase_c_paid_promotion_recompute_and_get(api_client, db_session, sample_org_data):
    headers, bid = await _auth_brand_two_offers(api_client, sample_org_data)
    bid_uuid = uuid.UUID(bid)

    ci = ContentItem(brand_id=bid_uuid, title="Promo Gate Test", content_type=ContentType.SHORT_VIDEO)
    db_session.add(ci)
    await db_session.commit()

    rc = await api_client.post(f"/api/v1/brands/{bid}/paid-promotion-candidates/recompute", headers=headers)
    assert rc.status_code == 200

    rows = await api_client.get(f"/api/v1/brands/{bid}/paid-promotion-candidates", headers=headers)
    assert rows.status_code == 200
    data = rows.json()
    assert len(data) >= 1
    row = data[0]
    assert "organic_winner_evidence" in row
    assert "is_eligible" in row
    assert "gate_reason" in row
    assert "confidence" in row


# ---------------------------------------------------------------------------
# Persistence — recompute replaces, does not duplicate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_phase_c_recurring_revenue_recompute_is_idempotent(api_client, sample_org_data):
    headers, bid = await _auth_brand_two_offers(api_client, sample_org_data)

    await api_client.post(f"/api/v1/brands/{bid}/recurring-revenue/recompute", headers=headers)
    first = await api_client.get(f"/api/v1/brands/{bid}/recurring-revenue", headers=headers)
    count_1 = len(first.json())

    await api_client.post(f"/api/v1/brands/{bid}/recurring-revenue/recompute", headers=headers)
    second = await api_client.get(f"/api/v1/brands/{bid}/recurring-revenue", headers=headers)
    count_2 = len(second.json())

    assert count_1 == count_2, "Recompute should replace, not duplicate rows"


# ---------------------------------------------------------------------------
# Celery task registration
# ---------------------------------------------------------------------------


def test_phase_c_celery_tasks_registered():
    import workers.revenue_ceiling_worker.tasks  # noqa: F401
    from workers.celery_app import app

    for name in (
        "workers.revenue_ceiling_worker.tasks.recompute_all_recurring_revenue",
        "workers.revenue_ceiling_worker.tasks.recompute_all_sponsor_inventory",
        "workers.revenue_ceiling_worker.tasks.recompute_all_trust_conversion",
        "workers.revenue_ceiling_worker.tasks.recompute_all_monetization_mix",
        "workers.revenue_ceiling_worker.tasks.refresh_all_paid_promotion_candidates",
    ):
        assert name in app.tasks, f"Task {name} not registered"
