"""Provider-specific webhook endpoints with signature/HMAC verification.

These are public — authentication is via the provider's own verification mechanism.
"""
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Form, Header, HTTPException, Request, status
from sqlalchemy import select

from apps.api.deps import DBSession
from packages.clients.external_clients import StripeWebhookVerifier, ShopifyWebhookVerifier
from packages.db.models.live_execution_phase2 import WebhookEvent

logger = structlog.get_logger()

router = APIRouter()


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: DBSession, stripe_signature: str = Header(alias="Stripe-Signature")):
    """Receive and verify a Stripe webhook event.

    Signing-secret resolution is DB-first via ``_resolve_stripe_webhook_secret``.
    Since webhooks are external and we do not know the owning org before
    signature verification, we try every DB-managed secret in turn until one
    verifies. Env is a last-resort legacy fallback logged as
    ``stripe_webhook.env_legacy_fallback``.
    """
    body = await request.body()

    result, matched_org_id = await _verify_webhook_with_candidates(
        verifier=StripeWebhookVerifier,
        body=body,
        signature=stripe_signature,
        candidates=await _resolve_stripe_webhook_secret(db),
        env_var="STRIPE_WEBHOOK_SECRET",
        provider_key="stripe_webhook",
        log_prefix="stripe_webhook",
    )

    if not result["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid signature: {result['error']}",
        )

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

        # ── Write to canonical revenue ledger ──
        try:
            from apps.api.services.monetization_bridge import record_service_payment_to_ledger
            await record_service_payment_to_ledger(
                db, brand_id=brand_id, gross_amount=revenue,
                payment_processor="stripe",
                external_transaction_id=obj.get("payment_intent") or obj.get("id") or "",
                webhook_ref=f"stripe:{event_id}" if event_id else None,
                description=f"Stripe {event_type}: ${revenue:.2f}",
                metadata={"stripe_event_id": event_id, "stripe_event_type": event_type},
            )
        except Exception as ledger_err:
            import structlog
            structlog.get_logger().warning("stripe.ledger_write_failed", error=str(ledger_err))

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

    # ── Operator payment processing: ledger writes + event_bus emissions ──
    from apps.api.services.event_bus import emit_event
    from packages.db.models.revenue_ledger import RevenueLedgerEntry

    try:
        await _process_operator_payment_event(
            db, event_type=event_type, obj=obj, meta=meta,
            brand_id=brand_id, event_id=event_id, webhook_event=event,
        )
    except Exception as op_err:
        logger.error("stripe.operator_payment_error", event_type=event_type, error=str(op_err))

    # ── Conversion backbone: write Payment row + emit payment.completed ──
    # Additive. Runs alongside the legacy ledger/event path; does not
    # replace any existing behavior. Only fires for successful payment
    # events where org_id is resolvable.
    try:
        await _record_conversion_payment(
            db,
            event_type=event_type,
            event_id=event_id,
            obj=obj,
            meta=meta,
            brand_id=brand_id,
        )
    except Exception as pay_err:
        logger.warning(
            "stripe.payment_record_failed",
            event_type=event_type,
            event_id=event_id,
            error=str(pay_err)[:200],
        )

    return {"status": "accepted", "event_id": event_id, "webhook_event_id": str(event.id)}


async def _record_conversion_payment(
    db: DBSession,
    *,
    event_type: str,
    event_id: Optional[str],
    obj: dict,
    meta: dict,
    brand_id,
) -> None:
    """Persist a ``payments`` row + emit ``payment.completed`` for any
    Stripe success event carrying resolvable org + amount.

    Idempotent on (provider, provider_event_id) — redelivered webhooks
    short-circuit inside ``record_payment_from_stripe``.

    Scope-narrow: only handles ``checkout.session.completed``,
    ``payment_intent.succeeded``, ``charge.succeeded``, ``invoice.paid``.
    Subscription + refund events stay on the legacy ledger path.
    """
    SUCCESS_EVENT_TYPES = {
        "checkout.session.completed",
        "payment_intent.succeeded",
        "charge.succeeded",
        "invoice.paid",
    }
    if event_type not in SUCCESS_EVENT_TYPES:
        return
    if not event_id:
        return

    org_id = _safe_uuid(meta.get("org_id"))
    if org_id is None and brand_id is not None:
        from packages.db.models.core import Brand
        org_id = (
            await db.execute(
                select(Brand.organization_id).where(Brand.id == brand_id)
            )
        ).scalar()
    if org_id is None:
        return

    amount_cents = _extract_amount_cents(obj, event_type)
    if amount_cents <= 0:
        return

    from apps.api.services.proposals_service import record_payment_from_stripe

    payment = await record_payment_from_stripe(
        db,
        org_id=org_id,
        brand_id=brand_id,
        event_id=event_id,
        event_type=event_type,
        amount_cents=amount_cents,
        currency=(obj.get("currency") or "usd").lower(),
        stripe_object=obj,
        payment_intent_id=obj.get("payment_intent") if isinstance(obj.get("payment_intent"), str) else None,
        checkout_session_id=obj.get("id") if event_type == "checkout.session.completed" else None,
        charge_id=obj.get("id") if event_type == "charge.succeeded" else None,
        customer_email=obj.get("customer_email") or obj.get("receipt_email") or "",
        customer_name=obj.get("customer_name") or (obj.get("customer_details", {}) or {}).get("name", "") or "",
        metadata=meta,
    )

    # ── Fulfillment activation: create Client + start onboarding ──
    # Runs only on the first delivery of a given Stripe event_id (the
    # record_payment service is already idempotent). activate_client
    # is itself idempotent — if a Client already exists for
    # (org_id, primary_email) the existing row is updated without a
    # duplicate client.created emission.
    if payment is not None and payment.status == "succeeded":
        try:
            from apps.api.services.client_activation import (
                activate_client_from_payment,
            )
            await activate_client_from_payment(db, payment=payment)
        except Exception as act_err:
            logger.warning(
                "stripe.client_activation_failed",
                payment_id=str(payment.id),
                error=str(act_err)[:200],
            )


def _extract_amount_cents(obj: dict, event_type: str) -> int:
    """Pull the paid amount (cents) out of a Stripe success event object."""
    if event_type == "checkout.session.completed":
        return int(obj.get("amount_total") or obj.get("amount_subtotal") or 0)
    if event_type == "invoice.paid":
        return int(obj.get("amount_paid") or 0)
    if event_type in ("payment_intent.succeeded", "charge.succeeded"):
        return int(obj.get("amount_received") or obj.get("amount") or 0)
    return 0


