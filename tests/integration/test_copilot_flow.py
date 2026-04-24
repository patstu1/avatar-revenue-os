"""DB-backed integration tests for Operator Copilot APIs."""

import pytest


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
        json={"name": "Copilot Brand", "slug": "copilot-brand", "niche": "tech"},
        headers=headers,
    )
    assert brand.status_code == 201, brand.text
    bid = brand.json()["id"]
    return headers, bid


@pytest.mark.asyncio
async def test_sessions_empty_initially(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.get(f"/api/v1/brands/{bid}/copilot/sessions", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_create_session(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.post(
        f"/api/v1/brands/{bid}/copilot/sessions",
        json={"title": "Test"},
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "id" in body
    assert body.get("title") == "Test"


@pytest.mark.asyncio
async def test_list_sessions_after_create(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(
        f"/api/v1/brands/{bid}/copilot/sessions",
        json={"title": "S1"},
        headers=headers,
    )
    r = await api_client.get(f"/api/v1/brands/{bid}/copilot/sessions", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1


@pytest.mark.asyncio
async def test_messages_empty_initially(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    cr = await api_client.post(
        f"/api/v1/brands/{bid}/copilot/sessions",
        json={"title": "Msg test"},
        headers=headers,
    )
    sid = cr.json()["id"]
    r = await api_client.get(f"/api/v1/copilot/sessions/{sid}/messages", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_send_message_and_get_response(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    cr = await api_client.post(
        f"/api/v1/brands/{bid}/copilot/sessions",
        json={"title": "Chat"},
        headers=headers,
    )
    sid = cr.json()["id"]
    r = await api_client.post(
        f"/api/v1/copilot/sessions/{sid}/messages",
        json={"content": "what is blocked", "quick_prompt_key": None},
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    msgs = data.get("messages", [])
    roles = {m.get("role") for m in msgs}
    assert "user" in roles
    assert "assistant" in roles


@pytest.mark.asyncio
async def test_response_has_grounding(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    cr = await api_client.post(
        f"/api/v1/brands/{bid}/copilot/sessions",
        json={"title": "G"},
        headers=headers,
    )
    sid = cr.json()["id"]
    r = await api_client.post(
        f"/api/v1/copilot/sessions/{sid}/messages",
        json={"content": "what is blocked", "quick_prompt_key": None},
        headers=headers,
    )
    assert r.status_code == 200
    assistant = next(m for m in r.json()["messages"] if m["role"] == "assistant")
    assert "grounding_sources" in assistant


@pytest.mark.asyncio
async def test_response_has_truth_boundaries(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    cr = await api_client.post(
        f"/api/v1/brands/{bid}/copilot/sessions",
        json={"title": "T"},
        headers=headers,
    )
    sid = cr.json()["id"]
    r = await api_client.post(
        f"/api/v1/copilot/sessions/{sid}/messages",
        json={"content": "what is blocked", "quick_prompt_key": None},
        headers=headers,
    )
    assert r.status_code == 200
    assistant = next(m for m in r.json()["messages"] if m["role"] == "assistant")
    assert assistant.get("truth_boundaries")
    assert "status" in (assistant["truth_boundaries"] or {})


@pytest.mark.asyncio
async def test_quick_status(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.get(f"/api/v1/brands/{bid}/copilot/quick-status", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "urgency" in body
    assert "blocked_count" in body


@pytest.mark.asyncio
async def test_operator_actions(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.get(f"/api/v1/brands/{bid}/copilot/operator-actions", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_missing_items(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.get(f"/api/v1/brands/{bid}/copilot/missing-items", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_providers(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.get(f"/api/v1/brands/{bid}/copilot/providers", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 20


@pytest.mark.asyncio
async def test_provider_readiness(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.get(f"/api/v1/brands/{bid}/copilot/provider-readiness", headers=headers)
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    for row in rows:
        assert "is_ready" in row
        assert "missing_keys" in row


@pytest.mark.asyncio
async def test_quick_prompt_key_recorded(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    cr = await api_client.post(
        f"/api/v1/brands/{bid}/copilot/sessions",
        json={"title": "QPK"},
        headers=headers,
    )
    sid = cr.json()["id"]
    r = await api_client.post(
        f"/api/v1/copilot/sessions/{sid}/messages",
        json={"content": "What is blocked?", "quick_prompt_key": "what_is_blocked"},
        headers=headers,
    )
    assert r.status_code == 200
    user = next(m for m in r.json()["messages"] if m["role"] == "user")
    assert user.get("quick_prompt_key") == "what_is_blocked"


@pytest.mark.asyncio
async def test_session_message_count_updates(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    cr = await api_client.post(
        f"/api/v1/brands/{bid}/copilot/sessions",
        json={"title": "Count"},
        headers=headers,
    )
    sid = cr.json()["id"]
    for _ in range(2):
        pr = await api_client.post(
            f"/api/v1/copilot/sessions/{sid}/messages",
            json={"content": "ping", "quick_prompt_key": None},
            headers=headers,
        )
        assert pr.status_code == 200
    lst = await api_client.get(f"/api/v1/brands/{bid}/copilot/sessions", headers=headers)
    assert lst.status_code == 200
    sess = next(s for s in lst.json() if s["id"] == sid)
    assert sess.get("message_count", 0) >= 4
