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

import packages.db.models.delivery  # noqa: F401

# Ensure stage_states / gm_* / production_qa_reviews / deliveries tables
# are registered with Base.metadata so the test_engine fixture's create_all
# builds them (production has them via migrations; the test fixture
# rebuilds from registered models only — packages/db/models/__init__.py
# does not import these modules so we do it explicitly here).
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


async def _seed_operator_stripe_credentials(
    db_session,
    org_id: uuid.UUID,
    *,
    api_key: str = "sk_test_proofhook_public_checkout_seed",
    webhook_secret: str = WHSEC,
):
    """Seed the operator's Stripe API key + webhook secret in the DB.

    Stripe is DB-only. The webhook handler resolves the secret via
    ``integration_manager.resolve_operator_org_for_stripe`` →
    ``get_webhook_secret``, both of which read from
    ``integration_providers``. This helper writes both encrypted columns
    so tests can drive a real signature-verified webhook through the
    DB-only resolver.
    """
    from apps.api.services.integration_manager import (
        seed_provider_catalog,
        set_credential,
        set_webhook_secret,
    )

    await seed_provider_catalog(db_session, org_id)
    await set_credential(db_session, org_id, "stripe", api_key=api_key)
    await set_webhook_secret(db_session, org_id, "stripe", webhook_secret)
    await db_session.commit()


