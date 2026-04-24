"""E2E smoke test fixtures — seeded org, brand, accounts, offers, mocks."""
from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from packages.db.base import Base
import packages.db.models  # noqa: F401 — force model registration

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://avataros:avataros_dev_2026@postgres:5432/avatar_revenue_os_test",
)


@pytest_asyncio.fixture(scope="session")
async def e2e_engine():
    """Session-scoped engine — tables created once per test run."""
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
async def db(e2e_engine) -> AsyncGenerator[AsyncSession, None]:
    """Per-test database session with automatic rollback."""
    factory = async_sessionmaker(e2e_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# FastAPI test client (overrides DB + rate limits)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def api(db):
    from apps.api.main import app
    from apps.api.deps import get_db
    from apps.api.rate_limit import auth_rate_limit, recompute_rate_limit

    async def _override_db():
        yield db

    async def _noop():
        pass

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[auth_rate_limit] = _noop
    app.dependency_overrides[recompute_rate_limit] = _noop

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seeded org / brand / account / offer
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seed(api, db):
    """Seed a complete org->brand->account->offer graph and return a namespace."""
    uid = uuid.uuid4().hex[:6]

    # Register + login
    reg = await api.post("/api/v1/auth/register", json={
        "organization_name": f"E2E Org {uid}",
        "email": f"e2e-{uid}@example.com",
        "password": "e2epass123",
        "full_name": "E2E Tester",
    })
    assert reg.status_code == 201, f"Register failed: {reg.text}"

    login = await api.post("/api/v1/auth/login", json={
        "email": f"e2e-{uid}@example.com",
        "password": "e2epass123",
    })
    assert login.status_code == 200, f"Login failed: {login.text}"
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Brand
    brand_resp = await api.post("/api/v1/brands/", json={
        "name": f"E2E Brand {uid}",
        "slug": f"e2e-{uid}",
        "niche": "finance",
    }, headers=headers)
    assert brand_resp.status_code == 201, f"Brand failed: {brand_resp.text}"
    brand_id = brand_resp.json()["id"]

    # Offer
    offer_resp = await api.post("/api/v1/offers/", json={
        "brand_id": brand_id,
        "name": "E2E Test Offer",
        "monetization_method": "affiliate",
        "payout_amount": 30.0,
        "epc": 2.5,
        "conversion_rate": 0.04,
    }, headers=headers)
    assert offer_resp.status_code == 201, f"Offer failed: {offer_resp.text}"
    offer_id = offer_resp.json()["id"]

    # Creator account
    acct_resp = await api.post("/api/v1/accounts/", json={
        "brand_id": brand_id,
        "platform": "youtube",
        "platform_username": f"@e2e_{uid}",
    }, headers=headers)
    assert acct_resp.status_code == 201, f"Account failed: {acct_resp.text}"
    account_id = acct_resp.json()["id"]

    class _Seed:
        pass

    s = _Seed()
    s.headers = headers
    s.brand_id = brand_id
    s.offer_id = offer_id
    s.account_id = account_id
    s.org_id = brand_resp.json().get("organization_id") or reg.json().get("organization_id")
    s.email = f"e2e-{uid}@example.com"
    return s


# ---------------------------------------------------------------------------
# Celery eager mode (tasks execute synchronously in-process)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def celery_eager():
    """Force Celery tasks to run eagerly (synchronously) for E2E tests."""
    from workers.celery_app import app as celery_app

    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )
    yield
    celery_app.conf.update(
        task_always_eager=False,
        task_eager_propagates=False,
    )


