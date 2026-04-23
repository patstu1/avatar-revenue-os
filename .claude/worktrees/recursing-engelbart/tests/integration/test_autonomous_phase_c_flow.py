"""Integration tests for Autonomous Phase C API persistence (DB-backed)."""
import pytest

from tests.conftest import register_and_login, create_brand_with_offer


@pytest.mark.asyncio
async def test_funnel_execution_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    post = await api_client.post(
        f"/api/v1/brands/{bid}/funnel-execution/recompute",
        headers=headers,
    )
    assert post.status_code == 200
    assert post.json().get("status") == "completed"

    get = await api_client.get(f"/api/v1/brands/{bid}/funnel-execution", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert "funnel_action" in rows[0]


@pytest.mark.asyncio
async def test_paid_operator_persists_runs_and_decisions(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    post = await api_client.post(
        f"/api/v1/brands/{bid}/paid-operator/recompute",
        headers=headers,
    )
    assert post.status_code == 200

    get = await api_client.get(f"/api/v1/brands/{bid}/paid-operator", headers=headers)
    assert get.status_code == 200
    data = get.json()
    assert "runs" in data and "decisions" in data
    assert len(data["runs"]) >= 1
    assert len(data["decisions"]) >= 1


@pytest.mark.asyncio
async def test_sponsor_autonomy_recompute_and_list(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    post = await api_client.post(
        f"/api/v1/brands/{bid}/sponsor-autonomy/recompute",
        headers=headers,
    )
    assert post.status_code == 200
    assert post.json().get("status") == "completed"
    counts = post.json().get("counts", {})
    assert counts.get("sponsor_actions_created", 0) >= 2  # at least rank_categories + outreach

    get = await api_client.get(f"/api/v1/brands/{bid}/sponsor-autonomy", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert isinstance(rows, list)
    assert len(rows) >= 2
    actions = {r["sponsor_action"] for r in rows}
    assert "rank_categories" in actions
    assert "generate_outreach_sequence" in actions
    for r in rows:
        assert r["pipeline_stage"] in ("inventory", "strategy", "outreach", "renewal", "prospect")
        assert r["expected_deal_value"] >= 0
        assert r["confidence"] > 0
        assert r["explanation"]


@pytest.mark.asyncio
async def test_retention_autonomy_recompute(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    post = await api_client.post(
        f"/api/v1/brands/{bid}/retention-autonomy/recompute",
        headers=headers,
    )
    assert post.status_code == 200

    get = await api_client.get(f"/api/v1/brands/{bid}/retention-autonomy", headers=headers)
    assert get.status_code == 200
    assert len(get.json()) >= 1


@pytest.mark.asyncio
async def test_recovery_autonomy_escalation_and_self_healing(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    post = await api_client.post(
        f"/api/v1/brands/{bid}/recovery-autonomy/recompute",
        headers=headers,
    )
    assert post.status_code == 200

    get = await api_client.get(f"/api/v1/brands/{bid}/recovery-autonomy", headers=headers)
    assert get.status_code == 200
    data = get.json()
    assert "escalations" in data and "self_healing" in data
    assert len(data["escalations"]) >= 1
    assert len(data["self_healing"]) >= 1