async def _process_operator_payment_event(
    db: DBSession,
    *,
    event_type: str,
    obj: dict,
    meta: dict,
    brand_id,
    event_id,
    webhook_event,
):
    """Handle operator-facing Stripe events: write to canonical revenue ledger
    and emit system events for downstream processing.

    Covers: checkout.session.completed, invoice.paid, charge.refunded,
    customer.subscription.created, customer.subscription.deleted.
    """
    from apps.api.services.event_bus import emit_event
    from apps.api.services.monetization_bridge import (
        record_service_payment_to_ledger,
        record_refund_to_ledger,
    )
    from packages.db.models.revenue_ledger import RevenueLedgerEntry
    from packages.db.models.core import Brand
    from sqlalchemy import select

    # Extract attribution metadata
    offer_id = _safe_uuid(meta.get("offer_id"))
    content_item_id = _safe_uuid(meta.get("content_item_id"))
    source_label = meta.get("source", "")

    # Resolve org_id from brand if brand_id present
    org_id = None
    if brand_id:
        org_id = (await db.execute(select(Brand.organization_id).where(Brand.id == brand_id))).scalar()

    # ── checkout.session.completed (operator offer payments) ──
    if event_type == "checkout.session.completed" and brand_id and meta.get("source") == "outreach_proposal":
        amount = float(obj.get("amount_total", 0)) / 100.0
        if amount > 0:
            webhook_ref = f"stripe_checkout:{event_id}" if event_id else None
            # Idempotency: check ledger for duplicate webhook_ref
            if webhook_ref:
                existing = (await db.execute(
                    select(RevenueLedgerEntry).where(RevenueLedgerEntry.webhook_ref == webhook_ref)
                )).scalar_one_or_none()
                if existing:
                    return

            entry = RevenueLedgerEntry(
                revenue_source_type="service_fee",
                brand_id=brand_id,
                offer_id=offer_id,
                content_item_id=content_item_id,
                gross_amount=amount,
                net_amount=amount,
                currency=obj.get("currency", "usd").upper(),
                payment_state="confirmed",
                attribution_state="auto_attributed" if offer_id else "unattributed",
                payment_processor="stripe",
                external_transaction_id=obj.get("payment_intent") or obj.get("id") or "",
                webhook_ref=webhook_ref,
                description=f"Stripe checkout: ${amount:.2f} — {obj.get('customer_email', '')}",
                metadata_json={
                    "stripe_event_id": event_id,
                    "stripe_event_type": event_type,
                    "source": "stripe_checkout",
                    "customer_email": obj.get("customer_email", ""),
                },
            )
            db.add(entry)
            await db.flush()

            await emit_event(
                db, domain="monetization", event_type="ledger.stripe_checkout",
                summary=f"Stripe checkout payment: ${amount:.2f}",
                org_id=org_id, brand_id=brand_id,
                entity_type="revenue_ledger", entity_id=entry.id,
                details={
                    "gross": amount, "source": "stripe_checkout",
                    "offer_id": str(offer_id) if offer_id else None,
                    "stripe_event_id": event_id,
                },
            )
            webhook_event.processed = True
            await db.flush()

    # ── invoice.paid ──
    elif event_type == "invoice.paid" and brand_id:
        amount = float(obj.get("amount_paid", 0)) / 100.0
        if amount > 0:
            webhook_ref = f"stripe_invoice:{event_id}" if event_id else None
            if webhook_ref:
                existing = (await db.execute(
                    select(RevenueLedgerEntry).where(RevenueLedgerEntry.webhook_ref == webhook_ref)
                )).scalar_one_or_none()
                if existing:
                    return

            entry = RevenueLedgerEntry(
                revenue_source_type="service_fee",
                brand_id=brand_id,
                offer_id=offer_id,
                content_item_id=content_item_id,
                gross_amount=amount,
                net_amount=amount,
                currency=obj.get("currency", "usd").upper(),
                payment_state="confirmed",
                attribution_state="auto_attributed" if offer_id else "unattributed",
                payment_processor="stripe",
                external_transaction_id=obj.get("payment_intent") or obj.get("id") or "",
                webhook_ref=webhook_ref,
                description=f"Stripe invoice paid: ${amount:.2f} — {obj.get('customer_email', '')}",
                metadata_json={
                    "stripe_event_id": event_id,
                    "stripe_event_type": event_type,
                    "source": "stripe_invoice",
                    "invoice_id": obj.get("id", ""),
                    "customer_email": obj.get("customer_email", ""),
                },
            )
            db.add(entry)
            await db.flush()

            await emit_event(
                db, domain="monetization", event_type="ledger.stripe_invoice_paid",
                summary=f"Stripe invoice paid: ${amount:.2f}",
                org_id=org_id, brand_id=brand_id,
                entity_type="revenue_ledger", entity_id=entry.id,
                details={
                    "gross": amount, "source": "stripe_invoice",
                    "offer_id": str(offer_id) if offer_id else None,
                    "stripe_event_id": event_id,
                },
            )
            webhook_event.processed = True
            await db.flush()

    # ── charge.refunded ──
    elif event_type == "charge.refunded" and brand_id:
        refund_amount = float(obj.get("amount_refunded", 0)) / 100.0
        if refund_amount > 0:
            webhook_ref = f"stripe_refund:{event_id}" if event_id else None
            if webhook_ref:
                existing = (await db.execute(
                    select(RevenueLedgerEntry).where(RevenueLedgerEntry.webhook_ref == webhook_ref)
                )).scalar_one_or_none()
                if existing:
                    return

            # Try to find original ledger entry by external_transaction_id (charge id)
            charge_id = obj.get("id", "")
            original_payment_intent = obj.get("payment_intent", "")
            original_entry = None
            if original_payment_intent:
                original_entry = (await db.execute(
                    select(RevenueLedgerEntry).where(
                        RevenueLedgerEntry.brand_id == brand_id,
                        RevenueLedgerEntry.external_transaction_id == original_payment_intent,
                        RevenueLedgerEntry.is_refund.is_(False),
                    )
                )).scalar_one_or_none()

            entry = RevenueLedgerEntry(
                revenue_source_type="refund",
                brand_id=brand_id,
                offer_id=offer_id or (original_entry.offer_id if original_entry else None),
                content_item_id=content_item_id or (original_entry.content_item_id if original_entry else None),
                gross_amount=-abs(refund_amount),
                net_amount=-abs(refund_amount),
                currency=obj.get("currency", "usd").upper(),
                payment_state="confirmed",
                attribution_state=original_entry.attribution_state if original_entry else "unattributed",
                payment_processor="stripe",
                external_transaction_id=charge_id,
                webhook_ref=webhook_ref,
                is_refund=True,
                refund_of_id=original_entry.id if original_entry else None,
                description=f"Stripe refund: -${refund_amount:.2f}",
                metadata_json={
                    "stripe_event_id": event_id,
                    "stripe_event_type": event_type,
                    "source": "stripe_refund",
                    "original_charge_id": charge_id,
                    "original_payment_intent": original_payment_intent,
                },
            )
            db.add(entry)

            # Mark original as refunded if found
            if original_entry:
                original_entry.payment_state = "refunded"

            await db.flush()

            await emit_event(
                db, domain="monetization", event_type="ledger.stripe_refund",
                summary=f"Stripe refund: -${refund_amount:.2f}",
                org_id=org_id, brand_id=brand_id,
                entity_type="revenue_ledger", entity_id=entry.id,
                severity="warning",
                details={
                    "refund_amount": refund_amount, "source": "stripe_refund",
                    "original_entry_id": str(original_entry.id) if original_entry else None,
                    "stripe_event_id": event_id,
                },
            )
            webhook_event.processed = True
            await db.flush()

    # ── customer.subscription.created ──
    elif event_type == "customer.subscription.created" and brand_id:
        # Log subscription creation to ledger
        sub_metadata = obj.get("metadata", {})
        plan_amount = float(obj.get("plan", {}).get("amount", 0)) / 100.0
        interval = obj.get("plan", {}).get("interval", "month")

        webhook_ref = f"stripe_sub_created:{event_id}" if event_id else None
        if webhook_ref:
            existing = (await db.execute(
                select(RevenueLedgerEntry).where(RevenueLedgerEntry.webhook_ref == webhook_ref)
            )).scalar_one_or_none()
            if existing:
                return

        if plan_amount > 0:
            entry = RevenueLedgerEntry(
                revenue_source_type="membership_payment",
                brand_id=brand_id,
                offer_id=offer_id or _safe_uuid(sub_metadata.get("offer_id")),
                gross_amount=plan_amount,
                net_amount=plan_amount,
                currency=obj.get("plan", {}).get("currency", "usd").upper(),
                payment_state="pending",
                attribution_state="auto_attributed" if offer_id or sub_metadata.get("offer_id") else "unattributed",
                payment_processor="stripe",
                external_transaction_id=obj.get("id", ""),
                webhook_ref=webhook_ref,
                description=f"Stripe subscription created: ${plan_amount:.2f}/{interval}",
                metadata_json={
                    "stripe_event_id": event_id,
                    "stripe_event_type": event_type,
                    "source": "subscription",
                    "subscription_id": obj.get("id", ""),
                    "interval": interval,
                },
            )
            db.add(entry)
            await db.flush()

            await emit_event(
                db, domain="monetization", event_type="ledger.stripe_subscription_created",
                summary=f"New subscription: ${plan_amount:.2f}/{interval}",
                org_id=org_id, brand_id=brand_id,
                entity_type="revenue_ledger", entity_id=entry.id,
                details={
                    "amount": plan_amount, "interval": interval,
                    "subscription_id": obj.get("id", ""),
                    "stripe_event_id": event_id,
                },
            )
        webhook_event.processed = True
        await db.flush()

    # ── customer.subscription.deleted (cancellation logging) ──
    elif event_type == "customer.subscription.deleted" and brand_id:
        sub_id = obj.get("id", "")
        await emit_event(
            db, domain="monetization", event_type="stripe.subscription_cancelled",
            summary=f"Subscription cancelled: {sub_id}",
            org_id=org_id, brand_id=brand_id,
            severity="warning",
            details={
                "subscription_id": sub_id,
                "stripe_event_id": event_id,
                "cancel_at_period_end": obj.get("cancel_at_period_end", False),
                "canceled_at": obj.get("canceled_at"),
            },
        )