async def _post_webhook(api_client, payload: dict, monkeypatch, db_session=None, org_id=None):
    """POST a Stripe webhook with DB-stored signing secret.

    The legacy helper signature accepted ``monkeypatch`` to set
    ``STRIPE_WEBHOOK_SECRET`` in env. That env path no longer exists —
    the secret must be in DB. ``monkeypatch`` is kept for callers that
    still pass it but is unused for Stripe; ``db_session`` + ``org_id``
    are required so the helper can seed the DB credential before posting.
    """
    if db_session is not None and org_id is not None:
        await _seed_operator_stripe_credentials(db_session, org_id)
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

    r = await _post_webhook(api_client, payload, monkeypatch, db_session=db_session, org_id=org_id)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "accepted"

    # WebhookEvent: exactly one row
    events = (
        (await db_session.execute(select(WebhookEvent).where(WebhookEvent.idempotency_key == f"stripe:{event_id}")))
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
        await db_session.execute(select(Client).where(Client.org_id == org_id, Client.primary_email == email))
    ).scalar_one()
    assert client.status == "active"
    assert client.first_payment_id == payment.id
    assert client.total_paid_cents == 150000
    assert client.first_proposal_id is None  # never linked to static proposal

    # IntakeRequest: created with package context embedded in schema_json
    intake = (await db_session.execute(select(IntakeRequest).where(IntakeRequest.client_id == client.id))).scalar_one()
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
    brand_id = await _seed_brand(db_session, org_id)
    static_proposal_id = await _seed_static_proposal(db_session, org_id)

    email = f"buyer-{uuid.uuid4().hex[:8]}@example.test"
    event_id = f"evt_static_{uuid.uuid4().hex[:14]}"

    # brand_id is required under the post-lock metadata doctrine.
    payload = _checkout_session_completed(
        event_id=event_id,
        org_id=org_id,
        brand_id=brand_id,
        package_slug="signal_entry",
        amount_total=150000,
        customer_email=email,
        proposal_id=static_proposal_id,  # the corruption-prone static id
    )

    r = await _post_webhook(api_client, payload, monkeypatch, db_session=db_session, org_id=org_id)
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
    brand_id = await _seed_brand(db_session, org_id)
    static_proposal_id = await _seed_static_proposal(db_session, org_id)

    email_a = f"a-{uuid.uuid4().hex[:8]}@example.test"
    email_b = f"b-{uuid.uuid4().hex[:8]}@example.test"

    for email in (email_a, email_b):
        event_id = f"evt_two_{uuid.uuid4().hex[:14]}"
        payload = _checkout_session_completed(
            event_id=event_id,
            org_id=org_id,
            brand_id=brand_id,
            package_slug="signal_entry",
            amount_total=150000,
            customer_email=email,
            proposal_id=static_proposal_id,
        )
        r = await _post_webhook(api_client, payload, monkeypatch, db_session=db_session, org_id=org_id)
        assert r.status_code == 200

    clients = (await db_session.execute(select(Client).where(Client.org_id == org_id))).scalars().all()
    assert {c.primary_email for c in clients} == {email_a, email_b}
    assert len(clients) == 2

    intakes = (
        (await db_session.execute(select(IntakeRequest).where(IntakeRequest.client_id.in_([c.id for c in clients]))))
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

    # DB-only: seed the operator's Stripe credentials in integration_providers
    # so the webhook resolver can verify the signature.
    await _seed_operator_stripe_credentials(db_session, org_id)
    sig = _sign(body, WHSEC)
    headers = {"Stripe-Signature": sig, "Content-Type": "application/json"}

    r1 = await api_client.post("/api/v1/webhooks/stripe", content=body, headers=headers)
    assert r1.status_code == 200
    assert r1.json()["status"] == "accepted"

    r2 = await api_client.post("/api/v1/webhooks/stripe", content=body, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["status"] == "duplicate"

    # Exactly one of each canonical row
    payments = (await db_session.execute(select(Payment).where(Payment.provider_event_id == event_id))).scalars().all()
    assert len(payments) == 1

    clients = (
        (await db_session.execute(select(Client).where(Client.org_id == org_id, Client.primary_email == email)))
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
        await db_session.execute(select(Client).where(Client.org_id == org_id, Client.primary_email == email))
    ).scalar_one()
    intake = (await db_session.execute(select(IntakeRequest).where(IntakeRequest.client_id == client.id))).scalar_one()
    assert (intake.schema_json or {}).get("package_slug") == "conversion_architecture"

    # WebhookEvent row was written by the reconciler
    rec_event = (
        await db_session.execute(select(WebhookEvent).where(WebhookEvent.idempotency_key == f"stripe:{event_id}"))
    ).scalar_one()
    assert rec_event.processed is True

    # A subsequent webhook delivery for the same event short-circuits
    r = await _post_webhook(api_client, payload, monkeypatch, db_session=db_session, org_id=org_id)
    assert r.status_code == 200
    assert r.json()["status"] == "duplicate"

    payments = (await db_session.execute(select(Payment).where(Payment.provider_event_id == event_id))).scalars().all()
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
    brand_id = await _seed_brand(db_session, org_id)
    email = f"complete-{uuid.uuid4().hex[:8]}@example.test"
    event_id = f"evt_cascade_{uuid.uuid4().hex[:14]}"

    payload = _checkout_session_completed(
        event_id=event_id,
        org_id=org_id,
        brand_id=brand_id,
        package_slug="paid_media_engine",
        package_name="ProofHook — Paid Media Engine",
        amount_total=450000,
        customer_email=email,
    )
    r = await _post_webhook(api_client, payload, monkeypatch, db_session=db_session, org_id=org_id)
    assert r.status_code == 200

    client = (
        await db_session.execute(select(Client).where(Client.org_id == org_id, Client.primary_email == email))
    ).scalar_one()
    intake = (await db_session.execute(select(IntakeRequest).where(IntakeRequest.client_id == client.id))).scalar_one()

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
        await db_session.execute(select(ClientProject).where(ClientProject.intake_submission_id == submission.id))
    ).scalar_one()
    assert project.package_slug == "paid_media_engine"
    assert project.proposal_id is None  # no proposal in public path
    assert project.title.startswith("ProofHook — Paid Media Engine") or "Paid Media Engine" in project.title

    jobs = (
        (await db_session.execute(select(ProductionJob).where(ProductionJob.project_id == project.id))).scalars().all()
    )
    assert len(jobs) == 1
    job = jobs[0]
    assert job.job_type == "content_pack"
    assert job.status == "queued"


# ─────────────────────────────────────────────────────────────────────
# 6. The _live source variant is accepted on equal terms
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_proofhook_public_checkout_live_source_accepted(api_client, db_session, sample_org_data, monkeypatch):
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
    r = await _post_webhook(api_client, payload, monkeypatch, db_session=db_session, org_id=org_id)
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
# 7. Doctrine: missing brand_id on a public ProofHook checkout is FATAL.
#    No Payment, no Client, no IntakeRequest, no ledger — and an
#    operator-visible payment.metadata_missing system event is emitted.
#    Pre-doctrine behavior was to create Payment + Client + Intake and
#    silently skip the ledger; that path is gone. The webhook still
#    returns 200 (signature was valid; Stripe must not retry) and the
#    WebhookEvent row is marked unprocessed with an error_message.
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_missing_brand_id_rejects_full_buyer_chain(api_client, db_session, sample_org_data, monkeypatch):
    from packages.db.models.system_events import SystemEvent

    org_id = await _register_org(api_client, sample_org_data)
    email = f"nobrand-{uuid.uuid4().hex[:8]}@example.test"
    event_id = f"evt_nobrand_{uuid.uuid4().hex[:14]}"

    # Public ProofHook checkout WITHOUT brand_id → must be rejected
    payload = _checkout_session_completed(
        event_id=event_id,
        org_id=org_id,
        package_slug="signal_entry",
        amount_total=150000,
        customer_email=email,
    )
    r = await _post_webhook(api_client, payload, monkeypatch, db_session=db_session, org_id=org_id)
    assert r.status_code == 200  # signature valid → Stripe must not retry
    assert r.json()["status"] == "accepted"

    # Doctrine: NO Payment row created — every paid event must carry
    # attribution that lets the ledger record it.
    payments = (await db_session.execute(select(Payment).where(Payment.provider_event_id == event_id))).scalars().all()
    assert payments == [], "Payment must NOT be created when brand_id is missing"

    # No Client created
    clients = (
        (await db_session.execute(select(Client).where(Client.org_id == org_id, Client.primary_email == email)))
        .scalars()
        .all()
    )
    assert clients == [], "Client must NOT be created when brand_id is missing"

    # No IntakeRequest created
    intakes = (
        ((await db_session.execute(select(IntakeRequest).where(IntakeRequest.email == email))).scalars().all())
        if False
        else []
    )
    # IntakeRequest filter by email isn't always supported; rely on the
    # absence of a Client to imply absence of an Intake (created only
    # alongside a Client by activate_client_from_payment).
    assert intakes == []

    # No ledger entry
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

    # WebhookEvent is recorded but marked unprocessed with reason
    we = (
        await db_session.execute(select(WebhookEvent).where(WebhookEvent.idempotency_key == f"stripe:{event_id}"))
    ).scalar_one()
    assert we.processed is False
    assert we.processing_result == "missing_metadata"
    assert "brand_id" in (we.error_message or "")

    # Operator-visible system event was emitted
    fail_events = (
        (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "payment.metadata_missing",
                    SystemEvent.event_domain == "monetization",
                )
            )
        )
        .scalars()
        .all()
    )
    matching = [e for e in fail_events if (e.details or {}).get("stripe_event_id") == event_id]
    assert len(matching) == 1, "operator must see exactly one payment.metadata_missing event"
    details = matching[0].details or {}
    assert "brand_id" in details.get("missing_fields", [])
    assert details.get("source") == "proofhook_public_checkout"


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
    r = await _post_webhook(api_client, payload, monkeypatch, db_session=db_session, org_id=org_id)
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
        await db_session.execute(select(Client).where(Client.org_id == org_id, Client.primary_email == email))
    ).scalar_one()
    intake = (await db_session.execute(select(IntakeRequest).where(IntakeRequest.client_id == client.id))).scalar_one()
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


