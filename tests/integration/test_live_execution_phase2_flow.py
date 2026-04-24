"""Integration tests for Live Execution Phase 2 + Buffer Expansion APIs."""

import pytest


async def _auth_brand(api_client, sample_org_data):
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": sample_org_data["email"], "password": sample_org_data["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    brand = await api_client.post(
        "/api/v1/brands/",
        json={"name": "LEC2 Brand", "slug": "lec2-brand", "niche": "tech"},
        headers=headers,
    )
    bid = brand.json()["id"]
    return headers, bid


@pytest.mark.asyncio
async def test_gets_empty_before_data(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    for path in [
        f"/api/v1/brands/{bid}/webhook-events",
        f"/api/v1/brands/{bid}/event-ingestions",
        f"/api/v1/brands/{bid}/sequence-triggers",
        f"/api/v1/brands/{bid}/payment-syncs",
        f"/api/v1/brands/{bid}/analytics-syncs",
        f"/api/v1/brands/{bid}/ad-imports",
        f"/api/v1/brands/{bid}/buffer-execution-truth",
        f"/api/v1/brands/{bid}/buffer-retries",
        f"/api/v1/brands/{bid}/buffer-capabilities",
    ]:
        r = await api_client.get(path, headers=headers)
        assert r.status_code == 200, f"GET {path} returned {r.status_code}"
        body = r.json()
        assert body == [] or body == {}, f"Expected empty for {path}"


@pytest.mark.asyncio
async def test_webhook_ingest_and_list(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    payload = {
        "source": "stripe",
        "source_category": "payment",
        "event_type": "checkout.completed",
        "idempotency_key": "test-1",
    }
    post = await api_client.post(
        f"/api/v1/brands/{bid}/webhook-events",
        json=payload,
        headers=headers,
    )
    assert post.status_code == 200

    listed = await api_client.get(f"/api/v1/brands/{bid}/webhook-events", headers=headers)
    assert listed.status_code == 200
    data = listed.json()
    assert len(data) >= 1
    row = data[0]
    assert row["source"] == "stripe"
    assert row["event_type"] == "checkout.completed"
    assert row.get("idempotency_key") == "test-1"


@pytest.mark.asyncio
async def test_idempotent_webhook(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    payload = {
        "source": "stripe",
        "source_category": "payment",
        "event_type": "checkout.completed",
        "idempotency_key": "idem-dup-1",
    }
    first = await api_client.post(
        f"/api/v1/brands/{bid}/webhook-events",
        json=payload,
        headers=headers,
    )
    assert first.status_code == 200
    second = await api_client.post(
        f"/api/v1/brands/{bid}/webhook-events",
        json=payload,
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json().get("status") == "duplicate"

    listed = await api_client.get(f"/api/v1/brands/{bid}/webhook-events", headers=headers)
    keys = [r.get("idempotency_key") for r in listed.json()]
    assert keys.count("idem-dup-1") == 1


@pytest.mark.asyncio
async def test_event_ingestions_recompute(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.post(
        f"/api/v1/brands/{bid}/event-ingestions/recompute",
        headers=headers,
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_sequence_triggers_process(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.post(
        f"/api/v1/brands/{bid}/sequence-triggers/process",
        headers=headers,
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_payment_sync_run(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.post(
        f"/api/v1/brands/{bid}/payment-syncs/run",
        headers=headers,
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_analytics_sync_run(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.post(
        f"/api/v1/brands/{bid}/analytics-syncs/run",
        headers=headers,
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_ad_import_run(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.post(
        f"/api/v1/brands/{bid}/ad-imports/run",
        headers=headers,
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_buffer_truth_recompute(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.post(
        f"/api/v1/brands/{bid}/buffer-execution-truth/recompute",
        headers=headers,
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_buffer_retries_recompute(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.post(
        f"/api/v1/brands/{bid}/buffer-retries/recompute",
        headers=headers,
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_buffer_capabilities_recompute(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.post(
        f"/api/v1/brands/{bid}/buffer-capabilities/recompute",
        headers=headers,
    )
    assert r.status_code == 200


def test_celery_tasks_registered():
    import workers.live_execution_phase2_worker.tasks  # noqa: F401
    from workers.celery_app import app

    for name in (
        "workers.live_execution_phase2_worker.tasks.process_webhook_events",
        "workers.live_execution_phase2_worker.tasks.process_sequence_triggers",
        "workers.live_execution_phase2_worker.tasks.run_payment_connector_sync",
        "workers.live_execution_phase2_worker.tasks.run_analytics_auto_pull",
        "workers.live_execution_phase2_worker.tasks.run_ad_reporting_import",
        "workers.live_execution_phase2_worker.tasks.recompute_buffer_execution_truth",
        "workers.live_execution_phase2_worker.tasks.detect_stale_buffer_jobs",
        "workers.live_execution_phase2_worker.tasks.recompute_buffer_capabilities",
    ):
        assert name in app.tasks, f"Task {name} not registered"
