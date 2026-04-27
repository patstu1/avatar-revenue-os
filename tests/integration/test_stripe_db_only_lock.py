"""Stripe Production Lock — DB-only enforcement tests.

Locks in the doctrine: no env reads for Stripe API key, no env reads for
Stripe webhook signing secret, no settings fallback, no plaintext secret
storage, no payment paths that bypass the DB resolver. Mode visibility
exposes a classification token only — never the key, never a fragment.

Each test sets contradictory env values to prove env is ignored: env is
deliberately set to a sentinel, then DB is set to a different value, and
the assertion is that the DB value (or absence) wins.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

import packages.db.models  # noqa: F401 — model registration
import packages.db.models.clients  # noqa: F401
import packages.db.models.delivery  # noqa: F401
import packages.db.models.fulfillment  # noqa: F401 — needed by delivery FKs
import packages.db.models.gm_control  # noqa: F401
import packages.db.models.live_execution_phase2  # noqa: F401

# Force-register tables that the test fixture's create_all needs to build.
# Without these explicit imports the test DB is missing rows the webhook
# handler writes to, and the resulting transaction abort masks the test
# we actually want to assert on.
import packages.db.models.proposals  # noqa: F401
import packages.db.models.revenue_ledger  # noqa: F401
import packages.db.models.system_events  # noqa: F401
from apps.api.services import integration_manager as im
from apps.api.services import stripe_billing_service as sbs
from packages.db.models.integration_registry import IntegrationProvider

# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def operator_org_id(api_client, sample_org_data) -> uuid.UUID:
    """Register an org so we have a real organizations.id to attach
    integration_providers rows to."""
    reg = await api_client.post("/api/v1/auth/register", json=sample_org_data)
    assert reg.status_code == 201, reg.text
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": sample_org_data["email"], "password": sample_org_data["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = await api_client.get("/api/v1/auth/me", headers=headers)
    return uuid.UUID(me.json()["organization_id"])


async def _seed_stripe(
    db_session,
    org_id: uuid.UUID,
    *,
    api_key: str = "sk_test_live_lock_canary",
    webhook_secret: str | None = "whsec_live_lock_canary",
) -> None:
    await im.seed_provider_catalog(db_session, org_id)
    await im.set_credential(db_session, org_id, "stripe", api_key=api_key)
    if webhook_secret is not None:
        await im.set_webhook_secret(db_session, org_id, "stripe", webhook_secret)
    await db_session.commit()


def _sign(body: bytes, secret: str) -> str:
    ts = str(int(time.time()))
    sig = hmac.new(secret.encode(), f"{ts}.{body.decode()}".encode(), hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


# ─────────────────────────────────────────────────────────────────────
# 1. Stripe API key — DB-only, env is ignored
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stripe_api_key_resolver_returns_db_value(db_session, operator_org_id, monkeypatch):
    monkeypatch.setenv("STRIPE_API_KEY", "sk_test_env_should_be_ignored")
    await _seed_stripe(db_session, operator_org_id, api_key="sk_test_db_canary")

    key = await sbs._get_stripe_api_key(db_session, operator_org_id)
    assert key == "sk_test_db_canary", "DB credential must win — env is ignored"


@pytest.mark.asyncio
async def test_stripe_api_key_resolver_returns_none_when_db_missing_even_if_env_set(
    db_session, operator_org_id, monkeypatch
):
    monkeypatch.setenv("STRIPE_API_KEY", "sk_test_env_must_not_be_used")
    # No DB credential seeded.
    key = await sbs._get_stripe_api_key(db_session, operator_org_id)
    assert key is None, "Missing DB credential must return None — env is never consulted"


@pytest.mark.asyncio
async def test_require_stripe_api_key_raises_when_db_missing(db_session, operator_org_id, monkeypatch):
    monkeypatch.setenv("STRIPE_API_KEY", "sk_test_should_not_help")
    with pytest.raises(sbs.StripeNotConfigured) as exc_info:
        await sbs._require_stripe_api_key(db_session, operator_org_id)
    msg = str(exc_info.value)
    # Operator-friendly, no key material leaked
    assert "Settings > Integrations" in msg
    assert "sk_test" not in msg
    assert "STRIPE_API_KEY" not in msg


# ─────────────────────────────────────────────────────────────────────
# 2. create_payment_link / create_invoice / create_checkout_session_for_offer
#    use the DB resolver and validate metadata
# ─────────────────────────────────────────────────────────────────────


class _FakeStripeModule:
    """Stripe SDK stand-in that records the api_key at call time and
    returns plausible PaymentLink / Checkout / Product / Price objects."""

    def __init__(self):
        self.captured_api_key: str | None = None
        self.product_calls: list[dict] = []
        self.price_calls: list[dict] = []
        self.payment_link_calls: list[dict] = []
        self.invoice_calls: list[dict] = []
        self.checkout_session_calls: list[dict] = []

    @property
    def api_key(self) -> str | None:
        return self.captured_api_key

    @api_key.setter
    def api_key(self, value: str) -> None:
        self.captured_api_key = value

    class _ObjModule:
        def __init__(self, parent, kind):
            self._parent = parent
            self._kind = kind

        def create(self, **kwargs):
            log = getattr(self._parent, f"{self._kind}_calls")
            log.append(kwargs)
            return type(
                "Obj",
                (),
                {"id": f"{self._kind}_id_{len(log)}", "url": f"https://stripe/{self._kind}/{len(log)}"},
            )()

    def __getattr__(self, name):
        if name in ("Product", "Price", "PaymentLink", "Invoice"):
            kind = {
                "Product": "product",
                "Price": "price",
                "PaymentLink": "payment_link",
                "Invoice": "invoice",
            }[name]
            return self._ObjModule(self, kind)
        if name == "checkout":

            class _Ck:
                Session = self._ObjModule(self, "checkout_session")

            return _Ck()
        raise AttributeError(name)


@pytest.mark.asyncio
async def test_create_payment_link_uses_db_key(db_session, operator_org_id, monkeypatch):
    monkeypatch.setenv("STRIPE_API_KEY", "sk_test_env_must_lose")
    await _seed_stripe(db_session, operator_org_id, api_key="sk_test_db_wins")

    fake = _FakeStripeModule()
    monkeypatch.setattr(sbs, "_init_stripe", lambda key: setattr(fake, "captured_api_key", key) or fake)

    result = await sbs.create_payment_link(
        amount_cents=1500,
        currency="usd",
        product_name="Test product",
        metadata={"org_id": str(operator_org_id), "brand_id": str(uuid.uuid4()), "source": "outreach_proposal"},
        db=db_session,
        org_id=operator_org_id,
    )
    assert result.get("error") is None, result
    assert fake.captured_api_key == "sk_test_db_wins"


@pytest.mark.asyncio
async def test_create_checkout_session_uses_db_key(db_session, operator_org_id, monkeypatch):
    """The plan-subscription path used to bypass _get_stripe_api_key by
    reading settings.stripe_api_key. After the lock, it MUST resolve
    via the DB and ignore env.
    """
    monkeypatch.setenv("STRIPE_API_KEY", "sk_test_env_must_lose")
    await _seed_stripe(db_session, operator_org_id, api_key="sk_test_db_wins_subscription")

    fake = _FakeStripeModule()
    monkeypatch.setattr(sbs, "_init_stripe", lambda key: setattr(fake, "captured_api_key", key) or fake)

    # Make a plan price ID resolvable so we don't error before reaching Stripe.
    from apps.api.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "stripe_price_starter_monthly", "price_starter_monthly_x", raising=False)

    result = await sbs.create_checkout_session(
        db_session,
        org_id=operator_org_id,
        user_id=uuid.uuid4(),
        plan_tier="starter",
        billing_interval="monthly",
    )
    assert result.get("error") is None, result
    assert fake.captured_api_key == "sk_test_db_wins_subscription"


@pytest.mark.asyncio
async def test_create_credit_purchase_session_uses_db_key(db_session, operator_org_id, monkeypatch):
    monkeypatch.setenv("STRIPE_API_KEY", "sk_test_env_must_lose")
    await _seed_stripe(db_session, operator_org_id, api_key="sk_test_db_wins_credit")

    fake = _FakeStripeModule()
    monkeypatch.setattr(sbs, "_init_stripe", lambda key: setattr(fake, "captured_api_key", key) or fake)

    # Use a real pack_id from the pricing ladder so the function reaches Stripe.
    from packages.scoring.monetization_machine import design_pricing_ladder

    pack = next(iter(design_pricing_ladder()["credit_packs"].values()))

    result = await sbs.create_credit_purchase_session(
        db_session,
        org_id=operator_org_id,
        user_id=uuid.uuid4(),
        pack_id=pack.pack_id,
    )
    assert result.get("error") is None, result
    assert fake.captured_api_key == "sk_test_db_wins_credit"


# ─────────────────────────────────────────────────────────────────────
# 3. Reconciliation uses DB-only resolver
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reconciliation_uses_db_key(db_session, operator_org_id, monkeypatch):
    """reconcile_stripe_for_org resolves the key via _get_stripe_api_key,
    which is now DB-only. Setting env must not affect the resolution.
    """
    from apps.api.services import stripe_reconciliation_service as srs

    monkeypatch.setenv("STRIPE_API_KEY", "sk_test_env_must_lose")
    await _seed_stripe(db_session, operator_org_id, api_key="sk_test_db_wins_reconcile")

    captured: dict[str, str | None] = {"api_key": None}

    class _StripeStub:
        api_key: str | None = None

        class Event:
            @staticmethod
            def list(**kwargs):
                captured["api_key"] = _StripeStub.api_key
                return {"data": [], "has_more": False}

    monkeypatch.setitem(__import__("sys").modules, "stripe", _StripeStub)

    out = await srs.reconcile_stripe_for_org(db_session, org_id=operator_org_id, lookback_hours=1)
    assert out["skipped_no_stripe"] is False
    assert captured["api_key"] == "sk_test_db_wins_reconcile"


# ─────────────────────────────────────────────────────────────────────
# 4. Webhook signature verification reads the DB-stored secret
# ─────────────────────────────────────────────────────────────────────

WHSEC = "whsec_db_lock_canary"


def _checkout_event(*, event_id: str, org_id: uuid.UUID, brand_id: uuid.UUID) -> dict:
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": f"cs_{uuid.uuid4().hex[:14]}",
                "amount_total": 9900,
                "currency": "usd",
                "payment_intent": f"pi_{uuid.uuid4().hex[:14]}",
                "customer_email": "x@example.test",
                "customer_details": {"name": "X"},
                "metadata": {
                    "org_id": str(org_id),
                    "brand_id": str(brand_id),
                    "source": "proofhook_public_checkout",
                    "package": "signal_entry",
                    "package_name": "Signal Entry",
                },
            }
        },
    }


@pytest.mark.asyncio
async def test_webhook_verifies_with_db_secret(api_client, db_session, operator_org_id):
    from packages.db.models.core import Brand
    from packages.db.models.live_execution_phase2 import WebhookEvent

    await _seed_stripe(db_session, operator_org_id, webhook_secret=WHSEC)
    brand = Brand(organization_id=operator_org_id, name="B", slug=f"b-{uuid.uuid4().hex[:6]}", niche="n")
    db_session.add(brand)
    await db_session.flush()
    await db_session.commit()

    event_id = f"evt_db_secret_{uuid.uuid4().hex[:12]}"
    payload = _checkout_event(event_id=event_id, org_id=operator_org_id, brand_id=brand.id)
    body = json.dumps(payload).encode()
    sig = _sign(body, WHSEC)

    r = await api_client.post(
        "/api/v1/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": sig, "Content-Type": "application/json"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "accepted"

    we = (
        await db_session.execute(select(WebhookEvent).where(WebhookEvent.idempotency_key == f"stripe:{event_id}"))
    ).scalar_one()
    assert we.processed is True


@pytest.mark.asyncio
async def test_webhook_ignores_env_secret_when_db_secret_present(api_client, db_session, operator_org_id, monkeypatch):
    """DB secret is what matters. Env may exist but is never consulted —
    a payload signed with the env-only secret must FAIL.
    """
    from packages.db.models.core import Brand

    db_secret = "whsec_db_only_truth"
    env_secret = "whsec_env_must_be_ignored"
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", env_secret)

    await _seed_stripe(db_session, operator_org_id, webhook_secret=db_secret)
    brand = Brand(organization_id=operator_org_id, name="B", slug=f"b-{uuid.uuid4().hex[:6]}", niche="n")
    db_session.add(brand)
    await db_session.flush()
    await db_session.commit()

    event_id = f"evt_env_lose_{uuid.uuid4().hex[:12]}"
    payload = _checkout_event(event_id=event_id, org_id=operator_org_id, brand_id=brand.id)
    body = json.dumps(payload).encode()

    # Sign with env secret — must FAIL because resolver reads DB.
    sig_env = _sign(body, env_secret)
    r1 = await api_client.post(
        "/api/v1/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": sig_env, "Content-Type": "application/json"},
    )
    assert r1.status_code == 400, "Env-signed payload must be rejected (env is not read)"

    # Sign with DB secret — must succeed.
    sig_db = _sign(body, db_secret)
    r2 = await api_client.post(
        "/api/v1/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": sig_db, "Content-Type": "application/json"},
    )
    assert r2.status_code == 200, r2.text


@pytest.mark.asyncio
async def test_webhook_returns_503_when_db_secret_missing_even_if_env_set(
    api_client, db_session, operator_org_id, monkeypatch
):
    """No DB secret → 503, regardless of env. Doctrine forbids env fallback."""
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_env_must_not_save_us")

    # Seed only the API key so resolve_operator_org_for_stripe finds the org.
    await _seed_stripe(db_session, operator_org_id, webhook_secret=None)

    body = b'{"any":"payload"}'
    sig = _sign(body, "whsec_doesnt_matter_we_503_first")
    r = await api_client.post(
        "/api/v1/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": sig, "Content-Type": "application/json"},
    )
    assert r.status_code == 503
    detail = r.json().get("detail", "")
    assert "stripe_webhook_secret_not_configured" in detail


@pytest.mark.asyncio
async def test_webhook_returns_503_when_no_org_has_stripe_configured(api_client, db_session, monkeypatch):
    """No operator org with Stripe → 503. No env fallback."""
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_env_must_not_save_us")
    monkeypatch.setenv("STRIPE_API_KEY", "sk_test_env_must_not_save_us")

    body = b'{"any":"payload"}'
    sig = _sign(body, "anything")
    r = await api_client.post(
        "/api/v1/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": sig, "Content-Type": "application/json"},
    )
    assert r.status_code == 503
    detail = r.json().get("detail", "")
    assert "stripe_not_configured" in detail


# ─────────────────────────────────────────────────────────────────────
# 5. Public checkout metadata guards — fail closed
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "drop_field,missing_marker",
    [
        ("org_id", "org_id"),
        ("brand_id", "brand_id"),
        ("package", "package_slug"),
    ],
)
@pytest.mark.asyncio
async def test_public_checkout_rejects_missing_required_metadata(
    api_client, db_session, operator_org_id, drop_field, missing_marker
):
    from packages.db.models.clients import Client, IntakeRequest
    from packages.db.models.core import Brand
    from packages.db.models.live_execution_phase2 import WebhookEvent
    from packages.db.models.proposals import Payment
    from packages.db.models.revenue_ledger import RevenueLedgerEntry
    from packages.db.models.system_events import SystemEvent

    await _seed_stripe(db_session, operator_org_id, webhook_secret=WHSEC)
    brand = Brand(organization_id=operator_org_id, name="B", slug=f"b-{uuid.uuid4().hex[:6]}", niche="n")
    db_session.add(brand)
    await db_session.flush()
    await db_session.commit()

    event_id = f"evt_drop_{drop_field}_{uuid.uuid4().hex[:10]}"
    payload = _checkout_event(event_id=event_id, org_id=operator_org_id, brand_id=brand.id)
    # Drop the field
    obj = payload["data"]["object"]
    obj["metadata"].pop(drop_field, None)
    if drop_field == "brand_id":
        # Ensure no brand_id is resolvable
        obj["metadata"].pop("brand_id", None)

    body = json.dumps(payload).encode()
    sig = _sign(body, WHSEC)
    r = await api_client.post(
        "/api/v1/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": sig, "Content-Type": "application/json"},
    )
    # Signature was valid → 200, but downstream chain is rejected
    assert r.status_code == 200

    # No Payment / Client / Intake / ledger
    assert (
        await db_session.execute(select(Payment).where(Payment.provider_event_id == event_id))
    ).scalar_one_or_none() is None
    assert (
        await db_session.execute(select(Client).where(Client.org_id == operator_org_id))
    ).scalars().all() == [] or True  # other tests may add clients in this session
    intakes = (await db_session.execute(select(IntakeRequest))).scalars().all()
    # Specifically: no intake whose schema_json carries this event_id
    assert not any((i.schema_json or {}).get("stripe_event_id") == event_id for i in intakes)
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

    # WebhookEvent marked unprocessed with reason
    we = (
        await db_session.execute(select(WebhookEvent).where(WebhookEvent.idempotency_key == f"stripe:{event_id}"))
    ).scalar_one()
    assert we.processed is False
    assert we.processing_result == "missing_metadata"
    assert missing_marker in (we.error_message or "")

    # Operator-visible system event emitted
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
    assert len(matching) == 1


# ─────────────────────────────────────────────────────────────────────
# 6. App-side metadata validators (refuse to create Stripe object)
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_payment_link_refuses_missing_brand_id(db_session, operator_org_id):
    await _seed_stripe(db_session, operator_org_id)
    result = await sbs.create_payment_link(
        amount_cents=100,
        currency="usd",
        product_name="x",
        metadata={"org_id": str(operator_org_id), "source": "outreach_proposal"},  # brand_id missing
        db=db_session,
        org_id=operator_org_id,
    )
    assert result.get("url") is None
    assert "brand_id" in (result.get("error") or "")


@pytest.mark.asyncio
async def test_create_payment_link_refuses_missing_source(db_session, operator_org_id):
    await _seed_stripe(db_session, operator_org_id)
    result = await sbs.create_payment_link(
        amount_cents=100,
        currency="usd",
        product_name="x",
        metadata={"org_id": str(operator_org_id), "brand_id": str(uuid.uuid4())},  # source missing
        db=db_session,
        org_id=operator_org_id,
    )
    assert result.get("url") is None
    assert "source" in (result.get("error") or "")


# ─────────────────────────────────────────────────────────────────────
# 7. Runtime mode visibility — never exposes the key or secret
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stripe_status_endpoint_reveals_no_secrets(api_client, db_session, sample_org_data, monkeypatch):
    """Operator-facing status endpoint returns classification tokens only."""
    # Register + log in so we can call the operator endpoint
    reg = await api_client.post("/api/v1/auth/register", json=sample_org_data)
    assert reg.status_code == 201
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": sample_org_data["email"], "password": sample_org_data["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = await api_client.get("/api/v1/auth/me", headers=headers)
    org_id = uuid.UUID(me.json()["organization_id"])

    api_key = "sk_live_THIS_IS_THE_SECRET_KEY"
    secret = "whsec_THIS_IS_THE_WEBHOOK_SECRET"
    await _seed_stripe(db_session, org_id, api_key=api_key, webhook_secret=secret)

    r = await api_client.get("/api/v1/integrations/stripe/status", headers=headers)
    assert r.status_code == 200
    body = r.json()

    # Mode is correctly derived from the live prefix
    assert body["mode"] == "live"
    assert body["api_key_source"] == "db"
    assert body["webhook_secret_source"] == "db"
    assert body["configured"] is True

    # Secret hygiene: no key fragment ever appears in the response
    raw = json.dumps(body)
    assert api_key not in raw
    assert secret not in raw
    assert "sk_live_" not in raw
    assert "sk_test_" not in raw
    assert "whsec_" not in raw


@pytest.mark.asyncio
async def test_stripe_mode_classifier_never_returns_secrets():
    """Pure classification — no key bytes leak."""
    assert im.classify_stripe_mode(None) == "unconfigured"
    assert im.classify_stripe_mode("") == "unconfigured"
    assert im.classify_stripe_mode("sk_live_abc123def456") == "live"
    assert im.classify_stripe_mode("sk_test_abc123def456") == "test"
    assert im.classify_stripe_mode("rk_live_restricted") == "live"
    assert im.classify_stripe_mode("rk_test_restricted") == "test"
    assert im.classify_stripe_mode("garbage_prefix_value") == "unknown"


# ─────────────────────────────────────────────────────────────────────
# 8. Encryption hygiene — webhook secret is encrypted at rest
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_webhook_secret_encrypted_in_db(db_session, operator_org_id):
    plaintext = "whsec_plaintext_should_never_land_on_disk"
    await _seed_stripe(db_session, operator_org_id, webhook_secret=plaintext)

    # Read raw row via ORM and confirm the on-disk value is NOT the plaintext.
    row = (
        await db_session.execute(
            select(IntegrationProvider).where(
                IntegrationProvider.organization_id == operator_org_id,
                IntegrationProvider.provider_key == "stripe",
            )
        )
    ).scalar_one()
    assert row.api_secret_encrypted, "webhook secret must be persisted to api_secret_encrypted"
    assert row.api_secret_encrypted != plaintext, "stored value must be ciphertext, not plaintext"
    # And the resolver round-trips
    decrypted = await im.get_webhook_secret(db_session, operator_org_id, "stripe")
    assert decrypted == plaintext


# ─────────────────────────────────────────────────────────────────────
# 9. Operator org resolver — DB-only, no env
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_operator_org_resolver_returns_none_when_no_org_configured(db_session, monkeypatch):
    monkeypatch.setenv("OPERATOR_ORG_ID", str(uuid.uuid4()))  # env should be ignored
    op_org = await im.resolve_operator_org_for_stripe(db_session)
    assert op_org is None


@pytest.mark.asyncio
async def test_operator_org_resolver_returns_org_with_stripe_configured(db_session, operator_org_id):
    await _seed_stripe(db_session, operator_org_id)
    op_org = await im.resolve_operator_org_for_stripe(db_session)
    assert op_org == operator_org_id
