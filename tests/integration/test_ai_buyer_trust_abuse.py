"""Public-form abuse protection on POST /api/v1/ai-search-authority/score.

Locks in:
  - honeypot rejection (non-empty bot_field → 400)
  - per-IP rate limit (10/h)
  - per-domain rate limit (3/h)
  - valid submission still passes when limits aren't tripped
"""

from __future__ import annotations

import uuid

import packages.db.models  # noqa: F401
import packages.db.models.expansion_pack2_phase_a  # noqa: F401
import packages.db.models.system_events  # noqa: F401
import packages.db.models.proposals  # noqa: F401
import packages.db.models.clients  # noqa: F401
import packages.db.models.fulfillment  # noqa: F401
import packages.db.models.live_execution_phase2  # noqa: F401
import packages.db.models.delivery  # noqa: F401
import packages.db.models.gm_control  # noqa: F401
import packages.db.models.authority_score_reports  # noqa: F401

import pytest

from packages.db.models.core import Brand, Organization

from tests.integration.test_ai_buyer_trust_flow import _patch_scanner  # noqa: E402


async def _seed_org(db_session) -> tuple[uuid.UUID, uuid.UUID]:
    org = Organization(name="ProofHook", slug="proofhook", is_active=True)
    db_session.add(org)
    await db_session.flush()
    brand = Brand(
        organization_id=org.id,
        name="ProofHook",
        slug="proofhook",
        niche="b2b",
        is_active=True,
    )
    db_session.add(brand)
    await db_session.flush()
    await db_session.commit()
    return org.id, brand.id


def _payload(**overrides):
    base = {
        "website_url": "https://acme.io",
        "company_name": "Acme",
        "industry": "B2B SaaS",
        "contact_email": "pat@acme.io",
        "bot_field": "",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_honeypot_non_empty_returns_400(api_client, db_session, monkeypatch):
    await _seed_org(db_session)
    _patch_scanner(monkeypatch)
    r = await api_client.post(
        "/api/v1/ai-search-authority/score",
        json=_payload(bot_field="https://spam.example"),
    )
    assert r.status_code == 400, r.text
    body = r.json()
    assert body["detail"]["field"] == "bot_field"


@pytest.mark.asyncio
async def test_valid_submission_passes_with_empty_honeypot(api_client, db_session, monkeypatch):
    await _seed_org(db_session)
    _patch_scanner(monkeypatch)
    r = await api_client.post(
        "/api/v1/ai-search-authority/score",
        json=_payload(),
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] in ("scored", "failed")


@pytest.mark.asyncio
async def test_per_ip_rate_limit_blocks_eleventh_submission(api_client, db_session, monkeypatch):
    """Insert 10 prior reports with the same fake request_ip directly,
    then attempt an 11th via the public endpoint. Expect 429.

    The starlette TestClient sends `127.0.0.1` as the request IP, so we
    seed reports with `127.0.0.1` to mirror what the real flow would.
    """
    from datetime import datetime, timezone

    from packages.db.models.authority_score_reports import AuthorityScoreReport

    org_id, _ = await _seed_org(db_session)
    _patch_scanner(monkeypatch)

    for i in range(10):
        db_session.add(
            AuthorityScoreReport(
                organization_id=org_id,
                company_name=f"Acme {i}",
                website_url=f"https://acme-{i}.io",
                website_domain=f"acme-{i}.io",
                contact_email=f"buyer-{i}@elsewhere.com",
                industry="other",
                request_ip="127.0.0.1",
                report_status="scored",
                total_score=50,
                authority_score=50,
                created_at=datetime.now(timezone.utc),
                is_active=True,
            )
        )
    await db_session.commit()

    r = await api_client.post(
        "/api/v1/ai-search-authority/score",
        json=_payload(website_url="https://eleventh-domain.io",
                     contact_email="newbuyer@elsewhere.com"),
    )
    assert r.status_code == 429, r.text
    body = r.json()
    assert body["detail"]["kind"] == "ip"
    assert "retry-after" in {k.lower() for k in r.headers.keys()}


@pytest.mark.asyncio
async def test_per_domain_rate_limit_blocks_fourth_submission(
    api_client, db_session, monkeypatch
):
    """Insert 3 prior reports for the same website_domain (different
    IPs), then attempt a 4th from a fresh IP. Expect 429.
    """
    from datetime import datetime, timezone

    from packages.db.models.authority_score_reports import AuthorityScoreReport

    org_id, _ = await _seed_org(db_session)
    _patch_scanner(monkeypatch)

    for i in range(3):
        db_session.add(
            AuthorityScoreReport(
                organization_id=org_id,
                company_name=f"Acme {i}",
                website_url="https://acme.io",
                website_domain="acme.io",
                contact_email=f"buyer-{i}@elsewhere.com",
                industry="other",
                # Use a public-IP shape — the rate limiter doesn't care
                # whether the value is routable, only whether it matches.
                # We use distinct IPs so the per-IP limit doesn't fire
                # before the per-domain limit.
                request_ip=f"203.0.113.{i + 1}",
                report_status="scored",
                total_score=50,
                authority_score=50,
                created_at=datetime.now(timezone.utc),
                is_active=True,
            )
        )
    await db_session.commit()

    r = await api_client.post(
        "/api/v1/ai-search-authority/score",
        json=_payload(),  # website_url=https://acme.io → domain=acme.io
    )
    assert r.status_code == 429, r.text
    body = r.json()
    assert body["detail"]["kind"] == "domain"


@pytest.mark.asyncio
async def test_archived_reports_do_not_count_toward_rate_limit(
    api_client, db_session, monkeypatch
):
    """An archived report (is_active=False) must not consume the rate
    budget. Otherwise operators couldn't archive duplicate spam without
    permanently locking the legitimate prospect out."""
    from datetime import datetime, timezone

    from packages.db.models.authority_score_reports import AuthorityScoreReport

    org_id, _ = await _seed_org(db_session)
    _patch_scanner(monkeypatch)

    for i in range(5):
        db_session.add(
            AuthorityScoreReport(
                organization_id=org_id,
                company_name=f"Old {i}",
                website_url="https://acme.io",
                website_domain="acme.io",
                contact_email=f"old-{i}@elsewhere.com",
                industry="other",
                request_ip="127.0.0.1",
                report_status="archived",
                total_score=50,
                authority_score=50,
                created_at=datetime.now(timezone.utc),
                is_active=False,
            )
        )
    await db_session.commit()

    r = await api_client.post(
        "/api/v1/ai-search-authority/score",
        json=_payload(),
    )
    assert r.status_code == 200, r.text
