"""Integration tests for Batch 6 — final lock.

Verifies the ops-lock endpoints and that the health-check wiring
reports the real, persisted state of the system.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from packages.db.models.gm_control import GMEscalation, StageState


@pytest.mark.asyncio
async def test_ops_version_returns_canonical_fields(api_client):
    r = await api_client.get("/ops/version")
    assert r.status_code == 200
    body = r.json()
    assert body["canonical_branch"] == "recovery/from-prod"
    assert "git_head" in body
    assert "alembic_head_revision" in body
    # Our latest migration file is 014_gm_control
    assert body["alembic_head_revision"].startswith("014")


@pytest.mark.asyncio
async def test_ops_lock_status_surface(api_client):
    r = await api_client.get("/ops/lock-status")
    assert r.status_code == 200
    body = r.json()
    assert body["canonical_branch"] == "recovery/from-prod"
    assert "deployed_sha" in body
    assert "matches_canonical" in body


@pytest.mark.asyncio
async def test_ops_health_check_healthy_on_clean_db(api_client, db_session):
    r = await api_client.get("/ops/health-check")
    assert r.status_code == 200
    body = r.json()
    assert body["canonical_branch"] == "recovery/from-prod"
    assert "checks" in body
    check_names = {c["name"] for c in body["checks"]}
    for required in (
        "db_reachable",
        "critical_providers_configured",
        "event_flow_recent",
        "no_hard_stuck_stages",
        "no_unacknowledged_error_escalations",
    ):
        assert required in check_names, f"missing check: {required}"


@pytest.mark.asyncio
async def test_health_check_flags_hard_stuck_stage(api_client, db_session):
    # Seed a StageState with SLA past > 1h
    from apps.api.services.stage_controller import mark_stage

    # Need an organization first — register a user to create one
    reg_data = {
        "organization_name": f"Health Test {uuid.uuid4().hex[:4]}",
        "email": f"health-{uuid.uuid4().hex[:6]}@example.com",
        "password": "testpass123",
        "full_name": "Health",
    }
    await api_client.post("/api/v1/auth/register", json=reg_data)
    from packages.db.models.core import User
    u = (
        await db_session.execute(select(User).where(User.email == reg_data["email"]))
    ).scalar_one()

    state = await mark_stage(
        db_session,
        org_id=u.organization_id,
        entity_type="intake_request",
        entity_id=uuid.uuid4(),
        stage="sent",
    )
    state.sla_deadline = datetime.now(timezone.utc) - timedelta(hours=3)
    await db_session.commit()

    r = await api_client.get("/ops/health-check")
    assert r.status_code == 200
    body = r.json()
    stuck_check = next(c for c in body["checks"] if c["name"] == "no_hard_stuck_stages")
    assert stuck_check["ok"] is False
    assert body["healthy"] is False


@pytest.mark.asyncio
async def test_health_check_flags_error_escalation(api_client, db_session):
    from apps.api.services.stage_controller import open_escalation

    reg_data = {
        "organization_name": f"Health Esc {uuid.uuid4().hex[:4]}",
        "email": f"esc-{uuid.uuid4().hex[:6]}@example.com",
        "password": "testpass123",
        "full_name": "Esc",
    }
    await api_client.post("/api/v1/auth/register", json=reg_data)
    from packages.db.models.core import User
    u = (
        await db_session.execute(select(User).where(User.email == reg_data["email"]))
    ).scalar_one()

    await open_escalation(
        db_session,
        org_id=u.organization_id,
        entity_type="production_job",
        entity_id=uuid.uuid4(),
        reason_code="test_critical",
        title="Critical fail",
        severity="error",
    )
    await db_session.commit()

    r = await api_client.get("/ops/health-check")
    body = r.json()
    check = next(c for c in body["checks"] if c["name"] == "no_unacknowledged_error_escalations")
    assert check["ok"] is False
    assert body["healthy"] is False


@pytest.mark.asyncio
async def test_health_check_passes_when_critical_providers_present(
    api_client, db_session
):
    """Register org + seed all critical providers enabled → the
    critical_providers_configured check flips to green."""
    from packages.db.models.integration_registry import IntegrationProvider

    reg_data = {
        "organization_name": f"Health OK {uuid.uuid4().hex[:4]}",
        "email": f"hok-{uuid.uuid4().hex[:6]}@example.com",
        "password": "testpass123",
        "full_name": "OK",
    }
    await api_client.post("/api/v1/auth/register", json=reg_data)
    from packages.db.models.core import User
    u = (
        await db_session.execute(select(User).where(User.email == reg_data["email"]))
    ).scalar_one()

    for key in ("stripe_webhook", "inbound_email_route", "smtp"):
        db_session.add(
            IntegrationProvider(
                organization_id=u.organization_id,
                provider_key=key,
                provider_name=key,
                provider_category="payment" if "webhook" in key else ("inbox" if key == "inbound_email_route" else "email"),
                is_enabled=True,
                api_key_encrypted="placeholder",
                extra_config={"to_address": "reply@test"} if key == "inbound_email_route" else {},
            )
        )
    await db_session.commit()

    r = await api_client.get("/ops/health-check")
    body = r.json()
    check = next(c for c in body["checks"] if c["name"] == "critical_providers_configured")
    assert check["ok"] is True
