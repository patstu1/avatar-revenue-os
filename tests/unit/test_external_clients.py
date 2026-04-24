"""Unit tests for real external service clients."""

import base64
import hashlib
import hmac
import json
import time

import pytest

from packages.clients.external_clients import (
    BufferClient,
    GoogleAdsClient,
    MetaAdsClient,
    ShopifyOrderClient,
    ShopifyWebhookVerifier,
    SmtpEmailClient,
    StripePaymentClient,
    StripeWebhookVerifier,
    TikTokAdsClient,
    TwilioSmsClient,
)

# ── Stripe Webhook Verification ──────────────────────────────────────


def test_stripe_valid_signature():
    payload = json.dumps({"id": "evt_test", "type": "checkout.session.completed"}).encode()
    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.{payload.decode()}"
    sig = hmac.new(b"whsec_test123", signed_payload.encode(), hashlib.sha256).hexdigest()
    header = f"t={timestamp},v1={sig}"

    result = StripeWebhookVerifier.verify(payload, header, "whsec_test123")

    assert result["valid"] is True
    assert result["error"] is None
    assert result["event_type"] == "checkout.session.completed"
    assert result["event_id"] == "evt_test"
    assert result["payload"]["id"] == "evt_test"


def test_stripe_invalid_signature():
    payload = json.dumps({"id": "evt_bad", "type": "charge.failed"}).encode()
    timestamp = str(int(time.time()))
    header = f"t={timestamp},v1=deadbeef0000"

    result = StripeWebhookVerifier.verify(payload, header, "whsec_test123")

    assert result["valid"] is False
    assert "ignature" in (result["error"] or "").lower() or "mismatch" in (result["error"] or "").lower()


def test_stripe_expired_timestamp():
    payload = json.dumps({"id": "evt_old", "type": "invoice.paid"}).encode()
    old_ts = str(int(time.time()) - 600)
    signed_payload = f"{old_ts}.{payload.decode()}"
    sig = hmac.new(b"whsec_test123", signed_payload.encode(), hashlib.sha256).hexdigest()
    header = f"t={old_ts},v1={sig}"

    result = StripeWebhookVerifier.verify(payload, header, "whsec_test123")

    assert result["valid"] is False
    assert any(w in (result["error"] or "").lower() for w in ("timestamp", "stale", "tolerance"))


def test_stripe_malformed_header():
    payload = json.dumps({"id": "evt_x"}).encode()

    result = StripeWebhookVerifier.verify(payload, "garbage", "whsec_test123")

    assert result["valid"] is False
    assert result["error"] is not None


def test_stripe_extracts_event_type():
    event_data = {"id": "evt_extract", "type": "payment_intent.succeeded"}
    payload = json.dumps(event_data).encode()
    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.{payload.decode()}"
    sig = hmac.new(b"whsec_key", signed_payload.encode(), hashlib.sha256).hexdigest()
    header = f"t={timestamp},v1={sig}"

    result = StripeWebhookVerifier.verify(payload, header, "whsec_key")

    assert result["valid"] is True
    assert result["event_type"] == "payment_intent.succeeded"
    assert result["event_id"] == "evt_extract"


# ── Shopify Webhook Verification ─────────────────────────────────────


def test_shopify_valid_hmac():
    payload = json.dumps({"id": 123, "topic": "orders/create"}).encode()
    secret = "shopify_secret"
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    hmac_header = base64.b64encode(digest).decode()

    result = ShopifyWebhookVerifier.verify(payload, hmac_header, secret)

    assert result["valid"] is True
    assert result["error"] is None
    assert result["payload"]["id"] == 123


def test_shopify_invalid_hmac():
    payload = json.dumps({"id": 456}).encode()

    result = ShopifyWebhookVerifier.verify(payload, "wrong_hmac_value", "shopify_secret")

    assert result["valid"] is False
    assert "mismatch" in (result["error"] or "").lower() or "hmac" in (result["error"] or "").lower()


def test_shopify_extracts_payload():
    data = {"id": 789, "topic": "products/update", "title": "Widget"}
    payload = json.dumps(data).encode()
    secret = "shopsecret"
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    hmac_header = base64.b64encode(digest).decode()

    result = ShopifyWebhookVerifier.verify(payload, hmac_header, secret)

    assert result["valid"] is True
    assert result["payload"]["title"] == "Widget"
    assert result["payload"]["id"] == 789


# ── Buffer Client ────────────────────────────────────────────────────


def test_buffer_client_not_configured():
    client = BufferClient(api_key="")
    assert client._is_configured() is False


def test_buffer_client_configured():
    client = BufferClient(api_key="real_key_value")
    assert client._is_configured() is True


# ── Ad Platform Clients ──────────────────────────────────────────────


