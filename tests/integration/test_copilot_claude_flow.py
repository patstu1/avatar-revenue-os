"""DB-backed integration tests for Claude copilot integration."""

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
        json={"name": "Claude Test Brand", "slug": "claude-test-brand", "niche": "tech"},
        headers=headers,
    )
    bid = brand.json()["id"]
    return headers, bid


async def _create_session_and_send(api_client, headers, bid, message, quick_prompt_key=None):
    sess_r = await api_client.post(
        f"/api/v1/brands/{bid}/copilot/sessions",
        json={"title": "Claude integration test"},
        headers=headers,
    )
    assert sess_r.status_code == 200
    sid = sess_r.json()["id"]

    body = {"content": message}
    if quick_prompt_key:
        body["quick_prompt_key"] = quick_prompt_key

    msg_r = await api_client.post(
        f"/api/v1/copilot/sessions/{sid}/messages",
        json=body,
        headers=headers,
    )
    assert msg_r.status_code == 200
    data = msg_r.json()
    messages = data.get("messages", data) if isinstance(data, dict) else data
    return sid, messages


@pytest.mark.asyncio
async def test_fallback_when_no_claude_key(api_client, sample_org_data, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    headers, bid = await _auth_brand(api_client, sample_org_data)
    _, messages = await _create_session_and_send(api_client, headers, bid, "what is blocked")

    assert isinstance(messages, list)
    assert len(messages) >= 2
    assistant = messages[1]
    assert assistant["role"] == "assistant"
    assert assistant["content"]
    assert assistant["generation_mode"] == "fallback_rule_based"
    assert assistant["generation_model"] == "rule_engine"
    assert assistant["failure_reason"] is not None
    assert "ANTHROPIC_API_KEY" in assistant["failure_reason"]


@pytest.mark.asyncio
async def test_fallback_preserves_grounding(api_client, sample_org_data, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    headers, bid = await _auth_brand(api_client, sample_org_data)
    _, messages = await _create_session_and_send(api_client, headers, bid, "what credentials are missing")

    assistant = messages[1]
    assert assistant["truth_boundaries"]
    assert assistant["truth_boundaries"].get("generation_fallback") is True


@pytest.mark.asyncio
async def test_fallback_preserves_context_hash(api_client, sample_org_data, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    headers, bid = await _auth_brand(api_client, sample_org_data)
    _, messages = await _create_session_and_send(api_client, headers, bid, "what is blocked")

    assistant = messages[1]
    assert assistant.get("context_hash")
    assert len(assistant["context_hash"]) > 0


@pytest.mark.asyncio
async def test_generation_mode_persisted(api_client, sample_org_data, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    headers, bid = await _auth_brand(api_client, sample_org_data)
    sid, _ = await _create_session_and_send(api_client, headers, bid, "which providers are active")

    get_r = await api_client.get(f"/api/v1/copilot/sessions/{sid}/messages", headers=headers)
    assert get_r.status_code == 200
    stored = get_r.json()
    assistant_stored = [m for m in stored if m["role"] == "assistant"][0]
    assert assistant_stored["generation_mode"] == "fallback_rule_based"


@pytest.mark.asyncio
async def test_user_message_has_no_generation_mode(api_client, sample_org_data, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    headers, bid = await _auth_brand(api_client, sample_org_data)
    _, messages = await _create_session_and_send(api_client, headers, bid, "test")

    user_msg = messages[0]
    assert user_msg["role"] == "user"
    assert user_msg.get("generation_mode") is None


@pytest.mark.asyncio
async def test_quick_status_still_works(api_client, sample_org_data, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.get(f"/api/v1/brands/{bid}/copilot/quick-status", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "urgency" in data
    assert "blocked_count" in data


@pytest.mark.asyncio
async def test_empty_context_produces_honest_response(api_client, sample_org_data, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    headers, bid = await _auth_brand(api_client, sample_org_data)
    _, messages = await _create_session_and_send(api_client, headers, bid, "what is the biggest revenue leak")

    assistant = messages[1]
    assert assistant["content"]
    assert assistant["confidence"] > 0
