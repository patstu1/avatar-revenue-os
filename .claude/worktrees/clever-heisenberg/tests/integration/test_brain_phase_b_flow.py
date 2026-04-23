"""Integration tests for Brain Architecture Phase B — DB-backed API tests."""
from __future__ import annotations

import pytest

from tests.conftest import create_brand_with_offer, register_and_login

pytestmark = pytest.mark.asyncio


async def test_brain_decisions_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    resp = await api_client.post(f"/api/v1/brands/{bid}/brain-decisions/recompute", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert "decisions_created" in body.get("counts", {})

    resp2 = await api_client.get(f"/api/v1/brands/{bid}/brain-decisions", headers=headers)
    assert resp2.status_code == 200
    rows = resp2.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    d = rows[0]
    assert d["decision_class"] in ["launch", "hold", "scale", "suppress", "monetize", "reroute", "recover", "escalate", "throttle", "split_account", "merge_lane", "test", "kill"]
    assert d["policy_mode"] in ["autonomous", "guarded", "manual"]


async def test_policy_evaluations_populated(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(f"/api/v1/brands/{bid}/brain-decisions/recompute", headers=headers)

    resp = await api_client.get(f"/api/v1/brands/{bid}/policy-evaluations", headers=headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert rows[0]["policy_mode"] in ["autonomous", "guarded", "manual"]


async def test_confidence_reports_populated(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(f"/api/v1/brands/{bid}/brain-decisions/recompute", headers=headers)

    resp = await api_client.get(f"/api/v1/brands/{bid}/confidence-reports", headers=headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert rows[0]["confidence_band"] in ["very_high", "high", "medium", "low", "very_low"]


async def test_upside_cost_estimates_populated(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(f"/api/v1/brands/{bid}/brain-decisions/recompute", headers=headers)

    resp = await api_client.get(f"/api/v1/brands/{bid}/upside-cost-estimates", headers=headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert "net_value" in rows[0]


async def test_arbitration_reports_populated(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(f"/api/v1/brands/{bid}/brain-decisions/recompute", headers=headers)

    resp = await api_client.get(f"/api/v1/brands/{bid}/arbitration-reports", headers=headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert "chosen_winner_class" in rows[0]


async def test_low_confidence_forces_guarded_mode(api_client, sample_org_data):
    """A fresh brand with minimal data should produce guarded or manual policy mode, not autonomous."""
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(f"/api/v1/brands/{bid}/brain-decisions/recompute", headers=headers)

    resp = await api_client.get(f"/api/v1/brands/{bid}/policy-evaluations", headers=headers)
    policies = resp.json()
    assert len(policies) >= 1
    for p in policies:
        assert p["policy_mode"] in ("guarded", "manual"), f"Expected guarded/manual for low-data brand, got {p['policy_mode']}"


async def test_idempotency(api_client, sample_org_data):
    """Repeated recompute deactivates previous entries."""
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(f"/api/v1/brands/{bid}/brain-decisions/recompute", headers=headers)
    r1 = await api_client.get(f"/api/v1/brands/{bid}/brain-decisions", headers=headers)
    count1 = len(r1.json())

    await api_client.post(f"/api/v1/brands/{bid}/brain-decisions/recompute", headers=headers)
    r2 = await api_client.get(f"/api/v1/brands/{bid}/brain-decisions", headers=headers)
    count2 = len(r2.json())

    assert count2 == count1
