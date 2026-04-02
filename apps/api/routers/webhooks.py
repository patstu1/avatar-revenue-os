"""Provider-specific webhook endpoints with signature/HMAC verification.

These are public — authentication is via the provider's own verification mechanism.
"""
import os
import uuid

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import select

from apps.api.deps import DBSession
from packages.clients.external_clients import StripeWebhookVerifier, ShopifyWebhookVerifier
from packages.db.models.live_execution_phase2 import WebhookEvent

router = APIRouter()


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: DBSession, stripe_signature: str = Header(alias="Stripe-Signature")):
    """Receive and verify a Stripe webhook event."""
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe webhook secret not configured")

    body = await request.body()
    result = StripeWebhookVerifier.verify(body, stripe_signature, secret)

    if not result["valid"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid signature: {result['error']}")

    # Idempotency: check if event_id already ingested
    event_id = result.get("event_id")
    if event_id:
        existing = (await db.execute(
            select(WebhookEvent).where(WebhookEvent.idempotency_key == f"stripe:{event_id}")
        )).scalar_one_or_none()
        if existing:
            return {"status": "duplicate", "event_id": event_id}

    # Determine brand_id from metadata if present (Stripe metadata.brand_id convention)
    payload = result.get("payload", {})
    brand_id = None
    meta = payload.get("data", {}).get("object", {}).get("metadata", {})
    if meta.get("brand_id"):
        try:
            brand_id = uuid.UUID(meta["brand_id"])
        except ValueError:
            pass

    event = WebhookEvent(
        brand_id=brand_id,
        source="stripe",
        source_category="payment",
        event_type=result.get("event_type", "unknown"),
        external_event_id=event_id,
        raw_payload=payload,
        processed=False,
        idempotency_key=f"stripe:{event_id}" if event_id else None,
    )
    db.add(event)
    await db.flush()

    event_type = result.get("event_type", "")
    obj = payload.get("data", {}).get("object", {})
    if brand_id and event_type in ("checkout.session.completed", "charge.succeeded", "payment_intent.succeeded"):
        from packages.db.models.creator_revenue import CreatorRevenueEvent
        revenue = float(obj.get("amount_total", obj.get("amount", 0))) / 100.0
        db.add(CreatorRevenueEvent(
            brand_id=brand_id,
            avenue_type="consulting" if "consulting" in str(meta) else "ugc_services",
            event_type="stripe_payment",
            revenue=revenue,
            cost=0.0,
            profit=revenue,
            client_name=obj.get("customer_email") or obj.get("receipt_email") or "",
            description=f"Stripe {event_type}: ${revenue:.2f}",
            metadata_json={"stripe_event_id": event_id, "stripe_event_type": event_type},
        ))
        event.processed = True
        await db.flush()

    return {"status": "accepted", "event_id": event_id, "webhook_event_id": str(event.id)}


@router.post("/webhooks/shopify")
async def shopify_webhook(request: Request, db: DBSession, x_shopify_hmac_sha256: str = Header(alias="X-Shopify-Hmac-SHA256"), x_shopify_topic: str = Header(alias="X-Shopify-Topic", default="")):
    """Receive and verify a Shopify webhook event."""
    secret = os.environ.get("SHOPIFY_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Shopify webhook secret not configured")

    body = await request.body()
    result = ShopifyWebhookVerifier.verify(body, x_shopify_hmac_sha256, secret)

    if not result["valid"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid HMAC: {result['error']}")

    payload = result.get("payload", {})

    # Idempotency via Shopify webhook id header if available
    shopify_id = request.headers.get("X-Shopify-Webhook-Id", "")
    idem_key = f"shopify:{shopify_id}" if shopify_id else None

    if idem_key:
        existing = (await db.execute(
            select(WebhookEvent).where(WebhookEvent.idempotency_key == idem_key)
        )).scalar_one_or_none()
        if existing:
            return {"status": "duplicate", "shopify_id": shopify_id}

    event = WebhookEvent(
        brand_id=None,  # Shopify doesn't carry our brand_id; resolved during processing
        source="shopify",
        source_category="payment",
        event_type=x_shopify_topic or "unknown",
        external_event_id=shopify_id or None,
        raw_payload=payload,
        processed=False,
        idempotency_key=idem_key,
    )
    db.add(event)
    await db.flush()
    return {"status": "accepted", "topic": x_shopify_topic, "webhook_event_id": str(event.id)}