def _safe_uuid(val):
    """Safely parse a string to UUID, returning None on failure."""
    if not val:
        return None
    try:
        return uuid.UUID(str(val))
    except (ValueError, AttributeError):
        return None


@router.post("/webhooks/shopify")
async def shopify_webhook(request: Request, db: DBSession, x_shopify_hmac_sha256: str = Header(alias="X-Shopify-Hmac-SHA256"), x_shopify_topic: str = Header(alias="X-Shopify-Topic", default="")):
    """Receive and verify a Shopify webhook event.

    DB-first signing-secret resolution via ``_resolve_shopify_webhook_secret``;
    env fallback logs ``shopify_webhook.env_legacy_fallback``.
    """
    body = await request.body()

    result, matched_org_id = await _verify_webhook_with_candidates(
        verifier=ShopifyWebhookVerifier,
        body=body,
        signature=x_shopify_hmac_sha256,
        candidates=await _resolve_shopify_webhook_secret(db),
        env_var="SHOPIFY_WEBHOOK_SECRET",
        provider_key="shopify_webhook",
        log_prefix="shopify_webhook",
    )

    if not result["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid HMAC: {result['error']}",
        )

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

            # ── Write to canonical revenue ledger ──
            try:
                from apps.api.services.monetization_bridge import record_product_sale_to_ledger
                await record_product_sale_to_ledger(
                    db, brand_id=brand_id, gross_amount=total,
                    payment_processor="shopify",
                    webhook_ref=idem_key,
                    external_transaction_id=str(order_id),
                    description=f"Shopify order #{payload.get('order_number', order_id)}: ${total:.2f}",
                    metadata={"shopify_order_id": str(order_id), "shopify_topic": x_shopify_topic},
                )
            except Exception as ledger_err:
                import structlog
                structlog.get_logger().warning("shopify.ledger_write_failed", error=str(ledger_err))

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

            # ── Write refund to canonical revenue ledger ──
            try:
                from apps.api.services.monetization_bridge import record_refund_to_ledger
                # Find original ledger entry for this order
                from packages.db.models.revenue_ledger import RevenueLedgerEntry
                original = (await db.execute(
                    select(RevenueLedgerEntry).where(
                        RevenueLedgerEntry.brand_id == brand_id,
                        RevenueLedgerEntry.external_transaction_id == str(payload.get("id", "")),
                    )
                )).scalar_one_or_none()
                if original:
                    await record_refund_to_ledger(
                        db, brand_id=brand_id, refund_amount=refund_amount,
                        refund_of_id=original.id,
                        reason=f"Shopify refund: {x_shopify_topic}",
                        webhook_ref=f"{idem_key}_refund" if idem_key else None,
                    )
            except Exception as ledger_err:
                import structlog
                structlog.get_logger().warning("shopify.refund_ledger_write_failed", error=str(ledger_err))

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


# =====================================================================
# Generic Media Job Webhook — handles ALL media providers
# =====================================================================

