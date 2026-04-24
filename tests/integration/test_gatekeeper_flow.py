"""DB-backed integration tests for AI Gatekeeper APIs."""

import pytest

GK = "/api/v1/brands/{bid}/gatekeeper"

GET_ENDPOINTS = [
    "completion",
    "truth",
    "execution-closure",
    "tests",
    "dependencies",
    "contradictions",
    "operator-commands",
    "expansion-permissions",
    "alerts",
    "audit-ledger",
]

RECOMPUTE_ENDPOINTS = [
    "completion",
    "truth",
    "execution-closure",
    "tests",
    "dependencies",
    "contradictions",
    "operator-commands",
    "expansion-permissions",
]


async def _auth_brand(api_client, sample_org_data):
    reg = await api_client.post("/api/v1/auth/register", json=sample_org_data)
    assert reg.status_code == 201, reg.text
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": sample_org_data["email"], "password": sample_org_data["password"]},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    brand = await api_client.post(
        "/api/v1/brands/",
        json={"name": "GK Brand", "slug": "gk-brand", "niche": "tech"},
        headers=headers,
    )
    assert brand.status_code == 201, brand.text
    bid = brand.json()["id"]
    return headers, bid


# ── 1. All GETs return 200 and empty lists before any recompute ───────


@pytest.mark.asyncio
async def test_all_gets_empty_before_recompute(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    for ep in GET_ENDPOINTS:
        r = await api_client.get(GK.format(bid=bid) + f"/{ep}", headers=headers)
        assert r.status_code == 200, f"{ep} failed: {r.text}"
        assert isinstance(r.json(), list)
        assert len(r.json()) == 0, f"{ep} should be empty before recompute"


# ── 2–3. Completion gate ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_completion_recompute(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.post(GK.format(bid=bid) + "/completion/recompute", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["rows_processed"] > 0
    assert body["status"] == "completed"


@pytest.mark.asyncio
async def test_completion_get_after_recompute(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(GK.format(bid=bid) + "/completion/recompute", headers=headers)
    r = await api_client.get(GK.format(bid=bid) + "/completion", headers=headers)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) > 0
    for row in rows:
        assert "module_name" in row
        assert "gate_passed" in row
        assert "completion_score" in row
        assert "missing_layers" in row


# ── 4. Truth gate ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_truth_recompute_and_get(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    post = await api_client.post(GK.format(bid=bid) + "/truth/recompute", headers=headers)
    assert post.status_code == 200
    assert post.json()["rows_processed"] > 0

    get = await api_client.get(GK.format(bid=bid) + "/truth", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert len(rows) > 0
    for row in rows:
        assert "module_name" in row
        assert "claimed_status" in row
        assert "actual_status" in row
        assert "gate_passed" in row


# ── 5. Execution Closure gate ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_execution_closure_recompute_and_get(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    post = await api_client.post(GK.format(bid=bid) + "/execution-closure/recompute", headers=headers)
    assert post.status_code == 200
    assert post.json()["rows_processed"] > 0

    get = await api_client.get(GK.format(bid=bid) + "/execution-closure", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert len(rows) > 0
    for row in rows:
        assert "module_name" in row
        assert "dead_end_detected" in row
        assert "gate_passed" in row


# ── 6. Test Sufficiency gate ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_tests_recompute_and_get(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    post = await api_client.post(GK.format(bid=bid) + "/tests/recompute", headers=headers)
    assert post.status_code == 200
    assert post.json()["rows_processed"] > 0

    get = await api_client.get(GK.format(bid=bid) + "/tests", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert len(rows) > 0
    for row in rows:
        assert "module_name" in row
        assert "unit_test_count" in row
        assert "gate_passed" in row


# ── 7. Dependency Readiness gate ──────────────────────────────────────


@pytest.mark.asyncio
async def test_dependencies_recompute_and_get(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    post = await api_client.post(GK.format(bid=bid) + "/dependencies/recompute", headers=headers)
    assert post.status_code == 200
    assert post.json()["status"] == "completed"

    get = await api_client.get(GK.format(bid=bid) + "/dependencies", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert isinstance(rows, list)
    for row in rows:
        assert "module_name" in row
        assert "gate_passed" in row
        assert "blocked_by_external" in row


# ── 8. Contradiction Detection gate ───────────────────────────────────


@pytest.mark.asyncio
async def test_contradictions_recompute_and_get(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    post = await api_client.post(GK.format(bid=bid) + "/contradictions/recompute", headers=headers)
    assert post.status_code == 200
    assert post.json()["status"] == "completed"

    get = await api_client.get(GK.format(bid=bid) + "/contradictions", headers=headers)
    assert get.status_code == 200
    assert isinstance(get.json(), list)


# ── 9. Operator Command Quality gate ─────────────────────────────────


@pytest.mark.asyncio
async def test_operator_commands_recompute_and_get(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    post = await api_client.post(GK.format(bid=bid) + "/operator-commands/recompute", headers=headers)
    assert post.status_code == 200
    assert post.json()["rows_processed"] > 0

    get = await api_client.get(GK.format(bid=bid) + "/operator-commands", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert len(rows) > 0
    for row in rows:
        assert "command_source" in row
        assert "quality_score" in row
        assert "gate_passed" in row


# ── 10. Expansion Permission gate ────────────────────────────────────


@pytest.mark.asyncio
async def test_expansion_permissions_recompute_and_get(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(GK.format(bid=bid) + "/completion/recompute", headers=headers)
    await api_client.post(GK.format(bid=bid) + "/tests/recompute", headers=headers)
    await api_client.post(GK.format(bid=bid) + "/dependencies/recompute", headers=headers)

    post = await api_client.post(GK.format(bid=bid) + "/expansion-permissions/recompute", headers=headers)
    assert post.status_code == 200
    assert post.json()["rows_processed"] > 0

    get = await api_client.get(GK.format(bid=bid) + "/expansion-permissions", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert len(rows) > 0
    for row in rows:
        assert "expansion_target" in row
        assert "permission_granted" in row
        assert "blocking_reasons" in row


# ── 11. Alerts generated after recomputes ─────────────────────────────


@pytest.mark.asyncio
async def test_alerts_generated_after_recomputes(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    for ep in RECOMPUTE_ENDPOINTS:
        r = await api_client.post(GK.format(bid=bid) + f"/{ep}/recompute", headers=headers)
        assert r.status_code == 200, f"{ep} recompute failed: {r.text}"

    get = await api_client.get(GK.format(bid=bid) + "/alerts", headers=headers)
    assert get.status_code == 200
    alerts = get.json()
    assert isinstance(alerts, list)


# ── 12. Expansion blocked when completion not run ────────────────────


@pytest.mark.asyncio
async def test_expansion_blocked_when_incomplete(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    post = await api_client.post(GK.format(bid=bid) + "/expansion-permissions/recompute", headers=headers)
    assert post.status_code == 200

    get = await api_client.get(GK.format(bid=bid) + "/expansion-permissions", headers=headers)
    assert get.status_code == 200
    rows = get.json()
    assert len(rows) > 0
    blocked = [r for r in rows if not r["permission_granted"]]
    assert len(blocked) > 0, "Expansion should be blocked when completion gate has not run"
    for b in blocked:
        assert len(b["blocking_reasons"]) > 0
