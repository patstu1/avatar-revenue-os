"""Batch 12 — high_ticket onboarding + issue handling close tests."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from apps.api.services.client_activation import start_onboarding
from apps.api.services.high_ticket_onboarding import (
    HIGH_TICKET_INTAKE_SCHEMA,
    ensure_profile,
    record_sow_countersigned,
    record_sow_sent,
    schedule_discovery_call,
    set_kickoff_date,
)
from apps.api.services.high_ticket_issue_service import (
    CRITICAL_THRESHOLD_CENTS,
    WARNING_THRESHOLD_CENTS,
    classify_high_ticket_issue,
    issue_credit,
)
from packages.db.models.clients import (
    Client, ClientHighTicketProfile, ClientOnboardingEvent,
    ClientRetentionEvent, IntakeRequest,
)
from packages.db.models.core import Brand, Organization
from packages.db.models.email_pipeline import (
    EmailMessage, EmailReplyDraft, EmailThread, InboxConnection,
)
from packages.db.models.gm_control import GMEscalation


async def _seed_org_and_ht_client(db_session, sample_org_data):
    name = sample_org_data["organization_name"]
    slug = f"b12-{uuid.uuid4().hex[:10]}"
    org = Organization(name=name, slug=slug)
    db_session.add(org); await db_session.flush()
    brand = Brand(
        organization_id=org.id, name=f"{name} Brand",
        slug=f"{slug}-brand", is_active=True,
    )
    db_session.add(brand); await db_session.flush()
    now = datetime.now(timezone.utc)
    c = Client(
        org_id=org.id, brand_id=brand.id,
        primary_email=f"ht_{uuid.uuid4().hex[:6]}@test.com",
        display_name=f"HT Client {uuid.uuid4().hex[:4]}",
        status="active", activated_at=now, last_paid_at=now,
        total_paid_cents=5_000_000,
        avenue_slug="high_ticket", retention_state="active",
    )
    db_session.add(c); await db_session.flush()
    return org.id, c


# ─────────────────────────────────────────────────────────────────────────
#  1. Intake schema selection
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_onboarding_uses_high_ticket_schema_for_high_ticket_client(
    db_session, sample_org_data
):
    _org_id, client = await _seed_org_and_ht_client(db_session, sample_org_data)
    intake = await start_onboarding(db_session, client=client)
    assert intake.schema_json.get("schema_version") == "high_ticket_v1"
    assert len(intake.schema_json["fields"]) == len(HIGH_TICKET_INTAKE_SCHEMA["fields"])
    field_ids = {f["field_id"] for f in intake.schema_json["fields"]}
    assert "legal_entity_name" in field_ids
    assert "current_monthly_ad_spend" in field_ids
    # Generic fields must NOT be present
    assert "brand_voice" not in field_ids

    # The high-ticket profile row was created at activation time
    profile = (
        await db_session.execute(
            select(ClientHighTicketProfile).where(
                ClientHighTicketProfile.client_id == client.id
            )
        )
    ).scalar_one()
    assert profile.status == "discovery_pending"
    await db_session.commit()


# ─────────────────────────────────────────────────────────────────────────
#  2. 4 onboarding state transitions
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_schedule_discovery_sets_first_class_field(
    db_session, sample_org_data
):
    _o, client = await _seed_org_and_ht_client(db_session, sample_org_data)
    await ensure_profile(db_session, client=client)
    when = datetime.now(timezone.utc) + timedelta(days=3)
    result = await schedule_discovery_call(
        db_session, client=client, when=when,
        attendees=[{"name": "CEO", "email": "ceo@buyer.test"}],
        agenda="Scope the SOW", actor_id="op@test",
    )
    profile = (
        await db_session.execute(
            select(ClientHighTicketProfile).where(
                ClientHighTicketProfile.client_id == client.id
            )
        )
    ).scalar_one()
    assert profile.discovery_call_at is not None
    assert (profile.discovery_attendees_json or {}).get("attendees")[0]["name"] == "CEO"
    assert result["discovery_call_at"]
    await db_session.commit()


@pytest.mark.asyncio
async def test_record_sow_sent_promotes_url_to_first_class(
    db_session, sample_org_data
):
    _o, client = await _seed_org_and_ht_client(db_session, sample_org_data)
    await ensure_profile(db_session, client=client)
    result = await record_sow_sent(
        db_session, client=client,
        sow_url="https://docs.example.com/sow-bigco.pdf",
        signer_email="ceo@buyer.test",
        counterparty_name="Big Co",
        actor_id="op@test",
    )
    profile = (
        await db_session.execute(
            select(ClientHighTicketProfile).where(
                ClientHighTicketProfile.client_id == client.id
            )
        )
    ).scalar_one()
    assert profile.sow_url == "https://docs.example.com/sow-bigco.pdf"
    assert profile.sow_sent_at is not None
    assert profile.counterparty_name == "Big Co"
    assert profile.status == "sow_sent"
    assert result["status"] == "sow_sent"
    await db_session.commit()


@pytest.mark.asyncio
async def test_record_sow_countersigned_is_idempotent(
    db_session, sample_org_data
):
    _o, client = await _seed_org_and_ht_client(db_session, sample_org_data)
    await ensure_profile(db_session, client=client)

    r1 = await record_sow_countersigned(
        db_session, client=client, actor_id="op@test",
    )
    assert r1["already_signed"] is False
    assert r1["sow_countersigned_at"]

    r2 = await record_sow_countersigned(
        db_session, client=client, actor_id="op@test",
    )
    assert r2["already_signed"] is True
    # Only ONE onboarding event should exist for sow_countersigned
    events = (
        await db_session.execute(
            select(ClientOnboardingEvent).where(
                ClientOnboardingEvent.client_id == client.id,
                ClientOnboardingEvent.event_type == "high_ticket.sow_countersigned",
            )
        )
    ).scalars().all()
    assert len(events) == 1
    await db_session.commit()


@pytest.mark.asyncio
async def test_set_kickoff_date_flips_status_and_stores_first_class_ts(
    db_session, sample_org_data
):
    _o, client = await _seed_org_and_ht_client(db_session, sample_org_data)
    await ensure_profile(db_session, client=client)
    future = datetime.now(timezone.utc) + timedelta(days=7)
    r = await set_kickoff_date(
        db_session, client=client, kickoff_at=future,
        team_members=[{"name": "PM", "email": "pm@op.test"}],
        actor_id="op@test",
    )
    profile = (
        await db_session.execute(
            select(ClientHighTicketProfile).where(
                ClientHighTicketProfile.client_id == client.id
            )
        )
    ).scalar_one()
    assert profile.kickoff_at is not None
    assert profile.status == "kickoff_scheduled"
    assert r["status"] == "kickoff_scheduled"

    # Past date → kickoff_complete
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    r2 = await set_kickoff_date(
        db_session, client=client, kickoff_at=past, actor_id="op@test",
    )
    assert r2["status"] == "kickoff_complete"
    await db_session.commit()


# ─────────────────────────────────────────────────────────────────────────
#  3. Issue handling — severity scaling + credit amount_cents rollup
# ─────────────────────────────────────────────────────────────────────────


async def _seed_draft_for_client(db_session, client: Client) -> EmailReplyDraft:
    ic = InboxConnection(
        org_id=client.org_id,
        email_address=f"hti+{uuid.uuid4().hex[:8]}@test.com",
        display_name="HT",
        provider="imap", host="imap.test", port=993, auth_method="oauth",
        credential_provider_key="gmail_oauth",
        status="active", consecutive_failures=0,
        messages_synced_total=0, is_active=True,
    )
    db_session.add(ic); await db_session.flush()
    now = datetime.now(timezone.utc)
    t = EmailThread(
        inbox_connection_id=ic.id, org_id=client.org_id,
        provider_thread_id=f"ht_{uuid.uuid4().hex[:8]}",
        subject="Contract disagreement", direction="inbound",
        sales_stage="issue", reply_status="pending", message_count=1,
        from_email=client.primary_email, from_name=client.display_name,
        first_message_at=now, last_message_at=now, last_inbound_at=now,
        is_active=True, avenue_slug="high_ticket",
    )
    db_session.add(t); await db_session.flush()
    m = EmailMessage(
        thread_id=t.id, inbox_connection_id=ic.id, org_id=client.org_id,
        provider_message_id=f"m_{uuid.uuid4().hex[:8]}",
        direction="inbound", from_email=client.primary_email,
        subject="Contract clarification", snippet="We need to discuss",
        message_date=now, size_bytes=50, is_active=True,
        avenue_slug="high_ticket",
    )
    db_session.add(m); await db_session.flush()
    d = EmailReplyDraft(
        thread_id=t.id, message_id=m.id, org_id=client.org_id,
        to_email=client.primary_email, subject="Re: Contract",
        body_text="Let's sync", reply_mode="draft", status="pending",
        confidence=0.6, is_active=True, avenue_slug="high_ticket",
    )
    db_session.add(d); await db_session.flush()
    return d


@pytest.mark.asyncio
async def test_classify_high_ticket_issue_severity_scales_with_dollars(
    db_session, sample_org_data
):
    _o, client = await _seed_org_and_ht_client(db_session, sample_org_data)
    d_critical = await _seed_draft_for_client(db_session, client)
    r1 = await classify_high_ticket_issue(
        db_session, draft=d_critical, subtype="scope_creep",
        affected_cents=CRITICAL_THRESHOLD_CENTS + 100,
        actor_id="op@test",
    )
    assert r1["severity"] == "critical"

    d_warning = await _seed_draft_for_client(db_session, client)
    r2 = await classify_high_ticket_issue(
        db_session, draft=d_warning, subtype="timeline_slip",
        affected_cents=WARNING_THRESHOLD_CENTS + 50,
        actor_id="op@test",
    )
    assert r2["severity"] == "warning"

    d_info = await _seed_draft_for_client(db_session, client)
    r3 = await classify_high_ticket_issue(
        db_session, draft=d_info, subtype="deliverable_dispute",
        affected_cents=500,  # $5
        actor_id="op@test",
    )
    assert r3["severity"] == "info"

    # All three escalations have reason_code prefix high_ticket_
    escs = (
        await db_session.execute(
            select(GMEscalation).where(
                GMEscalation.org_id == client.org_id,
                GMEscalation.reason_code.like("high_ticket_%"),
            )
        )
    ).scalars().all()
    reasons = {e.reason_code for e in escs}
    assert {"high_ticket_scope_creep", "high_ticket_timeline_slip",
            "high_ticket_deliverable_dispute"}.issubset(reasons)
    await db_session.commit()


@pytest.mark.asyncio
async def test_issue_credit_writes_amount_cents_first_class(
    db_session, sample_org_data
):
    _o, client = await _seed_org_and_ht_client(db_session, sample_org_data)
    r = await issue_credit(
        db_session, client=client,
        amount_cents=5_000_00,  # $5,000
        reason="Scope creep remedy",
        actor_id="op@test",
    )
    assert r["amount_cents"] == 5_000_00
    evt = (
        await db_session.execute(
            select(ClientRetentionEvent).where(
                ClientRetentionEvent.id == uuid.UUID(r["retention_event_id"])
            )
        )
    ).scalar_one()
    # First-class column, not JSONB extraction
    assert evt.amount_cents == 5_000_00
    assert evt.event_type == "high_ticket.credit_issued"
    await db_session.commit()


@pytest.mark.asyncio
async def test_issue_credit_rejects_non_positive_amount(
    db_session, sample_org_data
):
    _o, client = await _seed_org_and_ht_client(db_session, sample_org_data)
    with pytest.raises(ValueError):
        await issue_credit(
            db_session, client=client,
            amount_cents=0, reason="x", actor_id="op@test",
        )


@pytest.mark.asyncio
async def test_classify_rejects_unknown_subtype(db_session, sample_org_data):
    _o, client = await _seed_org_and_ht_client(db_session, sample_org_data)
    d = await _seed_draft_for_client(db_session, client)
    with pytest.raises(ValueError):
        await classify_high_ticket_issue(
            db_session, draft=d, subtype="totally_made_up",
            affected_cents=100, actor_id="op@test",
        )


# ─────────────────────────────────────────────────────────────────────────
#  4. Endpoint registration + auth tests
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_batch12_endpoints_all_registered(api_client):
    r = await api_client.get("/openapi.json")
    paths = set(r.json()["paths"].keys())
    for p in (
        "/api/v1/gm/write/clients/{client_id}/high-ticket/schedule-discovery",
        "/api/v1/gm/write/clients/{client_id}/high-ticket/sow-sent",
        "/api/v1/gm/write/clients/{client_id}/high-ticket/sow-countersigned",
        "/api/v1/gm/write/clients/{client_id}/high-ticket/kickoff",
        "/api/v1/gm/write/issues/drafts/{draft_id}/high-ticket-classify",
        "/api/v1/gm/write/clients/{client_id}/high-ticket/credit",
    ):
        assert p in paths, f"missing Batch 12 endpoint {p}"


@pytest.mark.asyncio
async def test_batch12_endpoints_require_auth(api_client):
    stub = "00000000-0000-0000-0000-000000000000"
    checks = [
        ("POST", f"/api/v1/gm/write/clients/{stub}/high-ticket/schedule-discovery",
         {"when_iso": "2026-05-01T00:00:00Z"}),
        ("POST", f"/api/v1/gm/write/clients/{stub}/high-ticket/sow-sent",
         {"sow_url": "https://x"}),
        ("POST", f"/api/v1/gm/write/clients/{stub}/high-ticket/sow-countersigned", {}),
        ("POST", f"/api/v1/gm/write/clients/{stub}/high-ticket/kickoff",
         {"kickoff_at_iso": "2026-05-05T00:00:00Z"}),
        ("POST", f"/api/v1/gm/write/issues/drafts/{stub}/high-ticket-classify",
         {"subtype": "scope_creep", "affected_cents": 0}),
        ("POST", f"/api/v1/gm/write/clients/{stub}/high-ticket/credit",
         {"amount_cents": 100, "reason": "x"}),
    ]
    for method, path, body in checks:
        r = await api_client.request(method, path, json=body)
        assert r.status_code == 401, f"{path} must 401 (got {r.status_code})"
