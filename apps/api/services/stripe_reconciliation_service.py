"""Stripe webhook reconciliation (Batch 9).

Backstop for missed Stripe webhooks. Polls Stripe's /v1/events endpoint
per org and re-ingests any event we never received via webhook.

Rationale: the webhook is the primary path, but Stripe itself documents
that webhooks can be missed (network, endpoint down, signing-secret
rotation, mistyped URL during setup). Without a reconciler, a missed
``checkout.session.completed`` means a paid customer never gets
onboarded. This service is the safety net — it compares Stripe's
authoritative event ledger against ``webhook_events`` and fills gaps.

Scheduled via Celery beat every 10 minutes. Uses the same
``record_payment_from_stripe`` + ``activate_client_from_payment`` path
as the live webhook so gap-fills are behaviorally identical to
real-time deliveries (idempotent throughout).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_event
from packages.db.models.live_execution_phase2 import WebhookEvent

logger = structlog.get_logger()

RELEVANT_EVENT_TYPES = (
    "checkout.session.completed",
    "payment_intent.succeeded",
    "charge.succeeded",
    "charge.refunded",
    "invoice.paid",
    "invoice.payment_failed",
    "customer.subscription.created",
    "customer.subscription.deleted",
    "customer.subscription.updated",
)


async def reconcile_stripe_for_org(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    lookback_hours: int = 24,
) -> dict:
    """Reconcile one org's Stripe events against ``webhook_events``.

    Fetches Stripe's /v1/events for the configured org's api_key, keeps
    events in RELEVANT_EVENT_TYPES newer than lookback, and for each
    one that's not already in ``webhook_events.external_event_id``
    synthesizes the same processing path as the live webhook.

    Returns:
      ``{"scanned": int, "gap_filled": int, "already_present": int,
         "errors": int, "skipped_no_stripe": bool}``
    """
    from apps.api.services.stripe_billing_service import _get_stripe_api_key

    api_key = await _get_stripe_api_key(db, org_id)
    if not api_key:
        return {"skipped_no_stripe": True, "scanned": 0, "gap_filled": 0,
                "already_present": 0, "errors": 0}

    try:
        import stripe
    except ImportError:
        logger.warning("stripe_reconciliation.stripe_sdk_missing", org_id=str(org_id))
        return {"skipped_no_stripe": True, "scanned": 0, "gap_filled": 0,
                "already_present": 0, "errors": 0}

    # Note: stripe.Event.list is sync. The stripe lib is sync-only; we
    # run it inline (each beat cycle is a short burst so blocking is OK).
    stripe.api_key = api_key
    since_ts = int(
        (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).timestamp()
    )

    scanned = 0
    gap_filled = 0
    already_present = 0
    errors = 0

    try:
        # Cap pages at 5 (500 events max per run) to keep each cycle bounded.
        starting_after = None
        for _page in range(5):
            kwargs = {
                "limit": 100,
                "created": {"gte": since_ts},
                "types": list(RELEVANT_EVENT_TYPES),
            }
            if starting_after:
                kwargs["starting_after"] = starting_after
            page = stripe.Event.list(**kwargs)
            events = page.get("data") or []
            scanned += len(events)
            if not events:
                break

            for ev in events:
                ev_id = ev.get("id")
                if not ev_id:
                    continue
                # Was this event already received by webhook?
                existing = (
                    await db.execute(
                        select(WebhookEvent).where(
                            WebhookEvent.external_event_id == ev_id,
                            WebhookEvent.source == "stripe",
                        )
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    already_present += 1
                    continue

                # Gap — re-ingest by mimicking the webhook path.
                try:
                    await _ingest_missed_event(db, org_id=org_id, event=ev)
                    gap_filled += 1
                except Exception as ingest_exc:
                    errors += 1
                    logger.warning(
                        "stripe_reconciliation.ingest_failed",
                        org_id=str(org_id),
                        event_id=ev_id,
                        event_type=ev.get("type"),
                        error=str(ingest_exc)[:200],
                    )
            if not page.get("has_more"):
                break
            starting_after = events[-1].get("id")
    except Exception as list_exc:
        errors += 1
        logger.warning(
            "stripe_reconciliation.list_failed",
            org_id=str(org_id),
            error=str(list_exc)[:200],
        )

    result = {
        "scanned": scanned,
        "gap_filled": gap_filled,
        "already_present": already_present,
        "errors": errors,
        "skipped_no_stripe": False,
    }
    if gap_filled > 0:
        await emit_event(
            db,
            domain="monetization",
            event_type="stripe.reconciliation.gap_filled",
            summary=f"Reconciled {gap_filled} missed Stripe events for org",
            org_id=org_id,
            entity_type="organization",
            entity_id=org_id,
            actor_type="system",
            actor_id="stripe_reconciliation_service",
            severity="warning" if errors else "info",
            details=result,
        )
    logger.info("stripe_reconciliation.done", org_id=str(org_id), **result)
    return result


async def _ingest_missed_event(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    event: dict,
) -> None:
    """Re-insert a missed Stripe event and run the same processing the
    live webhook would have run.

    Writes a ``webhook_events`` row with source='stripe' and then
    dispatches via the same record_payment + client_activation path.
    """
    event_id = event.get("id")
    event_type = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}
    meta = obj.get("metadata") or {}

    # 1. Record the webhook_events row so future reconciles see it.
    webhook_row = WebhookEvent(
        source="stripe",
        source_category="payment",
        event_type=event_type,
        external_event_id=event_id,
        raw_payload={"event": event, "reconciled": True},
        processed=True,
        processing_result="reconciled_by_service",
        idempotency_key=f"stripe:{event_id}",
        is_active=True,
    )
    db.add(webhook_row)
    await db.flush()

    # 2. Only the revenue-relevant subset needs downstream processing.
    if event_type in (
        "checkout.session.completed",
        "payment_intent.succeeded",
        "charge.succeeded",
        "invoice.paid",
    ):
        amount_cents = 0
        if event_type == "checkout.session.completed":
            amount_cents = int(obj.get("amount_total") or obj.get("amount_subtotal") or 0)
        elif event_type == "invoice.paid":
            amount_cents = int(obj.get("amount_paid") or 0)
        else:
            amount_cents = int(obj.get("amount_received") or obj.get("amount") or 0)

        if amount_cents <= 0:
            return

        from apps.api.services.proposals_service import record_payment_from_stripe

        payment = await record_payment_from_stripe(
            db,
            org_id=org_id,
            event_id=event_id,
            event_type=event_type,
            amount_cents=amount_cents,
            stripe_object=obj,
            payment_intent_id=obj.get("payment_intent")
                if isinstance(obj.get("payment_intent"), str) else None,
            checkout_session_id=obj.get("id") if event_type == "checkout.session.completed" else None,
            charge_id=obj.get("id") if event_type == "charge.succeeded" else None,
            customer_email=obj.get("customer_email") or obj.get("receipt_email") or "",
            customer_name=(obj.get("customer_details") or {}).get("name", "") or "",
            metadata=meta,
        )
        if payment is not None and payment.status == "succeeded":
            try:
                from apps.api.services.client_activation import (
                    activate_client_from_payment,
                )
                await activate_client_from_payment(db, payment=payment)
            except Exception as act_exc:
                logger.warning(
                    "stripe_reconciliation.client_activation_failed",
                    payment_id=str(payment.id),
                    error=str(act_exc)[:200],
                )


async def reconcile_all_stripe_orgs(db: AsyncSession) -> dict:
    """Reconcile every org that has Stripe credentials configured.

    Called by Celery beat every 10 min. Keeps the blast radius per
    cycle bounded (max 500 events × N orgs).
    """
    from packages.db.models.integration_registry import IntegrationProvider

    q = select(IntegrationProvider.organization_id).where(
        IntegrationProvider.provider_key == "stripe",
        IntegrationProvider.is_enabled.is_(True),
    ).distinct()
    org_ids = [r[0] for r in (await db.execute(q)).all()]

    summary = {
        "orgs_scanned": 0,
        "orgs_skipped_no_stripe": 0,
        "total_gap_filled": 0,
        "total_already_present": 0,
        "total_errors": 0,
    }
    for org_id in org_ids:
        try:
            result = await reconcile_stripe_for_org(db, org_id=org_id)
            summary["orgs_scanned"] += 1
            if result.get("skipped_no_stripe"):
                summary["orgs_skipped_no_stripe"] += 1
            summary["total_gap_filled"] += result.get("gap_filled", 0)
            summary["total_already_present"] += result.get("already_present", 0)
            summary["total_errors"] += result.get("errors", 0)
        except Exception as org_exc:
            summary["total_errors"] += 1
            logger.warning(
                "stripe_reconciliation.org_failed",
                org_id=str(org_id),
                error=str(org_exc)[:200],
            )
    return summary
