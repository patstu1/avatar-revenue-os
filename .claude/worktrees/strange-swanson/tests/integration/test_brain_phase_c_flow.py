"""Integration tests for Brain Architecture Phase C — DB-backed API tests."""
from __future__ import annotations

import pytest

from tests.conftest import create_brand_with_offer, register_and_login

pytestmark = pytest.mark.asyncio


async def test_agent_mesh_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    resp = await api_client.post(f"/api/v1/brands/{bid}/agent-mesh/recompute", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    counts = body.get("counts", {})
    assert counts.get("registry_created", 0) == 12
    assert counts.get("agent_runs_created", 0) == 12


async def test_agent_registry_populated(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(f"/api/v1/brands/{bid}/agent-mesh/recompute", headers=headers)

    resp = await api_client.get(f"/api/v1/brands/{bid}/agent-registry", headers=headers)
    assert resp.status_code == 200
    agents = resp.json()
    assert len(agents) == 12
    slugs = {a["agent_slug"] for a in agents}
    assert "trend_scout" in slugs
    assert "ops_watchdog" in slugs


async def test_agent_runs_v2_populated(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(f"/api/v1/brands/{bid}/agent-mesh/recompute", headers=headers)

    resp = await api_client.get(f"/api/v1/brands/{bid}/agent-runs-v2", headers=headers)
    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) >= 12
    for r in runs:
        assert r["run_status"] == "completed"
        assert r["confidence"] >= 0


async def test_workflow_coordination_populated(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(f"/api/v1/brands/{bid}/agent-mesh/recompute", headers=headers)

    resp = await api_client.get(f"/api/v1/brands/{bid}/workflow-coordination", headers=headers)
    assert resp.status_code == 200
    wfs = resp.json()
    assert len(wfs) >= 6
    types = {w["workflow_type"] for w in wfs}
    assert "opportunity_to_launch" in types
    assert "recovery_chain" in types
    for w in wfs:
        assert w["status"] in ("completed", "failed")


async def test_shared_context_events_populated(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(f"/api/v1/brands/{bid}/agent-mesh/recompute", headers=headers)

    resp = await api_client.get(f"/api/v1/brands/{bid}/shared-context-events", headers=headers)
    assert resp.status_code == 200
    events = resp.json()
    assert isinstance(events, list)
    for e in events:
        assert "event_type" in e
        assert "source_module" in e


async def test_multi_agent_chain_produces_coordinated_outcome(api_client, sample_org_data):
    """Verify the opportunity_to_launch workflow passes data through 3 agents."""
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(f"/api/v1/brands/{bid}/agent-mesh/recompute", headers=headers)

    resp = await api_client.get(f"/api/v1/brands/{bid}/workflow-coordination", headers=headers)
    wfs = resp.json()
    otl = [w for w in wfs if w["workflow_type"] == "opportunity_to_launch"]
    assert len(otl) >= 1
    w = otl[0]
    assert len(w["sequence_json"]) == 3
    assert len(w["handoff_events_json"]) == 2
    outputs = w["outputs_json"]
    assert "trend_scout" in outputs
    assert "niche_allocator" in outputs
    assert "account_launcher" in outputs


async def test_idempotency(api_client, sample_org_data):
    """Repeated recompute deactivates previous entries."""
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(f"/api/v1/brands/{bid}/agent-mesh/recompute", headers=headers)
    r1 = await api_client.get(f"/api/v1/brands/{bid}/agent-registry", headers=headers)
    count1 = len(r1.json())

    await api_client.post(f"/api/v1/brands/{bid}/agent-mesh/recompute", headers=headers)
    r2 = await api_client.get(f"/api/v1/brands/{bid}/agent-registry", headers=headers)
    count2 = len(r2.json())

    assert count2 == count1