@router.post("/webhooks/media/{provider_key}")
async def media_webhook(provider_key: str, request: Request, db: DBSession):
    """Receive a webhook callback from any media generation provider.

    Single endpoint for all providers (heygen, did, runway, elevenlabs,
    kling, flux, etc.). Each provider sends a different payload format;
    the parser registry normalises them into a common shape.

    Flow:
        1. Parse provider_key from URL
        2. Use provider-specific parser to extract job_id, status, output_url, error
        3. Look up MediaJob by provider + provider_job_id
        4. Update status, output_payload, output_url, completed_at
        5. If next_pipeline_task is set, dispatch via Celery
        6. Emit event via event_bus
        7. Return 200 immediately

    Idempotent: if the job is already completed, returns 200 and does nothing.
    Unknown job IDs: logs a warning and returns 200 (never 4xx — providers retry).
    """
    from packages.clients.webhook_parsers import parse_webhook_payload
    from packages.db.models.media_jobs import MediaJob

    # ── 1. Read raw payload ──────────────────────────────────────────
    try:
        payload = await request.json()
    except Exception:
        logger.warning("media_webhook.invalid_json", provider=provider_key)
        return {"status": "accepted", "detail": "invalid json ignored"}

    # ── 2. Parse via provider-specific parser ────────────────────────
    try:
        result = parse_webhook_payload(provider_key, payload)
    except ValueError:
        logger.warning("media_webhook.unknown_provider", provider=provider_key)
        return {"status": "accepted", "detail": f"no parser for provider '{provider_key}'"}

    if not result.job_id:
        logger.warning("media_webhook.no_job_id", provider=provider_key, payload_keys=list(payload.keys()))
        return {"status": "accepted", "detail": "no job_id in payload"}

    # ── 3. Look up MediaJob ──────────────────────────────────────────
    job = (await db.execute(
        select(MediaJob).where(
            MediaJob.provider == provider_key,
            MediaJob.provider_job_id == result.job_id,
        )
    )).scalar_one_or_none()

    if job is None:
        logger.warning(
            "media_webhook.unknown_job",
            provider=provider_key,
            provider_job_id=result.job_id,
        )
        return {"status": "accepted", "detail": "unknown job_id — ignored"}

    # ── 4. Idempotency: skip if already completed ────────────────────
    if job.status == "completed":
        logger.info(
            "media_webhook.duplicate",
            provider=provider_key,
            provider_job_id=result.job_id,
            media_job_id=str(job.id),
        )
        return {"status": "accepted", "detail": "already completed"}

    # ── 5. Update MediaJob ───────────────────────────────────────────
    now = datetime.now(timezone.utc)
    job.status = result.status
    job.output_payload = payload
    job.output_url = result.output_url
    job.error_message = result.error

    if result.status == "completed" or result.status == "failed":
        job.completed_at = now

    await db.flush()

    logger.info(
        "media_webhook.updated",
        provider=provider_key,
        provider_job_id=result.job_id,
        media_job_id=str(job.id),
        new_status=result.status,
    )

    # ── 6. Dispatch next pipeline task via Celery (if configured) ────
    if result.status == "completed" and job.next_pipeline_task:
        try:
            from workers.celery_app import app as celery_app

            task_kwargs = job.next_pipeline_args or {}
            # Inject the media_job_id so downstream tasks can reference it
            task_kwargs["media_job_id"] = str(job.id)
            if job.output_url:
                task_kwargs["output_url"] = job.output_url

            celery_app.send_task(
                job.next_pipeline_task,
                kwargs=task_kwargs,
            )
            logger.info(
                "media_webhook.pipeline_dispatched",
                task=job.next_pipeline_task,
                media_job_id=str(job.id),
            )
        except Exception as e:
            logger.error(
                "media_webhook.pipeline_dispatch_failed",
                task=job.next_pipeline_task,
                media_job_id=str(job.id),
                error=str(e),
            )

    # ── 7. Emit system event ─────────────────────────────────────────
    try:
        from apps.api.services.event_bus import emit_event

        event_type = (
            "media.job_completed" if result.status == "completed"
            else "media.job_failed" if result.status == "failed"
            else "media.job_updated"
        )
        await emit_event(
            db,
            domain="media",
            event_type=event_type,
            entity_type="media_job",
            entity_id=job.id,
            org_id=job.org_id,
            brand_id=job.brand_id,
            previous_state="dispatched",
            new_state=result.status,
            summary=f"Media job {result.status}: {job.job_type} via {provider_key}",
            details={
                "provider": provider_key,
                "provider_job_id": result.job_id,
                "job_type": job.job_type,
                "output_url": result.output_url,
                "error": result.error,
            },
        )
    except Exception as e:
        logger.error(
            "media_webhook.event_emit_failed",
            media_job_id=str(job.id),
            error=str(e),
        )

    return {"status": "accepted", "media_job_id": str(job.id), "new_status": result.status}


# =====================================================================
# Affiliate Click Tracking Webhook
# =====================================================================

