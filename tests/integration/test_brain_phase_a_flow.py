"""Integration tests for Brain Architecture Phase A — DB-backed API tests."""
from __future__ import annotations

import pytest

from tests.conftest import create_brand_with_offer, register_and_login

pytestmark = pytest.mark.asyncio


async def test_brain_memory_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    resp = await api_client.post(f"/api/v1/brands/{bid}/brain-memory/recompute", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert "entries_created" in body.get("counts", {})

    resp2 = await api_client.get(f"/api/v1/brands/{bid}/brain-memory", headers=headers)
    assert resp2.status_code == 200
    data = resp2.json()
    assert "entries" in data
    assert "links" in data
    assert isinstance(data["entries"], list)


async def test_account_states_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    resp = await api_client.post(f"/api/v1/brands/{bid}/account-states/recompute", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert "account_states_created" in body.get("counts", {})

    resp2 = await api_client.get(f"/api/v1/brands/{bid}/account-states", headers=headers)
    assert resp2.status_code == 200
    rows = resp2.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert rows[0]["current_state"] in ["newborn", "warming", "stable", "scaling", "max_output", "saturated", "cooling", "at_risk"]


async def test_opportunity_states_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    resp = await api_client.post(f"/api/v1/brands/{bid}/opportunity-states/recompute", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"

    resp2 = await api_client.get(f"/api/v1/brands/{bid}/opportunity-states", headers=headers)
    assert resp2.status_code == 200
    rows = resp2.json()
    assert isinstance(rows, list)


async def test_execution_states_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    resp = await api_client.post(f"/api/v1/brands/{bid}/execution-states/recompute", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"

    resp2 = await api_client.get(f"/api/v1/brands/{bid}/execution-states", headers=headers)
    assert resp2.status_code == 200
    rows = resp2.json()
    assert isinstance(rows, list)


async def test_audience_states_v2_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    resp = await api_client.post(f"/api/v1/brands/{bid}/audience-states-v2/recompute", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert "audience_states_created" in body.get("counts", {})

    resp2 = await api_client.get(f"/api/v1/brands/{bid}/audience-states-v2", headers=headers)
    assert resp2.status_code == 200
    rows = resp2.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1


async def test_brain_memory_idempotency(api_client, sample_org_data):
    """Repeated recompute should not duplicate — previous entries are deactivated."""
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(f"/api/v1/brands/{bid}/brain-memory/recompute", headers=headers)
    resp1 = await api_client.get(f"/api/v1/brands/{bid}/brain-memory", headers=headers)
    count1 = len(resp1.json()["entries"])

    await api_client.post(f"/api/v1/brands/{bid}/brain-memory/recompute", headers=headers)
    resp2 = await api_client.get(f"/api/v1/brands/{bid}/brain-memory", headers=headers)
    count2 = len(resp2.json()["entries"])

    assert count2 == count1, "Repeated recompute should not accumulate active entries"
