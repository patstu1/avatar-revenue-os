"""Integration tests for Phase 6 growth APIs and persistence.

Architecture: POST recompute populates data, then GETs read it.
GETs never trigger recompute — they return persisted state only.
"""

import pytest


async def _auth_brand_minimal(api_client, sample_org_data):
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": sample_org_data["email"], "password": sample_org_data["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    brand = await api_client.post(
        "/api/v1/brands/",
        json={"name": "Growth Brand", "slug": "growth-brand", "niche": "saas reviews"},
        headers=headers,
    )
    bid = brand.json()["id"]

    await api_client.post(
        "/api/v1/accounts/",
        json={
            "brand_id": bid,
            "platform": "youtube",
            "platform_username": "@growth_yt",
            "niche_focus": "saas",
            "posting_capacity_per_day": 2,
            "scale_role": "flagship",
        },
        headers=headers,
    )

    await api_client.post(
        "/api/v1/offers/",
        json={
            "brand_id": bid,
            "name": "Growth Offer",
            "monetization_method": "affiliate",
            "epc": 2.5,
            "conversion_rate": 0.025,
        },
        headers=headers,
    )

    return headers, bid


@pytest.mark.asyncio
async def test_recompute_then_read_segments_and_ltv(api_client, sample_org_data):
    headers, bid = await _auth_brand_minimal(api_client, sample_org_data)

    rc = await api_client.post(f"/api/v1/brands/{bid}/growth-intel/recompute", headers=headers)
    assert rc.status_code == 200
    summary = rc.json()
    assert summary["segments"] >= 1
    assert summary["ltv_rows"] >= 1
    assert summary["trust_reports"] >= 1

    r1 = await api_client.get(f"/api/v1/brands/{bid}/audience-segments", headers=headers)
    assert r1.status_code == 200
    segs = r1.json()
    assert isinstance(segs, list) and len(segs) >= 1
    assert segs[0]["segment_criteria"].get("phase6_auto") is True

    r2 = await api_client.get(f"/api/v1/brands/{bid}/ltv", headers=headers)
    assert r2.status_code == 200
    ltvs = r2.json()
    assert isinstance(ltvs, list) and len(ltvs) >= 1
    assert ltvs[0]["model_type"] == "rules_based_phase6"


@pytest.mark.asyncio
async def test_gets_are_side_effect_free(api_client, sample_org_data):
    """GETs before recompute return empty lists — no hidden mutations."""
    headers, bid = await _auth_brand_minimal(api_client, sample_org_data)

    r = await api_client.get(f"/api/v1/brands/{bid}/audience-segments", headers=headers)
    assert r.status_code == 200
    assert r.json() == []

    r2 = await api_client.get(f"/api/v1/brands/{bid}/trust-signals", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["reports"] == []


@pytest.mark.asyncio
async def test_repeated_recomputes_no_duplicate_decisions(api_client, sample_org_data):
    """Two recomputes should not create duplicate ExpansionDecision rows."""
    headers, bid = await _auth_brand_minimal(api_client, sample_org_data)

    await api_client.post(f"/api/v1/brands/{bid}/growth-intel/recompute", headers=headers)
    await api_client.post(f"/api/v1/brands/{bid}/growth-intel/recompute", headers=headers)

    r = await api_client.get(f"/api/v1/brands/{bid}/expansion-recommendations", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data.get("latest_expansion_decision_id") is not None


@pytest.mark.asyncio
async def test_dashboard_leaks_and_growth_intel(api_client, sample_org_data):
    headers, bid = await _auth_brand_minimal(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/growth-intel/recompute", headers=headers)

    r = await api_client.get("/api/v1/dashboard/leaks", params={"brand_id": bid}, headers=headers)
    assert r.status_code == 200
    d = r.json()
    assert d["brand_id"] == bid
    assert "funnel" in d and "leaks" in d and "summary" in d

    r2 = await api_client.get("/api/v1/dashboard/growth-intel", params={"brand_id": bid}, headers=headers)
    assert r2.status_code == 200
    g = r2.json()
    assert g["brand_id"] == bid
    assert "audience_segments" in g and "ltv_models" in g
    assert "expansion" in g and "cross_platform_flow_plans" in g["expansion"]
    assert "paid_amplification" in g
    assert "trust_signals" in g


@pytest.mark.asyncio
async def test_expansion_paid_trust_brand_routes(api_client, sample_org_data):
    headers, bid = await _auth_brand_minimal(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/growth-intel/recompute", headers=headers)

    re = await api_client.get(f"/api/v1/brands/{bid}/expansion-recommendations", headers=headers)
    assert re.status_code == 200
    assert "geo_language_recommendations" in re.json()

    rp = await api_client.get(f"/api/v1/brands/{bid}/paid-amplification", headers=headers)
    assert rp.status_code == 200
    assert "jobs" in rp.json()

    rt = await api_client.get(f"/api/v1/brands/{bid}/trust-signals", headers=headers)
    assert rt.status_code == 200
    reports = rt.json()["reports"]
    assert isinstance(reports, list) and len(reports) >= 1
    assert 0 <= reports[0]["trust_score"] <= 100