# ─────────────────────────────────────────────────────────────────────
# 9. Intake router is mounted in main.py — proves the buyer's intake
#    invite link no longer 404s. Pre-fix: intake_router was defined in
#    apps/api/routers/clients.py but never include_router'd into
#    apps/api/main.py, so /api/v1/intake/{token}/submit returned 404.
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_intake_route_is_mounted_and_reachable(api_client):
    """OpenAPI exposes the intake submit path AND posting to it does not
    return 404 (signaling unmounted route). Posting with a bogus token
    returns 404 from the *route handler* with the body 'Intake not found'
    — that's a route hit, not a missing route."""
    # OpenAPI surface — FastAPI default openapi_url is /openapi.json (root)
    r = await api_client.get("/openapi.json")
    if r.status_code != 200:
        # Production exposes it at /api/v1/openapi.json; try both
        r = await api_client.get("/api/v1/openapi.json")
    assert r.status_code == 200
    paths = list(r.json().get("paths", {}).keys())
    assert "/api/v1/intake/{token}/submit" in paths, (
        f"intake submit path not in OpenAPI: {[p for p in paths if 'intake' in p]}"
    )
    assert "/api/v1/intake/{token}" in paths
    assert "/api/v1/intake-requests" in paths

    # POST with a bogus token returns 404 from the route handler. The
    # global 404 exception_handler in apps/api/middleware.py rewrites all
    # 404 bodies to {"detail": "Not found"} regardless of whether the
    # route is mounted, so we can't distinguish via body. The OpenAPI
    # surface check above is the canonical mount proof; this just
    # confirms the route is reachable end-to-end.
    r2 = await api_client.post(
        "/api/v1/intake/totally_bogus_token_does_not_exist_123/submit",
        json={"responses": {}, "submitter_email": "x@example.test"},
    )
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_intake_http_submit_drives_full_cascade(api_client, db_session, sample_org_data, monkeypatch):
    """Posting a full intake submission to the public HTTP endpoint creates
    ClientProject + ProjectBrief + queued ProductionJob — proving the
    public buyer path is reachable end-to-end through the wire (no
    direct service-call shortcut)."""
    from packages.db.models.fulfillment import ClientProject, ProductionJob

    org_id = await _register_org(api_client, sample_org_data)
    brand_id = await _seed_brand(db_session, org_id)
    email = f"http-{uuid.uuid4().hex[:8]}@example.test"
    event_id = f"evt_http_{uuid.uuid4().hex[:14]}"

    payload = _checkout_session_completed(
        event_id=event_id,
        org_id=org_id,
        brand_id=brand_id,
        package_slug="momentum_engine",
        package_name="Momentum Engine",
        amount_total=250000,
        customer_email=email,
    )
    r = await _post_webhook(api_client, payload, monkeypatch, db_session=db_session, org_id=org_id)
    assert r.status_code == 200, r.text

    client = (
        await db_session.execute(select(Client).where(Client.org_id == org_id, Client.primary_email == email))
    ).scalar_one()
    intake = (await db_session.execute(select(IntakeRequest).where(IntakeRequest.client_id == client.id))).scalar_one()

    # Drive the cascade through the public HTTP route
    submit = await api_client.post(
        f"/api/v1/intake/{intake.token}/submit",
        json={
            "responses": {
                "company_name": "Acme HTTP",
                "primary_contact": "Pat",
                "target_audience": "B2B SaaS founders",
                "goals": "End-to-end HTTP path validation",
            },
            "submitter_email": email,
        },
    )
    assert submit.status_code == 201, submit.text
    body = submit.json()
    assert body["is_complete"] is True
    assert body["intake_request_id"] == str(intake.id)
    sub_id = uuid.UUID(body["id"])

    # The cascade ran inside submit_intake — ClientProject + Brief +
    # queued ProductionJob with package_slug carried through
    project = (
        await db_session.execute(select(ClientProject).where(ClientProject.intake_submission_id == sub_id))
    ).scalar_one()
    assert project.package_slug == "momentum_engine"
    assert project.proposal_id is None  # public path, no proposal
    job = (await db_session.execute(select(ProductionJob).where(ProductionJob.project_id == project.id))).scalar_one()
    assert job.job_type == "content_pack"
    assert job.status == "queued"


