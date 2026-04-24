"""Integration tests for scale alerts APIs and persistence."""

import pytest


async def _auth_brand(api_client, sample_org_data):
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post(
        "/api/v1/auth/login", json={"email": sample_org_data["email"], "password": sample_org_data["password"]}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    brand = await api_client.post(
        "/api/v1/brands/", json={"name": "Alert Brand", "slug": "alert-brand", "niche": "finance"}, headers=headers
    )
    bid = brand.json()["id"]
    await api_client.post(
        "/api/v1/accounts/",
        json={
            "brand_id": bid,
            "platform": "youtube",
            "platform_username": "@alert_yt",
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
            "name": "Alert Offer",
            "monetization_method": "affiliate",
            "epc": 2.5,
            "conversion_rate": 0.03,
        },
        headers=headers,
    )
    return headers, bid


@pytest.mark.asyncio
async def test_recompute_then_read_alerts(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    rc = await api_client.post(f"/api/v1/brands/{bid}/alerts/recompute", headers=headers)
    assert rc.status_code == 200
    r = await api_client.get(f"/api/v1/brands/{bid}/alerts", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_gets_are_side_effect_free(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.get(f"/api/v1/brands/{bid}/alerts", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_launch_candidates_and_blockers(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/scale-recommendations/recompute", headers=headers)
    await api_client.post(f"/api/v1/brands/{bid}/launch-candidates/recompute", headers=headers)
    r = await api_client.get(f"/api/v1/brands/{bid}/launch-candidates", headers=headers)
    assert r.status_code == 200

    await api_client.post(f"/api/v1/brands/{bid}/scale-blockers/recompute", headers=headers)
    r2 = await api_client.get(f"/api/v1/brands/{bid}/scale-blockers", headers=headers)
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_launch_readiness(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/launch-readiness/recompute", headers=headers)
    r = await api_client.get(f"/api/v1/brands/{bid}/launch-readiness", headers=headers)
    assert r.status_code == 200
    assert "launch_readiness_score" in r.json()


@pytest.mark.asyncio
async def test_notifications(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/alerts/recompute", headers=headers)
    r = await api_client.get(f"/api/v1/brands/{bid}/notifications", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_scale_intel_recompute_all(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/scale-recommendations/recompute", headers=headers)
    r = await api_client.post(f"/api/v1/brands/{bid}/scale-intel/recompute-all", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "alerts" in body and "launch_candidates" in body


@pytest.mark.asyncio
async def test_acknowledge_via_root_path(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/alerts/recompute", headers=headers)
    lst = await api_client.get(f"/api/v1/brands/{bid}/alerts", headers=headers)
    assert lst.status_code == 200
    rows = lst.json()
    if not rows:
        return
    aid = rows[0]["id"]
    ack = await api_client.post(f"/api/v1/alerts/{aid}/acknowledge", headers=headers)
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"


@pytest.mark.asyncio
async def test_alerts_filter_by_severity(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/alerts/recompute", headers=headers)
    r = await api_client.get(f"/api/v1/brands/{bid}/alerts", headers=headers, params={"severity": "high"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_persistence_alerts_and_notifications(api_client, sample_org_data):
    """After recompute, operator_alerts and notification_deliveries are surfaced via API."""
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/scale-recommendations/recompute", headers=headers)
    await api_client.post(f"/api/v1/brands/{bid}/alerts/recompute", headers=headers)
    alerts = await api_client.get(f"/api/v1/brands/{bid}/alerts", headers=headers)
    assert alerts.status_code == 200
    assert len(alerts.json()) >= 1
    notif = await api_client.get(f"/api/v1/brands/{bid}/notifications", headers=headers)
    assert notif.status_code == 200
    assert len(notif.json()) >= 1


@pytest.mark.asyncio
async def test_alert_types_deduplicated_per_recompute(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/scale-recommendations/recompute", headers=headers)
    await api_client.post(f"/api/v1/brands/{bid}/alerts/recompute", headers=headers)
    r = await api_client.get(f"/api/v1/brands/{bid}/alerts", headers=headers)
    types = [a["alert_type"] for a in r.json()]
    assert len(types) == len(set(types))


@pytest.mark.asyncio
async def test_resolve_alert(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/alerts/recompute", headers=headers)
    lst = await api_client.get(f"/api/v1/brands/{bid}/alerts", headers=headers)
    aid = lst.json()[0]["id"]
    r = await api_client.post(f"/api/v1/alerts/{aid}/resolve", headers=headers, json={"notes": "verified"})
    assert r.status_code == 200
    assert r.json()["status"] == "resolved"


@pytest.mark.asyncio
async def test_get_launch_candidate_by_id(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/scale-recommendations/recompute", headers=headers)
    await api_client.post(f"/api/v1/brands/{bid}/launch-candidates/recompute", headers=headers)
    cands = await api_client.get(f"/api/v1/brands/{bid}/launch-candidates", headers=headers)
    rows = cands.json()
    if not rows:
        return
    cid = rows[0]["id"]
    one = await api_client.get(f"/api/v1/brands/launch-candidates/{cid}", headers=headers)
    assert one.status_code == 200
    assert one.json()["id"] == cid
