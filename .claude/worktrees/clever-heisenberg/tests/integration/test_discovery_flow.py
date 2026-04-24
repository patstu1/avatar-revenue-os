"""Integration tests for Phase 2 discovery, scoring, and recommendation flow."""
import pytest


async def _setup(api_client, sample_org_data):
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post("/api/v1/auth/login", json={
        "email": sample_org_data["email"], "password": sample_org_data["password"],
    })
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    brand = await api_client.post("/api/v1/brands/", json={
        "name": "Discovery Brand", "slug": "disc-brand", "niche": "finance",
    }, headers=headers)
    bid = brand.json()["id"]
    await api_client.post("/api/v1/offers/", json={
        "brand_id": bid, "name": "Test Offer", "monetization_method": "affiliate",
        "payout_amount": 30.0, "epc": 2.0, "conversion_rate": 0.04,
    }, headers=headers)
    await api_client.post("/api/v1/accounts/", json={
        "brand_id": bid, "platform": "youtube", "platform_username": "@disc_test",
    }, headers=headers)
    return headers, bid


@pytest.mark.asyncio
async def test_signal_ingestion(api_client, sample_org_data):
    headers, bid = await _setup(api_client, sample_org_data)
    response = await api_client.post(f"/api/v1/brands/{bid}/signals/ingest", json={
        "source_type": "manual_seed",
        "topics": [
            {"title": "Best Budget Apps 2026", "keywords": ["budget", "app"], "category": "budgeting", "volume": 10000, "velocity": 0.7},
            {"title": "How to Save $1000 Fast", "keywords": ["savings", "fast"], "category": "savings", "volume": 8000, "velocity": 0.5},
        ],
    }, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["records_created"] == 2


@pytest.mark.asyncio
async def test_niches_recompute(api_client, sample_org_data):
    headers, bid = await _setup(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/signals/ingest", json={
        "source_type": "manual_seed",
        "topics": [
            {"title": "T1", "category": "cat_a", "volume": 5000, "velocity": 0.5},
            {"title": "T2", "category": "cat_b", "volume": 3000, "velocity": 0.3},
        ],
    }, headers=headers)
    response = await api_client.post(f"/api/v1/brands/{bid}/niches/recompute", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) >= 2


@pytest.mark.asyncio
async def test_opportunity_scoring(api_client, sample_org_data):
    headers, bid = await _setup(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/signals/ingest", json={
        "source_type": "manual_seed",
        "topics": [{"title": "Scoring Test", "keywords": ["finance"], "volume": 10000, "velocity": 0.8, "relevance": 0.9}],
    }, headers=headers)
    response = await api_client.post(f"/api/v1/brands/{bid}/opportunities/recompute", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["topics_scored"]) == 1
    assert data["topics_scored"][0]["score"] > 0


@pytest.mark.asyncio
async def test_recommendation_queue_ordering(api_client, sample_org_data):
    headers, bid = await _setup(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/signals/ingest", json={
        "source_type": "manual_seed",
        "topics": [
            {"title": "High Score", "volume": 50000, "velocity": 0.9, "relevance": 0.95},
            {"title": "Low Score", "volume": 500, "velocity": 0.1, "relevance": 0.2},
        ],
    }, headers=headers)
    await api_client.post(f"/api/v1/brands/{bid}/opportunities/recompute", headers=headers)

    response = await api_client.get(f"/api/v1/brands/{bid}/recommendations", headers=headers)
    assert response.status_code == 200
    recs = response.json()
    assert len(recs) >= 2
    assert recs[0]["composite_score"] >= recs[1]["composite_score"]
    assert recs[0]["rank"] < recs[1]["rank"]


@pytest.mark.asyncio
async def test_forecast_endpoint(api_client, sample_org_data):
    headers, bid = await _setup(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/signals/ingest", json={
        "source_type": "manual_seed",
        "topics": [{"title": "Forecast Test", "volume": 10000, "velocity": 0.6}],
    }, headers=headers)

    signals = await api_client.get(f"/api/v1/brands/{bid}/signals", headers=headers)
    tid = signals.json()["topic_candidates"][0]["id"]

    response = await api_client.post(f"/api/v1/brands/{bid}/opportunities/{tid}/forecast", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "expected_profit" in data
    assert "confidence" in data
    assert "explanation" in data


@pytest.mark.asyncio
async def test_offer_fit_endpoint(api_client, sample_org_data):
    headers, bid = await _setup(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/signals/ingest", json={
        "source_type": "manual_seed",
        "topics": [{"title": "Offer Fit Test", "keywords": ["budget"], "volume": 5000}],
    }, headers=headers)

    signals = await api_client.get(f"/api/v1/brands/{bid}/signals", headers=headers)
    tid = signals.json()["topic_candidates"][0]["id"]

    response = await api_client.post(f"/api/v1/brands/{bid}/opportunities/{tid}/offer-fit", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert "fit_score" in data[0]


@pytest.mark.asyncio
async def test_trigger_brief(api_client, sample_org_data):
    headers, bid = await _setup(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/signals/ingest", json={
        "source_type": "manual_seed",
        "topics": [{"title": "Brief Trigger Test", "volume": 8000}],
    }, headers=headers)

    signals = await api_client.get(f"/api/v1/brands/{bid}/signals", headers=headers)
    tid = signals.json()["topic_candidates"][0]["id"]

    response = await api_client.post(f"/api/v1/brands/{bid}/opportunities/{tid}/trigger-brief", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "triggered"
    assert "brief_id" in data


@pytest.mark.asyncio
async def test_signal_ingestion_creates_audit_log(api_client, sample_org_data):
    headers, bid = await _setup(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/signals/ingest", json={
        "source_type": "manual_seed",
        "topics": [{"title": "Audit Test"}],
    }, headers=headers)

    audit = await api_client.get("/api/v1/jobs/audit/logs", headers=headers)
    actions = [e["action"] for e in audit.json()["items"]]
    assert "signals.ingested" in actions


@pytest.mark.asyncio
async def test_persistence_correctness(api_client, sample_org_data):
    """Verify scores are persisted and can be re-read."""
    headers, bid = await _setup(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/signals/ingest", json={
        "source_type": "manual_seed",
        "topics": [{"title": "Persistence Test", "volume": 15000, "velocity": 0.7}],
    }, headers=headers)
    await api_client.post(f"/api/v1/brands/{bid}/opportunities/recompute", headers=headers)

    opp_response = await api_client.get(f"/api/v1/brands/{bid}/opportunities", headers=headers)
    assert opp_response.status_code == 200
    opps = opp_response.json()
    assert len(opps) >= 1
    assert opps[0]["composite_score"] > 0
    assert opps[0]["explanation"] is not None
    assert opps[0]["score_components"] is not None