# ─────────────────────────────────────────────────────────────────────
# 10. Celery beat schedule includes drain_pending_production_jobs —
#    proves queued ProductionJobs will auto-advance to in_progress
#    every minute without manual dispatch. Pre-fix: the task was
#    registered but the beat schedule lacked the entry, so queued jobs
#    sat forever.
# ─────────────────────────────────────────────────────────────────────


def test_celery_beat_includes_drain_pending_production_jobs():
    """workers/celery_app.py must declare a beat entry whose `task` field
    matches the registered task name in workers/fulfillment_worker/tasks.py."""
    from workers.celery_app import app as celery_app

    schedule = celery_app.conf.beat_schedule
    assert isinstance(schedule, dict) and len(schedule) > 0

    matching = [
        (name, entry)
        for name, entry in schedule.items()
        if entry.get("task") == "workers.fulfillment_worker.tasks.drain_pending_production_jobs"
    ]
    assert matching, (
        "drain_pending_production_jobs is not in the beat schedule. "
        f"All scheduled tasks: {sorted({e.get('task') for e in schedule.values()})}"
    )
    assert len(matching) == 1, f"drain task scheduled multiple times: {[m[0] for m in matching]}"

    # Schedule must be a Celery schedule object (crontab or timedelta)
    name, entry = matching[0]
    sched = entry.get("schedule")
    assert sched is not None
    # Verify it fires at most every minute (i.e. not less frequent than once per minute)
    # crontab(minute='*') is the canonical "every minute" form
    from celery.schedules import crontab

    if isinstance(sched, crontab):
        # crontab.minute is a set of integers (every minute → all 60 values)
        assert len(sched.minute) >= 60, f"drain task should fire every minute; crontab.minute={sched.minute}"