# ---------------------------------------------------------------------------
# Mock AI clients
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_ai():
    """Patch AI generation to return deterministic results."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = (
        "This is a generated test script. It covers the key talking points "
        "about the offer. The hook grabs attention immediately. The call to "
        "action drives clicks. Word count is adequate for a short video."
    )
    mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=200, total_tokens=300)

    with patch("openai.AsyncOpenAI", autospec=True) as mock_openai, \
         patch("anthropic.AsyncAnthropic", autospec=True) as mock_anthropic:

        # OpenAI mock
        instance = mock_openai.return_value
        instance.chat.completions.create = AsyncMock(return_value=mock_response)

        # Anthropic mock
        anth_resp = MagicMock()
        anth_resp.content = [MagicMock(text=mock_response.choices[0].message.content)]
        anth_resp.usage = MagicMock(input_tokens=100, output_tokens=200)
        anth_instance = mock_anthropic.return_value
        anth_instance.messages.create = AsyncMock(return_value=anth_resp)

        yield {"openai": instance, "anthropic": anth_instance}


# ---------------------------------------------------------------------------
# Mock SMTP
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_smtp():
    """Mock SMTP so outreach emails are captured, not sent."""
    sent_emails: list[dict] = []

    async def _fake_send(to: str, subject: str, body: str, **kwargs):
        sent_emails.append({"to": to, "subject": subject, "body": body, **kwargs})

    with patch("smtplib.SMTP", autospec=True) as smtp_cls, \
         patch("smtplib.SMTP_SSL", autospec=True) as smtp_ssl_cls:
        for cls in (smtp_cls, smtp_ssl_cls):
            inst = cls.return_value.__enter__ = MagicMock()
            cls.return_value.__exit__ = MagicMock(return_value=False)
            cls.return_value.sendmail = MagicMock()
            cls.return_value.send_message = MagicMock()

        yield {
            "smtp": smtp_cls,
            "smtp_ssl": smtp_ssl_cls,
            "sent": sent_emails,
            "send": _fake_send,
        }


# ---------------------------------------------------------------------------
# Mock webhook payloads
# ---------------------------------------------------------------------------


@pytest.fixture
def webhook_payloads():
    """Factory for common webhook payloads."""

    def _stripe_charge_succeeded(amount_cents: int = 2999, brand_id: str = "", offer_id: str = ""):
        return {
            "id": f"evt_{uuid.uuid4().hex[:12]}",
            "type": "charge.succeeded",
            "data": {
                "object": {
                    "id": f"ch_{uuid.uuid4().hex[:12]}",
                    "amount": amount_cents,
                    "currency": "usd",
                    "metadata": {
                        "brand_id": brand_id,
                        "offer_id": offer_id,
                        "source": "affiliate",
                    },
                },
            },
        }

    def _heygen_video_completed(job_id: str = "", video_url: str = "https://cdn.test/video.mp4"):
        return {
            "event_type": "avatar_video.success",
            "data": {
                "video_id": job_id or uuid.uuid4().hex,
                "status": "completed",
                "video_url": video_url,
                "duration": 45.2,
            },
        }

    def _elevenlabs_voice_completed(job_id: str = "", audio_url: str = "https://cdn.test/audio.mp3"):
        return {
            "event_type": "voice.completed",
            "data": {
                "request_id": job_id or uuid.uuid4().hex,
                "status": "completed",
                "audio_url": audio_url,
                "duration_seconds": 30.5,
            },
        }

    class _Payloads:
        stripe_charge_succeeded = staticmethod(_stripe_charge_succeeded)
        heygen_video_completed = staticmethod(_heygen_video_completed)
        elevenlabs_voice_completed = staticmethod(_elevenlabs_voice_completed)

    return _Payloads()


# ---------------------------------------------------------------------------
# Mock external provider calls (S3, ffmpeg, etc.)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_storage():
    """Mock S3/storage uploads to return predictable URLs."""
    uploaded: list[dict] = []

    async def _fake_upload(file_path: str, bucket: str = "assets", **kwargs):
        url = f"https://s3.test/{bucket}/{uuid.uuid4().hex[:8]}/{file_path.split('/')[-1]}"
        uploaded.append({"file_path": file_path, "bucket": bucket, "url": url})
        return url

    with patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test"}):
        yield {"upload": _fake_upload, "uploaded": uploaded}


@pytest.fixture
def mock_ffmpeg(tmp_path):
    """Mock ffmpeg to create small output files instead of real transcoding."""
    outputs: list[str] = []

    def _fake_run(cmd: list[str], **kwargs):
        # Find output file from command args (usually last arg or after -o)
        output_file = None
        for i, arg in enumerate(cmd):
            if arg == "-o" and i + 1 < len(cmd):
                output_file = cmd[i + 1]
                break
        if output_file is None and len(cmd) > 1:
            # Last argument is often the output
            output_file = cmd[-1]
            if output_file.startswith("-"):
                output_file = None

        if output_file:
            # Create a small placeholder file
            os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
            with open(output_file, "wb") as f:
                f.write(b"\x00" * 1024)  # 1KB placeholder
            outputs.append(output_file)

        return MagicMock(returncode=0, stdout=b"", stderr=b"")

    with patch("subprocess.run", side_effect=_fake_run) as mock_run:
        yield {"run": mock_run, "outputs": outputs, "tmp_path": tmp_path}
