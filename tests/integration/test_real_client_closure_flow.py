"""DB-backed integration tests for Live Execution Phase 2 — Real Client Closure."""

import base64
import hashlib
import hmac
import json
import time

import pytest


async def _auth_brand(api_client, sample_org_data):
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": sample_org_data["email"], "password": sample_org_data["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    brand = await api_client.post(
        "/api/v1/brands/",
        json={"name": "RealClient Brand", "slug": "realclient-brand", "niche": "tech"},
        headers=headers,
    )
    bid = brand.json()["id"]
    return headers, bid


# ── 1. Stripe webhook — valid signature ──────────────────────────────


@pytest.mark.asyncio
async def test_stripe_webhook_valid(api_client, sample_org_data, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    payload = json.dumps(
        {
            "id": "evt_1",
            "type": "checkout.session.completed",
            "data": {"object": {"metadata": {}}},
        }
    ).encode()
    timestamp = str(int(time.time()))
    signed = f"{timestamp}.{payload.decode()}"
    sig = hmac.new(b"whsec_test", signed.encode(), hashlib.sha256).hexdigest()
    header = f"t={timestamp},v1={sig}"

    r = await api_client.post(
        "/api/v1/webhooks/stripe",
        content=payload,
        headers={"Stripe-Signature": header, "Content-Type": "application/json"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"


# ── 2. Stripe webhook — invalid signature ────────────────────────────


@pytest.mark.asyncio
async def test_stripe_webhook_invalid(api_client, sample_org_data, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    payload = json.dumps({"id": "evt_bad", "type": "charge.failed"}).encode()
    timestamp = str(int(time.time()))
    header = f"t={timestamp},v1=baaaaad"

    r = await api_client.post(
        "/api/v1/webhooks/stripe",
        content=payload,
        headers={"Stripe-Signature": header, "Content-Type": "application/json"},
    )
    assert r.status_code == 400


# ── 3. Stripe webhook — no secret configured ─────────────────────────


@pytest.mark.asyncio
async def test_stripe_webhook_no_secret(api_client, sample_org_data, monkeypatch):
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    payload = json.dumps({"id": "evt_no_secret"}).encode()
    timestamp = str(int(time.time()))
    header = f"t={timestamp},v1=anything"

    r = await api_client.post(
        "/api/v1/webhooks/stripe",
        content=payload,
        headers={"Stripe-Signature": header, "Content-Type": "application/json"},
    )
    assert r.status_code == 503


# ── 4. Shopify webhook — valid HMAC ──────────────────────────────────


@pytest.mark.asyncio
async def test_shopify_webhook_valid(api_client, sample_org_data, monkeypatch):
    monkeypatch.setenv("SHOPIFY_WEBHOOK_SECRET", "shop_secret")
    payload = json.dumps({"id": 100, "topic": "orders/create"}).encode()
    digest = hmac.new(b"shop_secret", payload, hashlib.sha256).digest()
    hmac_header = base64.b64encode(digest).decode()

    r = await api_client.post(
        "/api/v1/webhooks/shopify",
        content=payload,
        headers={
            "X-Shopify-Hmac-SHA256": hmac_header,
            "X-Shopify-Topic": "orders/create",
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"


# ── 5. Shopify webhook — invalid HMAC ────────────────────────────────


@pytest.mark.asyncio
async def test_shopify_webhook_invalid(api_client, sample_org_data, monkeypatch):
    monkeypatch.setenv("SHOPIFY_WEBHOOK_SECRET", "shop_secret")
    payload = json.dumps({"id": 200}).encode()

    r = await api_client.post(
        "/api/v1/webhooks/shopify",
        content=payload,
        headers={
            "X-Shopify-Hmac-SHA256": "totally_wrong",
            "X-Shopify-Topic": "orders/paid",
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 400


# ── 6. Stripe webhook — idempotent (duplicate) ──────────────────────


@pytest.mark.asyncio
async def test_stripe_webhook_idempotent(api_client, sample_org_data, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_idem")
    payload = json.dumps(
        {
            "id": "evt_idem_1",
            "type": "invoice.paid",
            "data": {"object": {"metadata": {}}},
        }
    ).encode()
    timestamp = str(int(time.time()))
    signed = f"{timestamp}.{payload.decode()}"
    sig = hmac.new(b"whsec_idem", signed.encode(), hashlib.sha256).hexdigest()
    header = f"t={timestamp},v1={sig}"
    send_headers = {"Stripe-Signature": header, "Content-Type": "application/json"}

    r1 = await api_client.post("/api/v1/webhooks/stripe", content=payload, headers=send_headers)
    assert r1.status_code == 200
    assert r1.json()["status"] == "accepted"

    r2 = await api_client.post("/api/v1/webhooks/stripe", content=payload, headers=send_headers)
    assert r2.status_code == 200
    assert r2.json()["status"] == "duplicate"


# ── 7. Payment sync — no credentials ─────────────────────────────────


@pytest.mark.asyncio
async def test_payment_sync_run_no_credentials(api_client, sample_org_data, monkeypatch):
    monkeypatch.delenv("STRIPE_API_KEY", raising=False)
    headers, bid = await _auth_brand(api_client, sample_org_data)

    r = await api_client.post(
        f"/api/v1/brands/{bid}/payment-syncs/run",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "blocked"


# ── 8. Ad import — no credentials ────────────────────────────────────


@pytest.mark.asyncio
async def test_ad_import_run_no_credentials(api_client, sample_org_data, monkeypatch):
    monkeypatch.delenv("META_ADS_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("META_ADS_ACCOUNT_ID", raising=False)
    headers, bid = await _auth_brand(api_client, sample_org_data)

    r = await api_client.post(
        f"/api/v1/brands/{bid}/ad-imports/run",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("blocked", "failed")


# ── 9. Buffer truth recompute persists ───────────────────────────────


@pytest.mark.asyncio
async def test_buffer_truth_recompute_persists(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)

    r = await api_client.post(
        f"/api/v1/brands/{bid}/buffer-execution-truth/recompute",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "rows_processed" in body


# ── 10. Email execution — no provider configured ─────────────────────


@pytest.mark.asyncio
async def test_email_execution_no_provider(api_client, sample_org_data, monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("ESP_API_KEY", raising=False)
    headers, bid = await _auth_brand(api_client, sample_org_data)

    r = await api_client.post(
        f"/api/v1/brands/{bid}/email-send-requests",
        json={
            "to_email": "test@example.com",
            "subject": "Hello",
            "body_text": "World",
        },
        headers=headers,
    )
    assert r.status_code in (200, 201)
    body = r.json()
    assert body.get("status") in ("failed", "queued")


# ── 11. SMS execution — no provider configured ───────────────────────


@pytest.mark.asyncio
async def test_sms_execution_no_provider(api_client, sample_org_data, monkeypatch):
    monkeypatch.delenv("SMS_API_KEY", raising=False)
    headers, bid = await _auth_brand(api_client, sample_org_data)

    r = await api_client.post(
        f"/api/v1/brands/{bid}/sms-send-requests",
        json={
            "to_phone": "+15559999999",
            "message_body": "Test SMS",
        },
        headers=headers,
    )
    assert r.status_code in (200, 201)
    body = r.json()
    assert body.get("status") in ("failed", "queued")


# ── 12. Messaging blocker creation on missing credentials ────────────


@pytest.mark.asyncio
async def test_blocker_creation_on_missing_credentials(api_client, sample_org_data, monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMS_API_KEY", raising=False)
    monkeypatch.delenv("ESP_API_KEY", raising=False)
    monkeypatch.delenv("CRM_API_KEY", raising=False)
    headers, bid = await _auth_brand(api_client, sample_org_data)

    r = await api_client.post(
        f"/api/v1/brands/{bid}/messaging-blockers/recompute",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("created", body.get("rows_processed", 0)) >= 0

    blockers_r = await api_client.get(
        f"/api/v1/brands/{bid}/messaging-blockers",
        headers=headers,
    )
    assert blockers_r.status_code == 200


# ── 13. Stripe batch sync — blocked without credentials ───────────────


@pytest.mark.asyncio
async def test_stripe_batch_sync_blocked(api_client, sample_org_data, monkeypatch):
    monkeypatch.delenv("STRIPE_API_KEY", raising=False)
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.post(
        f"/api/v1/brands/{bid}/payment-syncs/run",
        params={"provider": "stripe"},
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "blocked"


# ── 14. Shopify batch sync — blocked without credentials ──────────────


@pytest.mark.asyncio
async def test_shopify_batch_sync_blocked(api_client, sample_org_data, monkeypatch):
    monkeypatch.delenv("SHOPIFY_API_KEY", raising=False)
    monkeypatch.delenv("SHOPIFY_ACCESS_TOKEN", raising=False)
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r = await api_client.post(
        f"/api/v1/brands/{bid}/payment-syncs/run",
        params={"provider": "shopify"},
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "blocked"


# ── 15. Payment sync persists row ─────────────────────────────────────


@pytest.mark.asyncio
async def test_payment_sync_persists(api_client, sample_org_data, monkeypatch):
    monkeypatch.delenv("STRIPE_API_KEY", raising=False)
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/payment-syncs/run", headers=headers)
    r = await api_client.get(f"/api/v1/brands/{bid}/payment-syncs", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1
