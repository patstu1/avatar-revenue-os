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

    # ── Stripe Billing: subscription & credit-pack events ──
    from apps.api.services import stripe_billing_service as sbs
    import structlog as _sl
    _billing_log = _sl.get_logger()

    try:
        if event_type == "checkout.session.completed":
            if meta.get("type") == "credit_purchase":
                await sbs.handle_credit_purchase(db, obj)
                event.processed = True
                await db.flush()
            elif obj.get("mode") == "subscription":
                await sbs.handle_subscription_created(db, obj)
                event.processed = True
                await db.flush()
        elif event_type == "customer.subscription.deleted":
            await sbs.handle_subscription_cancelled(db, obj)
            event.processed = True
            await db.flush()
        elif event_type == "invoice.payment_failed":
            _billing_log.warning("stripe.invoice_payment_failed", event_id=event_id, customer=obj.get("customer"))
            event.processed = True
            await db.flush()
        elif event_type == "customer.subscription.updated":
            _billing_log.info("stripe.subscription_updated", event_id=event_id)
            event.processed = True
            await db.flush()
    except Exception as billing_err:
        _billing_log.error("stripe.billing_handler_error", event_type=event_type, error=str(billing_err))
        event.processed = False
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

    brand_id = _resolve_shopify_brand_id(payload)
    if not brand_id:
        import structlog
        structlog.get_logger().warning(
            "shopify_webhook.no_brand_id",
            shopify_id=shopify_id,
            topic=x_shopify_topic,
        )

    event = WebhookEvent(
        brand_id=brand_id,
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

    if brand_id and x_shopify_topic in ("orders/paid", "orders/create"):
        from packages.db.models.creator_revenue import CreatorRevenueEvent
        total = float(payload.get("total_price", 0))
        if total > 0:
            order_id = payload.get("id", "")
            db.add(CreatorRevenueEvent(
                brand_id=brand_id,
                avenue_type="ecommerce",
                event_type="shopify_order",
                revenue=total,
                cost=0.0,
                profit=total,
                client_name=payload.get("email") or payload.get("customer", {}).get("email", ""),
                description=f"Shopify order #{payload.get('order_number', order_id)}: ${total:.2f}",
                metadata_json={
                    "shopify_order_id": str(order_id),
                    "shopify_topic": x_shopify_topic,
                    "shopify_webhook_id": shopify_id,
                    "order_number": payload.get("order_number"),
                    "line_items_count": len(payload.get("line_items", [])),
                },
            ))
            event.processed = True
            await db.flush()
    elif brand_id and x_shopify_topic in ("orders/refunded", "refunds/create"):
        from packages.db.models.creator_revenue import CreatorRevenueEvent
        refund_amount = 0.0
        for refund in payload.get("refunds", [payload]):
            for txn in refund.get("transactions", []):
                refund_amount += float(txn.get("amount", 0))
        if not refund_amount:
            refund_amount = float(payload.get("total_price", 0))
        if refund_amount > 0:
            db.add(CreatorRevenueEvent(
                brand_id=brand_id,
                avenue_type="ecommerce",
                event_type="shopify_refund",
                revenue=-refund_amount,
                cost=0.0,
                profit=-refund_amount,
                client_name=payload.get("email") or "",
                description=f"Shopify refund #{payload.get('order_number', '')}: -${refund_amount:.2f}",
                metadata_json={
                    "shopify_order_id": str(payload.get("id", "")),
                    "shopify_topic": x_shopify_topic,
                },
            ))
            event.processed = True
            await db.flush()

    return {"status": "accepted", "topic": x_shopify_topic, "webhook_event_id": str(event.id)}


def _resolve_shopify_brand_id(payload: dict):
    """Try to extract brand_id from Shopify order metadata."""
    for attr in payload.get("note_attributes", []):
        if attr.get("name", "").lower() == "brand_id":
            try:
                return uuid.UUID(attr["value"])
            except (ValueError, KeyError):
                pass
    tags = payload.get("tags", "")
    if "brand:" in tags:
        for tag in tags.split(","):
            tag = tag.strip()
            if tag.startswith("brand:"):
                try:
                    return uuid.UUID(tag[6:].strip())
                except ValueError:
                    pass
    meta = payload.get("metafields", [])
    for mf in meta:
        if mf.get("key") == "brand_id":
            try:
                return uuid.UUID(mf["value"])
            except (ValueError, KeyError):
                pass
    return None
