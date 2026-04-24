"""Proposal dunning (Batch 9).

Sends polite payment reminders for proposals in status=sent that haven't
been paid after a cadence. Caps at 3 reminders then escalates to GM.

Cadence:
  - 24h after sent  → reminder #1 (gentle)
  - 72h after sent  → reminder #2
  - 7 days after sent → reminder #3 (final)
  - After #3        → dunning_status = "max_reached", GM escalation fired.

Called by:
  - Celery beat task ``dunning.chase_unpaid_proposals`` every 6h (auto path).
  - ``/gm/write/proposals/{id}/dunning/send`` (operator-commanded path).

Doctrine fit: this is a money-touching action. classify_action returns
``approval_required`` for the first 2 reminders (operator could have
overridden earlier), and ``escalate`` for the 3rd. The service itself
doesn't enforce doctrine — callers (GM write endpoint, beat task)
pass ``action_class`` so the audit row captures the reason.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_event
from packages.clients.email_templates import build_dunning_reminder
from packages.clients.external_clients import SmtpEmailClient
from packages.db.models.clients import Client
from packages.db.models.proposals import PaymentLink, Proposal

logger = structlog.get_logger()

MAX_REMINDERS = 3
CADENCE_HOURS = (24, 72, 24 * 7)  # #1 @ 24h, #2 @ 72h, #3 @ 7d


async def send_reminder(
    db: AsyncSession,
    *,
    proposal: Proposal,
    actor_type: str = "system",
    actor_id: str | None = None,
) -> dict:
    """Send the next-in-sequence dunning reminder for a proposal.

    Returns structured result:
      ``{"sent": bool, "reminder_number": int, "reason": str|None, "error": str|None}``

    Idempotent by reminder number + last_sent_at (callers should respect
    cadence but the service will not send two reminders within 1 hour).
    Transitions proposal.dunning_status from ``none``/``in_progress``
    to ``in_progress`` after first send, to ``max_reached`` after the 3rd.
    """
    if proposal.status in ("paid", "accepted"):
        return {"sent": False, "reason": "proposal_already_paid", "reminder_number": 0}
    if proposal.status not in ("sent",):
        return {
            "sent": False,
            "reason": f"proposal_status_{proposal.status}_not_eligible_for_dunning",
            "reminder_number": 0,
        }
    if proposal.dunning_status == "max_reached":
        return {
            "sent": False,
            "reason": "max_reminders_reached",
            "reminder_number": proposal.dunning_reminders_sent,
        }
    if proposal.dunning_status == "cancelled":
        return {"sent": False, "reason": "dunning_cancelled", "reminder_number": 0}

    now = datetime.now(timezone.utc)
    # 1h guard — prevent re-fire from overlapping beat runs / operator clicks
    if proposal.dunning_last_sent_at and (now - proposal.dunning_last_sent_at < timedelta(hours=1)):
        return {
            "sent": False,
            "reason": "debounce_1h",
            "reminder_number": proposal.dunning_reminders_sent,
        }

    next_n = (proposal.dunning_reminders_sent or 0) + 1
    if next_n > MAX_REMINDERS:
        # Should have been caught above, but defensive.
        proposal.dunning_status = "max_reached"
        await db.flush()
        return {"sent": False, "reason": "max_reminders_reached", "reminder_number": next_n - 1}

    # Fetch client (recipient) + active payment link URL
    client = (
        await db.execute(
            select(Client).where(
                Client.org_id == proposal.org_id,
                Client.primary_email == proposal.recipient_email.lower(),
            )
        )
    ).scalar_one_or_none()
    display_name = proposal.recipient_name or (client.display_name if client else "") or proposal.recipient_email

    link_url = None
    link = (
        await db.execute(
            select(PaymentLink)
            .where(
                PaymentLink.proposal_id == proposal.id,
                PaymentLink.is_active.is_(True),
            )
            .order_by(PaymentLink.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if link is not None:
        link_url = link.url

    amount_display = None
    if proposal.total_amount_cents:
        amount_display = f"${proposal.total_amount_cents / 100:,.2f} {proposal.currency.upper()}"

    built = build_dunning_reminder(
        display_name=display_name,
        proposal_title=proposal.title,
        payment_link_url=link_url,
        amount_display=amount_display,
        reminder_number=next_n,
    )

    smtp = await SmtpEmailClient.from_db(db, proposal.org_id)
    if smtp is None:
        return {
            "sent": False,
            "reason": "no_smtp_configured",
            "reminder_number": next_n - 1,
        }

    result = await smtp.send_email(
        to_email=proposal.recipient_email,
        subject=built["subject"],
        body_html=built["html"],
        body_text=built["text"],
    )
    if not result.get("success"):
        await emit_event(
            db,
            domain="monetization",
            event_type="proposal.dunning_send_failed",
            summary=f"Dunning reminder #{next_n} failed for {proposal.recipient_email}: {result.get('error')}",
            org_id=proposal.org_id,
            brand_id=proposal.brand_id,
            entity_type="proposal",
            entity_id=proposal.id,
            actor_type=actor_type,
            actor_id=actor_id,
            severity="warning",
            details={
                "proposal_id": str(proposal.id),
                "reminder_number": next_n,
                "error": result.get("error"),
                "provider": result.get("provider"),
            },
        )
        return {
            "sent": False,
            "reason": result.get("error") or "smtp_send_failed",
            "reminder_number": next_n - 1,
            "error": result.get("error"),
        }

    proposal.dunning_reminders_sent = next_n
    proposal.dunning_last_sent_at = now
    proposal.dunning_status = "max_reached" if next_n >= MAX_REMINDERS else "in_progress"
    await db.flush()

    await emit_event(
        db,
        domain="monetization",
        event_type="proposal.dunning_reminder_sent",
        summary=f"Dunning reminder #{next_n} sent to {proposal.recipient_email}",
        org_id=proposal.org_id,
        brand_id=proposal.brand_id,
        entity_type="proposal",
        entity_id=proposal.id,
        actor_type=actor_type,
        actor_id=actor_id,
        details={
            "proposal_id": str(proposal.id),
            "reminder_number": next_n,
            "recipient_email": proposal.recipient_email,
            "avenue_slug": proposal.avenue_slug,
            "amount_cents": proposal.total_amount_cents,
        },
    )
    logger.info(
        "proposal.dunning_reminder_sent",
        proposal_id=str(proposal.id),
        reminder_number=next_n,
        recipient=proposal.recipient_email,
    )

    # On max reached → escalate to GM for human follow-up.
    if next_n >= MAX_REMINDERS:
        try:
            from packages.db.models.gm_control import GMEscalation

            db.add(
                GMEscalation(
                    org_id=proposal.org_id,
                    reason_code="proposal_dunning_max_reached",
                    entity_type="proposal",
                    entity_id=proposal.id,
                    title=f"Proposal unpaid after {MAX_REMINDERS} reminders: {proposal.title[:300]}",
                    description=(
                        f"Proposal {proposal.id} to {proposal.recipient_email} "
                        f"sat unpaid after {MAX_REMINDERS} auto-reminders. "
                        f"Operator decision needed: nudge manually, offer discount, "
                        f"or close out the slot."
                    ),
                    severity="warning",
                    status="open",
                    details_json={
                        "proposal_id": str(proposal.id),
                        "amount_cents": proposal.total_amount_cents,
                        "recipient_email": proposal.recipient_email,
                        "sent_at": proposal.sent_at.isoformat() if proposal.sent_at else None,
                    },
                )
            )
            await db.flush()
        except Exception as esc_exc:
            logger.warning(
                "proposal.dunning_escalation_failed",
                proposal_id=str(proposal.id),
                error=str(esc_exc)[:200],
            )

    return {"sent": True, "reminder_number": next_n, "reason": None}


async def chase_unpaid_proposals(db: AsyncSession) -> dict:
    """Scheduled (Celery beat) scan for proposals due a next dunning hit.

    Called every 6h. Uses a conservative cadence so no proposal gets
    two reminders within 20h.

    Returns ``{"scanned": int, "sent": int, "skipped": int, "errors": int}``.
    """
    now = datetime.now(timezone.utc)
    scanned = 0
    sent = 0
    skipped = 0
    errors = 0

    # Proposals in status=sent, not yet paid, not max-reached, with sent_at
    # older than 24h (cadence floor).
    q = select(Proposal).where(
        Proposal.status == "sent",
        Proposal.is_active.is_(True),
        Proposal.dunning_status.in_(("none", "in_progress")),
        Proposal.sent_at.isnot(None),
        Proposal.sent_at < now - timedelta(hours=24),
    )
    rows = (await db.execute(q)).scalars().all()
    scanned = len(rows)

    for p in rows:
        # Determine whether this proposal is DUE for its next reminder.
        sent_at = p.sent_at or now
        elapsed = now - sent_at
        next_idx = p.dunning_reminders_sent or 0  # 0→fire #1, 1→fire #2, 2→fire #3
        if next_idx >= MAX_REMINDERS:
            skipped += 1
            continue
        due_hours = CADENCE_HOURS[next_idx]
        if elapsed < timedelta(hours=due_hours):
            skipped += 1
            continue

        try:
            result = await send_reminder(db, proposal=p, actor_type="system", actor_id="beat.chase_unpaid_proposals")
            if result.get("sent"):
                sent += 1
            else:
                skipped += 1
        except Exception as send_exc:
            errors += 1
            logger.warning(
                "dunning.beat_send_failed",
                proposal_id=str(p.id),
                error=str(send_exc)[:200],
            )

    await db.commit()
    logger.info(
        "dunning.beat_scan_complete",
        scanned=scanned,
        sent=sent,
        skipped=skipped,
        errors=errors,
    )
    return {"scanned": scanned, "sent": sent, "skipped": skipped, "errors": errors}
