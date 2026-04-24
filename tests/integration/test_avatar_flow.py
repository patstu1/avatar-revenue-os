"""Integration tests for avatar CRUD and provider profile persistence."""

import pytest


async def _setup_brand(api_client, sample_org_data) -> tuple[dict, str]:
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login_resp = await api_client.post(
        "/api/v1/auth/login",
        json={
            "email": sample_org_data["email"],
            "password": sample_org_data["password"],
        },
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    brand_resp = await api_client.post(
        "/api/v1/brands/",
        json={
            "name": "Avatar Test Brand",
            "slug": "avatar-test",
        },
        headers=headers,
    )
    return headers, brand_resp.json()["id"]


@pytest.mark.asyncio
async def test_create_avatar(api_client, sample_org_data):
    headers, brand_id = await _setup_brand(api_client, sample_org_data)
    response = await api_client.post(
        "/api/v1/avatars/",
        json={
            "brand_id": brand_id,
            "name": "Test Avatar",
            "persona_description": "A friendly educator",
            "voice_style": "warm",
            "visual_style": "professional",
        },
        headers=headers,
    )
    assert response.status_code == 201
    avatar = response.json()
    assert avatar["name"] == "Test Avatar"
    assert avatar["brand_id"] == brand_id


@pytest.mark.asyncio
async def test_list_avatars(api_client, sample_org_data):
    headers, brand_id = await _setup_brand(api_client, sample_org_data)
    await api_client.post(
        "/api/v1/avatars/",
        json={
            "brand_id": brand_id,
            "name": "Avatar 1",
        },
        headers=headers,
    )
    await api_client.post(
        "/api/v1/avatars/",
        json={
            "brand_id": brand_id,
            "name": "Avatar 2",
        },
        headers=headers,
    )

    response = await api_client.get(f"/api/v1/avatars/?brand_id={brand_id}", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) >= 2


@pytest.mark.asyncio
async def test_delete_avatar(api_client, sample_org_data):
    headers, brand_id = await _setup_brand(api_client, sample_org_data)
    create_resp = await api_client.post(
        "/api/v1/avatars/",
        json={
            "brand_id": brand_id,
            "name": "To Delete",
        },
        headers=headers,
    )
    avatar_id = create_resp.json()["id"]

    response = await api_client.delete(f"/api/v1/avatars/{avatar_id}", headers=headers)
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_avatar_provider_profile_crud(api_client, sample_org_data):
    headers, brand_id = await _setup_brand(api_client, sample_org_data)
    avatar_resp = await api_client.post(
        "/api/v1/avatars/",
        json={
            "brand_id": brand_id,
            "name": "Provider Test Avatar",
        },
        headers=headers,
    )
    avatar_id = avatar_resp.json()["id"]

    # Create avatar provider profile (Tavus)
    response = await api_client.post(
        "/api/v1/providers/avatar",
        json={
            "avatar_id": avatar_id,
            "provider": "tavus",
            "is_primary": True,
            "cost_per_minute": 0.50,
            "capabilities": {"async_video": True, "lip_sync": True},
        },
        headers=headers,
    )
    assert response.status_code == 201
    profile = response.json()
    assert profile["provider"] == "tavus"
    assert profile["is_primary"] is True

    # List avatar providers
    list_resp = await api_client.get(f"/api/v1/providers/avatar?avatar_id={avatar_id}", headers=headers)
    assert response.status_code == 201
    assert len(list_resp.json()) >= 1

    # Update provider
    update_resp = await api_client.patch(
        f"/api/v1/providers/avatar/{profile['id']}",
        json={
            "cost_per_minute": 0.60,
        },
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["cost_per_minute"] == 0.60


@pytest.mark.asyncio
async def test_voice_provider_profile_crud(api_client, sample_org_data):
    headers, brand_id = await _setup_brand(api_client, sample_org_data)
    avatar_resp = await api_client.post(
        "/api/v1/avatars/",
        json={
            "brand_id": brand_id,
            "name": "Voice Test Avatar",
        },
        headers=headers,
    )
    avatar_id = avatar_resp.json()["id"]

    # Create voice provider profile (ElevenLabs)
    response = await api_client.post(
        "/api/v1/providers/voice",
        json={
            "avatar_id": avatar_id,
            "provider": "elevenlabs",
            "is_primary": True,
            "cost_per_minute": 0.30,
            "capabilities": {"voice_cloning": True, "streaming": True},
        },
        headers=headers,
    )
    assert response.status_code == 201
    profile = response.json()
    assert profile["provider"] == "elevenlabs"

    # Create fallback voice (OpenAI Realtime)
    fallback_resp = await api_client.post(
        "/api/v1/providers/voice",
        json={
            "avatar_id": avatar_id,
            "provider": "openai_realtime",
            "is_fallback": True,
            "cost_per_minute": 0.12,
            "capabilities": {"realtime_conversation": True},
        },
        headers=headers,
    )
    assert fallback_resp.status_code == 201
    assert fallback_resp.json()["is_fallback"] is True

    # List voice providers
    list_resp = await api_client.get(f"/api/v1/providers/voice?avatar_id={avatar_id}", headers=headers)
    assert len(list_resp.json()) >= 2


@pytest.mark.asyncio
async def test_unsupported_provider_rejected(api_client, sample_org_data):
    headers, brand_id = await _setup_brand(api_client, sample_org_data)
    avatar_resp = await api_client.post(
        "/api/v1/avatars/",
        json={
            "brand_id": brand_id,
            "name": "Bad Provider Avatar",
        },
        headers=headers,
    )
    avatar_id = avatar_resp.json()["id"]

    response = await api_client.post(
        "/api/v1/providers/avatar",
        json={
            "avatar_id": avatar_id,
            "provider": "nonexistent_provider",
        },
        headers=headers,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_avatar_creation_creates_audit_log(api_client, sample_org_data):
    headers, brand_id = await _setup_brand(api_client, sample_org_data)
    await api_client.post(
        "/api/v1/avatars/",
        json={
            "brand_id": brand_id,
            "name": "Audit Avatar",
        },
        headers=headers,
    )

    audit_resp = await api_client.get("/api/v1/jobs/audit/logs", headers=headers)
    actions = [e["action"] for e in audit_resp.json()["items"]]
    assert "avatar.created" in actions
