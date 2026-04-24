"""Shared test fixtures for the Avatar Revenue OS test suite."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import packages.db.models  # noqa: F401
from packages.db.base import Base

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://avataros:avataros_dev_2026@localhost:5433/avatar_revenue_os_test",
)


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"Test database unreachable ({TEST_DATABASE_URL!r}): {exc}")
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def async_session(db_session):
    """Alias for integration tests that expect `async_session` (same as `db_session`)."""
    yield db_session


@pytest_asyncio.fixture
async def api_client(db_session):
    from apps.api.deps import get_db
    from apps.api.main import app
    from apps.api.rate_limit import auth_rate_limit, recompute_rate_limit

    async def override_get_db():
        yield db_session

    async def noop_rate_limit():
        pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[auth_rate_limit] = noop_rate_limit
    app.dependency_overrides[recompute_rate_limit] = noop_rate_limit

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(api_client):
    """Alias for integration tests that expect `client` (same as `api_client`)."""
    yield api_client


@pytest.fixture
def sample_org_data():
    return {
        "organization_name": f"Test Org {uuid.uuid4().hex[:6]}",
        "email": f"test-{uuid.uuid4().hex[:6]}@example.com",
        "password": "testpass123",
        "full_name": "Test User",
    }


# ---------------------------------------------------------------------------
# Shared auth helpers — use these instead of duplicating register/login logic
# ---------------------------------------------------------------------------


async def register_and_login(api_client: AsyncClient, sample_org_data: dict) -> dict:
    """Register a user, log in, and return Authorization headers.

    Use from tests as:
        headers = await register_and_login(api_client, sample_org_data)
    """
    resp = await api_client.post("/api/v1/auth/register", json=sample_org_data)
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    login_resp = await api_client.post(
        "/api/v1/auth/login",
        json={"email": sample_org_data["email"], "password": sample_org_data["password"]},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    return {"Authorization": f"Bearer {login_resp.json()['access_token']}"}


@pytest_asyncio.fixture
async def auth_headers(api_client, sample_org_data) -> dict:
    """Ready-to-use auth headers fixture. Registers + logs in a fresh user."""
    return await register_and_login(api_client, sample_org_data)


async def create_brand_with_offer(
    api_client: AsyncClient,
    headers: dict,
    *,
    brand_name: str = "Test Brand",
    brand_slug: str | None = None,
    niche: str = "finance",
    offer_name: str = "Test Offer",
    platform: str = "youtube",
    platform_username: str | None = None,
) -> tuple:
    """Create a brand with an offer and a creator account. Returns (brand_id, offer_id, account_id)."""
    slug = brand_slug or f"test-{uuid.uuid4().hex[:6]}"
    username = platform_username or f"@test_{uuid.uuid4().hex[:6]}"

    brand_resp = await api_client.post(
        "/api/v1/brands/",
        json={"name": brand_name, "slug": slug, "niche": niche},
        headers=headers,
    )
    assert brand_resp.status_code == 201, f"Brand creation failed: {brand_resp.text}"
    bid = brand_resp.json()["id"]

    offer_resp = await api_client.post(
        "/api/v1/offers/",
        json={
            "brand_id": bid,
            "name": offer_name,
            "monetization_method": "affiliate",
            "payout_amount": 30.0,
            "epc": 2.0,
            "conversion_rate": 0.04,
        },
        headers=headers,
    )
    assert offer_resp.status_code == 201, f"Offer creation failed: {offer_resp.text}"

    acct_resp = await api_client.post(
        "/api/v1/accounts/",
        json={"brand_id": bid, "platform": platform, "platform_username": username},
        headers=headers,
    )
    assert acct_resp.status_code == 201, f"Account creation failed: {acct_resp.text}"

    return bid, offer_resp.json()["id"], acct_resp.json()["id"]


def make_operator_user(
    org_id,
    *,
    email: str = "operator@example.com",
    password: str = "operatorpass123",
    full_name: str = "Operator User",
):
    """Build a User ORM instance compatible with the real model (hashed_password, role)."""
    from apps.api.services.auth_service import hash_password
    from packages.db.enums import UserRole
    from packages.db.models.core import User

    return User(
        organization_id=org_id,
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=UserRole.OPERATOR,
    )


def create_access_token_for_user(user):
    """Generate a JWT for the given User ORM instance."""
    from apps.api.config import get_settings
    from apps.api.deps import create_access_token

    return create_access_token(user.id, get_settings())
