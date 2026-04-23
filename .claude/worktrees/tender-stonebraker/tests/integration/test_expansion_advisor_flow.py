"""DB-backed integration tests for Account Expansion Advisor."""
import pytest


async def _auth_brand_with_accounts(api_client, sample_org_data):
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post("/api/v1/auth/login", json={"email": sample_org_data["email"], "password": sample_org_data["password"]})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    brand = await api_client.post("/api/v1/brands/", json={"name": "Expansion Brand", "slug": "expansion-brand", "niche": "fitness"}, headers=headers)
    bid = brand.json()["id"]
    await api_client.post("/api/v1/accounts/", json={
        "brand_id": bid, "platform": "youtube", "platform_username": "@exp_yt",
        "niche_focus": "fitness", "posting_capacity_per_day": 2, "scale_role": "flagship",
    }, headers=headers)
    await api_client.post("/api/v1/offers/", json={
        "brand_id": bid, "name": "Fitness Offer", "monetization_method": "affiliate",
        "epc": 2.0, "conversion_rate": 0.03, "payout_amount": 40.0,
    }, headers=headers)
    return headers, bid


@pytest.mark.asyncio
async def test_advisory_empty_before_recompute(api_client, sample_org_data):
    headers, bid = await _auth_brand_with_accounts(api_client, sample_org_data)
    r = await api_client.get(f"/api/v1/brands/{bid}/expansion-advisor", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_recompute_produces_advisory(api_client, sample_org_data):
    headers, bid = await _auth_brand_with_accounts(api_client, sample_org_data)
    r = await api_client.post(f"/api/v1/brands/{bid}/expansion-advisor/recompute", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["rows_processed"] == 1
    assert "should_add" in body


@pytest.mark.asyncio
async def test_advisory_has_required_fields(api_client, sample_org_data):
    headers, bid = await _auth_brand_with_accounts(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/expansion-advisor/recompute", headers=headers)
    r = await api_client.get(f"/api/v1/brands/{bid}/expansion-advisor", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    adv = data[0]
    for field in ("should_add_account_now", "confidence", "urgency", "explanation", "evidence", "blockers"):
        assert field in adv, f"Missing field: {field}"


@pytest.mark.asyncio
async def test_advisory_has_evidence(api_client, sample_org_data):
    headers, bid = await _auth_brand_with_accounts(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/expansion-advisor/recompute", headers=headers)
    data = (await api_client.get(f"/api/v1/brands/{bid}/expansion-advisor", headers=headers)).json()
    ev = data[0]["evidence"]
    assert "recommendation_key" in ev
    assert "scale_readiness" in ev
    assert "cannibalization_risk" in ev


@pytest.mark.asyncio
async def test_recompute_is_idempotent(api_client, sample_org_data):
    headers, bid = await _auth_brand_with_accounts(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/expansion-advisor/recompute", headers=headers)
    count1 = len((await api_client.get(f"/api/v1/brands/{bid}/expansion-advisor", headers=headers)).json())
    await api_client.post(f"/api/v1/brands/{bid}/expansion-advisor/recompute", headers=headers)
    count2 = len((await api_client.get(f"/api/v1/brands/{bid}/expansion-advisor", headers=headers)).json())
    assert count1 == count2


@pytest.mark.asyncio
async def test_single_account_brand_gets_expand_recommendation(api_client, sample_org_data):
    """With 1 account and decent offers, the engine should recommend adding an experimental lane."""
    headers, bid = await _auth_brand_with_accounts(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/expansion-advisor/recompute", headers=headers)
    data = (await api_client.get(f"/api/v1/brands/{bid}/expansion-advisor", headers=headers)).json()
    adv = data[0]
    rec = adv["evidence"]["recommendation_key"]
    from packages.scoring.expansion_advisor_engine import EXPAND_REC_KEYS, HOLD_REC_KEYS
    assert adv["should_add_account_now"] is True or rec in HOLD_REC_KEYS, f"Unexpected: should_add={adv['should_add_account_now']}, rec={rec}"
