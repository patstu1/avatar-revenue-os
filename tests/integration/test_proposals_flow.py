"""Integration tests for Batch 3A — conversion backbone.

Covers:
  1. POST /proposals creates Proposal + ProposalLineItems,
     total_amount_cents computed, proposal.created event emitted.
  2. Add line item updates total_amount_cents.
  3. POST /proposals/{id}/send transitions draft → sent,
     proposal.sent event emitted.
  4. POST /proposals/{id}/payment-link creates PaymentLink row +
     emits payment.link.created (Stripe call mocked).
  5. GET /proposals/{id} returns proposal with nested line_items,
     payment_links, payments.
  6. Cross-org access → 403.
  7. Stripe webhook checkout.session.completed + metadata.proposal_id
     → writes Payment row, transitions proposal to paid, marks
     PaymentLink completed, emits payment.completed.
  8. Stripe webhook idempotency — same event_id twice → one Payment row.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from packages.db.models.proposals import Payment, PaymentLink, Proposal, ProposalLineItem
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
    org_id = uuid.UUID(me.json()["organization_id"])
    return headers, org_id


@pytest.mark.asyncio
async def test_create_proposal_persists_rows_and_emits_event(
    api_client, db_session, sample_org_data
):
    headers, org_id = await _auth(api_client, sample_org_data)

    resp = await api_client.post(
        "/api/v1/proposals",
        headers=headers,
        json={
            "recipient_email": "ceo@acme.example",
            "recipient_name": "Sam CEO",
            "title": "Growth Content Pack — Acme",
            "package_slug": "growth-content-pack",
            "line_items": [
                {
                    "description": "Growth Content Pack — 30 days",
                    "unit_amount_cents": 150000,
                    "quantity": 1,
                    "package_slug": "growth-content-pack",
                    "position": 0,
                },
                {
                    "description": "Strategy call + creative brief",
                    "unit_amount_cents": 50000,
                    "quantity": 1,
                    "position": 1,
                },
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "draft"
    assert body["total_amount_cents"] == 200000
    assert body["recipient_email"] == "ceo@acme.example"
    proposal_id = uuid.UUID(body["id"])

    # DB: proposal row
    proposal = (
        await db_session.execute(select(Proposal).where(Proposal.id == proposal_id))
    ).scalar_one()
    assert proposal.org_id == org_id
    assert proposal.total_amount_cents == 200000
    assert proposal.status == "draft"

    # DB: two line items
    items = (
        await db_session.execute(
            select(ProposalLineItem)
            .where(ProposalLineItem.proposal_id == proposal.id)
            .order_by(ProposalLineItem.position)
        )
    ).scalars().all()
    assert len(items) == 2
    assert items[0].unit_amount_cents == 150000
    assert items[1].unit_amount_cents == 50000

    # Event
    evt = (
        await db_session.execute(
            select(SystemEvent).where(
                SystemEvent.event_type == "proposal.created",
                SystemEvent.entity_id == proposal.id,
            )
        )
    ).scalar_one()
    assert evt.event_domain == "monetization"
    assert evt.new_state == "draft"
    assert evt.details["line_item_count"] == 2
    assert evt.details["total_amount_cents"] == 200000


@pytest.mark.asyncio
async def test_add_line_item_updates_proposal_total(
    api_client, db_session, sample_org_data
):
    headers, _org_id = await _auth(api_client, sample_org_data)
    create = await api_client.post(
        "/api/v1/proposals",
        headers=headers,
        json={
            "recipient_email": "founder@acme.example",
            "title": "Custom pilot",
            "line_items": [
                {"description": "Pilot sprint", "unit_amount_cents": 100000}
            ],
        },
    )
    pid = create.json()["id"]

    resp = await api_client.post(
        f"/api/v1/proposals/{pid}/line-items",
        headers=headers,
        json={
            "description": "Add-on analytics",
            "unit_amount_cents": 25000,
            "quantity": 2,
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["total_amount_cents"] == 50000

    proposal = (
        await db_session.execute(select(Proposal).where(Proposal.id == uuid.UUID(pid)))
    ).scalar_one()
    assert proposal.total_amount_cents == 150000  # 100k + 2 * 25k


@pytest.mark.asyncio
async def test_send_proposal_transitions_state_and_emits_event(
    api_client, db_session, sample_org_data
):
    headers, _ = await _auth(api_client, sample_org_data)
    create = await api_client.post(
        "/api/v1/proposals",
        headers=headers,
        json={
            "recipient_email": "lead@acme.example",
            "title": "Pilot proposal",
            "line_items": [{"description": "Pilot", "unit_amount_cents": 100000}],
        },
    )
    pid = create.json()["id"]

    resp = await api_client.post(f"/api/v1/proposals/{pid}/send", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "sent"
    assert resp.json()["sent_at"]

    evt = (
        await db_session.execute(
            select(SystemEvent).where(
                SystemEvent.event_type == "proposal.sent",
                SystemEvent.entity_id == uuid.UUID(pid),
            )
        )
    ).scalar_one()
    assert evt.previous_state == "draft"
    assert evt.new_state == "sent"


@pytest.mark.asyncio
async def test_create_payment_link_persists_row_and_emits_event(
    api_client, db_session, sample_org_data, monkeypatch
):
    # Bypass real Stripe — return a fake successful link create result.
    async def _fake_create_link(**kwargs):
        return {
            "url": "https://checkout.stripe.com/c/pay/cs_test_fake123",
            "id": "plink_test_fake123",
        }

    from apps.api.services import stripe_billing_service
    monkeypatch.setattr(stripe_billing_service, "create_payment_link", _fake_create_link)

    headers, org_id = await _auth(api_client, sample_org_data)
    create = await api_client.post(
        "/api/v1/proposals",
        headers=headers,
        json={
            "recipient_email": "buyer@acme.example",
            "title": "Growth pack proposal",
            "line_items": [{"description": "Pack", "unit_amount_cents": 150000}],
        },
    )
    pid = create.json()["id"]

    resp = await api_client.post(
        f"/api/v1/proposals/{pid}/payment-link",
        headers=headers,
        json={},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["amount_cents"] == 150000
    assert body["url"].startswith("https://checkout.stripe.com")
    assert body["provider_link_id"] == "plink_test_fake123"

    link = (
        await db_session.execute(
            select(PaymentLink).where(PaymentLink.id == uuid.UUID(body["id"]))
        )
    ).scalar_one()
    assert link.proposal_id == uuid.UUID(pid)
    assert link.status == "active"

    evt = (
        await db_session.execute(
            select(SystemEvent).where(
                SystemEvent.event_type == "payment.link.created",
                SystemEvent.entity_id == link.id,
            )
        )
    ).scalar_one()
    assert evt.new_state == "active"
    assert evt.details["amount_cents"] == 150000


@pytest.mark.asyncio
async def test_get_proposal_returns_nested_shape(api_client, db_session, sample_org_data):
    headers, _ = await _auth(api_client, sample_org_data)
    create = await api_client.post(
        "/api/v1/proposals",
        headers=headers,
        json={
            "recipient_email": "check@acme.example",
            "title": "Shape test",
            "line_items": [{"description": "Thing", "unit_amount_cents": 50000}],
        },
    )
    pid = create.json()["id"]

    resp = await api_client.get(f"/api/v1/proposals/{pid}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == pid
    assert len(body["line_items"]) == 1
    assert body["payment_links"] == []
    assert body["payments"] == []


@pytest.mark.asyncio
async def test_cross_org_access_returns_403(api_client, db_session, sample_org_data):
    # Org A creates a proposal
    headers_a, _ = await _auth(api_client, sample_org_data)
    create = await api_client.post(
        "/api/v1/proposals",
        headers=headers_a,
        json={
            "recipient_email": "a@acme.example",
            "title": "Org A proposal",
            "line_items": [{"description": "Thing", "unit_amount_cents": 1000}],
        },
    )
    pid = create.json()["id"]

    # Org B tries to read it
    org_b_data = {
        "organization_name": f"Other Org {uuid.uuid4().hex[:6]}",
        "email": f"other-{uuid.uuid4().hex[:6]}@example.com",
        "password": "testpass456",
        "full_name": "Other User",
    }
    headers_b, _ = await _auth(api_client, org_b_data)
    resp = await api_client.get(f"/api/v1/proposals/{pid}", headers=headers_b)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_stripe_webhook_writes_payment_and_transitions_proposal(
    api_client, db_session, sample_org_data, monkeypatch
):
    """Inbound Stripe checkout.session.completed with metadata.proposal_id
    writes a Payment row, transitions the Proposal to status=paid, marks
    the PaymentLink completed, emits payment.completed."""
    headers, org_id = await _auth(api_client, sample_org_data)

    # Seed proposal + payment link
    create = await api_client.post(
        "/api/v1/proposals",
        headers=headers,
        json={
            "recipient_email": "paying-customer@acme.example",
            "title": "Paid proposal",
            "line_items": [{"description": "Pack", "unit_amount_cents": 150000}],
        },
    )
    pid_str = create.json()["id"]

    async def _fake_create_link(**kwargs):
        return {"url": "https://checkout.stripe.com/cs_webhook_test", "id": "plink_wh_test"}

    from apps.api.services import stripe_billing_service
    monkeypatch.setattr(stripe_billing_service, "create_payment_link", _fake_create_link)

    link_resp = await api_client.post(
        f"/api/v1/proposals/{pid_str}/payment-link", headers=headers, json={}
    )
    payment_link_id = uuid.UUID(link_resp.json()["id"])

    # Bypass Stripe signature verification — return a valid result dict.
    event_id = f"evt_test_{uuid.uuid4().hex[:12]}"
    fake_payload = {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_abc123",
                "object": "checkout.session",
                "amount_total": 150000,
                "currency": "usd",
                "payment_intent": "pi_test_xyz789",
                "customer_email": "paying-customer@acme.example",
                "payment_link": "plink_wh_test",
                "metadata": {
                    "proposal_id": pid_str,
                    "org_id": str(org_id),
                    "source": "proposal",
                    "origin": "proposal_drain",
                },
            }
        },
    }

    async def _fake_verify(
        *,
        verifier,
        body,
        signature,
        candidates,
        env_var,
        provider_key,
        log_prefix,
    ):
        return {
            "valid": True,
            "event_id": event_id,
            "event_type": "checkout.session.completed",
            "payload": fake_payload,
        }, None

    from apps.api.routers import webhooks as webhooks_mod
    monkeypatch.setattr(webhooks_mod, "_verify_webhook_with_candidates", _fake_verify)

    # Fire the webhook
    resp = await api_client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": "t=0,v1=fake"},
        content=b"{}",
    )
    assert resp.status_code == 200, resp.text

    # Payment row
    payment = (
        await db_session.execute(
            select(Payment).where(
                Payment.provider == "stripe",
                Payment.provider_event_id == event_id,
            )
        )
    ).scalar_one()
    assert payment.status == "succeeded"
    assert payment.amount_cents == 150000
    assert payment.proposal_id == uuid.UUID(pid_str)
    assert payment.payment_link_id == payment_link_id
    assert payment.completed_at is not None
    assert payment.customer_email == "paying-customer@acme.example"

    # Proposal transitioned
    proposal = (
        await db_session.execute(
            select(Proposal).where(Proposal.id == uuid.UUID(pid_str))
        )
    ).scalar_one()
    assert proposal.status == "paid"
    assert proposal.paid_at is not None

    # PaymentLink marked completed
    link = (
        await db_session.execute(
            select(PaymentLink).where(PaymentLink.id == payment_link_id)
        )
    ).scalar_one()
    assert link.status == "completed"
    assert link.completed_at is not None

    # payment.completed event
    evt = (
        await db_session.execute(
            select(SystemEvent).where(
                SystemEvent.event_type == "payment.completed",
                SystemEvent.entity_id == payment.id,
            )
        )
    ).scalar_one()
    assert evt.new_state == "succeeded"
    assert evt.actor_type == "stripe_webhook"
    assert evt.details["amount_cents"] == 150000
    assert evt.details["proposal_id"] == pid_str


@pytest.mark.asyncio
async def test_stripe_webhook_payment_is_idempotent_on_event_id(
    api_client, db_session, sample_org_data, monkeypatch
):
    headers, org_id = await _auth(api_client, sample_org_data)

    create = await api_client.post(
        "/api/v1/proposals",
        headers=headers,
        json={
            "recipient_email": "dupe-test@acme.example",
            "title": "Dedup test",
            "line_items": [{"description": "Pack", "unit_amount_cents": 100000}],
        },
    )
    pid_str = create.json()["id"]

    event_id = f"evt_dedup_{uuid.uuid4().hex[:12]}"
    fake_payload = {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_dedup",
                "amount_total": 100000,
                "currency": "usd",
                "metadata": {"proposal_id": pid_str, "org_id": str(org_id)},
            }
        },
    }

    async def _fake_verify(**kwargs):
        return {
            "valid": True,
            "event_id": event_id,
            "event_type": "checkout.session.completed",
            "payload": fake_payload,
        }, None

    from apps.api.routers import webhooks as webhooks_mod
    monkeypatch.setattr(webhooks_mod, "_verify_webhook_with_candidates", _fake_verify)

    # POST twice with the same event_id
    r1 = await api_client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": "fake"},
        content=b"{}",
    )
    r2 = await api_client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": "fake"},
        content=b"{}",
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Second call returns duplicate marker (webhook_events pre-filters)
    assert r2.json().get("status") in {"accepted", "duplicate"}

    # Only one Payment row
    payments = (
        await db_session.execute(
            select(Payment).where(
                Payment.provider == "stripe",
                Payment.provider_event_id == event_id,
            )
        )
    ).scalars().all()
    assert len(payments) == 1
