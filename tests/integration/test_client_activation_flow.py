"""Integration tests for Batch 3B — paid-client activation + intake start.

Covers:
  1. Stripe webhook → payment.completed → client.created +
     onboarding.started + intake.sent.
  2. Duplicate Stripe event does NOT duplicate Client or IntakeRequest
     (short-circuited by webhook_events idempotency).
  3. Same email across two different Stripe events reuses the existing
     Client, updates total_paid_cents + last_paid_at, does NOT
     re-emit client.created.
  4. GET /intake/{token} surfaces the schema, marks status=viewed.
  5. POST /intake/{token}/submit with all required fields ->
     is_complete=True, intake.completed event, IntakeRequest.status=completed.
  6. POST /intake/{token}/submit with missing fields -> is_complete=False,
     NO intake.completed event, status stays viewed/sent.
  7. GET /clients and GET /clients/{id} return org-scoped records.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from packages.db.models.clients import (
    Client,
    ClientOnboardingEvent,
    IntakeRequest,
    IntakeSubmission,
)
from packages.db.models.proposals import Payment
from packages.db.models.system_events import SystemEvent


async def _auth(api_client, sample_org_data) -> tuple[dict, uuid.UUID]:
    reg = await api_client.post("/api/v1/auth/register", json=sample_org_data)
    assert reg.status_code == 201, reg.text
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": sample_org_data["email"], "password": sample_org_data["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = await api_client.get("/api/v1/auth/me", headers=headers)
    return headers, uuid.UUID(me.json()["organization_id"])


async def _seed_proposal_with_payment_link(
    api_client, db_session, headers, monkeypatch, recipient_email: str
) -> tuple[uuid.UUID, uuid.UUID]:
    """Create a proposal + payment link. Returns (proposal_id, payment_link_id)."""

    async def _fake_create_link(**kwargs):
        return {"url": "https://checkout.stripe.com/test", "id": "plink_client_act"}

    from apps.api.services import stripe_billing_service

    monkeypatch.setattr(stripe_billing_service, "create_payment_link", _fake_create_link)

    create = await api_client.post(
        "/api/v1/proposals",
        headers=headers,
        json={
            "recipient_email": recipient_email,
            "recipient_name": "Pat Customer",
            "title": "Growth Pack — Activation Test",
            "line_items": [{"description": "Pack", "unit_amount_cents": 150000}],
        },
    )
    pid = uuid.UUID(create.json()["id"])
    link = await api_client.post(f"/api/v1/proposals/{pid}/payment-link", headers=headers, json={})
    plid = uuid.UUID(link.json()["id"])
    return pid, plid


def _fake_stripe_payload(event_id: str, proposal_id: uuid.UUID, org_id: uuid.UUID, email: str) -> dict:
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": f"cs_test_{uuid.uuid4().hex[:10]}",
                "amount_total": 150000,
                "currency": "usd",
                "payment_intent": f"pi_test_{uuid.uuid4().hex[:10]}",
                "customer_email": email,
                "customer_details": {"name": "Pat Customer"},
                "payment_link": "plink_client_act",
                "metadata": {
                    "proposal_id": str(proposal_id),
                    "org_id": str(org_id),
                    "source": "proposal",
                },
            }
        },
    }


def _make_webhook_verify_patcher(payload: dict, event_id: str):
    async def _fake_verify(**kwargs):
        return {
            "valid": True,
            "event_id": event_id,
            "event_type": "checkout.session.completed",
            "payload": payload,
        }, None

    return _fake_verify


@pytest.mark.asyncio
async def test_payment_completed_creates_client_and_starts_onboarding(
    api_client, db_session, sample_org_data, monkeypatch
):
    headers, org_id = await _auth(api_client, sample_org_data)
    email = f"founder-{uuid.uuid4().hex[:6]}@acme.example"
    proposal_id, _ = await _seed_proposal_with_payment_link(api_client, db_session, headers, monkeypatch, email)

    event_id = f"evt_act_{uuid.uuid4().hex[:12]}"
    payload = _fake_stripe_payload(event_id, proposal_id, org_id, email)

    from apps.api.routers import webhooks as webhooks_mod

    monkeypatch.setattr(
        webhooks_mod,
        "_verify_webhook_with_candidates",
        _make_webhook_verify_patcher(payload, event_id),
    )

    r = await api_client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": "fake"},
        content=b"{}",
    )
    assert r.status_code == 200, r.text

    # Client created
    client = (
        await db_session.execute(
            select(Client).where(
                Client.org_id == org_id,
                Client.primary_email == email,
            )
        )
    ).scalar_one()
    assert client.status == "active"
    assert client.first_proposal_id == proposal_id
    assert client.total_paid_cents == 150000

    # IntakeRequest created, status=sent
    intake = (await db_session.execute(select(IntakeRequest).where(IntakeRequest.client_id == client.id))).scalar_one()
    assert intake.status == "sent"
    assert intake.token  # token is populated
    assert intake.sent_at is not None

    # Events: client.created + onboarding.started + intake.sent
    event_types = (
        (
            await db_session.execute(
                select(SystemEvent.event_type).where(
                    SystemEvent.event_domain == "fulfillment",
                    SystemEvent.organization_id == org_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert "client.created" in event_types
    assert "onboarding.started" in event_types
    assert "intake.sent" in event_types

    # ClientOnboardingEvent rows
    onb_events = (
        (await db_session.execute(select(ClientOnboardingEvent).where(ClientOnboardingEvent.client_id == client.id)))
        .scalars()
        .all()
    )
    types = {e.event_type for e in onb_events}
    assert "onboarding.started" in types
    assert "intake.sent" in types


@pytest.mark.asyncio
async def test_duplicate_stripe_event_does_not_duplicate_client(api_client, db_session, sample_org_data, monkeypatch):
    headers, org_id = await _auth(api_client, sample_org_data)
    email = f"dedup-{uuid.uuid4().hex[:6]}@acme.example"
    proposal_id, _ = await _seed_proposal_with_payment_link(api_client, db_session, headers, monkeypatch, email)

    event_id = f"evt_dup_{uuid.uuid4().hex[:12]}"
    payload = _fake_stripe_payload(event_id, proposal_id, org_id, email)
    from apps.api.routers import webhooks as webhooks_mod

    monkeypatch.setattr(
        webhooks_mod,
        "_verify_webhook_with_candidates",
        _make_webhook_verify_patcher(payload, event_id),
    )

    await api_client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": "fake"},
        content=b"{}",
    )
    # Second call — same event_id
    await api_client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": "fake"},
        content=b"{}",
    )

    clients = (
        (
            await db_session.execute(
                select(Client).where(
                    Client.org_id == org_id,
                    Client.primary_email == email,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(clients) == 1
    intakes = (
        (await db_session.execute(select(IntakeRequest).where(IntakeRequest.client_id == clients[0].id)))
        .scalars()
        .all()
    )
    assert len(intakes) == 1

    # Exactly one client.created event for this org
    evts = (
        (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "client.created",
                    SystemEvent.organization_id == org_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(evts) == 1


@pytest.mark.asyncio
async def test_second_payment_reuses_client_updates_totals(api_client, db_session, sample_org_data, monkeypatch):
    headers, org_id = await _auth(api_client, sample_org_data)
    email = f"repeat-{uuid.uuid4().hex[:6]}@acme.example"
    proposal_id, _ = await _seed_proposal_with_payment_link(api_client, db_session, headers, monkeypatch, email)

    # First payment
    from apps.api.routers import webhooks as webhooks_mod

    event_id_1 = f"evt_first_{uuid.uuid4().hex[:12]}"
    monkeypatch.setattr(
        webhooks_mod,
        "_verify_webhook_with_candidates",
        _make_webhook_verify_patcher(_fake_stripe_payload(event_id_1, proposal_id, org_id, email), event_id_1),
    )
    await api_client.post("/api/v1/webhooks/stripe", headers={"Stripe-Signature": "fake"}, content=b"{}")

    # Second payment with DIFFERENT event_id (Stripe recurring/renewal case)
    event_id_2 = f"evt_second_{uuid.uuid4().hex[:12]}"
    monkeypatch.setattr(
        webhooks_mod,
        "_verify_webhook_with_candidates",
        _make_webhook_verify_patcher(_fake_stripe_payload(event_id_2, proposal_id, org_id, email), event_id_2),
    )
    await api_client.post("/api/v1/webhooks/stripe", headers={"Stripe-Signature": "fake"}, content=b"{}")

    # One Client, two Payments, client.total_paid_cents == 300000
    clients = (
        (
            await db_session.execute(
                select(Client).where(
                    Client.org_id == org_id,
                    Client.primary_email == email,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(clients) == 1
    assert clients[0].total_paid_cents == 300000

    payments = (await db_session.execute(select(Payment).where(Payment.org_id == org_id))).scalars().all()
    assert len(payments) == 2

    # Only ONE client.created event
    evts = (
        (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "client.created",
                    SystemEvent.organization_id == org_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(evts) == 1


@pytest.mark.asyncio
async def test_intake_public_view_marks_viewed(api_client, db_session, sample_org_data, monkeypatch):
    headers, org_id = await _auth(api_client, sample_org_data)
    email = f"view-{uuid.uuid4().hex[:6]}@acme.example"
    proposal_id, _ = await _seed_proposal_with_payment_link(api_client, db_session, headers, monkeypatch, email)
    event_id = f"evt_view_{uuid.uuid4().hex[:12]}"
    from apps.api.routers import webhooks as webhooks_mod

    monkeypatch.setattr(
        webhooks_mod,
        "_verify_webhook_with_candidates",
        _make_webhook_verify_patcher(_fake_stripe_payload(event_id, proposal_id, org_id, email), event_id),
    )
    await api_client.post("/api/v1/webhooks/stripe", headers={"Stripe-Signature": "fake"}, content=b"{}")

    intake = (await db_session.execute(select(IntakeRequest).where(IntakeRequest.org_id == org_id))).scalar_one()

    r = await api_client.get(f"/api/v1/intake/{intake.token}")
    assert r.status_code == 200
    body = r.json()
    assert body["title"]
    assert "schema" in body
    assert body["completed"] is False

    await db_session.refresh(intake)
    assert intake.status == "viewed"
    assert intake.first_viewed_at is not None


@pytest.mark.asyncio
async def test_intake_submit_complete_fires_intake_completed(api_client, db_session, sample_org_data, monkeypatch):
    headers, org_id = await _auth(api_client, sample_org_data)
    email = f"submit-{uuid.uuid4().hex[:6]}@acme.example"
    proposal_id, _ = await _seed_proposal_with_payment_link(api_client, db_session, headers, monkeypatch, email)
    event_id = f"evt_submit_{uuid.uuid4().hex[:12]}"
    from apps.api.routers import webhooks as webhooks_mod

    monkeypatch.setattr(
        webhooks_mod,
        "_verify_webhook_with_candidates",
        _make_webhook_verify_patcher(_fake_stripe_payload(event_id, proposal_id, org_id, email), event_id),
    )
    await api_client.post("/api/v1/webhooks/stripe", headers={"Stripe-Signature": "fake"}, content=b"{}")

    intake = (await db_session.execute(select(IntakeRequest).where(IntakeRequest.org_id == org_id))).scalar_one()

    r = await api_client.post(
        f"/api/v1/intake/{intake.token}/submit",
        json={
            "submitter_email": email,
            "responses": {
                "company_name": "Acme Brand",
                "primary_contact": "Pat Customer",
                "target_audience": "SaaS founders in growth stage",
                "goals": "Grow owned audience to 50k in 90 days",
            },
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["is_complete"] is True
    assert body["missing_fields"] == []
    assert body["intake_status"] == "completed"

    # intake.completed event fired
    evt = (
        await db_session.execute(
            select(SystemEvent).where(
                SystemEvent.event_type == "intake.completed",
                SystemEvent.entity_id == intake.id,
            )
        )
    ).scalar_one()
    assert evt.new_state == "completed"

    # Submission persisted, intake flipped to completed
    await db_session.refresh(intake)
    assert intake.status == "completed"
    assert intake.completed_at is not None

    sub = (
        await db_session.execute(select(IntakeSubmission).where(IntakeSubmission.intake_request_id == intake.id))
    ).scalar_one()
    assert sub.is_complete is True


@pytest.mark.asyncio
async def test_intake_submit_missing_required_stays_open(api_client, db_session, sample_org_data, monkeypatch):
    headers, org_id = await _auth(api_client, sample_org_data)
    email = f"partial-{uuid.uuid4().hex[:6]}@acme.example"
    proposal_id, _ = await _seed_proposal_with_payment_link(api_client, db_session, headers, monkeypatch, email)
    event_id = f"evt_partial_{uuid.uuid4().hex[:12]}"
    from apps.api.routers import webhooks as webhooks_mod

    monkeypatch.setattr(
        webhooks_mod,
        "_verify_webhook_with_candidates",
        _make_webhook_verify_patcher(_fake_stripe_payload(event_id, proposal_id, org_id, email), event_id),
    )
    await api_client.post("/api/v1/webhooks/stripe", headers={"Stripe-Signature": "fake"}, content=b"{}")

    intake = (await db_session.execute(select(IntakeRequest).where(IntakeRequest.org_id == org_id))).scalar_one()

    r = await api_client.post(
        f"/api/v1/intake/{intake.token}/submit",
        json={"submitter_email": email, "responses": {"company_name": "Acme only"}},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["is_complete"] is False
    assert "primary_contact" in body["missing_fields"]
    assert "target_audience" in body["missing_fields"]
    assert "goals" in body["missing_fields"]

    # intake.completed NOT fired
    evts = (
        (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "intake.completed",
                    SystemEvent.entity_id == intake.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(evts) == 0

    await db_session.refresh(intake)
    assert intake.status != "completed"


@pytest.mark.asyncio
async def test_get_clients_is_org_scoped(api_client, db_session, sample_org_data, monkeypatch):
    headers, org_id = await _auth(api_client, sample_org_data)
    email = f"scoped-{uuid.uuid4().hex[:6]}@acme.example"
    proposal_id, _ = await _seed_proposal_with_payment_link(api_client, db_session, headers, monkeypatch, email)
    event_id = f"evt_scope_{uuid.uuid4().hex[:12]}"
    from apps.api.routers import webhooks as webhooks_mod

    monkeypatch.setattr(
        webhooks_mod,
        "_verify_webhook_with_candidates",
        _make_webhook_verify_patcher(_fake_stripe_payload(event_id, proposal_id, org_id, email), event_id),
    )
    await api_client.post("/api/v1/webhooks/stripe", headers={"Stripe-Signature": "fake"}, content=b"{}")

    r = await api_client.get("/api/v1/clients", headers=headers)
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 1
    assert any(c["primary_email"] == email for c in items)

    cid = items[0]["id"]
    detail = await api_client.get(f"/api/v1/clients/{cid}", headers=headers)
    assert detail.status_code == 200
    assert "onboarding_events" in detail.json()
    assert "intake_requests" in detail.json()