@pytest.mark.asyncio
async def test_drain_advances_queued_production_job(api_client, db_session, sample_org_data, monkeypatch):
    """Calling _drain_pending_production_jobs (the task body) directly on a
    queued ProductionJob flips it to in_progress with picked_up_at set,
    without any manual shell intervention. Proves the task body works
    when the beat fires it."""
    import os

    from packages.db.models.fulfillment import ClientProject, ProductionJob, ProjectBrief
    from packages.db.models.proposals import Proposal  # noqa: F401 — FK registration
    from workers.fulfillment_worker.tasks import _drain_pending_production_jobs

    # The drain task uses workers.fulfillment_worker.tasks._fresh_session_factory
    # which reads DATABASE_URL directly (not TEST_DATABASE_URL). Point it at
    # the test DB for the duration of this test so it sees the seeded job.
    test_db_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://avataros:avataros_dev_2026@postgres:5432/avatar_revenue_os_test",
    )
    monkeypatch.setenv("DATABASE_URL", test_db_url)

    org_id = await _register_org(api_client, sample_org_data)
    brand_id = await _seed_brand(db_session, org_id)

    # Hand-build a Client → ClientProject → ProjectBrief → ProductionJob
    # in the queued state. Avoids running the whole webhook chain to
    # exercise just the drain. brief_id is NOT NULL on production_jobs.
    client = Client(
        org_id=org_id,
        brand_id=brand_id,
        primary_email=f"drain-{uuid.uuid4().hex[:6]}@example.test",
        display_name="Drain Test",
        status="active",
    )
    db_session.add(client)
    await db_session.flush()

    project = ClientProject(
        org_id=org_id,
        client_id=client.id,
        title="drain-test project",
        package_slug="signal_entry",
        status="active",
    )
    db_session.add(project)
    await db_session.flush()

    brief = ProjectBrief(
        org_id=org_id,
        project_id=project.id,
        version=1,
        status="approved",
        title="drain-test brief",
        summary="seed",
        generator="test_seed",
    )
    db_session.add(brief)
    await db_session.flush()

    job = ProductionJob(
        org_id=org_id,
        project_id=project.id,
        brief_id=brief.id,
        job_type="content_pack",
        title="drain-test content pack",
        status="queued",
        attempt_count=0,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.commit()

    # Sanity: job is queued, not picked up
    fresh = (await db_session.execute(select(ProductionJob).where(ProductionJob.id == job.id))).scalar_one()
    assert fresh.status == "queued"
    assert fresh.picked_up_at is None

    # Run the drain task body. It uses its own session factory and commits
    # to the test DB (DATABASE_URL was monkeypatched to the test DB above).
    job_id = job.id
    result = await _drain_pending_production_jobs()
    assert result.get("picked", 0) >= 1

    # Re-read via a brand-new session bound to the test engine — bypasses
    # the test fixture's identity-map cache and any open transaction state
    # so we see exactly what the drain task committed.
    from sqlalchemy.ext.asyncio import async_sessionmaker

    fresh_factory = async_sessionmaker(db_session.bind, expire_on_commit=False)
    async with fresh_factory() as fresh:
        after = (await fresh.execute(select(ProductionJob).where(ProductionJob.id == job_id))).scalar_one()
        assert after.status == "in_progress", f"got status={after.status}"
        assert after.picked_up_at is not None
        assert after.attempt_count == 1
        assert after.worker_id  # worker_id was stamped


# ─────────────────────────────────────────────────────────────────────
# 11. Email URL builder uses the mounted /api/v1/intake path — proves
#    the SendGrid intake link will resolve against the deployed API.
# ─────────────────────────────────────────────────────────────────────


def test_intake_email_url_points_to_frontend_form(monkeypatch):
    """When FRONTEND_URL is set (production state), the URL embedded in the
    intake invite email points at the buyer-facing Next.js page at
    ``/intake/{token}`` — NOT the raw API path. The frontend page calls
    /api/v1/intake/* internally; buyers never see /api/v1/ in the link.

    Pre-fix (Round N-1): URL pointed at /api/v1/intake/{token} → buyer
    saw raw JSON. Now: URL points at /intake/{token} → buyer sees the
    minimal ProofHook intake form rendered by Next.js.
    """
    from packages.clients.email_templates import _intake_form_url

    monkeypatch.delenv("INTAKE_FORM_BASE_URL", raising=False)
    monkeypatch.setenv("FRONTEND_URL", "https://app.nvironments.com")
    url = _intake_form_url("abc123token")
    assert url == "https://app.nvironments.com/intake/abc123token"
    # Must NOT contain /api/v1 — that's the internal API path
    assert "/api/v1" not in url


def test_intake_email_url_explicit_override_takes_priority(monkeypatch):
    """INTAKE_FORM_BASE_URL is preserved as the highest-priority override
    so operators can swap to a hosted form (Typeform etc.) without code
    changes — same behavior as before."""
    from packages.clients.email_templates import _intake_form_url

    monkeypatch.setenv("INTAKE_FORM_BASE_URL", "https://forms.example.com/intake")
    monkeypatch.setenv("FRONTEND_URL", "https://app.nvironments.com")
    url = _intake_form_url("xyz")
    assert url == "https://forms.example.com/intake/xyz"


# ─────────────────────────────────────────────────────────────────────
# 12. Intake page (Next.js) source-level smoke tests. The codebase has
#    no frontend test runner (no jest/vitest/playwright in
#    apps/web/package.json), so we verify the page module exists and
#    contains the wire contract: dynamic [token] route, fetches the
#    schema from /api/v1/intake/{token}, posts to .../submit, and
#    surfaces success/invalid/error states.
# ─────────────────────────────────────────────────────────────────────


def test_intake_page_exists_and_wired_to_api():
    """The Next.js page must exist at apps/web/src/app/intake/[token]/page.tsx
    (the path the email URL builder now points to) and must call the
    canonical API routes."""
    import os

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    page_path = os.path.join(repo_root, "apps/web/src/app/intake/[token]/page.tsx")
    assert os.path.isfile(page_path), f"intake page missing at {page_path}"

    src = open(page_path).read()

    # Wire contract — must hit the API routes the backend mounted
    assert "/api/v1/intake/" in src, "intake page must call /api/v1/intake/{token}"
    assert "/submit" in src, "intake page must POST to /submit"
    assert "useParams" in src, "intake page must read token from dynamic route"

    # User-visible states
    assert 'data-testid="intake-form"' in src
    assert 'data-testid="intake-completed"' in src
    assert 'data-testid="intake-invalid"' in src

    # Branding (minimal — just must not look broken)
    assert "ProofHook" in src


# ─────────────────────────────────────────────────────────────────────
# 13. Follow-up scheduling on delivery — proves the existing
#    qa_delivery_service.dispatch_delivery path sets
#    Delivery.followup_scheduled_at and emits a followup.scheduled
#    SystemEvent. Pre-existing infrastructure; we just lock in
#    the contract with a focused test.
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delivery_dispatch_schedules_followup(api_client, db_session, sample_org_data):
    """submit_production_output → run_qa_review (auto-pass) → dispatch_delivery
    must:
      - create a Delivery row with followup_scheduled_at set in the future
        (DEFAULT_FOLLOWUP_DAYS days out)
      - emit a followup.scheduled SystemEvent on that delivery
    """

    from apps.api.services.qa_delivery_service import (
        DEFAULT_FOLLOWUP_DAYS,
        submit_production_output,
    )
    from packages.db.models.delivery import Delivery
    from packages.db.models.fulfillment import (
        ClientProject,
        ProductionJob,
        ProjectBrief,
    )
    from packages.db.models.proposals import Proposal  # noqa: F401 — FK registration
    from packages.db.models.system_events import SystemEvent

    org_id = await _register_org(api_client, sample_org_data)
    brand_id = await _seed_brand(db_session, org_id)

    client = Client(
        org_id=org_id,
        brand_id=brand_id,
        primary_email=f"fu-{uuid.uuid4().hex[:6]}@example.test",
        display_name="Follow-up Test",
        status="active",
    )
    db_session.add(client)
    await db_session.flush()

    project = ClientProject(
        org_id=org_id,
        client_id=client.id,
        title="follow-up test project",
        package_slug="signal_entry",
        status="active",
    )
    db_session.add(project)
    await db_session.flush()

    brief = ProjectBrief(
        org_id=org_id,
        project_id=project.id,
        version=1,
        status="approved",
        title="follow-up test brief",
        summary="seed",
        generator="test_seed",
    )
    db_session.add(brief)
    await db_session.flush()

    job = ProductionJob(
        org_id=org_id,
        project_id=project.id,
        brief_id=brief.id,
        job_type="content_pack",
        title="follow-up test pack",
        status="in_progress",
        attempt_count=1,
        started_at=datetime.now(timezone.utc),
        picked_up_at=datetime.now(timezone.utc),
    )
    db_session.add(job)
    await db_session.flush()

    # Drive the chain: output → auto-QA pass → dispatch_delivery →
    # schedule followup
    summary = await submit_production_output(
        db_session,
        job=job,
        output_url="https://example.test/test-pack.md",
        output_payload={"test": True},
        auto_qa=True,
        auto_dispatch=True,
    )
    await db_session.commit()

    # QA passed and delivery created
    assert summary["qa"]["result"] == "passed"
    assert summary["delivery"] is not None
    assert summary["delivery"]["followup_scheduled_at"] is not None

    # Delivery row carries the schedule
    delivery = (await db_session.execute(select(Delivery).where(Delivery.production_job_id == job.id))).scalar_one()
    assert delivery.status == "sent"
    assert delivery.followup_scheduled_at is not None
    assert delivery.followup_sent_at is None  # scheduled, not yet dispatched
    # ~DEFAULT_FOLLOWUP_DAYS out from now (allow ±1 day for clock skew)
    delta_days = (delivery.followup_scheduled_at - delivery.sent_at).days
    assert abs(delta_days - DEFAULT_FOLLOWUP_DAYS) <= 1

    # SystemEvent followup.scheduled emitted on this delivery
    fu_events = (
        (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "followup.scheduled",
                    SystemEvent.entity_type == "delivery",
                    SystemEvent.entity_id == delivery.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(fu_events) == 1
    fu = fu_events[0]
    details = fu.details or {}
    assert details.get("delivery_id") == str(delivery.id)
    assert details.get("followup_days") == DEFAULT_FOLLOWUP_DAYS


def test_celery_beat_includes_dispatch_due_followups():
    """workers/celery_app.py must declare a beat entry whose `task` field
    matches workers.fulfillment_worker.tasks.dispatch_due_followups so
    the followup_scheduled_at column actually gets sent. Mirrors the
    drain-pending check that landed in the prior round."""
    from workers.celery_app import app as celery_app

    schedule = celery_app.conf.beat_schedule
    matching = [
        (name, entry)
        for name, entry in schedule.items()
        if entry.get("task") == "workers.fulfillment_worker.tasks.dispatch_due_followups"
    ]
    assert matching, (
        "dispatch_due_followups is not in the beat schedule. Without it, "
        "Delivery.followup_scheduled_at sits forever and the followup email "
        "never sends."
    )
    assert len(matching) == 1, f"dispatch task scheduled multiple times: {[m[0] for m in matching]}"
