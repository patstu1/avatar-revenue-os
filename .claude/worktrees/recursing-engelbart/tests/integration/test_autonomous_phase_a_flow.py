"""Integration tests for Autonomous Execution Phase A API persistence (DB-backed)."""
import pytest

from tests.conftest import register_and_login, create_brand_with_offer


@pytest.mark.asyncio
async def test_signal_scan_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    post = await api_client.post(
        f"/api/v1/brands/{bid}/signal-scans/recompute", headers=headers,
    )
    assert post.status_code == 200
    data = post.json()
    assert data["status"] == "completed"

    get = await api_client.get(f"/api/v1/brands/{bid}/signal-scans", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1


@pytest.mark.asyncio
async def test_auto_queue_rebuild_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    post = await api_client.post(
        f"/api/v1/brands/{bid}/auto-queue/rebuild", headers=headers,
    )
    assert post.status_code == 200
    data = post.json()
    assert data["status"] == "completed"

    get = await api_client.get(f"/api/v1/brands/{bid}/auto-queue", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert isinstance(rows, list)


@pytest.mark.asyncio
async def test_warmup_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    post = await api_client.post(
        f"/api/v1/brands/{bid}/account-warmup/recompute", headers=headers,
    )
    assert post.status_code == 200
    data = post.json()
    assert data["status"] == "completed"

    get = await api_client.get(f"/api/v1/brands/{bid}/account-warmup", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1


@pytest.mark.asyncio
async def test_account_output_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(f"/api/v1/brands/{bid}/account-warmup/recompute", headers=headers)

    post = await api_client.post(
        f"/api/v1/brands/{bid}/account-output/recompute", headers=headers,
    )
    assert post.status_code == 200

    get = await api_client.get(f"/api/v1/brands/{bid}/account-output", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert isinstance(rows, list)


@pytest.mark.asyncio
async def test_account_maturity_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    get = await api_client.get(f"/api/v1/brands/{bid}/account-maturity", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert isinstance(rows, list)


@pytest.mark.asyncio
async def test_signal_events_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(f"/api/v1/brands/{bid}/signal-scans/recompute", headers=headers)

    get = await api_client.get(f"/api/v1/brands/{bid}/signal-events", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert isinstance(rows, list)
