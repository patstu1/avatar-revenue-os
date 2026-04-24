"""Invoice service (Batch 13).

Creates and manages invoices billed outside Stripe Checkout (ACH,
wire, check, PO). Payment recording funnels into the same Batch 9
activation chain Stripe webhooks use, so invoice-paid clients get
the same Client → IntakeRequest → cascade treatment (with the
sponsor-specific intake schema applied at ``start_onboarding``).

Exposed functions:

  create_invoice_from_proposal(proposal, milestones, due_date, actor)
  send_invoice(invoice, actor, attempt_email)
  mark_paid(invoice, amount_cents, payment_method, payment_reference,
            milestone_position=None, paid_at=None, actor)
  mark_overdue(invoice)                   # beat task path
  scan_overdue_invoices()                  # beat task entry
  void_invoice(invoice, reason, actor)

Every mutation writes a canonical SystemEvent in domain='monetization'.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_event
from packages.db.models.invoices import (
    Invoice,
    InvoiceLineItem,
    InvoiceMilestone,
)
from packages.db.models.proposals import Payment, Proposal

logger = structlog.get_logger()


VALID_PAYMENT_METHODS = ("wire", "ach", "check", "stripe", "other")


# ═══════════════════════════════════════════════════════════════════════════
#  create_invoice_from_proposal
# ═══════════════════════════════════════════════════════════════════════════


async def create_invoice_from_proposal(
    db: AsyncSession,
    *,
    proposal: Proposal,
    milestones: list[dict] | None = None,
    due_date: datetime | None = None,
    notes: str | None = None,
    actor_type: str = "operator",
    actor_id: str | None = None,
) -> Invoice:
    """Create an Invoice from an existing Proposal. Copies line items,
    sets recipient from the proposal. Optionally seeds milestones
    (e.g. ``[{label: "Signing", amount_cents: 54_000_00}, ...]``).
    If milestones are omitted, the full invoice amount is due on
    due_date (or 30 days from now if not specified).
    """
    # Auto-generate an invoice number scoped to the org
    seq_count = (
        await db.execute(
            select(func.count(Invoice.id)).where(Invoice.org_id == proposal.org_id)
        )
    ).scalar() or 0
    invoice_number = f"INV-{datetime.now(timezone.utc).year}-{seq_count + 1:05d}"

    due = due_date or (datetime.now(timezone.utc) + timedelta(days=30))

    invoice = Invoice(
        org_id=proposal.org_id,
        brand_id=proposal.brand_id,
        proposal_id=proposal.id,
        avenue_slug=proposal.avenue_slug,
        invoice_number=invoice_number,
        total_cents=proposal.total_amount_cents,
        currency=proposal.currency,
        status="draft",
        due_date=due,
        recipient_email=proposal.recipient_email,
        recipient_name=proposal.recipient_name,
        recipient_company=proposal.recipient_company,
        notes=notes,
    )
    db.add(invoice)
    await db.flush()

    # Copy proposal line items onto the invoice
    from packages.db.models.proposals import ProposalLineItem
    proposal_lines = (
        await db.execute(
            select(ProposalLineItem).where(
                ProposalLineItem.proposal_id == proposal.id,
                ProposalLineItem.is_active.is_(True),
            ).order_by(ProposalLineItem.position)
        )
    ).scalars().all()

    for pl in proposal_lines:
        db.add(InvoiceLineItem(
            invoice_id=invoice.id,
            description=pl.description,
            quantity=pl.quantity,
            unit_amount_cents=pl.unit_amount_cents,
            total_amount_cents=pl.total_amount_cents,
            currency=pl.currency,
            position=pl.position,
        ))

    # Add milestones (or one "full amount" milestone)
    seeded_milestones = milestones or [
        {"label": "Full amount", "amount_cents": invoice.total_cents,
         "due_date": due}
    ]
    total_ms = 0
    for i, m in enumerate(seeded_milestones):
        amt = int(m.get("amount_cents", 0))
        total_ms += amt
        ms_due = m.get("due_date")
        if isinstance(ms_due, str):
            ms_due = datetime.fromisoformat(ms_due.replace("Z", "+00:00"))
        db.add(InvoiceMilestone(
            invoice_id=invoice.id,
            position=m.get("position", i),
            label=str(m.get("label", f"Milestone {i+1}"))[:255],
            amount_cents=amt,
            due_date=ms_due or due,
            status="pending",
        ))

    await db.flush()

    if total_ms != invoice.total_cents:
        logger.warning(
            "invoice.milestone_total_mismatch",
            invoice_id=str(invoice.id),
            invoice_total=invoice.total_cents,
            milestone_total=total_ms,
        )

    await emit_event(
        db,
        domain="monetization",
        event_type="invoice.created",
        summary=(
            f"Invoice {invoice_number} created: "
            f"${invoice.total_cents/100:,.2f} {invoice.currency.upper()}"
        ),
        org_id=invoice.org_id,
        brand_id=invoice.brand_id,
        entity_type="invoice",
        entity_id=invoice.id,
        new_state="draft",
        actor_type=actor_type,
        actor_id=actor_id,
        details={
            "invoice_id": str(invoice.id),
            "invoice_number": invoice_number,
            "proposal_id": str(proposal.id),
            "total_cents": invoice.total_cents,
            "milestone_count": len(seeded_milestones),
            "avenue_slug": invoice.avenue_slug,
        },
    )
    logger.info(
        "invoice.created",
        invoice_id=str(invoice.id),
        invoice_number=invoice_number,
        total_cents=invoice.total_cents,
    )
    return invoice


# ═══════════════════════════════════════════════════════════════════════════
#  send_invoice
# ═══════════════════════════════════════════════════════════════════════════


async def send_invoice(
    db: AsyncSession,
    *,
    invoice: Invoice,
    actor_type: str = "operator",
    actor_id: str | None = None,
) -> dict:
    """Mark invoice as sent. Attempts email delivery via SMTP (fails
    gracefully — the status flips to 'sent' regardless, same pattern
    as Batch 9 intake email).
    """
    if invoice.status in ("paid", "void"):
        raise ValueError(
            f"Cannot send invoice in status={invoice.status}"
        )
    prior = invoice.status
    invoice.status = "sent"
    invoice.sent_at = datetime.now(timezone.utc)
    await db.flush()

    send_result = {"success": False, "error": "no_smtp_configured"}
    try:
        from packages.clients.external_clients import SmtpEmailClient
        smtp = await SmtpEmailClient.from_db(db, invoice.org_id)
        if smtp is not None and invoice.recipient_email:
            subject = f"Invoice {invoice.invoice_number} — ${invoice.total_cents/100:,.2f}"
            body = (
                f"Invoice {invoice.invoice_number}\n"
                f"Amount: ${invoice.total_cents/100:,.2f} {invoice.currency.upper()}\n"
                f"Due: {invoice.due_date.isoformat() if invoice.due_date else 'on receipt'}\n\n"
                f"Payment via wire, ACH, or check. Reply here with questions."
            )
            send_result = await smtp.send_email(
                to_email=invoice.recipient_email,
                subject=subject, body_text=body,
                body_html=f"<pre>{body}</pre>",
            )
    except Exception as smtp_exc:
        send_result = {"success": False, "error": str(smtp_exc)[:200]}

    await emit_event(
        db,
        domain="monetization",
        event_type="invoice.sent",
        summary=f"Invoice {invoice.invoice_number} marked sent",
        org_id=invoice.org_id,
        brand_id=invoice.brand_id,
        entity_type="invoice",
        entity_id=invoice.id,
        previous_state=prior,
        new_state="sent",
        actor_type=actor_type,
        actor_id=actor_id,
        details={
            "invoice_id": str(invoice.id),
            "send_success": bool(send_result.get("success")),
            "send_error": send_result.get("error"),
            "avenue_slug": invoice.avenue_slug,
        },
    )
    return {
        "invoice_id": str(invoice.id),
        "status": invoice.status,
        "sent_at": invoice.sent_at.isoformat(),
        "send_success": bool(send_result.get("success")),
        "send_error": send_result.get("error"),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  mark_paid — fires the Batch 9 activation chain
# ═══════════════════════════════════════════════════════════════════════════


async def mark_paid(
    db: AsyncSession,
    *,
    invoice: Invoice,
    amount_cents: int,
    payment_method: str,
    payment_reference: str,
    milestone_position: int | None = None,
    paid_at: datetime | None = None,
    actor_type: str = "operator",
    actor_id: str | None = None,
) -> dict:
    """Record payment against an invoice. Creates a Payment row with
    provider='invoice' and fires activate_client_from_payment, so
    the Client + IntakeRequest + cascade fire exactly like a Stripe
    webhook would. Idempotent on provider+provider_event_id.

    If ``milestone_position`` is given, marks only that milestone
    paid; if None, marks the whole invoice + all pending milestones.

    Returns:
      {"triggered": bool, "reason" | None, "payment_id", "client_id"?,
       "invoice_status", "milestone_status"?}
    """
    if payment_method not in VALID_PAYMENT_METHODS:
        raise ValueError(
            f"payment_method must be one of {VALID_PAYMENT_METHODS}"
        )
    if amount_cents <= 0:
        raise ValueError("amount_cents must be positive")
    if invoice.status == "void":
        return {
            "triggered": False,
            "reason": "invoice_void",
            "payment_id": None,
        }

    now = paid_at or datetime.now(timezone.utc)

    # Build the provider_event_id so idempotence catches repeat calls
    if milestone_position is not None:
        event_id = f"invoice:{invoice.id}:ms:{milestone_position}"
    else:
        event_id = f"invoice:{invoice.id}"

    # Idempotence check on Payment table
    existing = (
        await db.execute(
            select(Payment).where(
                Payment.provider == "invoice",
                Payment.provider_event_id == event_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return {
            "triggered": False,
            "reason": "already_paid",
            "payment_id": str(existing.id),
            "invoice_status": invoice.status,
        }

    # Resolve the milestone if specified
    target_ms: InvoiceMilestone | None = None
    if milestone_position is not None:
        target_ms = (
            await db.execute(
                select(InvoiceMilestone).where(
                    InvoiceMilestone.invoice_id == invoice.id,
                    InvoiceMilestone.position == milestone_position,
                )
            )
        ).scalar_one_or_none()
        if target_ms is None:
            raise ValueError(
                f"Invoice has no milestone at position {milestone_position}"
            )
        if target_ms.status == "paid":
            return {
                "triggered": False,
                "reason": "milestone_already_paid",
                "milestone_status": "paid",
            }

    # Create the canonical Payment row
    payment = Payment(
        org_id=invoice.org_id,
        brand_id=invoice.brand_id,
        proposal_id=invoice.proposal_id,
        provider="invoice",
        provider_event_id=event_id,
        amount_cents=amount_cents,
        currency=invoice.currency,
        status="succeeded",
        completed_at=now,
        customer_email=(invoice.recipient_email or "")[:255],
        customer_name=(invoice.recipient_name or "")[:255],
        raw_event_json={
            "invoice_id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
            "payment_method": payment_method,
            "payment_reference": payment_reference,
            "milestone_position": milestone_position,
        },
        metadata_json={
            "proposal_id": str(invoice.proposal_id) if invoice.proposal_id else None,
            "avenue": invoice.avenue_slug,
            "source": "invoice",
        },
        avenue_slug=invoice.avenue_slug,
    )
    db.add(payment)
    await db.flush()

    # Flip invoice/milestone status
    if target_ms is not None:
        target_ms.status = "paid"
        target_ms.paid_at = now
        target_ms.payment_reference = payment_reference
        # If every milestone is now paid, flip the invoice too
        pending = (
            await db.execute(
                select(func.count(InvoiceMilestone.id)).where(
                    InvoiceMilestone.invoice_id == invoice.id,
                    InvoiceMilestone.status == "pending",
                    InvoiceMilestone.is_active.is_(True),
                )
            )
        ).scalar() or 0
        if pending == 0:
            invoice.status = "paid"
            invoice.paid_at = now
            invoice.payment_method = payment_method
            invoice.payment_reference = payment_reference
    else:
        # Full-amount payment — flip invoice + all pending milestones
        invoice.status = "paid"
        invoice.paid_at = now
        invoice.payment_method = payment_method
        invoice.payment_reference = payment_reference
        await db.execute(
            InvoiceMilestone.__table__.update().where(
                (InvoiceMilestone.invoice_id == invoice.id) &
                (InvoiceMilestone.status == "pending")
            ).values(status="paid", paid_at=now,
                      payment_reference=payment_reference)
        )

    # Flip the proposal to paid (same as the Stripe path does)
    if invoice.proposal_id is not None:
        prop = (
            await db.execute(
                select(Proposal).where(Proposal.id == invoice.proposal_id)
            )
        ).scalar_one_or_none()
        if prop is not None and prop.status not in ("paid", "accepted"):
            prop.status = "paid"
            prop.paid_at = now
            prop.dunning_status = "paid"

    await db.flush()

    # Activate the Client using the canonical Batch 9 path.
    client = None
    if invoice.status == "paid":
        try:
            from apps.api.services.client_activation import (
                activate_client_from_payment,
            )
            client_tuple = await activate_client_from_payment(db, payment=payment)
            # Returns (client, is_new, intake_request)
            if client_tuple and client_tuple[0] is not None:
                client = client_tuple[0]
                invoice.client_id = client.id
                await db.flush()
        except Exception as act_exc:
            logger.warning(
                "invoice.client_activation_failed",
                invoice_id=str(invoice.id),
                error=str(act_exc)[:200],
            )

    await emit_event(
        db,
        domain="monetization",
        event_type="invoice.paid",
        summary=(
            f"Invoice {invoice.invoice_number} paid: "
            f"${amount_cents/100:,.2f} via {payment_method}"
        ),
        org_id=invoice.org_id,
        brand_id=invoice.brand_id,
        entity_type="invoice",
        entity_id=invoice.id,
        new_state="paid",
        actor_type=actor_type,
        actor_id=actor_id,
        details={
            "invoice_id": str(invoice.id),
            "payment_id": str(payment.id),
            "amount_cents": amount_cents,
            "payment_method": payment_method,
            "payment_reference": payment_reference,
            "milestone_position": milestone_position,
            "client_id": str(client.id) if client else None,
            "avenue_slug": invoice.avenue_slug,
        },
    )
    logger.info(
        "invoice.paid",
        invoice_id=str(invoice.id),
        payment_id=str(payment.id),
        amount_cents=amount_cents,
    )
    return {
        "triggered": True,
        "payment_id": str(payment.id),
        "client_id": str(client.id) if client else None,
        "invoice_status": invoice.status,
        "milestone_status": target_ms.status if target_ms else None,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  void_invoice
# ═══════════════════════════════════════════════════════════════════════════


async def void_invoice(
    db: AsyncSession,
    *,
    invoice: Invoice,
    reason: str,
    actor_type: str = "operator",
    actor_id: str | None = None,
) -> dict:
    if invoice.status == "paid":
        raise ValueError("Cannot void a paid invoice")
    if invoice.status == "void":
        return {"triggered": False, "reason": "already_void"}

    prior = invoice.status
    invoice.status = "void"
    # Void all pending milestones too
    await db.execute(
        InvoiceMilestone.__table__.update().where(
            (InvoiceMilestone.invoice_id == invoice.id) &
            (InvoiceMilestone.status == "pending")
        ).values(status="void")
    )
    await db.flush()

    await emit_event(
        db,
        domain="monetization",
        event_type="invoice.voided",
        summary=f"Invoice {invoice.invoice_number} voided: {reason}",
        org_id=invoice.org_id,
        brand_id=invoice.brand_id,
        entity_type="invoice",
        entity_id=invoice.id,
        previous_state=prior,
        new_state="void",
        actor_type=actor_type,
        actor_id=actor_id,
        details={
            "invoice_id": str(invoice.id),
            "reason": reason,
        },
    )
    return {
        "triggered": True,
        "invoice_status": "void",
        "previous_status": prior,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  mark_overdue + scan_overdue_invoices (beat task entry)
# ═══════════════════════════════════════════════════════════════════════════


async def scan_overdue_invoices(db: AsyncSession) -> dict:
    """Beat task — flip status='sent' invoices with due_date < now to
    'overdue' and open a GMEscalation so GM surfaces them.
    """
    from packages.db.models.gm_control import GMEscalation

    now = datetime.now(timezone.utc)
    rows = (
        await db.execute(
            select(Invoice).where(
                Invoice.status == "sent",
                Invoice.due_date.isnot(None),
                Invoice.due_date < now,
                Invoice.is_active.is_(True),
            ).limit(200)
        )
    ).scalars().all()

    flipped = 0
    for inv in rows:
        inv.status = "overdue"
        # Check if an escalation already exists
        existing = (
            await db.execute(
                select(GMEscalation).where(
                    GMEscalation.entity_type == "invoice",
                    GMEscalation.entity_id == inv.id,
                    GMEscalation.reason_code == "invoice_overdue",
                    GMEscalation.status == "open",
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(GMEscalation(
                org_id=inv.org_id,
                reason_code="invoice_overdue",
                entity_type="invoice",
                entity_id=inv.id,
                title=f"Invoice overdue: {inv.invoice_number} (${inv.total_cents/100:,.2f})",
                description=(
                    f"Invoice {inv.invoice_number} to "
                    f"{inv.recipient_email} is past due date "
                    f"({inv.due_date.isoformat() if inv.due_date else '?'}). "
                    "Decide: chase / negotiate / void."
                ),
                severity="warning",
                status="open",
                details_json={
                    "invoice_id": str(inv.id),
                    "invoice_number": inv.invoice_number,
                    "total_cents": inv.total_cents,
                    "recipient_email": inv.recipient_email,
                    "avenue_slug": inv.avenue_slug,
                },
            ))
        flipped += 1

    await db.commit()
    logger.info("invoice.overdue_scan_complete", flipped=flipped)
    return {"scanned": len(rows), "flipped_to_overdue": flipped}
