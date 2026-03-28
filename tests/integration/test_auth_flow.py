"""Integration tests for the authentication flow."""
import pytest


@pytest.mark.asyncio
async def test_health_check(api_client):
    response = await api_client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "avatar-revenue-os-api"


@pytest.mark.asyncio
async def test_register_and_login(api_client, sample_org_data):
    # Register
    response = await api_client.post("/api/v1/auth/register", json=sample_org_data)
    assert response.status_code == 201
    user = response.json()
    assert user["email"] == sample_org_data["email"]
    assert user["role"] == "admin"

    # Login
    response = await api_client.post("/api/v1/auth/login", json={
        "email": sample_org_data["email"],
        "password": sample_org_data["password"],
    })
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data

    # Get current user
    headers = {"Authorization": f"Bearer {token_data['access_token']}"}
    response = await api_client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    me = response.json()
    assert me["email"] == sample_org_data["email"]


@pytest.mark.asyncio
async def test_register_duplicate_email(api_client, sample_org_data):
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    response = await api_client.post("/api/v1/auth/register", json=sample_org_data)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_invalid_credentials(api_client):
    response = await api_client.post("/api/v1/auth/login", json={
        "email": "nonexistent@example.com",
        "password": "wrong",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_without_token(api_client):
    response = await api_client.get("/api/v1/brands")
    assert response.status_code == 401
