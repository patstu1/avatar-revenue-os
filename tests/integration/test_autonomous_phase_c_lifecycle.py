"""Integration tests for Phase C full execution lifecycle (DB-backed).

Tests the closed loop: recompute → propose → approve → execute → complete,
plus paid performance ingestion, batch execute, and operator notifications.
"""
import pytest

from tests.conftest import create_brand_with_offer, register_and_login


@pytest.mark.asyncio
async def test_funnel_lifecycle_propose_approve_execute(api_client, sample_org_data):
    """Full lifecycle: recompute → get record → approve → execute → completed."""
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    # Recompute creates proposals
    post = await api_client.post(
        f"/api/v1/brands/{bid}/funnel-execution/recompute", headers=headers,
    )
    assert post.status_code == 200

    # Get a record
    get = await api_client.get(f"/api/v1/brands/{bid}/funnel-execution", headers=headers)
    rows = get.json()
    assert len(rows) >= 1
    record_id = rows[0]["id"]
    assert rows[0]["run_status"] in ("active", "proposed")

    # Advance to approved
    patch = await api_client.patch(
        f"/api/v1/brands/{bid}/phase-c/funnel_execution/{record_id}/status",
        json={"target_status": "approved", "operator_notes": "Looks good"},
        headers=headers,
    )
    assert patch.status_code == 200
    data = patch.json()
    assert data["new_status"] == "approved"

    # Advance to executing → auto-completes
    patch2 = await api_client.patch(
        f"/api/v1/brands/{bid}/phase-c/funnel_execution/{record_id}/status",
        json={"target_status": "executing"},
        headers=headers,
    )
    assert patch2.status_code == 200
    data2 = patch2.json()
    assert data2["new_status"] == "completed"
    assert data2["execution_notes"]  # executor returned notes


