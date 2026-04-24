"""Integration tests for Brain Architecture Phase D — DB-backed API tests."""
from __future__ import annotations

import pytest

from tests.conftest import create_brand_with_offer, register_and_login

pytestmark = pytest.mark.asyncio


async def test_meta_monitoring_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    resp = await api_client.post(f"/api/v1/brands/{bid}/meta-monitoring/recompute", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"

    resp2 = await api_client.get(f"/api/v1/brands/{bid}/meta-monitoring", headers=headers)
    assert resp2.status_code == 200
    reports = resp2.json()
    assert len(reports) >= 1
    r = reports[0]
    assert r["health_band"] in ["excellent", "good", "medium", "degraded", "critical"]
    assert 0 <= r["health_score"] <= 1


async def test_self_corrections_populated(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(f"/api/v1/brands/{bid}/meta-monitoring/recompute", headers=headers)

    resp = await api_client.get(f"/api/v1/brands/{bid}/self-corrections", headers=headers)
    assert resp.status_code == 200
    corrections = resp.json()
    assert isinstance(corrections, list)


async def test_readiness_brain_populated(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(f"/api/v1/brands/{bid}/readiness-brain/recompute", headers=headers)

    resp = await api_client.get(f"/api/v1/brands/{bid}/readiness-brain", headers=headers)
    assert resp.status_code == 200
    reports = resp.json()
    assert len(reports) >= 1
    r = reports[0]
    assert r["readiness_band"] in ["ready", "mostly_ready", "partially_ready", "not_ready", "blocked"]
    assert isinstance(r["blockers_json"], list)
    assert isinstance(r["allowed_actions_json"], list)
    assert isinstance(r["forbidden_actions_json"], list)


async def test_brain_escalations_populated(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(f"/api/v1/brands/{bid}/meta-monitoring/recompute", headers=headers)

    resp = await api_client.get(f"/api/v1/brands/{bid}/brain-escalations", headers=headers)
    assert resp.status_code == 200
    esc = resp.json()
    assert isinstance(esc, list)
    assert len(esc) >= 1
    e = esc[0]
    assert "escalation_type" in e
    assert "command" in e
    assert "urgency" in e


async def test_readiness_brain_blocks_unsafe_auto_run(api_client, sample_org_data):
    """Fresh brand without credentials should have auto_run forbidden."""
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(f"/api/v1/brands/{bid}/readiness-brain/recompute", headers=headers)

    resp = await api_client.get(f"/api/v1/brands/{bid}/readiness-brain", headers=headers)
    r = resp.json()[0]
    assert "auto_run" in r["forbidden_actions_json"]


async def test_missing_credentials_generates_escalation(api_client, sample_org_data):
    """Fresh brand has no platform credentials, should generate connect_credential escalation."""
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(f"/api/v1/brands/{bid}/meta-monitoring/recompute", headers=headers)

    resp = await api_client.get(f"/api/v1/brands/{bid}/brain-escalations", headers=headers)
    types = [e["escalation_type"] for e in resp.json()]
    assert "connect_credential" in types


async def test_idempotency(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(f"/api/v1/brands/{bid}/meta-monitoring/recompute", headers=headers)
    r1 = await api_client.get(f"/api/v1/brands/{bid}/meta-monitoring", headers=headers)

    await api_client.post(f"/api/v1/brands/{bid}/meta-monitoring/recompute", headers=headers)
    r2 = await api_client.get(f"/api/v1/brands/{bid}/meta-monitoring", headers=headers)

    assert len(r1.json()) == len(r2.json())
