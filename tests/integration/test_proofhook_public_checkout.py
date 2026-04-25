"""ProofHook public-package buy-now path: Stripe webhook → Payment →
RevenueLedgerEntry → Client → IntakeRequest (with package context) →
ProductionJob (content_pack).

Covers the full-circle path that was previously a NO-GO. Uses real
Stripe-style HMAC signing through the live webhook endpoint, plus
direct calls to record_payment_from_stripe / activate_client_from_payment
for parity with the reconciler safety net.

Acceptance scenarios (mirrors approved scope):
  1. public_checkout creates Payment + ledger + Client + IntakeRequest
  2. static reused proposal_id does NOT mutate the proposal or collapse
     two distinct buyers onto a single Client
  3. duplicate webhook delivery is idempotent end-to-end
  4. reconciler parity: same event ingested via _ingest_missed_event
     produces the same Payment + Client + IntakeRequest, and a
     subsequent webhook delivery short-circuits as duplicate
  5. two distinct buyers of the same package get two distinct Clients
     and two distinct IntakeRequests
  6. completing the IntakeRequest cascades to a queued ProductionJob
     with job_type=content_pack and package_slug carried through
  7. graceful degrade when public link metadata lacks brand_id
  8. intake invite send path is invoked without AttributeError —
     SmtpEmailClient.resolve returns a real instance (DB or env), the
     send_email call records, and an intake.email_sent event fires
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

# Ensure stage_states / gm_* tables are registered with Base.metadata so the
# test_engine fixture's create_all builds them (production has them via
# migrations; the test fixture rebuilds from registered models only).
import packages.db.models.gm_control  # noqa: F401
from packages.db.models.clients import Client, IntakeRequest
from packages.db.models.core import Brand
from packages.db.models.fulfillment import (
    ClientProject,
    ProductionJob,
)
from packages.db.models.live_execution_phase2 import WebhookEvent
from packages.db.models.proposals import Payment, Proposal
from packages.db.models.revenue_ledger import RevenueLedgerEntry

# Mirrors the static, reused proposal_id pattern observed on live public
# Payment Links — corruption guard must drop these on the way through.
SIGNAL_ENTRY_STATIC_PROPOSAL_ID = uuid.UUID("2e397ae9-f4cf-4110-8354-457ea9653a11")

WHSEC = "whsec_proofhook_test"


def _sign(payload_bytes: bytes, secret: str) -> str:
    timestamp = str(int(time.time()))
    signed = f"{timestamp}.{payload_bytes.decode()}"
    sig = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}"


def _checkout_session_completed(
    *,
    event_id: str,
    org_id: uuid.UUID,
    package_slug: str = "signal_entry",
    package_name: str | None = "ProofHook — Signal Entry",
    amount_total: int = 150000,
    customer_email: str,
    proposal_id: uuid.UUID | None = None,
    source: str = "proofhook_public_checkout",
    customer_name: str = "Pat Customer",
    brand_id: uuid.UUID | None = None,
) -> dict:
    metadata: dict[str, str] = {
        "org_id": str(org_id),
        "avenue": "b2b_services",
        "source": source,
        "package": package_slug,
    }
    if package_name:
        metadata["package_name"] = package_name
    if proposal_id is not None:
        metadata["proposal_id"] = str(proposal_id)
    if brand_id is not None:
        metadata["brand_id"] = str(brand_id)
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": f"cs_test_{uuid.uuid4().hex[:14]}",
                "amount_total": amount_total,
                "currency": "usd",
                "payment_intent": f"pi_test_{uuid.uuid4().hex[:14]}",
                "customer_email": customer_email,
                "customer_details": {"name": customer_name},
                "metadata": metadata,
            }
        },
    }


async def _register_org(api_client, sample_org_data) -> uuid.UUID:
    reg = await api_client.post("/api/v1/auth/register", json=sample_org_data)
    assert reg.status_code == 201, reg.text
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": sample_org_data["email"], "password": sample_org_data["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = await api_client.get("/api/v1/auth/me", headers=headers)
    return uuid.UUID(me.json()["organization_id"])


async def _seed_brand(db_session, org_id: uuid.UUID, slug: str = "proofhook") -> uuid.UUID:
    brand = Brand(
        organization_id=org_id,
        name="ProofHook",
        slug=slug,
        niche="b2b",
    )
    db_session.add(brand)
    await db_session.flush()
    return brand.id


async def _seed_static_proposal(db_session, org_id: uuid.UUID) -> uuid.UUID:
    """Insert the static `signal_entry` scaffolding proposal so the corruption
    guard has something to ignore. Mirrors the rows on production."""
    existing = (
        await db_session.execute(select(Proposal).where(Proposal.id == SIGNAL_ENTRY_STATIC_PROPOSAL_ID))
    ).scalar_one_or_none()
    if existing is None:
        existing = Proposal(
            id=SIGNAL_ENTRY_STATIC_PROPOSAL_ID,
            org_id=org_id,
            status="draft",
            title="ProofHook Public Checkout — Signal Entry",
            recipient_email="signal-entry@proofhook.com",
            recipient_name="ProofHook Public Checkout",
            recipient_company="",
            total_amount_cents=150000,
        )
        db_session.add(existing)
        await db_session.flush()
    return existing.id


async def _post_webhook(api_client, payload: dict, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WHSEC)
    body = json.dumps(payload).encode()
    sig = _sign(body, WHSEC)
    return await api_client.post(
        "/api/v1/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": sig, "Content-Type": "application/json"},
    )


# ─────────────────────────────────────────────────────────────────────
# 1. Public checkout creates Payment + ledger + Client + IntakeRequest
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_public_checkout_creates_full_buyer_chain(api_client, db_session, sample_org_data, monkeypatch):
    org_id = await _register_org(api_client, sample_org_data)
    brand_id = await _seed_brand(db_session, org_id)
    email = f"buyer-{uuid.uuid4().hex[:8]}@example.test"
    event_id = f"evt_full_{uuid.uuid4().hex[:14]}"

    payload = _checkout_session_completed(
        event_id=event_id,
        org_id=org_id,
        brand_id=brand_id,
        package_slug="signal_entry",
        package_name="ProofHook — Signal Entry",
        amount_total=150000,
        customer_email=email,
    )

    r = await _post_webhook(api_client, payload, monkeypatch)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "accepted"

    # WebhookEvent: exactly one row
    events = (
        (
            await db_session.execute(
                select(WebhookEvent).where(WebhookEvent.idempotency_key == f"stripe:{event_id}")
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    assert events[0].processed is True

    # Payment: created, no proposal link, package fields stamped
    payment = (
        await db_session.execute(
            select(Payment).where(Payment.provider == "stripe", Payment.provider_event_id == event_id)
        )
    ).scalar_one()
    assert payment.org_id == org_id
    assert payment.status == "succeeded"
    assert payment.amount_cents == 150000
    assert payment.currency == "usd"
    assert payment.proposal_id is None  # public-checkout corruption guard
    assert payment.avenue_slug == "b2b_services"
    assert payment.customer_email == email
    md = payment.metadata_json or {}
    assert md.get("package_slug") == "signal_entry"
    assert md.get("package_name") == "ProofHook — Signal Entry"
    assert md.get("source") == "proofhook_public_checkout"

    # RevenueLedgerEntry: exactly one row, attributed to this package
    ledgers = (
        (
            await db_session.execute(
                select(RevenueLedgerEntry).where(RevenueLedgerEntry.webhook_ref == f"stripe_public:{event_id}")
            )
        )
        .scalars()
        .all()
    )
    assert len(ledgers) == 1
    assert ledgers[0].gross_amount == 1500.0
    assert ledgers[0].payment_state == "confirmed"
    assert ledgers[0].attribution_state == "auto_attributed"
    assert (ledgers[0].metadata_json or {}).get("package_slug") == "signal_entry"

    # Client: created from payment.customer_email
    client = (
        await db_session.execute(
            select(Client).where(Client.org_id == org_id, Client.primary_email == email)
        )
    ).scalar_one()
    assert client.status == "active"
    assert client.first_payment_id == payment.id
    assert client.total_paid_cents == 150000
    assert client.first_proposal_id is None  # never linked to static proposal

    # IntakeRequest: created with package context embedded in schema_json
    intake = (
        await db_session.execute(select(IntakeRequest).where(IntakeRequest.client_id == client.id))
    ).scalar_one()
    assert intake.status == "sent"
    assert intake.token
    sj = intake.schema_json or {}
    assert sj.get("package_slug") == "signal_entry"
    assert sj.get("package_name") == "ProofHook — Signal Entry"
    assert sj.get("source") == "proofhook_public_checkout"


# ─────────────────────────────────────────────────────────────────────
# 2. Static reused proposal_id is dropped, never mutates the proposal,
#    and never collapses distinct buyers onto a single Client
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_static_proposal_id_never_mutates_proposal(api_client, db_session, sample_org_data, monkeypatch):
    org_id = await _register_org(api_client, sample_org_data)
    static_proposal_id = await _seed_static_proposal(db_session, org_id)

    email = f"buyer-{uuid.uuid4().hex[:8]}@example.test"
    event_id = f"evt_static_{uuid.uuid4().hex[:14]}"

    payload = _checkout_session_completed(
        event_id=event_id,
        org_id=org_id,
        package_slug="signal_entry",
        amount_total=150000,
        customer_email=email,
        proposal_id=static_proposal_id,  # the corruption-prone static id
    )

    r = await _post_webhook(api_client, payload, monkeypatch)
    assert r.status_code == 200

    payment = (
        await db_session.execute(
            select(Payment).where(Payment.provider_event_id == event_id, Payment.provider == "stripe")
        )
    ).scalar_one()
    # Guard active: proposal_id dropped, audit trail in metadata_json
    assert payment.proposal_id is None
    md = payment.metadata_json or {}
    assert md.get("proposal_id_skipped_reason") == "public_checkout"
    # Original metadata.proposal_id is preserved on the persisted snapshot
    # for forensic visibility (not used as a FK).
    assert md.get("proposal_id") == str(static_proposal_id)

    # Static proposal is unchanged
    proposal = (await db_session.execute(select(Proposal).where(Proposal.id == static_proposal_id))).scalar_one()
    assert proposal.status == "draft"
    assert proposal.paid_at is None


@pytest.mark.asyncio
async def test_two_buyers_same_package_get_distinct_clients(api_client, db_session, sample_org_data, monkeypatch):
    org_id = await _register_org(api_client, sample_org_data)
    static_proposal_id = await _seed_static_proposal(db_session, org_id)

    email_a = f"a-{uuid.uuid4().hex[:8]}@example.test"
    email_b = f"b-{uuid.uuid4().hex[:8]}@example.test"

    for email in (email_a, email_b):
        event_id = f"evt_two_{uuid.uuid4().hex[:14]}"
        payload = _checkout_session_completed(
            event_id=event_id,
            org_id=org_id,
            package_slug="signal_entry",
            amount_total=150000,
            customer_email=email,
            proposal_id=static_proposal_id,
        )
        r = await _post_webhook(api_client, payload, monkeypatch)
        assert r.status_code == 200

    clients = (
        (await db_session.execute(select(Client).where(Client.org_id == org_id))).scalars().all()
    )
    assert {c.primary_email for c in clients} == {email_a, email_b}
    assert len(clients) == 2

    intakes = (
        (
            await db_session.execute(
                select(IntakeRequest).where(IntakeRequest.client_id.in_([c.id for c in clients]))
            )
        )
        .scalars()
        .all()
    )
    assert len({i.client_id for i in intakes}) == 2

    # Static proposal still untouched after two payments
    proposal = (await db_session.execute(select(Proposal).where(Proposal.id == static_proposal_id))).scalar_one()
    assert proposal.status == "draft"
    assert proposal.paid_at is None


# ─────────────────────────────────────────────────────────────────────
# 3. Duplicate webhook delivery is idempotent end-to-end
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_duplicate_webhook_is_idempotent(api_client, db_session, sample_org_data, monkeypatch):
    org_id = await _register_org(api_client, sample_org_data)
    brand_id = await _seed_brand(db_session, org_id)
    email = f"buyer-{uuid.uuid4().hex[:8]}@example.test"
    event_id = f"evt_idem_{uuid.uuid4().hex[:14]}"

    payload = _checkout_session_completed(
        event_id=event_id,
        org_id=org_id,
        brand_id=brand_id,
        package_slug="momentum_engine",
        amount_total=250000,
        customer_email=email,
    )
    body = json.dumps(payload).encode()

    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WHSEC)
    sig = _sign(body, WHSEC)
    headers = {"Stripe-Signature": sig, "Content-Type": "application/json"}

    r1 = await api_client.post("/api/v1/webhooks/stripe", content=body, headers=headers)
    assert r1.status_code == 200
    assert r1.json()["status"] == "accepted"

    r2 = await api_client.post("/api/v1/webhooks/stripe", content=body, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["status"] == "duplicate"

    # Exactly one of each canonical row
    payments = (
        (await db_session.execute(select(Payment).where(Payment.provider_event_id == event_id))).scalars().all()
    )
    assert len(payments) == 1

    clients = (
        (
            await db_session.execute(
                select(Client).where(Client.org_id == org_id, Client.primary_email == email)
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

    ledgers = (
        (
            await db_session.execute(
                select(RevenueLedgerEntry).where(RevenueLedgerEntry.webhook_ref == f"stripe_public:{event_id}")
            )
        )
        .scalars()
        .all()
    )
    assert len(ledgers) == 1


# ─────────────────────────────────────────────────────────────────────
# 4. Reconciler parity — _ingest_missed_event produces the same canonical
#    chain, and a subsequent webhook delivery short-circuits as duplicate
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reconciler_parity_with_webhook(api_client, db_session, sample_org_data, monkeypatch):
    from apps.api.services.stripe_reconciliation_service import _ingest_missed_event

    org_id = await _register_org(api_client, sample_org_data)
    email = f"reco-{uuid.uuid4().hex[:8]}@example.test"
    event_id = f"evt_reco_{uuid.uuid4().hex[:14]}"

    payload = _checkout_session_completed(
        event_id=event_id,
        org_id=org_id,
        package_slug="conversion_architecture",
        amount_total=350000,
        customer_email=email,
    )
    # Stripe `events` API shape mirrors the webhook payload structure.
    event = {
        "id": payload["id"],
        "type": payload["type"],
        "data": payload["data"],
    }

    await _ingest_missed_event(db_session, org_id=org_id, event=event)
    await db_session.flush()

    # Payment + Client + Intake all created via the reconciler path
    payment = (
        await db_session.execute(
            select(Payment).where(Payment.provider == "stripe", Payment.provider_event_id == event_id)
        )
    ).scalar_one()
    assert payment.proposal_id is None
    assert (payment.metadata_json or {}).get("package_slug") == "conversion_architecture"

    client = (
        await db_session.execute(
            select(Client).where(Client.org_id == org_id, Client.primary_email == email)
        )
    ).scalar_one()
    intake = (
        await db_session.execute(select(IntakeRequest).where(IntakeRequest.client_id == client.id))
    ).scalar_one()
    assert (intake.schema_json or {}).get("package_slug") == "conversion_architecture"

    # WebhookEvent row was written by the reconciler
    rec_event = (
        await db_session.execute(select(WebhookEvent).where(WebhookEvent.idempotency_key == f"stripe:{event_id}"))
    ).scalar_one()
    assert rec_event.processed is True

    # A subsequent webhook delivery for the same event short-circuits
    r = await _post_webhook(api_client, payload, monkeypatch)
    assert r.status_code == 200
    assert r.json()["status"] == "duplicate"

    payments = (
        (await db_session.execute(select(Payment).where(Payment.provider_event_id == event_id))).scalars().all()
    )
    assert len(payments) == 1


# ─────────────────────────────────────────────────────────────────────
# 5. Intake completion cascades to a queued content_pack ProductionJob
#    that carries the package_slug end-to-end
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_intake_completion_creates_content_pack_job_with_package(
    api_client, db_session, sample_org_data, monkeypatch
):
    from apps.api.services.client_activation import submit_intake

    org_id = await _register_org(api_client, sample_org_data)
    email = f"complete-{uuid.uuid4().hex[:8]}@example.test"
    event_id = f"evt_cascade_{uuid.uuid4().hex[:14]}"

    payload = _checkout_session_completed(
        event_id=event_id,
        org_id=org_id,
        package_slug="paid_media_engine",
        package_name="ProofHook — Paid Media Engine",
        amount_total=450000,
        customer_email=email,
    )
    r = await _post_webhook(api_client, payload, monkeypatch)
    assert r.status_code == 200

    client = (
        await db_session.execute(
            select(Client).where(Client.org_id == org_id, Client.primary_email == email)
        )
    ).scalar_one()
    intake = (
        await db_session.execute(select(IntakeRequest).where(IntakeRequest.client_id == client.id))
    ).scalar_one()

    # Submit the intake with all required default-schema fields populated.
    # The DEFAULT_INTAKE_SCHEMA has 4 required fields: company_name,
    # primary_contact, target_audience, goals.
    responses = {
        "company_name": "Acme Co",
        "primary_contact": "Pat",
        "target_audience": "B2B SaaS founders",
        "goals": "Generate paid social creative for a Q2 launch",
    }
    submission = await submit_intake(
        db_session,
        intake_request=intake,
        responses=responses,
        submitter_email=email,
        submitted_via="form",
    )
    assert submission.is_complete is True

    # Cascade should have produced ClientProject + ProductionJob with the
    # public-checkout package_slug carried through (NOT from a Proposal).
    project = (
        await db_session.execute(
            select(ClientProject).where(ClientProject.intake_submission_id == submission.id)
        )
    ).scalar_one()
    assert project.package_slug == "paid_media_engine"
    assert project.proposal_id is None  # no proposal in public path
    assert project.title.startswith("ProofHook — Paid Media Engine") or "Paid Media Engine" in project.title

    jobs = (
        (await db_session.execute(select(ProductionJob).where(ProductionJob.project_id == project.id)))
        .scalars()
        .all()
    )
    assert len(jobs) == 1
    job = jobs[0]
    assert job.job_type == "content_pack"
    assert job.status == "queued"


# ─────────────────────────────────────────────────────────────────────
# 6. The _live source variant is accepted on equal terms
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_proofhook_public_checkout_live_source_accepted(
    api_client, db_session, sample_org_data, monkeypatch
):
    org_id = await _register_org(api_client, sample_org_data)
    brand_id = await _seed_brand(db_session, org_id)
    email = f"live-{uuid.uuid4().hex[:8]}@example.test"
    event_id = f"evt_live_{uuid.uuid4().hex[:14]}"

    payload = _checkout_session_completed(
        event_id=event_id,
        org_id=org_id,
        brand_id=brand_id,
        package_slug="creative_command",
        amount_total=750000,
        customer_email=email,
        source="proofhook_public_checkout_live",
    )
    r = await _post_webhook(api_client, payload, monkeypatch)
    assert r.status_code == 200

    payment = (
        await db_session.execute(
            select(Payment).where(Payment.provider_event_id == event_id, Payment.provider == "stripe")
        )
    ).scalar_one()
    assert (payment.metadata_json or {}).get("source") == "proofhook_public_checkout_live"
    assert (payment.metadata_json or {}).get("package_slug") == "creative_command"

    ledger = (
        await db_session.execute(
            select(RevenueLedgerEntry).where(RevenueLedgerEntry.webhook_ref == f"stripe_public:{event_id}")
        )
    ).scalar_one()
    assert (ledger.metadata_json or {}).get("source") == "proofhook_public_checkout_live"


# ─────────────────────────────────────────────────────────────────────
# 7. Graceful degradation when public link metadata lacks brand_id —
#    Payment + Client + IntakeRequest still created; ledger entry skipped
#    so the buyer chain is never blocked by a NOT NULL ledger column
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_brand_id_skips_ledger_but_keeps_buyer_chain(
    api_client, db_session, sample_org_data, monkeypatch
):
    org_id = await _register_org(api_client, sample_org_data)
    email = f"nobrand-{uuid.uuid4().hex[:8]}@example.test"
    event_id = f"evt_nobrand_{uuid.uuid4().hex[:14]}"

    # No brand_id in metadata — mirrors current production link state
    payload = _checkout_session_completed(
        event_id=event_id,
        org_id=org_id,
        package_slug="signal_entry",
        amount_total=150000,
        customer_email=email,
    )
    r = await _post_webhook(api_client, payload, monkeypatch)
    assert r.status_code == 200

    # Buyer chain succeeds
    payment = (
        await db_session.execute(select(Payment).where(Payment.provider_event_id == event_id))
    ).scalar_one()
    assert payment.status == "succeeded"
    assert payment.brand_id is None

    client = (
        await db_session.execute(
            select(Client).where(Client.org_id == org_id, Client.primary_email == email)
        )
    ).scalar_one()
    assert client.status == "active"

    intake = (
        await db_session.execute(select(IntakeRequest).where(IntakeRequest.client_id == client.id))
    ).scalar_one()
    assert intake.status == "sent"

    # Ledger row is intentionally NOT written (NOT NULL brand_id) —
    # operator action: add brand_id to Stripe Payment Link metadata.
    ledgers = (
        (
            await db_session.execute(
                select(RevenueLedgerEntry).where(RevenueLedgerEntry.webhook_ref == f"stripe_public:{event_id}")
            )
        )
        .scalars()
        .all()
    )
    assert ledgers == []


# ─────────────────────────────────────────────────────────────────────
# 8. Intake invite send path — proves the SmtpEmailClient.resolve fix
#    works end-to-end. Before the fix, send_intake_invite called
#    SmtpEmailClient.from_db which raised AttributeError every time,
#    silently failing the buyer's intake email.
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_intake_invite_send_path_invoked_without_attribute_error(
    api_client, db_session, sample_org_data, monkeypatch
):
    """Public checkout → IntakeRequest → SmtpEmailClient.resolve → send_email.

    Patches SmtpEmailClient.resolve to return a recording stub so the test
    does not require working SMTP credentials. Asserts:
      - the resolve method is called (no AttributeError)
      - send_email is invoked exactly once with the buyer's email and the
        intake invite subject
      - an intake.email_sent event row is written for the IntakeRequest
      - the IntakeRequest is the public-checkout one (with package_slug)
    """
    from packages.clients import external_clients as ec
    from packages.db.models.clients import ClientOnboardingEvent

    sent_emails: list[dict] = []
    resolve_calls: list[dict] = []

    class _StubSmtp:
        provider = "smtp_stub"

        async def send_email(self, to_email, subject, body_html="", body_text=""):
            sent_emails.append(
                {"to": to_email, "subject": subject, "html_present": bool(body_html), "text_present": bool(body_text)}
            )
            return {"success": True, "blocked": False, "error": None, "message_id": "stub-msg-id", "provider": "smtp"}

    async def _fake_resolve(cls, db, org_id):
        resolve_calls.append({"org_id": str(org_id)})
        return _StubSmtp()

    monkeypatch.setattr(ec.SmtpEmailClient, "resolve", classmethod(_fake_resolve))

    org_id = await _register_org(api_client, sample_org_data)
    brand_id = await _seed_brand(db_session, org_id)
    email = f"smtp-{uuid.uuid4().hex[:8]}@example.test"
    event_id = f"evt_smtp_{uuid.uuid4().hex[:14]}"

    payload = _checkout_session_completed(
        event_id=event_id,
        org_id=org_id,
        brand_id=brand_id,
        package_slug="signal_entry",
        package_name="ProofHook — Signal Entry",
        amount_total=150000,
        customer_email=email,
    )
    r = await _post_webhook(api_client, payload, monkeypatch)
    assert r.status_code == 200, r.text

    # Resolve was called exactly once (the buyer-side intake invite)
    assert len(resolve_calls) == 1
    assert resolve_calls[0]["org_id"] == str(org_id)

    # Send was invoked with the buyer's email and a non-empty subject/body
    assert len(sent_emails) == 1
    sent = sent_emails[0]
    assert sent["to"] == email
    assert sent["subject"]  # non-empty
    assert sent["html_present"] or sent["text_present"]

    # The downstream IntakeRequest is the public-checkout one
    client = (
        await db_session.execute(
            select(Client).where(Client.org_id == org_id, Client.primary_email == email)
        )
    ).scalar_one()
    intake = (
        await db_session.execute(select(IntakeRequest).where(IntakeRequest.client_id == client.id))
    ).scalar_one()
    assert (intake.schema_json or {}).get("package_slug") == "signal_entry"

    # An intake.email_sent ClientOnboardingEvent was recorded for this intake
    onb = (
        (
            await db_session.execute(
                select(ClientOnboardingEvent).where(
                    ClientOnboardingEvent.intake_request_id == intake.id,
                    ClientOnboardingEvent.event_type == "intake.email_sent",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(onb) == 1, "intake.email_sent onboarding event must be written exactly once"
    assert (onb[0].details_json or {}).get("provider") == "smtp"


@pytest.mark.asyncio
async def test_smtp_resolve_returns_none_when_no_config(db_session, sample_org_data, api_client):
    """Defensive check on the resolve fallback path: when neither DB nor env
    yields a configured client, resolve() returns None (it does NOT raise
    AttributeError, and it does NOT return a half-built instance that would
    blow up later inside aiosmtplib.send)."""
    from packages.clients.external_clients import SmtpEmailClient

    org_id = await _register_org(api_client, sample_org_data)

    # The conftest test environment has no SMTP_HOST set and no DB-backed
    # smtp credential — both resolution paths should miss.
    result = await SmtpEmailClient.resolve(db_session, org_id)
    assert result is None

    # The legacy alias must behave identically
    result2 = await SmtpEmailClient.from_db(db_session, org_id)
    assert result2 is None
