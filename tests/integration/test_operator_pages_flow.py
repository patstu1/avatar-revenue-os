"""Integration tests for Batch 5 — minimum operator HTML surfaces.

Verifies every operator page renders 200 with expected core markup and
that form POSTs mutate the right tables.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from packages.db.models.core import User
from packages.db.models.integration_registry import IntegrationProvider


async def _auth(api_client, sample_org_data) -> dict:
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": sample_org_data["email"], "password": sample_org_data["password"]},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_operator_home_renders(api_client, sample_org_data):
    headers = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/operator/", headers=headers)
    assert r.status_code == 200
    assert "Operator home" in r.text
    assert "Queue" in r.text
    assert "Pending drafts" in r.text


@pytest.mark.asyncio
async def test_operator_pipeline_page_renders(api_client, sample_org_data):
    headers = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/operator/pipeline", headers=headers)
    assert r.status_code == 200
    for section in (
        "Reply drafts",
        "Proposals",
        "Payments",
        "Clients",
        "Intakes",
        "Projects",
        "Production jobs",
        "Deliveries",
    ):
        assert section in r.text, f"Missing section {section}"


@pytest.mark.asyncio
async def test_providers_page_renders_and_save(api_client, db_session, sample_org_data):
    headers = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/operator/settings/providers", headers=headers)
    assert r.status_code == 200
    assert "Provider settings" in r.text

    # Save a new provider via form POST
    save = await api_client.post(
        "/api/v1/operator/settings/providers/save",
        headers=headers,
        data={
            "provider_key": "test_provider_xyz",
            "provider_name": "Test Provider",
            "provider_category": "llm",
            "api_key": "sk-test-123",
            "extra_config_json": "",
            "is_enabled": "on",
        },
        follow_redirects=False,
    )
    assert save.status_code == 303

    row = (
        await db_session.execute(
            select(IntegrationProvider).where(IntegrationProvider.provider_key == "test_provider_xyz")
        )
    ).scalar_one()
    assert row.is_enabled is True
    assert row.api_key_encrypted  # stored encrypted


@pytest.mark.asyncio
async def test_inbound_route_page_and_save(api_client, db_session, sample_org_data):
    headers = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/operator/settings/inbound-route", headers=headers)
    assert r.status_code == 200
    assert "Inbound email route" in r.text

    save = await api_client.post(
        "/api/v1/operator/settings/inbound-route/save",
        headers=headers,
        data={
            "match_mode": "to_address",
            "match_value": "reply@test.proofhook.dev",
            "is_enabled": "on",
        },
        follow_redirects=False,
    )
    assert save.status_code == 303

    row = (
        await db_session.execute(
            select(IntegrationProvider).where(IntegrationProvider.provider_key == "inbound_email_route")
        )
    ).scalar_one()
    assert row.extra_config["to_address"] == "reply@test.proofhook.dev"


@pytest.mark.asyncio
async def test_webhooks_page_renders(api_client, sample_org_data):
    headers = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/operator/webhooks", headers=headers)
    assert r.status_code == 200
    assert "Webhooks" in r.text


@pytest.mark.asyncio
async def test_team_page_and_invite(api_client, db_session, sample_org_data):
    headers = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/operator/team", headers=headers)
    assert r.status_code == 200
    assert "Team" in r.text

    new_email = f"invited-{uuid.uuid4().hex[:6]}@example.com"
    invite = await api_client.post(
        "/api/v1/operator/team/invite",
        headers=headers,
        data={
            "email": new_email,
            "full_name": "Invited Person",
            "password": "testpass123",
            "role": "operator",
        },
        follow_redirects=False,
    )
    assert invite.status_code == 303

    u = (await db_session.execute(select(User).where(User.email == new_email))).scalar_one()
    assert u.full_name == "Invited Person"
    assert u.is_active is True


@pytest.mark.asyncio
async def test_gm_board_page_renders(api_client, sample_org_data):
    headers = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/operator/gm", headers=headers)
    assert r.status_code == 200
    assert "GM control board" in r.text
    assert "Awaiting approval" in r.text
    assert "Escalations" in r.text
    assert "Stuck stages" in r.text


@pytest.mark.asyncio
async def test_gm_watcher_run_form(api_client, sample_org_data):
    headers = await _auth(api_client, sample_org_data)
    r = await api_client.post(
        "/api/v1/operator/gm/watcher/run-now",
        headers=headers,
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "flash=" in r.headers["location"]