def test_meta_ads_not_configured(monkeypatch):
    monkeypatch.delenv("META_ADS_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("META_ADS_ACCOUNT_ID", raising=False)
    client = MetaAdsClient()
    assert client._is_configured() is False


def test_google_ads_not_configured(monkeypatch):
    monkeypatch.delenv("GOOGLE_ADS_DEVELOPER_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_CUSTOMER_ID", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_OAUTH_TOKEN", raising=False)
    client = GoogleAdsClient()
    assert client._is_configured() is False


def test_tiktok_ads_not_configured(monkeypatch):
    monkeypatch.delenv("TIKTOK_ADS_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("TIKTOK_ADS_ADVERTISER_ID", raising=False)
    client = TikTokAdsClient()
    assert client._is_configured() is False


# ── SMTP Client ──────────────────────────────────────────────────────


def test_smtp_not_configured(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_FROM_EMAIL", raising=False)
    client = SmtpEmailClient()
    assert client._is_configured() is False


def test_smtp_configured(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "noreply@example.com")
    client = SmtpEmailClient()
    assert client._is_configured() is True


# ── Twilio Client ────────────────────────────────────────────────────


def test_twilio_not_configured(monkeypatch):
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_FROM_NUMBER", raising=False)
    client = TwilioSmsClient()
    assert client._is_configured() is False


def test_twilio_configured(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_test")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "auth_tok")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15551234567")
    client = TwilioSmsClient()
    assert client._is_configured() is True


# ── Blocked Result Tests (async) ─────────────────────────────────────


@pytest.mark.asyncio
async def test_buffer_create_update_blocked():
    client = BufferClient(api_key="")
    result = await client.create_update(["profile_1"], "Hello world")
    assert result["blocked"] is True
    assert result["success"] is False
    assert "BUFFER_API_KEY" in result.get("error", "")


@pytest.mark.asyncio
async def test_smtp_send_blocked(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_FROM_EMAIL", raising=False)
    client = SmtpEmailClient()
    result = await client.send_email("user@example.com", "Test Subject")
    assert result["blocked"] is True
    assert result["success"] is False
    assert "SMTP" in result.get("error", "")


@pytest.mark.asyncio
async def test_twilio_send_blocked(monkeypatch):
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_FROM_NUMBER", raising=False)
    client = TwilioSmsClient()
    result = await client.send_sms("+15559876543", "Hello from test")
    assert result["blocked"] is True
    assert result["success"] is False
    assert "TWILIO" in result.get("error", "")


# ── Additional Coverage ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_meta_ads_fetch_blocked(monkeypatch):
    monkeypatch.delenv("META_ADS_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("META_ADS_ACCOUNT_ID", raising=False)
    client = MetaAdsClient()
    result = await client.fetch_campaign_insights()
    assert result["blocked"] is True
    assert result["success"] is False


@pytest.mark.asyncio
async def test_google_ads_fetch_blocked(monkeypatch):
    monkeypatch.delenv("GOOGLE_ADS_DEVELOPER_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_CUSTOMER_ID", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_OAUTH_TOKEN", raising=False)
    client = GoogleAdsClient()
    result = await client.fetch_campaign_report()
    assert result["blocked"] is True
    assert result["success"] is False


@pytest.mark.asyncio
async def test_tiktok_ads_fetch_blocked(monkeypatch):
    monkeypatch.delenv("TIKTOK_ADS_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("TIKTOK_ADS_ADVERTISER_ID", raising=False)
    client = TikTokAdsClient()
    result = await client.fetch_campaign_report()
    assert result["blocked"] is True
    assert result["success"] is False


@pytest.mark.asyncio
async def test_buffer_get_update_blocked():
    client = BufferClient(api_key="")
    result = await client.get_update("update_123")
    assert result["success"] is True
    assert result["blocked"] is False


@pytest.mark.asyncio
async def test_buffer_get_profiles_blocked():
    client = BufferClient(api_key="")
    result = await client.get_profiles()
    assert result["blocked"] is True
    assert result["success"] is False


def test_stripe_no_webhook_secret():
    payload = b'{"id":"x"}'
    result = StripeWebhookVerifier.verify(payload, "t=123,v1=abc", "")
    assert result["valid"] is False
    assert "secret" in (result["error"] or "").lower()


def test_shopify_no_api_secret():
    payload = b'{"id":1}'
    result = ShopifyWebhookVerifier.verify(payload, "abc", "")
    assert result["valid"] is False
    assert "secret" in (result["error"] or "").lower()


# ---------------------------------------------------------------------------
# Stripe Batch Payment Client
# ---------------------------------------------------------------------------


def test_stripe_payment_client_not_configured():
    c = StripePaymentClient()
    assert not c._is_configured()


def test_stripe_payment_client_configured(monkeypatch):
    monkeypatch.setenv("STRIPE_API_KEY", "sk_test_xxx")
    c = StripePaymentClient()
    assert c._is_configured()


@pytest.mark.asyncio
async def test_stripe_payment_fetch_blocked():
    c = StripePaymentClient()
    result = await c.fetch_recent_charges()
    assert result["blocked"] is True
    assert result["success"] is False


@pytest.mark.asyncio
async def test_stripe_payment_intents_blocked():
    c = StripePaymentClient()
    result = await c.fetch_recent_payment_intents()
    assert result["blocked"] is True


# ---------------------------------------------------------------------------
# Shopify Batch Order Client
# ---------------------------------------------------------------------------


def test_shopify_order_client_not_configured():
    c = ShopifyOrderClient()
    assert not c._is_configured()


def test_shopify_order_client_configured(monkeypatch):
    monkeypatch.setenv("SHOPIFY_SHOP_DOMAIN", "test.myshopify.com")
    monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", "shpat_xxx")
    c = ShopifyOrderClient()
    assert c._is_configured()


@pytest.mark.asyncio
async def test_shopify_order_fetch_blocked():
    c = ShopifyOrderClient()
    result = await c.fetch_recent_orders()
    assert result["blocked"] is True
    assert result["success"] is False