@pytest.mark.asyncio
async def test_sponsor_lifecycle_full_loop(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(
        f"/api/v1/brands/{bid}/sponsor-autonomy/recompute", headers=headers,
    )
    get = await api_client.get(f"/api/v1/brands/{bid}/sponsor-autonomy", headers=headers)
    rows = get.json()
    assert len(rows) >= 2
    record_id = rows[0]["id"]
    assert rows[0]["execution_status"] == "proposed"

    # proposed → approved
    p1 = await api_client.patch(
        f"/api/v1/brands/{bid}/phase-c/sponsor_autonomy/{record_id}/status",
        json={"target_status": "approved"},
        headers=headers,
    )
    assert p1.status_code == 200
    assert p1.json()["new_status"] == "approved"

    # approved → executing → completed
    p2 = await api_client.patch(
        f"/api/v1/brands/{bid}/phase-c/sponsor_autonomy/{record_id}/status",
        json={"target_status": "executing"},
        headers=headers,
    )
    assert p2.status_code == 200
    assert p2.json()["new_status"] == "completed"
    assert p2.json()["execution_notes"]


@pytest.mark.asyncio
async def test_retention_lifecycle_with_rejection(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(
        f"/api/v1/brands/{bid}/retention-autonomy/recompute", headers=headers,
    )
    get = await api_client.get(f"/api/v1/brands/{bid}/retention-autonomy", headers=headers)
    rows = get.json()
    record_id = rows[0]["id"]

    # proposed → rejected
    p = await api_client.patch(
        f"/api/v1/brands/{bid}/phase-c/retention_autonomy/{record_id}/status",
        json={"target_status": "rejected", "operator_notes": "Not appropriate now"},
        headers=headers,
    )
    assert p.status_code == 200
    assert p.json()["new_status"] == "rejected"


@pytest.mark.asyncio
async def test_self_healing_lifecycle_execute(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(
        f"/api/v1/brands/{bid}/recovery-autonomy/recompute", headers=headers,
    )
    get = await api_client.get(f"/api/v1/brands/{bid}/recovery-autonomy", headers=headers)
    data = get.json()
    assert len(data["self_healing"]) >= 1
    heal_id = data["self_healing"][0]["id"]

    # proposed → approved → executing → completed
    await api_client.patch(
        f"/api/v1/brands/{bid}/phase-c/self_healing/{heal_id}/status",
        json={"target_status": "approved"},
        headers=headers,
    )
    p = await api_client.patch(
        f"/api/v1/brands/{bid}/phase-c/self_healing/{heal_id}/status",
        json={"target_status": "executing"},
        headers=headers,
    )
    assert p.status_code == 200
    assert p.json()["new_status"] == "completed"
    assert "Self-healing" in p.json()["execution_notes"] or "self_healing" in p.json()["module"]


@pytest.mark.asyncio
async def test_paid_performance_ingestion_replaces_synthetic(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    # Recompute creates runs with synthetic data
    await api_client.post(
        f"/api/v1/brands/{bid}/paid-operator/recompute", headers=headers,
    )
    get = await api_client.get(f"/api/v1/brands/{bid}/paid-operator", headers=headers)
    data = get.json()
    assert len(data["runs"]) >= 1
    run_id = data["runs"][0]["id"]

    # Ingest real performance data
    perf = await api_client.post(
        f"/api/v1/brands/{bid}/paid-operator/{run_id}/performance",
        json={
            "cpa_actual": 120.0,
            "cpa_target": 50.0,
            "spend_7d": 600.0,
            "conversions_7d": 5,
            "roi_actual": 0.3,
        },
        headers=headers,
    )
    assert perf.status_code == 200
    perf_data = perf.json()
    assert perf_data["data_source"] == "real_ad_platform"
    assert perf_data["decision_type"] in ("stop", "scale", "hold", "budget_adjust")

    # Verify the new decision is visible
    get2 = await api_client.get(f"/api/v1/brands/{bid}/paid-operator", headers=headers)
    new_decisions = get2.json()["decisions"]
    real_decisions = [d for d in new_decisions if "real_ad_platform" in (d.get("explanation") or "")]
    assert len(real_decisions) >= 1


@pytest.mark.asyncio
async def test_batch_execute_approved(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    # Create sponsor actions
    await api_client.post(
        f"/api/v1/brands/{bid}/sponsor-autonomy/recompute", headers=headers,
    )
    get = await api_client.get(f"/api/v1/brands/{bid}/sponsor-autonomy", headers=headers)
    rows = get.json()

    # Approve two of them
    for r in rows[:2]:
        await api_client.patch(
            f"/api/v1/brands/{bid}/phase-c/sponsor_autonomy/{r['id']}/status",
            json={"target_status": "approved"},
            headers=headers,
        )

    # Batch execute
    batch = await api_client.post(
        f"/api/v1/brands/{bid}/phase-c/execute-approved", headers=headers,
    )
    assert batch.status_code == 200
    assert batch.json()["actions_executed"] >= 2


@pytest.mark.asyncio
async def test_invalid_transition_rejected(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(
        f"/api/v1/brands/{bid}/retention-autonomy/recompute", headers=headers,
    )
    get = await api_client.get(f"/api/v1/brands/{bid}/retention-autonomy", headers=headers)
    record_id = get.json()[0]["id"]

    # proposed → completed is NOT valid (must go through approved first)
    p = await api_client.patch(
        f"/api/v1/brands/{bid}/phase-c/retention_autonomy/{record_id}/status",
        json={"target_status": "completed"},
        headers=headers,
    )
    assert p.status_code == 400
    assert "Invalid transition" in p.json()["detail"]


@pytest.mark.asyncio
async def test_operator_notification_endpoint(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    # Create actions and move one to operator_review
    await api_client.post(
        f"/api/v1/brands/{bid}/sponsor-autonomy/recompute", headers=headers,
    )
    get = await api_client.get(f"/api/v1/brands/{bid}/sponsor-autonomy", headers=headers)
    record_id = get.json()[0]["id"]

    await api_client.patch(
        f"/api/v1/brands/{bid}/phase-c/sponsor_autonomy/{record_id}/status",
        json={"target_status": "operator_review"},
        headers=headers,
    )

    # Notify operator
    notify = await api_client.post(
        f"/api/v1/brands/{bid}/phase-c/notify-operator", headers=headers,
    )
    assert notify.status_code == 200
    data = notify.json()
    assert data["notifications_sent"] >= 1
    assert any(item["module"] == "sponsor_autonomy" for item in data["items"])
