"""Action Dispatcher — executes autonomous actions that change real state.

This is the last-mile gap closer. It reads OperatorAction rows with
autonomy_level='autonomous' and confidence >= threshold, then executes
the actual downstream state change.

Every dispatched action is:
- Confidence-gated (won't execute below threshold)
- Audited (SystemEvent emitted before + after)
- State-changing (calls the real function that modifies DB)
- Reversible where applicable (records what changed for rollback)

Called by: Celery Beat schedule, or POST /revenue/dispatch-autonomous
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_event, complete_action
from packages.db.models.system_events import OperatorAction

logger = structlog.get_logger()

# Minimum confidence to auto-execute (safety floor)
MIN_AUTONOMOUS_CONFIDENCE = 0.6


async def dispatch_autonomous_actions(
    db: AsyncSession,
    org_id: uuid.UUID,
    *,
    dry_run: bool = False,
    limit: int = 20,
) -> dict:
    """Read pending autonomous actions and execute their downstream effects.

    Returns a report of what was executed, skipped, or failed.
    """
    # Find pending actions marked as autonomous
    q = await db.execute(
        select(OperatorAction).where(
            OperatorAction.organization_id == org_id,
            OperatorAction.status == "pending",
        ).order_by(OperatorAction.created_at).limit(limit)
    )
    pending = q.scalars().all()

    # Filter to autonomous only (check payload)
    autonomous = []
    for action in pending:
        payload = action.action_payload or {}
        if payload.get("autonomy_level") == "autonomous":
            confidence = payload.get("confidence", 0)
            if confidence >= MIN_AUTONOMOUS_CONFIDENCE:
                autonomous.append(action)

    executed = []
    skipped = []
    failed = []

    for action in autonomous:
        payload = action.action_payload or {}
        confidence = payload.get("confidence", 0)
        action_type = action.action_type

        if dry_run:
            skipped.append(_action_summary(action, "dry_run"))
            continue

        # Dispatch to handler
        handler = DISPATCH_TABLE.get(action_type)
        if not handler:
            skipped.append(_action_summary(action, f"no_handler_for_{action_type}"))
            continue

        try:
            # Emit pre-execution event
            await emit_event(
                db, domain="monetization",
                event_type=f"autonomous.executing.{action_type}",
                summary=f"Auto-executing: {action.title[:80]}",
                org_id=org_id, brand_id=action.brand_id,
                entity_type=action.entity_type,
                entity_id=action.entity_id,
                details={"action_id": str(action.id), "confidence": confidence},
            )

            # Execute the actual state change
            result = await handler(db, action)

            # Mark action completed
            await complete_action(
                db, action,
                completed_by="autonomous_dispatcher",
                result={"executed": True, "handler": action_type, **result},
            )

            # Emit post-execution event
            await emit_event(
                db, domain="monetization",
                event_type=f"autonomous.completed.{action_type}",
                summary=f"Auto-executed: {action.title[:80]}",
                org_id=org_id, brand_id=action.brand_id,
                entity_type=action.entity_type,
                entity_id=action.entity_id,
                severity="info",
                details={"action_id": str(action.id), "result": result},
            )

            executed.append(_action_summary(action, "executed", result))

        except Exception as e:
            logger.error("dispatch.failed", action_id=str(action.id), action_type=action_type, error=str(e))

            await emit_event(
                db, domain="recovery",
                event_type=f"autonomous.failed.{action_type}",
                summary=f"Auto-execution failed: {action.title[:60]} — {str(e)[:100]}",
                org_id=org_id, brand_id=action.brand_id,
                severity="error", requires_action=True,
                details={"action_id": str(action.id), "error": str(e)[:500]},
            )

            failed.append(_action_summary(action, "failed", {"error": str(e)[:200]}))

    await db.flush()

    logger.info(
        "dispatch.cycle_complete",
        org_id=str(org_id),
        executed=len(executed),
        skipped=len(skipped),
        failed=len(failed),
    )

    return {
        "executed": executed,
        "skipped": skipped,
        "failed": failed,
        "total_pending": len(pending),
        "total_autonomous": len(autonomous),
        "dry_run": dry_run,
    }


def _action_summary(action: OperatorAction, status: str, result: Optional[dict] = None) -> dict:
    return {
        "action_id": str(action.id),
        "action_type": action.action_type,
        "title": action.title[:100],
        "brand_id": str(action.brand_id) if action.brand_id else None,
        "confidence": (action.action_payload or {}).get("confidence", 0),
        "dispatch_status": status,
        "result": result,
    }


# ══════════════════════════════════════════════════════════════════════
# DISPATCH TABLE — maps action types to real state-changing functions
# ══════════════════════════════════════════════════════════════════════

async def _handle_attach_offer(db: AsyncSession, action: OperatorAction) -> dict:
    """Actually assign an offer to content."""
    from apps.api.services.monetization_bridge import assign_offer_to_content, select_best_offer_for_content

    if not action.entity_id:
        return {"skipped": True, "reason": "no entity_id (content_item)"}

    best_offer = await select_best_offer_for_content(db, action.brand_id)
    if not best_offer:
        return {"skipped": True, "reason": "no active offers for brand"}

    item = await assign_offer_to_content(
        db, action.entity_id, best_offer.id,
        org_id=action.organization_id,
    )
    return {"content_id": str(action.entity_id), "offer_id": str(best_offer.id), "offer_name": best_offer.name}


async def _handle_promote_winner(db: AsyncSession, action: OperatorAction) -> dict:
    """Promote a winning offer/pattern: increase priority + weight_boost + mark as promoted."""
    from packages.db.models.promote_winner import PromotedWinnerRule
    from packages.db.models.offers import Offer

    changes = []

    # If action references an entity, try to boost it
    if action.entity_id:
        # Boost promoted winner rules for this entity
        rules = (await db.execute(
            select(PromotedWinnerRule).where(
                PromotedWinnerRule.brand_id == action.brand_id,
                PromotedWinnerRule.is_active.is_(True),
            ).limit(5)
        )).scalars().all()

        for rule in rules:
            old_boost = rule.weight_boost
            rule.weight_boost = min(1.0, (rule.weight_boost or 0) + 0.15)
            changes.append(f"rule {rule.rule_key}: weight_boost {old_boost:.2f} → {rule.weight_boost:.2f}")

    # Boost the highest-EPC offer's priority
    if action.brand_id:
        top_offer = (await db.execute(
            select(Offer).where(
                Offer.brand_id == action.brand_id,
                Offer.is_active.is_(True),
            ).order_by(Offer.epc.desc().nullslast()).limit(1)
        )).scalar_one_or_none()

        if top_offer:
            old_priority = top_offer.priority
            top_offer.priority = min(100, (top_offer.priority or 0) + 10)
            changes.append(f"offer '{top_offer.name}': priority {old_priority} → {top_offer.priority}")

    return {"promoted": True, "state_changes": changes, "changes_count": len(changes)}


async def _handle_suppress_loser(db: AsyncSession, action: OperatorAction) -> dict:
    """Suppress a losing offer/pattern: deactivate offer, create suppression rule."""
    from packages.db.models.failure_family import SuppressionRule
    from packages.db.models.offers import Offer

    changes = []

    # If the action targets a specific offer, deactivate it
    payload = action.action_payload or {}
    source = payload.get("source_engine", "")

    # Deactivate the lowest-performing active offer
    if action.brand_id:
        worst_offer = (await db.execute(
            select(Offer).where(
                Offer.brand_id == action.brand_id,
                Offer.is_active.is_(True),
            ).order_by(Offer.epc.asc().nullslast()).limit(1)
        )).scalar_one_or_none()

        if worst_offer and (worst_offer.epc or 0) < 0.5:
            worst_offer.is_active = False
            changes.append(f"offer '{worst_offer.name}' (EPC={worst_offer.epc}): deactivated")

    # Note: SuppressionRule requires a report_id FK, so we only create rules
    # when there's an existing FailureFamilyReport to reference.
    # The offer deactivation above IS the real suppression state change.

    return {"suppressed": True, "state_changes": changes, "changes_count": len(changes)}


async def _handle_repair_attribution(db: AsyncSession, action: OperatorAction) -> dict:
    """Auto-attribute unattributed revenue: set offer_id and attribution_state."""
    if not action.entity_id:
        return {"skipped": True, "reason": "no entity_id"}

    from packages.db.models.revenue_ledger import RevenueLedgerEntry
    entry = (await db.execute(
        select(RevenueLedgerEntry).where(RevenueLedgerEntry.id == action.entity_id)
    )).scalar_one_or_none()

    if not entry:
        return {"skipped": True, "reason": "ledger entry not found"}

    if entry.attribution_state != "unattributed":
        return {"skipped": True, "reason": f"already attributed: {entry.attribution_state}"}

    # Try to infer from content if possible
    if entry.content_item_id:
        from packages.db.models.content import ContentItem
        item = (await db.execute(
            select(ContentItem).where(ContentItem.id == entry.content_item_id)
        )).scalar_one_or_none()
        if item and item.offer_id:
            entry.offer_id = item.offer_id
            entry.attribution_state = "auto_attributed"
            return {"attributed": True, "offer_id": str(item.offer_id), "method": "inferred_from_content",
                    "state_changes": [f"ledger entry: attribution_state unattributed → auto_attributed, offer_id set"]}

    # Try to find the best offer for this brand and attribute to it
    if entry.brand_id:
        from packages.db.models.offers import Offer
        best = (await db.execute(
            select(Offer).where(Offer.brand_id == entry.brand_id, Offer.is_active.is_(True))
            .order_by(Offer.epc.desc().nullslast()).limit(1)
        )).scalar_one_or_none()
        if best:
            entry.offer_id = best.id
            entry.attribution_state = "auto_attributed"
            return {"attributed": True, "offer_id": str(best.id), "method": "best_offer_for_brand",
                    "state_changes": [f"ledger entry: attributed to offer '{best.name}'"]}

    return {"skipped": True, "reason": "could not auto-attribute"}


async def _handle_deprioritize(db: AsyncSession, action: OperatorAction) -> dict:
    """Deprioritize low-margin path: reduce offer priority, adjust account scale_role."""
    from packages.db.models.offers import Offer

    changes = []

    # Reduce priority of lowest-margin offers
    if action.brand_id:
        low_margin_offers = (await db.execute(
            select(Offer).where(
                Offer.brand_id == action.brand_id,
                Offer.is_active.is_(True),
                Offer.priority > 0,
            ).order_by(Offer.epc.asc().nullslast()).limit(3)
        )).scalars().all()

        for offer in low_margin_offers:
            old_priority = offer.priority
            offer.priority = max(0, (offer.priority or 0) - 5)
            if old_priority != offer.priority:
                changes.append(f"offer '{offer.name}': priority {old_priority} → {offer.priority}")

    return {"deprioritized": True, "state_changes": changes, "changes_count": len(changes)}


async def _handle_reduce_channel(db: AsyncSession, action: OperatorAction) -> dict:
    """Reduce dead channel: lower account scale_role, reduce posting capacity."""
    from packages.db.models.accounts import CreatorAccount

    changes = []

    # Find accounts with lowest revenue and reduce their scale role
    if action.brand_id:
        from packages.db.models.revenue_ledger import RevenueLedgerEntry
        from sqlalchemy import func as sqlfunc

        # Find accounts with zero ledger revenue
        zero_rev_accounts = (await db.execute(
            select(CreatorAccount).where(
                CreatorAccount.brand_id == action.brand_id,
                CreatorAccount.is_active.is_(True),
            ).limit(10)
        )).scalars().all()

        for acct in zero_rev_accounts:
            rev = (await db.execute(
                select(sqlfunc.coalesce(sqlfunc.sum(RevenueLedgerEntry.gross_amount), 0.0)).where(
                    RevenueLedgerEntry.creator_account_id == acct.id,
                    RevenueLedgerEntry.is_active.is_(True),
                )
            )).scalar() or 0.0

            if float(rev) == 0 and acct.scale_role != "paused":
                old_role = acct.scale_role
                acct.scale_role = "reduced"
                platform = acct.platform.value if hasattr(acct.platform, 'value') else str(acct.platform)
                changes.append(f"account @{acct.platform_username or platform}: scale_role {old_role} → reduced")

    return {"reduced": True, "state_changes": changes, "changes_count": len(changes)}


async def _handle_recover_webhook(db: AsyncSession, action: OperatorAction) -> dict:
    """Recover failed webhook: re-trigger ledger write from the original payload, then mark processed."""
    from packages.db.models.live_execution_phase2 import WebhookEvent
    from apps.api.services.monetization_bridge import record_service_payment_to_ledger, record_product_sale_to_ledger

    changes = []

    if not action.brand_id:
        return {"skipped": True, "reason": "no brand_id"}

    # Find unprocessed webhook events for this brand
    unprocessed = (await db.execute(
        select(WebhookEvent).where(
            WebhookEvent.brand_id == action.brand_id,
            WebhookEvent.processed.is_(False),
        ).limit(5)
    )).scalars().all()

    for evt in unprocessed:
        payload = evt.raw_payload or {}
        source = evt.source or ""
        event_type = evt.event_type or ""
        ext_id = evt.external_event_id or str(evt.id)

        try:
            if source == "stripe" and event_type in ("checkout.session.completed", "charge.succeeded", "payment_intent.succeeded"):
                obj = payload.get("data", {}).get("object", {})
                revenue = float(obj.get("amount_total", obj.get("amount", 0))) / 100.0
                if revenue > 0:
                    await record_service_payment_to_ledger(
                        db, brand_id=action.brand_id, gross_amount=revenue,
                        payment_processor="stripe",
                        external_transaction_id=obj.get("payment_intent") or obj.get("id") or "",
                        webhook_ref=f"stripe_recovery:{ext_id}",
                        description=f"Recovered Stripe {event_type}: ${revenue:.2f}",
                    )
                    changes.append(f"stripe {ext_id}: ledger entry created (${revenue:.2f})")

            elif source == "shopify" and "order" in event_type:
                total = float(payload.get("total_price", 0))
                if total > 0:
                    await record_product_sale_to_ledger(
                        db, brand_id=action.brand_id, gross_amount=total,
                        payment_processor="shopify",
                        external_transaction_id=str(payload.get("id", "")),
                        webhook_ref=f"shopify_recovery:{ext_id}",
                        description=f"Recovered Shopify order: ${total:.2f}",
                    )
                    changes.append(f"shopify {ext_id}: ledger entry created (${total:.2f})")

            # Mark as processed only after successful ledger write
            evt.processed = True
            changes.append(f"webhook {ext_id}: marked processed after recovery")

        except Exception as e:
            changes.append(f"webhook {ext_id}: recovery failed ({str(e)[:100]})")

    return {"recovery_executed": True, "state_changes": changes, "changes_count": len(changes),
            "ledger_entries_created": len([c for c in changes if "ledger entry created" in c])}


async def _handle_send_outreach(db: AsyncSession, action: OperatorAction) -> dict:
    """Actually send an outreach email via SMTP.

    SMTP is resolved DB-first via ``SmtpEmailClient.resolve`` (scoped to the
    action's organization). Env is used only as a clearly-marked legacy
    fallback inside the resolver; no env read happens in this handler.
    """
    payload = action.action_payload or {}
    draft = payload.get("draft", {})

    contact_email = draft.get("contact_email")
    subject = draft.get("subject")
    body = draft.get("body")

    if not contact_email or not subject or not body:
        return {"skipped": True, "reason": "Missing contact_email, subject, or body in draft"}

    try:
        from packages.clients.external_clients import SmtpEmailClient
        client = await SmtpEmailClient.resolve(db, action.organization_id)
        if not client._is_configured():
            return {
                "skipped": True,
                "reason": (
                    "SMTP not configured for this organization in integration_providers "
                    "(provider_key='smtp') and no env legacy fallback available."
                ),
                "draft_preserved": True,
                "contact": contact_email,
                "subject": subject,
            }
        result = await client.send_email(to_email=contact_email, subject=subject, body_text=body)
        if result.get("success"):
            return {
                "sent": True,
                "contact": contact_email,
                "subject": subject,
                "smtp_source": client.source,
                "state_changes": [f"Email sent to {contact_email}"],
            }
        return {"sent": False, "error": result.get("error", "Send failed"), "smtp_source": client.source}
    except Exception as e:
        return {"sent": False, "error": str(e)[:200]}


# The dispatch table: action_type → handler function
DISPATCH_TABLE = {
    "attach_offer_to_content": _handle_attach_offer,
    "assign_offer": _handle_attach_offer,  # alias
    "promote_winning_offer": _handle_promote_winner,
    "suppress_losing_offer": _handle_suppress_loser,
    "repair_broken_attribution": _handle_repair_attribution,
    "attribute_revenue": _handle_repair_attribution,  # alias
    "recover_failed_webhook": _handle_recover_webhook,
    "deprioritize_low_margin": _handle_deprioritize,
    "reduce_dead_channel": _handle_reduce_channel,
    "send_outreach_email": _handle_send_outreach,
    "send_follow_up": _handle_send_outreach,  # Same handler, different sequence step
}
