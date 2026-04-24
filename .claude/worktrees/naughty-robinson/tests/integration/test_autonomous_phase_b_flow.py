"""Integration tests for Autonomous Execution Phase B API persistence (DB-backed)."""
import pytest

from tests.conftest import register_and_login, create_brand_with_offer


@pytest.mark.asyncio
async def test_execution_policies_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    post = await api_client.post(
        f"/api/v1/brands/{bid}/execution-policies/recompute", headers=headers,
    )
    assert post.status_code == 200
    data = post.json()
    assert data["status"] == "completed"

    get = await api_client.get(f"/api/v1/brands/{bid}/execution-policies", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert "action_type" in rows[0]
    assert "execution_mode" in rows[0]


@pytest.mark.asyncio
async def test_autonomous_run_start_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    post = await api_client.post(
        f"/api/v1/brands/{bid}/autonomous-runs/start", headers=headers,
    )
    assert post.status_code == 200
    data = post.json()
    assert data["status"] == "completed"

    get = await api_client.get(f"/api/v1/brands/{bid}/autonomous-runs", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert isinstance(rows, list)


@pytest.mark.asyncio
async def test_distribution_plans_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    post = await api_client.post(
        f"/api/v1/brands/{bid}/distribution-plans/recompute", headers=headers,
    )
    assert post.status_code == 200

    get = await api_client.get(f"/api/v1/brands/{bid}/distribution-plans", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert isinstance(rows, list)


@pytest.mark.asyncio
async def test_monetization_routes_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    post = await api_client.post(
        f"/api/v1/brands/{bid}/monetization-routes/recompute", headers=headers,
    )
    assert post.status_code == 200

    get = await api_client.get(f"/api/v1/brands/{bid}/monetization-routes", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert isinstance(rows, list)


@pytest.mark.asyncio
async def test_suppression_executions_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    post = await api_client.post(
        f"/api/v1/brands/{bid}/suppression-executions/recompute", headers=headers,
    )
    assert post.status_code == 200
    data = post.json()
    assert data["status"] == "completed"

    get = await api_client.get(f"/api/v1/brands/{bid}/suppression-executions", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert isinstance(rows, list)
