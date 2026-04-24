"""Integration tests for Autonomous Execution Phase D API persistence (DB-backed)."""
import pytest

from tests.conftest import register_and_login, create_brand_with_offer


@pytest.mark.asyncio
async def test_revenue_pressure_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    post = await api_client.post(
        f"/api/v1/brands/{bid}/revenue-pressure/recompute",
        headers=headers,
    )
    assert post.status_code == 200
    data = post.json()
    assert data["status"] == "completed"

    get = await api_client.get(f"/api/v1/brands/{bid}/revenue-pressure", headers=headers)
    assert get.status_code == 200
    items = get.json()
    assert isinstance(items, list)
    assert len(items) >= 1
    assert items[0]["pressure_score"] >= 0


@pytest.mark.asyncio
async def test_override_policies_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    post = await api_client.post(
        f"/api/v1/brands/{bid}/override-policies/recompute",
        headers=headers,
    )
    assert post.status_code == 200

    get = await api_client.get(f"/api/v1/brands/{bid}/override-policies", headers=headers)
    assert get.status_code == 200
    items = get.json()
    assert isinstance(items, list)
    assert len(items) >= 1
    assert "action_ref" in items[0]
    assert "override_mode" in items[0]


@pytest.mark.asyncio
async def test_blocker_detection_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    post = await api_client.post(
        f"/api/v1/brands/{bid}/blocker-detection/recompute",
        headers=headers,
    )
    assert post.status_code == 200

    get = await api_client.get(f"/api/v1/brands/{bid}/blocker-detection", headers=headers)
    assert get.status_code == 200
    items = get.json()
    assert isinstance(items, list)


@pytest.mark.asyncio
async def test_agent_runs_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    get = await api_client.get(f"/api/v1/brands/{bid}/agent-runs", headers=headers)
    assert get.status_code == 200
    data = get.json()
    assert "runs" in data
    assert "messages" in data


@pytest.mark.asyncio
async def test_operator_escalations_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    get = await api_client.get(f"/api/v1/brands/{bid}/operator-escalations", headers=headers)
    assert get.status_code == 200
    data = get.json()
    assert "escalations" in data
    assert "commands" in data