@router.post("/webhooks/affiliate/click")
async def affiliate_click_webhook(request: Request, db: DBSession):
    """Receive click events from link shorteners or affiliate tracking pixels.

    Expected payload (flexible — adapts to multiple shortener backends):
        {
            "link_id": "af_link UUID or shortener link ID",
            "short_url": "https://dub.sh/abc123",
            "clicked_at": "2024-01-01T12:00:00Z",
            "referrer": "https://youtube.com/...",
            "platform": "youtube",
            "ip_country": "US",
            "user_agent": "...",
            "brand_id": "uuid",
        }

    Also handles Dub.co webhook format:
        { "id": "...", "event": "link.clicked", "data": { "link": {...}, "click": {...} } }

    Returns 200 immediately — processing is best-effort.
    """
    try:
        payload = await request.json()
    except Exception:
        logger.warning("affiliate_click_webhook.invalid_json")
        return {"status": "accepted", "detail": "invalid json ignored"}

    # ── Normalize payload across shortener formats ──────────────────
    if payload.get("event") == "link.clicked" and payload.get("data"):
        # Dub.co webhook format
        dub_data = payload["data"]
        click_data = dub_data.get("click", {})
        link_data = dub_data.get("link", {})
        normalized = {
            "shortener_link_id": link_data.get("id", ""),
            "short_url": link_data.get("shortLink", ""),
            "long_url": link_data.get("url", ""),
            "clicked_at": click_data.get("timestamp"),
            "referrer": click_data.get("referer", ""),
            "ip_country": click_data.get("country", ""),
            "user_agent": click_data.get("ua", ""),
            "platform": "",
        }
    else:
        # Generic format (Bitly webhook, Short.io, or custom)
        normalized = {
            "shortener_link_id": payload.get("link_id", payload.get("shortener_link_id", "")),
            "short_url": payload.get("short_url", payload.get("url", "")),
            "long_url": payload.get("long_url", payload.get("destination", "")),
            "clicked_at": payload.get("clicked_at", payload.get("timestamp")),
            "referrer": payload.get("referrer", payload.get("referer", "")),
            "ip_country": payload.get("ip_country", payload.get("country", "")),
            "user_agent": payload.get("user_agent", ""),
            "platform": payload.get("platform", ""),
        }

    # ── Resolve the AffiliateLink record ────────────────────────────
    from packages.db.models.affiliate_intel import AffiliateLink, AffiliateClickEvent

    af_link = None

    # Try to find by link UUID
    link_id_str = normalized.get("shortener_link_id", "") or payload.get("af_link_id", "")

    if link_id_str:
        try:
            link_uuid = uuid.UUID(link_id_str)
            af_link = (await db.execute(
                select(AffiliateLink).where(AffiliateLink.id == link_uuid, AffiliateLink.is_active.is_(True))
            )).scalar_one_or_none()
        except (ValueError, AttributeError):
            pass

    # Try by short_url match
    if not af_link and normalized.get("short_url"):
        af_link = (await db.execute(
            select(AffiliateLink).where(
                AffiliateLink.short_url == normalized["short_url"],
                AffiliateLink.is_active.is_(True),
            )
        )).scalar_one_or_none()

    # Try by full_url match
    if not af_link and normalized.get("long_url"):
        af_link = (await db.execute(
            select(AffiliateLink).where(
                AffiliateLink.full_url == normalized["long_url"],
                AffiliateLink.is_active.is_(True),
            )
        )).scalar_one_or_none()

    if af_link:
        brand_id = af_link.brand_id

        # Increment click counter
        af_link.click_count = (af_link.click_count or 0) + 1
        await db.flush()

        # Record the click event
        now = datetime.now(timezone.utc)
        click_ts = now
        if normalized.get("clicked_at"):
            try:
                ts = normalized["clicked_at"]
                if isinstance(ts, str):
                    click_ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                click_ts = now

        click_event = AffiliateClickEvent(
            brand_id=brand_id,
            link_id=af_link.id,
            clicked_at=click_ts,
            referrer=normalized.get("referrer", "")[:500] if normalized.get("referrer") else None,
            platform=normalized.get("platform") or af_link.platform,
        )
        db.add(click_event)
        await db.flush()

        # ── Emit event via event_bus ────────────────────────────────
        try:
            from apps.api.services.event_bus import emit_event
            await emit_event(
                db,
                domain="affiliate",
                event_type="affiliate.link_clicked",
                summary=f"Affiliate link clicked: {af_link.short_url or af_link.full_url}",
                brand_id=brand_id,
                entity_type="af_link",
                entity_id=af_link.id,
                details={
                    "link_id": str(af_link.id),
                    "offer_id": str(af_link.offer_id),
                    "click_count": af_link.click_count,
                    "referrer": normalized.get("referrer", ""),
                    "platform": normalized.get("platform", ""),
                    "ip_country": normalized.get("ip_country", ""),
                },
            )
        except Exception as e:
            logger.warning("affiliate_click_webhook.event_emit_failed", error=str(e))

        return {
            "status": "accepted",
            "af_link_id": str(af_link.id),
            "click_count": af_link.click_count,
        }
    else:
        # Unknown link — log but still return 200
        logger.info(
            "affiliate_click_webhook.unresolved_link",
            short_url=normalized.get("short_url"),
            long_url=normalized.get("long_url"),
            link_id=link_id_str,
        )
        return {"status": "accepted", "detail": "link not resolved — event logged"}


# =====================================================================
# Inbound Email Webhook (SendGrid Inbound Parse)
# =====================================================================
#
# SendGrid's Inbound Parse POSTs multipart/form-data to this endpoint
# whenever a message is received at the configured inbound subdomain
# (e.g. reply@reply.proofhook.com).
#
# We forward sender + subject + body + In-Reply-To to ingest_reply(),
# which classifies the reply, matches it to a SponsorProfile /
# SponsorOutreachSequence, and advances the deal stage.
#
# Scope is strictly additive:
#   - does NOT modify outbound SMTP / From / SPF / DKIM / DMARC.
#   - org routing is via a header/plus-address/destination-subdomain
#     mapping held in the PROOFHOOK_INBOUND_ORG_ID env var or derived
#     from the local-part of the original outbound message.
#
# Reference: https://docs.sendgrid.com/for-developers/parsing-email/setting-up-the-inbound-parse-webhook
# =====================================================================

