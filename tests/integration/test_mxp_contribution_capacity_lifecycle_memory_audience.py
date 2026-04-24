"""Integration tests for MXP sub-modules: contribution, capacity, offer lifecycle, creative memory, audience state."""

import pytest

from tests.conftest import create_brand_with_offer, register_and_login


@pytest.mark.asyncio
async def test_contribution_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    post = await api_client.post(
        f"/api/v1/brands/{bid}/contribution-reports/recompute",
        headers=headers,
    )
    assert post.status_code == 200

    get = await api_client.get(f"/api/v1/brands/{bid}/contribution-reports", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert "attribution_model" in rows[0]
    assert "contribution_score" in rows[0]


@pytest.mark.asyncio
async def test_capacity_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    post = await api_client.post(
        f"/api/v1/brands/{bid}/capacity-reports/recompute",
        headers=headers,
    )
    assert post.status_code == 200

    get = await api_client.get(f"/api/v1/brands/{bid}/capacity-reports", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert "capacity_type" in rows[0]

    get_alloc = await api_client.get(f"/api/v1/brands/{bid}/queue-allocations", headers=headers)
    assert get_alloc.status_code == 200
    alloc_rows = get_alloc.json()
    assert isinstance(alloc_rows, list)


@pytest.mark.asyncio
async def test_offer_lifecycle_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    post = await api_client.post(
        f"/api/v1/brands/{bid}/offer-lifecycle-reports/recompute",
        headers=headers,
    )
    assert post.status_code == 200

    get = await api_client.get(f"/api/v1/brands/{bid}/offer-lifecycle-reports", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert "lifecycle_state" in rows[0]
    assert "health_score" in rows[0]


@pytest.mark.asyncio
async def test_creative_memory_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    post = await api_client.post(
        f"/api/v1/brands/{bid}/creative-memory-atoms/recompute",
        headers=headers,
    )
    assert post.status_code == 200

    get = await api_client.get(f"/api/v1/brands/{bid}/creative-memory-atoms", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert isinstance(rows, list)


@pytest.mark.asyncio
async def test_audience_state_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    post = await api_client.post(
        f"/api/v1/brands/{bid}/audience-states/recompute",
        headers=headers,
    )
    assert post.status_code == 200

    get = await api_client.get(f"/api/v1/brands/{bid}/audience-states", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert isinstance(rows, list)