@router.post("/webhooks/inbound-email")
async def sendgrid_inbound_parse(
    request: Request,
    db: DBSession,
):
    """Receive a reply from SendGrid Inbound Parse and feed it to ingest_reply().

    SendGrid sends multipart/form-data with these key fields:
        from      — sender email
        to        — recipient (our reply@ address)
        subject   — subject line
        text      — plaintext body
        html      — html body
        headers   — raw headers (we parse In-Reply-To from here)
        envelope  — JSON with SMTP envelope
        dkim      — DKIM check result (e.g. "{@sender.com : pass}")
        SPF       — SPF check result
        spam_score
        spam_report

    Returns 2xx quickly so SendGrid does not retry.  Failures inside
    ingest_reply() are logged but do not bubble up (SendGrid would
    otherwise mark the webhook as failing).
    """
    try:
        form = await request.form()
    except Exception as exc:
        logger.warning("inbound_email.invalid_form", error=str(exc)[:200])
        return {"status": "accepted", "detail": "invalid form ignored"}

    sender_full = form.get("from", "")
    to_full = form.get("to", "")
    subject = form.get("subject", "") or ""
    body_text = form.get("text", "") or ""
    body_html = form.get("html", "") or ""
    headers_raw = form.get("headers", "") or ""
    envelope_raw = form.get("envelope", "") or ""
    spam_score = form.get("spam_score", "")
    dkim_result = form.get("dkim", "")
    spf_result = form.get("SPF", "")

    # Parse sender email out of "Name <email@example.com>" form
    import email.utils
    sender_email = email.utils.parseaddr(str(sender_full))[1] or ""

    # Extract In-Reply-To from raw headers
    in_reply_to = ""
    for line in str(headers_raw).splitlines():
        if line.lower().startswith("in-reply-to:"):
            in_reply_to = line.split(":", 1)[1].strip().strip("<>")
            break

    # Prefer text body, fall back to html stripped of tags
    body = body_text.strip()
    if not body and body_html:
        import re
        body = re.sub(r"<[^>]+>", " ", body_html)
        body = re.sub(r"\s+", " ", body).strip()

    # Drop obvious spam early (SendGrid assigns 0-5; conservative threshold)
    try:
        if spam_score and float(spam_score) >= 5.0:
            logger.info(
                "inbound_email.dropped_as_spam",
                sender=sender_email,
                spam_score=spam_score,
            )
            return {"status": "accepted", "detail": "dropped_as_spam", "spam_score": spam_score}
    except (TypeError, ValueError):
        pass

    # Resolve organization_id — DB-backed, system-managed routing.
    # Primary path: a matching row in integration_providers with
    #   provider_key='inbound_email_route'
    #   is_enabled=true
    #   extra_config contains one of:
    #     - "to_address": exact recipient ("reply@reply.proofhook.com")
    #     - "to_domain":  recipient domain ("reply.proofhook.com")
    #     - "plus_token": token matched against "reply+<token>@..." local-part
    # The row's organization_id is the owning org.
    # Legacy fallback: PROOFHOOK_INBOUND_ORG_ID env var. Only applied when no
    # DB route matches. A warning is logged every time the legacy path fires.
    import email.utils as _email_utils_inbound
    _, to_bare = _email_utils_inbound.parseaddr(str(to_full or "").strip())
    org_uuid = await _resolve_inbound_org_id(db, to_bare or str(to_full or ""))

    if org_uuid is None:
        env_org = os.environ.get("PROOFHOOK_INBOUND_ORG_ID", "").strip()
        if env_org:
            try:
                org_uuid = uuid.UUID(env_org)
                logger.warning(
                    "inbound_email.env_legacy_fallback",
                    to_address=to_bare,
                    hint="Using PROOFHOOK_INBOUND_ORG_ID env. Add an 'inbound_email_route' provider row (extra_config.to_address / to_domain / plus_token) to move this to system-managed.",
                )
            except ValueError:
                logger.error("inbound_email.invalid_org_env", env_value=env_org)
                return {"status": "accepted", "detail": "invalid_org_env"}

    if org_uuid is None:
        logger.warning(
            "inbound_email.no_org_configured",
            hint="Configure inbound routing in Settings > Integrations (provider_key='inbound_email_route'). PROOFHOOK_INBOUND_ORG_ID env remains as a legacy fallback only.",
            sender=sender_email,
            to_address=to_bare,
            subject=subject[:80],
        )
        return {
            "status": "accepted",
            "detail": "no_org_configured",
            "note": "Webhook received, but no DB inbound_email_route matched and no legacy env fallback was set.",
        }

    # Feed into existing reply-ingestion pipeline
    try:
        from apps.api.services.reply_ingestion import ingest_reply

        result = await ingest_reply(
            db, org_uuid,
            sender_email=sender_email,
            subject=subject,
            body=body,
            in_reply_to=in_reply_to or None,
        )
        await db.commit()

        # Also attempt to match against SponsorOutreachSequence records
        try:
            from workers.outreach_worker.tasks import _match_reply_to_outreach
            await _match_reply_to_outreach(db, org_uuid, sender_email, subject, body)
            await db.commit()
        except Exception as match_exc:
            # Best-effort. ingest_reply already ran and is committed.
            logger.warning(
                "inbound_email.match_outreach_failed",
                error=str(match_exc)[:200],
            )

        # ── email_pipeline persistence (additive, isolated) ──────────────
        # Writes InboxConnection + EmailThread + EmailMessage +
        # EmailClassification + EmailReplyDraft for the same inbound
        # message. Runs in its own try/except so a failure here cannot
        # break the committed ingest_reply path above.
        pipeline_result: dict = {}
        try:
            pipeline_result = await _persist_email_pipeline(
                db,
                org_uuid=org_uuid,
                to_bare=to_bare or str(to_full or ""),
                sender_email=sender_email,
                sender_full=str(sender_full or ""),
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                body_preview=body,
                headers_raw=str(headers_raw or ""),
                in_reply_to=in_reply_to,
            )
            await db.commit()
            logger.info("email_pipeline.ingest.ok", **pipeline_result)
        except Exception as pipe_exc:
            try:
                await db.rollback()
            except Exception:
                pass
            logger.exception(
                "email_pipeline.ingest_failed",
                sender=sender_email,
                subject=subject[:80],
                error=str(pipe_exc)[:300],
            )

        logger.info(
            "inbound_email.ingested",
            sender=sender_email,
            subject=subject[:80],
            classification=result.get("classification"),
            matched_sponsor=result.get("matched_sponsor"),
            matched_deal=result.get("matched_deal"),
            dkim=dkim_result,
            spf=spf_result,
        )

        return {
            "status": "accepted",
            "detail": "ingested",
            "classification": result.get("classification"),
            "matched_sponsor": result.get("matched_sponsor"),
            "matched_deal": result.get("matched_deal"),
            "email_pipeline": pipeline_result,
        }
    except Exception as exc:
        # Swallow exceptions so SendGrid doesn't retry-loop.
        # The raw form data is logged for post-mortem.
        logger.exception(
            "inbound_email.ingest_failed",
            sender=sender_email,
            subject=subject[:80],
            error=str(exc)[:300],
        )
        return {"status": "accepted", "detail": "ingest_failed_logged"}


# =====================================================================
# email_pipeline persistence — InboxConnection → EmailThread →
# EmailMessage → EmailClassification → EmailReplyDraft
# =====================================================================
#
# Called from sendgrid_inbound_parse after the legacy reply_ingestion
# path has completed and committed. This path is strictly additive: all
# writes are isolated in the caller's try/except so a failure here
# cannot break the committed reply_ingestion state.
#
# Idempotent: EmailMessage is keyed on provider_message_id (uniqueness
# enforced by the DB). EmailThread is keyed on (inbox_connection_id,
# provider_thread_id). InboxConnection is keyed on (org_id,
# email_address). If the message has already been ingested, the helper
# returns early with skipped=True and writes nothing new.


async def _persist_email_pipeline(
    db,
    *,
    org_uuid,
    to_bare: str,
    sender_email: str,
    sender_full: str,
    subject: str,
    body_text: str,
    body_html: str,
    body_preview: str,
    headers_raw: str,
    in_reply_to: str,
) -> dict:
    """Persist one inbound email into the email_pipeline tables.

    Returns a dict of the IDs written, suitable for spreading into a
    structured log line. Raises on persistence error — the caller is
    responsible for rollback + logging.
    """
    import hashlib
    from datetime import datetime, timezone

    from packages.db.models.email_pipeline import (
        EmailMessage,
        EmailThread,
        InboxConnection,
    )
    from apps.api.services.email_classifier import (
        ClassificationResult,
        classify_and_persist,
    )
    from apps.api.services.reply_engine import create_reply_draft

    now = datetime.now(timezone.utc)

    # ── 1. Upsert InboxConnection (org_id, email_address) ────────────
    inbox_address = (to_bare or "").strip().lower() or "reply@proofhook-inbound"
    inbox = (
        await db.execute(
            select(InboxConnection).where(
                InboxConnection.org_id == org_uuid,
                InboxConnection.email_address == inbox_address,
            )
        )
    ).scalar_one_or_none()
    if inbox is None:
        inbox = InboxConnection(
            org_id=org_uuid,
            email_address=inbox_address,
            display_name="SendGrid Inbound",
            provider="sendgrid_inbound",
            auth_method="webhook",
            credential_provider_key="sendgrid_inbound",
            status="active",
            is_active=True,
        )
        db.add(inbox)
        await db.flush()

    # ── 2. Derive provider_message_id (Message-ID header or synth) ───
    provider_message_id = _extract_header_value(headers_raw, "Message-ID")
    if not provider_message_id:
        synth_seed = f"{sender_email}|{subject}|{now.isoformat()}"
        provider_message_id = (
            f"<synth-{hashlib.sha256(synth_seed.encode()).hexdigest()[:24]}"
            f"@proofhook.internal>"
        )

    # Idempotency: skip if this message is already ingested
    existing_msg = (
        await db.execute(
            select(EmailMessage).where(
                EmailMessage.provider_message_id == provider_message_id
            )
        )
    ).scalar_one_or_none()
    if existing_msg is not None:
        return {
            "skipped": True,
            "reason": "message_already_ingested",
            "message_id": str(existing_msg.id),
            "thread_id": str(existing_msg.thread_id),
            "provider_message_id": provider_message_id,
        }

    # ── 3. Resolve thread: In-Reply-To chain first, stable hash fallback
    thread = None
    if in_reply_to:
        parent = (
            await db.execute(
                select(EmailMessage).where(
                    EmailMessage.provider_message_id == in_reply_to
                )
            )
        ).scalar_one_or_none()
        if parent is not None:
            thread = (
                await db.execute(
                    select(EmailThread).where(EmailThread.id == parent.thread_id)
                )
            ).scalar_one_or_none()

    if thread is None:
        normalized_subject = _normalize_subject_for_thread(subject)
        thread_seed = f"{normalized_subject}|{(sender_email or '').lower()}"
        provider_thread_id = (
            f"sha256:{hashlib.sha256(thread_seed.encode()).hexdigest()[:48]}"
        )
        thread = (
            await db.execute(
                select(EmailThread).where(
                    EmailThread.inbox_connection_id == inbox.id,
                    EmailThread.provider_thread_id == provider_thread_id,
                )
            )
        ).scalar_one_or_none()
        if thread is None:
            thread = EmailThread(
                inbox_connection_id=inbox.id,
                org_id=org_uuid,
                provider_thread_id=provider_thread_id,
                subject=(subject or "")[:1000],
                direction="inbound",
                from_email=sender_email or "",
                from_name=_parse_display_name(sender_full),
                to_emails=[inbox_address] if inbox_address else [],
                first_message_at=now,
                last_message_at=now,
                last_inbound_at=now,
                message_count=0,
            )
            db.add(thread)
            await db.flush()

    # ── 4. Insert EmailMessage (idempotent via provider_message_id) ──
    msg = EmailMessage(
        thread_id=thread.id,
        inbox_connection_id=inbox.id,
        org_id=org_uuid,
        provider_message_id=provider_message_id,
        in_reply_to=in_reply_to or None,
        direction="inbound",
        from_email=sender_email or "",
        from_name=_parse_display_name(sender_full),
        to_emails=[inbox_address] if inbox_address else [],
        subject=(subject or "")[:1000],
        body_text=body_text or None,
        body_html=body_html or None,
        snippet=(body_preview or body_text or "")[:500],
        message_date=now,
        size_bytes=len(body_text or "") + len(body_html or ""),
    )
    db.add(msg)
    await db.flush()

    thread.message_count = (thread.message_count or 0) + 1
    thread.last_message_at = now
    thread.last_inbound_at = now

    # ── 5. Classify + persist EmailClassification row ─────────────────
    classification_row = await classify_and_persist(db, message=msg, org_id=org_uuid)
    thread.latest_classification = classification_row.intent

    # ── 6. Draft reply (reply_policy runs inside; trace persisted) ───
    cls_dataclass = ClassificationResult(
        intent=classification_row.intent,
        confidence=float(classification_row.confidence or 0.0),
        rationale=classification_row.rationale or "",
        secondary_intent=classification_row.secondary_intent,
        secondary_confidence=classification_row.secondary_confidence,
        reply_mode=classification_row.reply_mode or "draft",
    )
    draft_result = await create_reply_draft(
        db,
        thread_id=thread.id,
        message_id=msg.id,
        classification=cls_dataclass,
        org_id=org_uuid,
        to_email=sender_email or "",
        body_text=body_preview or body_text or "",
        thread_subject=subject or "",
        classification_id=classification_row.id,
    )

    # Link draft id onto classification + record policy's final mode
    final_mode = draft_result.get("reply_mode") or cls_dataclass.reply_mode
    if final_mode:
        classification_row.reply_mode = final_mode
    draft_id_str = draft_result.get("draft_id")
    if draft_id_str:
        try:
            classification_row.action_id = uuid.UUID(draft_id_str)
        except (ValueError, TypeError):
            pass

    await db.flush()

    return {
        "inbox_connection_id": str(inbox.id),
        "thread_id": str(thread.id),
        "message_id": str(msg.id),
        "provider_message_id": provider_message_id,
        "classification_id": str(classification_row.id),
        "intent": classification_row.intent,
        "confidence": float(classification_row.confidence or 0.0),
        "reply_mode": final_mode,
        "mode_source": draft_result.get("mode_source"),
        "draft_id": draft_id_str,
        "draft_status": draft_result.get("status"),
    }


def _extract_header_value(headers_raw: str, header_name: str) -> str:
    """Case-insensitive lookup of a single header value from raw text."""
    if not headers_raw:
        return ""
    needle = f"{header_name}:".lower()
    for line in str(headers_raw).splitlines():
        if line.lower().startswith(needle):
            return line.split(":", 1)[1].strip().strip("<>")
    return ""


def _normalize_subject_for_thread(subject: str) -> str:
    """Strip stacked Re:/Fwd: prefixes + collapse whitespace for a stable thread key."""
    import re

    if not subject:
        return "(no subject)"
    # Strip any number of stacked "Re:" / "Fwd:" / "Fw:" prefixes in one pass
    s = re.sub(r"^(\s*(?:re|fwd?|fw)\s*:\s*)+", "", subject, flags=re.IGNORECASE).strip()
    s = re.sub(r"\s+", " ", s)
    return s.lower()[:500]


def _parse_display_name(from_full: str) -> str:
    """Extract display name from 'Name <email>' tuple form."""
    import email.utils

    name, _ = email.utils.parseaddr(str(from_full or ""))
    return (name or "")[:255]


# =====================================================================
# Inbound-email org routing resolver (system-managed)
# =====================================================================

async def _resolve_inbound_org_id(db, to_address: str):
    """Resolve an inbound recipient address to an organization_id using
    DB-managed routing rows in ``integration_providers``.

    Match priority (first match wins):
      1. exact ``extra_config.to_address`` equal to the recipient
      2. exact ``extra_config.plus_token`` equal to the token extracted from
         a ``local+<token>@domain`` recipient
      3. exact ``extra_config.to_domain`` equal to the recipient's domain

    Returns ``uuid.UUID`` or ``None``. Env is never consulted here; the
    legacy PROOFHOOK_INBOUND_ORG_ID fallback is applied by the caller only
    when this function returns ``None``.
    """
    from packages.db.models.integration_registry import IntegrationProvider

    to_address = (to_address or "").strip().lower()
    if not to_address:
        return None

    local = to_address.split("@", 1)[0] if "@" in to_address else ""
    domain = to_address.split("@", 1)[1] if "@" in to_address else ""
    plus_token = ""
    if "+" in local:
        plus_token = local.split("+", 1)[1]

    rows = (await db.execute(
        select(IntegrationProvider).where(
            IntegrationProvider.provider_key == "inbound_email_route",
            IntegrationProvider.is_enabled.is_(True),
        )
    )).scalars().all()

    # Pass 1: exact to_address
    for row in rows:
        extra = row.extra_config or {}
        route_to = str(extra.get("to_address", "")).strip().lower()
        if route_to and route_to == to_address:
            return row.organization_id

    # Pass 2: plus_token
    if plus_token:
        for row in rows:
            extra = row.extra_config or {}
            token = str(extra.get("plus_token", "")).strip().lower()
            if token and token == plus_token:
                return row.organization_id

    # Pass 3: to_domain
    if domain:
        for row in rows:
            extra = row.extra_config or {}
            route_domain = str(extra.get("to_domain", "")).strip().lower()
            if route_domain and route_domain == domain:
                return row.organization_id

    return None


# =====================================================================
# Webhook signing-secret resolvers (system-managed)
# =====================================================================
#
# Webhooks arrive before we know the owning org — the signing secret must
# therefore be looked up without org context. We pull every DB-managed
# secret for the relevant provider_key, try each against the incoming
# signature, and let the verifier decide which one is correct.
#
# Env (STRIPE_WEBHOOK_SECRET / SHOPIFY_WEBHOOK_SECRET) remains only as a
# last-resort legacy fallback, logged every time it fires.


async def _resolve_stripe_webhook_secret(db):
    """Return candidate Stripe webhook secrets from integration_providers.

    Reads every row with provider_key='stripe_webhook' and is_enabled=true
    across all orgs, decrypts the api_key_encrypted column, and returns
    ``[(org_id, secret), ...]`` in priority order (priority_order ASC, then
    created_at ASC). Env is NOT consulted here; that's done by the caller.
    """
    from packages.db.models.integration_registry import IntegrationProvider
    from apps.api.services.integration_manager import _decrypt

    rows = (await db.execute(
        select(IntegrationProvider)
        .where(
            IntegrationProvider.provider_key == "stripe_webhook",
            IntegrationProvider.is_enabled.is_(True),
        )
        .order_by(
            IntegrationProvider.priority_order.asc(),
            IntegrationProvider.created_at.asc(),
        )
    )).scalars().all()

    candidates: list[tuple[uuid.UUID, str]] = []
    for row in rows:
        if not row.api_key_encrypted:
            continue
        try:
            secret = _decrypt(row.api_key_encrypted)
        except Exception as exc:
            logger.warning("stripe_webhook.decrypt_failed", row_id=str(row.id), error=str(exc)[:120])
            continue
        if secret:
            candidates.append((row.organization_id, secret))
    return candidates


async def _resolve_shopify_webhook_secret(db):
    """Return candidate Shopify webhook secrets from integration_providers.

    Same shape as ``_resolve_stripe_webhook_secret`` but keyed to
    ``provider_key='shopify_webhook'``.
    """
    from packages.db.models.integration_registry import IntegrationProvider
    from apps.api.services.integration_manager import _decrypt

    rows = (await db.execute(
        select(IntegrationProvider)
        .where(
            IntegrationProvider.provider_key == "shopify_webhook",
            IntegrationProvider.is_enabled.is_(True),
        )
        .order_by(
            IntegrationProvider.priority_order.asc(),
            IntegrationProvider.created_at.asc(),
        )
    )).scalars().all()

    candidates: list[tuple[uuid.UUID, str]] = []
    for row in rows:
        if not row.api_key_encrypted:
            continue
        try:
            secret = _decrypt(row.api_key_encrypted)
        except Exception as exc:
            logger.warning("shopify_webhook.decrypt_failed", row_id=str(row.id), error=str(exc)[:120])
            continue
        if secret:
            candidates.append((row.organization_id, secret))
    return candidates


async def _verify_webhook_with_candidates(
    *,
    verifier,
    body: bytes,
    signature: str,
    candidates,
    env_var: str,
    provider_key: str,
    log_prefix: str,
):
    """Try each DB-managed candidate secret; fall back to env only if all fail.

    Returns ``(result, matched_org_id)`` where ``result`` is the verifier's
    dict (``{"valid": bool, "error": str, ...}``) and ``matched_org_id`` is
    the org that owned the secret that verified, or ``None`` if the env
    fallback was used, or ``None`` on total failure.

    Signature verification itself is the identity proof — only the org that
    generated the webhook can have signed with the matching secret, so the
    first candidate that verifies is the correct owner.
    """
    last_error: str = ""

    for org_id, secret in candidates or []:
        result = verifier.verify(body, signature, secret)
        if result.get("valid"):
            logger.info(
                f"{log_prefix}.db_verified",
                provider_key=provider_key,
                org_id=str(org_id),
            )
            return result, org_id
        last_error = result.get("error") or last_error

    # DB candidates exhausted (or none existed) — try env legacy fallback.
    env_secret = os.environ.get(env_var, "")
    if env_secret:
        result = verifier.verify(body, signature, env_secret)
        if result.get("valid"):
            logger.warning(
                f"{log_prefix}.env_legacy_fallback",
                env_var=env_var,
                hint=f"Verified via {env_var} env var. Create an integration_providers row with provider_key='{provider_key}' and api_key set to the signing secret to move this to system-managed.",
            )
            return result, None
        last_error = result.get("error") or last_error

    # Nothing verified — caller will return 400 using the error field.
    if not candidates and not env_secret:
        last_error = f"No {provider_key} signing secret configured (integration_providers.provider_key='{provider_key}' empty and {env_var} env unset)"
    return {"valid": False, "error": last_error or "signature did not verify"}, None
