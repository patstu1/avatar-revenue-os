"""Retention / renewal / reactivation (Batch 11).

Closes the ninth stage of the full-circle: once a Client pays + gets
onboarded + receives a delivery (Batches 9+10 infrastructure), this
layer owns what happens next — renewal cycles, reactivation of
lapsed clients, upsell offers at delivery-time, and the graceful
cancellation path.

Three detectors (beat task uses these):
    detect_renewal_due      → clients whose next_renewal_at <= now
    detect_reactivation_candidates → lapsed clients not already chased
    detect_expansion_candidates    → completed-delivery clients ripe
                                      for upsell

Four triggers (GM write endpoints wrap these):
    trigger_renewal(client, package, line_items)
    trigger_reactivation(client, template)
    trigger_upsell(client, package, line_items)
    cancel_subscription(client, reason)

One state scanner:
    scan_retention_state(client) → recomputes retention_state +
                                    next_renewal_at + churn_risk_score
    scan_all_retention_states()  → scanner entry point for the beat

Idempotence rules:
  - trigger_renewal is debounced by a 24h guard on
    client_retention_events (event_type='renewal_triggered').
  - trigger_reactivation is debounced by 14d.
  - trigger_upsell is debounced by 7d (one upsell offer per week max
    per client).
  - cancel_subscription is one-shot — subsequent calls return the
    existing ClientRetentionEvent.

Every trigger writes exactly one ClientRetentionEvent + emits one
``client.retention.<event>`` SystemEvent. Proposals created by
renew/upsell carry ``extra_json.retention_source='renewal'|'upsell'``
so downstream queries can tell a first-cycle sale apart from a
renewal.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_event
from apps.api.services.test_record_guard import is_test_or_synthetic_email
from packages.db.models.clients import (
    Client,
    ClientRetentionEvent,
)
from packages.db.models.fulfillment import ClientProject

logger = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════════════
#  Recurring-package catalog (used by client_activation to populate
#  is_recurring + recurring_period_days at client creation).
# ═══════════════════════════════════════════════════════════════════════════

# Map package_slug → recurring_period_days. Anything not in this dict
# is treated as one-time; retention scanner ignores non-recurring
# clients for renewal detection but still evaluates reactivation /
# expansion candidacy.
RECURRING_PACKAGE_PERIOD: dict[str, int] = {
    # ProofHook recurring SKUs
    "momentum_engine": 30,
    "paid_media_engine": 30,
    "creative_command": 30,
    # Common UGC retainer shapes
    "ugc_monthly": 30,
    "ugc_quarterly": 90,
    # B2B retainers
    "b2b_retainer_monthly": 30,
    "b2b_retainer_quarterly": 90,
    # Consulting retainers
    "consulting_monthly": 30,
    # Premium/membership
    "premium_access_monthly": 30,
    "premium_access_annual": 365,
    "saas_monthly": 30,
    "saas_annual": 365,
}


def recurring_period_for_package(package_slug: str | None) -> int | None:
    """Return the recurring period (days) for a package_slug, or None
    if the package is one-time.

    Called by client_activation.activate_client_from_payment so the
    retention scanner can key renewal detection on is_recurring alone.
    """
    if not package_slug:
        return None
    return RECURRING_PACKAGE_PERIOD.get(package_slug.lower())


# ═══════════════════════════════════════════════════════════════════════════
#  State evaluation
# ═══════════════════════════════════════════════════════════════════════════


LAPSED_DAYS_THRESHOLD = 60  # no-payment + no-activity cutoff
EXPANSION_CANDIDATE_MIN_PROJECTS = 1  # any completed project makes a
# one-time client an expansion target

RETENTION_STATES = (
    "active",
    "renewal_due",
    "renewal_overdue",
    "lapsed",
    "churned",
    "expansion_candidate",
)


async def scan_retention_state(db: AsyncSession, client: Client) -> dict:
    """Recompute retention_state for one client. Writes the updated
    fields on the client row and returns the evaluation summary.

    State transition logic:
      - churned stays churned (operator-set terminal state)
      - is_recurring + last_paid_at present:
          now < next_renewal_at - 3d   → active
          next_renewal_at - 3d <= now  → renewal_due
          next_renewal_at + 7d < now   → renewal_overdue
          next_renewal_at + 30d < now  → lapsed
      - not recurring + last_paid_at present:
          last_paid_at + LAPSED_DAYS_THRESHOLD > now → active
                 + has completed delivery           → expansion_candidate
          last_paid_at + LAPSED_DAYS_THRESHOLD <= now → lapsed
    """
    now = datetime.now(timezone.utc)

    # Churned is terminal — never re-evaluate.
    if client.retention_state == "churned":
        client.last_retention_check_at = now
        await db.flush()
        return {
            "client_id": str(client.id),
            "state": "churned",
            "terminal": True,
            "churn_risk_score": client.churn_risk_score or 0.0,
        }

    prior_state = client.retention_state or "active"
    new_state = prior_state
    risk = 0.0

    lpa = client.last_paid_at

    if client.is_recurring and lpa and client.recurring_period_days:
        period = client.recurring_period_days
        next_renewal = lpa + timedelta(days=period)
        client.next_renewal_at = next_renewal

        lead_window = next_renewal - timedelta(days=3)
        overdue_cutoff = next_renewal + timedelta(days=7)
        lapsed_cutoff = next_renewal + timedelta(days=30)

        if now < lead_window:
            new_state = "active"
            risk = 0.05
        elif now < overdue_cutoff:
            new_state = "renewal_due"
            risk = 0.25
        elif now < lapsed_cutoff:
            new_state = "renewal_overdue"
            risk = 0.55
        else:
            new_state = "lapsed"
            risk = 0.85

    elif lpa is not None:
        # one-time client — check lapse + expansion
        days_since_paid = (now - lpa).days
        if days_since_paid < LAPSED_DAYS_THRESHOLD:
            # Expansion-candidate if they have at least one completed project.
            q = (
                select(ClientProject)
                .where(
                    ClientProject.client_id == client.id,
                    ClientProject.status == "completed",
                )
                .limit(EXPANSION_CANDIDATE_MIN_PROJECTS)
            )
            has_completed = (await db.execute(q)).first() is not None
            new_state = "expansion_candidate" if has_completed else "active"
            risk = 0.15 if has_completed else 0.05
        else:
            new_state = "lapsed"
            risk = 0.70

    else:
        # No last_paid_at (e.g. onboarded but payment not captured) —
        # leave as active; retention doesn't fire on never-paid clients.
        new_state = "active"
        risk = 0.10

    client.retention_state = new_state
    client.churn_risk_score = risk
    client.last_retention_check_at = now
    await db.flush()

    if new_state != prior_state:
        db.add(
            ClientRetentionEvent(
                org_id=client.org_id,
                client_id=client.id,
                avenue_slug=client.avenue_slug,
                event_type="state_evaluated",
                previous_state=prior_state,
                new_state=new_state,
                triggered_by_actor_type="system",
                triggered_by_actor_id="retention_service.scan",
                details_json={
                    "churn_risk_score": risk,
                    "next_renewal_at": (client.next_renewal_at.isoformat() if client.next_renewal_at else None),
                },
            )
        )
        await emit_event(
            db,
            domain="fulfillment",
            event_type="client.retention_state.changed",
            summary=(f"Client {client.display_name or client.primary_email} {prior_state} → {new_state}"),
            org_id=client.org_id,
            brand_id=client.brand_id,
            entity_type="client",
            entity_id=client.id,
            previous_state=prior_state,
            new_state=new_state,
            actor_type="system",
            actor_id="retention_service.scan",
            details={
                "client_id": str(client.id),
                "avenue_slug": client.avenue_slug,
                "churn_risk_score": risk,
            },
        )
        await db.flush()

    return {
        "client_id": str(client.id),
        "previous_state": prior_state,
        "state": new_state,
        "churn_risk_score": risk,
        "next_renewal_at": (client.next_renewal_at.isoformat() if client.next_renewal_at else None),
    }


async def scan_all_retention_states(
    db: AsyncSession,
    *,
    org_id: uuid.UUID | None = None,
    limit: int = 500,
) -> dict:
    """Beat-task entry — evaluate every active client (optionally
    scoped to one org) and return a summary."""
    q = select(Client).where(Client.is_active.is_(True))
    if org_id is not None:
        q = q.where(Client.org_id == org_id)
    q = q.limit(limit)
    clients = (await db.execute(q)).scalars().all()

    scanned = len(clients)
    changed = 0
    per_state: dict[str, int] = {s: 0 for s in RETENTION_STATES}
    for c in clients:
        r = await scan_retention_state(db, c)
        if r.get("previous_state") and r["previous_state"] != r["state"]:
            changed += 1
        per_state[r["state"]] = per_state.get(r["state"], 0) + 1

    summary = {
        "scanned": scanned,
        "state_changed": changed,
        "per_state": per_state,
    }
    logger.info("retention.scan_complete", **summary)
    return summary


# ═══════════════════════════════════════════════════════════════════════════
#  Detectors (query-only helpers used by beat + GM read layer)
# ═══════════════════════════════════════════════════════════════════════════


async def detect_renewal_due(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    limit: int = 100,
) -> list[Client]:
    q = (
        select(Client)
        .where(
            Client.org_id == org_id,
            Client.is_active.is_(True),
            Client.retention_state.in_(("renewal_due", "renewal_overdue")),
        )
        .order_by(Client.next_renewal_at.asc())
        .limit(limit)
    )
    candidates = list((await db.execute(q)).scalars().all())

    # ── Live-payment safety guard ──────────────────────────────────────────
    # Filter out test / synthetic / fixture clients before returning so
    # that no caller can accidentally reach Stripe or send email to a
    # non-real address.  Logged at warning level so the exclusion is
    # always visible in the task log without being noisy on normal runs.
    safe: list[Client] = []
    for c in candidates:
        if is_test_or_synthetic_email(c.primary_email or ""):
            logger.warning(
                "detect_renewal_due.blocked_test_record",
                client_id=str(c.id),
                email=c.primary_email,
                reason="email matched test_record_guard pattern",
            )
        else:
            safe.append(c)
    return safe


async def detect_reactivation_candidates(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    limit: int = 100,
) -> list[Client]:
    q = (
        select(Client)
        .where(
            Client.org_id == org_id,
            Client.is_active.is_(True),
            Client.retention_state == "lapsed",
        )
        .order_by(Client.last_paid_at.asc())
        .limit(limit)
    )
    return list((await db.execute(q)).scalars().all())


async def detect_expansion_candidates(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    limit: int = 100,
) -> list[Client]:
    q = (
        select(Client)
        .where(
            Client.org_id == org_id,
            Client.is_active.is_(True),
            Client.retention_state == "expansion_candidate",
        )
        .order_by(Client.total_paid_cents.desc())
        .limit(limit)
    )
    return list((await db.execute(q)).scalars().all())


# ═══════════════════════════════════════════════════════════════════════════
#  Idempotence helper — used by triggers to debounce
# ═══════════════════════════════════════════════════════════════════════════


async def _recent_retention_event(
    db: AsyncSession,
    *,
    client_id: uuid.UUID,
    event_type: str,
    within_hours: int,
) -> ClientRetentionEvent | None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=within_hours)
    q = (
        select(ClientRetentionEvent)
        .where(
            ClientRetentionEvent.client_id == client_id,
            ClientRetentionEvent.event_type == event_type,
            ClientRetentionEvent.created_at >= cutoff,
            ClientRetentionEvent.is_active.is_(True),
        )
        .order_by(ClientRetentionEvent.created_at.desc())
        .limit(1)
    )
    return (await db.execute(q)).scalar_one_or_none()


# ═══════════════════════════════════════════════════════════════════════════
#  Triggers
# ═══════════════════════════════════════════════════════════════════════════


async def trigger_renewal(
    db: AsyncSession,
    *,
    client: Client,
    package_slug: str,
    line_items: list[dict],
    title: str | None = None,
    notes: str | None = None,
    actor_type: str = "operator",
    actor_id: str | None = None,
    force: bool = False,
) -> dict:
    """Trigger a renewal cycle for a recurring client by creating the
    next Proposal. Debounced 24h unless force=True.

    Returns {"triggered": bool, "retention_event_id", "proposal_id",
             "reason": str | None}.
    """
    if not force:
        recent = await _recent_retention_event(
            db,
            client_id=client.id,
            event_type="renewal_triggered",
            within_hours=24,
        )
        if recent is not None:
            return {
                "triggered": False,
                "reason": "debounce_24h",
                "retention_event_id": str(recent.id),
                "proposal_id": (str(recent.target_proposal_id) if recent.target_proposal_id else None),
            }

    from apps.api.services.proposals_service import (
        LineItemInput,
        create_proposal,
    )

    li_inputs = [
        LineItemInput(
            description=str(li.get("description", ""))[:500],
            unit_amount_cents=int(li.get("unit_amount_cents", 0)),
            quantity=int(li.get("quantity", 1)),
            offer_id=li.get("offer_id"),
            package_slug=li.get("package_slug") or package_slug,
            currency=str(li.get("currency", "usd")),
            position=int(li.get("position", i)),
        )
        for i, li in enumerate(line_items)
    ]
    if not li_inputs:
        raise ValueError("trigger_renewal requires at least one line item")

    proposal = await create_proposal(
        db,
        org_id=client.org_id,
        brand_id=client.brand_id,
        recipient_email=client.primary_email,
        recipient_name=client.display_name or "",
        recipient_company=client.company_name or "",
        title=title or f"Renewal — {client.display_name or client.primary_email}",
        summary=f"Recurring renewal on {package_slug}",
        package_slug=package_slug,
        avenue_slug=client.avenue_slug,
        line_items=li_inputs,
        notes=notes,
        created_by_actor_type=actor_type,
        created_by_actor_id=actor_id,
        extra_json={
            "retention_source": "renewal",
            "source_client_id": str(client.id),
            "source_first_proposal_id": (str(client.first_proposal_id) if client.first_proposal_id else None),
        },
    )

    evt = ClientRetentionEvent(
        org_id=client.org_id,
        client_id=client.id,
        avenue_slug=client.avenue_slug,
        event_type="renewal_triggered",
        previous_state=client.retention_state,
        new_state=client.retention_state,
        triggered_by_actor_type=actor_type,
        triggered_by_actor_id=actor_id,
        source_proposal_id=client.first_proposal_id,
        target_proposal_id=proposal.id,
        details_json={
            "package_slug": package_slug,
            "total_amount_cents": proposal.total_amount_cents,
            "avenue_slug": client.avenue_slug,
        },
    )
    db.add(evt)
    await db.flush()

    await emit_event(
        db,
        domain="fulfillment",
        event_type="client.retention.renewal_triggered",
        summary=(
            f"Renewal proposal created for {client.display_name or client.primary_email}: "
            f"${proposal.total_amount_cents / 100:,.2f}"
        ),
        org_id=client.org_id,
        brand_id=client.brand_id,
        entity_type="client",
        entity_id=client.id,
        actor_type=actor_type,
        actor_id=actor_id,
        details={
            "client_id": str(client.id),
            "proposal_id": str(proposal.id),
            "avenue_slug": client.avenue_slug,
            "package_slug": package_slug,
            "retention_event_id": str(evt.id),
        },
    )
    logger.info(
        "retention.renewal_triggered",
        client_id=str(client.id),
        proposal_id=str(proposal.id),
        avenue_slug=client.avenue_slug,
    )
    return {
        "triggered": True,
        "retention_event_id": str(evt.id),
        "proposal_id": str(proposal.id),
        "total_amount_cents": proposal.total_amount_cents,
        "avenue_slug": client.avenue_slug,
    }


async def trigger_reactivation(
    db: AsyncSession,
    *,
    client: Client,
    template_slug: str = "reactivation_default_v1",
    subject_override: str | None = None,
    body_override: str | None = None,
    notes: str | None = None,
    actor_type: str = "operator",
    actor_id: str | None = None,
    force: bool = False,
) -> dict:
    """Send a reactivation email to a lapsed client. Debounced 14d
    unless force=True."""
    if not force:
        recent = await _recent_retention_event(
            db,
            client_id=client.id,
            event_type="reactivation_sent",
            within_hours=24 * 14,
        )
        if recent is not None:
            return {
                "triggered": False,
                "reason": "debounce_14d",
                "retention_event_id": str(recent.id),
                "sent": False,
            }

    from packages.clients.external_clients import SmtpEmailClient

    subject = (
        subject_override
        or f"Checking in — anything we can help with, {(client.display_name or '').split(' ')[0] or 'there'}?"
    )
    body_text = body_override or (
        f"Hi {(client.display_name or client.primary_email).split(' ')[0] or 'there'},\n\n"
        f"It's been a while since we worked together. Wanted to reach out and see "
        f"if anything's changed on your side that we could help with.\n\n"
        f"If now's a good moment, reply here and I'll send a current options page. "
        f"If not, no problem — just wanted to keep the door open."
    )

    smtp = await SmtpEmailClient.from_db(db, client.org_id)
    send_result: dict
    if smtp is None:
        send_result = {"success": False, "error": "no_smtp_configured", "provider": None}
    else:
        send_result = await smtp.send_email(
            to_email=client.primary_email,
            subject=subject,
            body_text=body_text,
            body_html=f"<p>{body_text.replace(chr(10), '<br>')}</p>",
        )

    evt = ClientRetentionEvent(
        org_id=client.org_id,
        client_id=client.id,
        avenue_slug=client.avenue_slug,
        event_type="reactivation_sent",
        previous_state=client.retention_state,
        new_state=client.retention_state,
        triggered_by_actor_type=actor_type,
        triggered_by_actor_id=actor_id,
        details_json={
            "template_slug": template_slug,
            "subject": subject,
            "notes": notes,
            "send_success": bool(send_result.get("success")),
            "send_error": send_result.get("error"),
            "provider": send_result.get("provider"),
        },
    )
    db.add(evt)
    await db.flush()

    await emit_event(
        db,
        domain="fulfillment",
        event_type="client.retention.reactivation_sent",
        summary=(
            f"Reactivation email {'sent' if send_result.get('success') else 'attempted'} "
            f"for {client.display_name or client.primary_email}"
        ),
        org_id=client.org_id,
        brand_id=client.brand_id,
        entity_type="client",
        entity_id=client.id,
        actor_type=actor_type,
        actor_id=actor_id,
        severity="info" if send_result.get("success") else "warning",
        details={
            "client_id": str(client.id),
            "avenue_slug": client.avenue_slug,
            "send_success": bool(send_result.get("success")),
            "send_error": send_result.get("error"),
            "retention_event_id": str(evt.id),
        },
    )
    logger.info(
        "retention.reactivation_sent",
        client_id=str(client.id),
        success=bool(send_result.get("success")),
    )
    return {
        "triggered": True,
        "sent": bool(send_result.get("success")),
        "retention_event_id": str(evt.id),
        "error": send_result.get("error"),
        "provider": send_result.get("provider"),
    }


async def trigger_upsell(
    db: AsyncSession,
    *,
    client: Client,
    package_slug: str,
    line_items: list[dict],
    title: str | None = None,
    notes: str | None = None,
    actor_type: str = "operator",
    actor_id: str | None = None,
    force: bool = False,
) -> dict:
    """Offer an upsell to an expansion-candidate or active client by
    creating a new Proposal with a (typically larger) package. Debounced
    7d unless force=True."""
    if not force:
        recent = await _recent_retention_event(
            db,
            client_id=client.id,
            event_type="upsell_offered",
            within_hours=24 * 7,
        )
        if recent is not None:
            return {
                "triggered": False,
                "reason": "debounce_7d",
                "retention_event_id": str(recent.id),
                "proposal_id": (str(recent.target_proposal_id) if recent.target_proposal_id else None),
            }

    from apps.api.services.proposals_service import (
        LineItemInput,
        create_proposal,
    )

    li_inputs = [
        LineItemInput(
            description=str(li.get("description", ""))[:500],
            unit_amount_cents=int(li.get("unit_amount_cents", 0)),
            quantity=int(li.get("quantity", 1)),
            offer_id=li.get("offer_id"),
            package_slug=li.get("package_slug") or package_slug,
            currency=str(li.get("currency", "usd")),
            position=int(li.get("position", i)),
        )
        for i, li in enumerate(line_items)
    ]
    if not li_inputs:
        raise ValueError("trigger_upsell requires at least one line item")

    proposal = await create_proposal(
        db,
        org_id=client.org_id,
        brand_id=client.brand_id,
        recipient_email=client.primary_email,
        recipient_name=client.display_name or "",
        recipient_company=client.company_name or "",
        title=title or f"Expansion — {client.display_name or client.primary_email}",
        summary=f"Upsell offer: {package_slug}",
        package_slug=package_slug,
        avenue_slug=client.avenue_slug,
        line_items=li_inputs,
        notes=notes,
        created_by_actor_type=actor_type,
        created_by_actor_id=actor_id,
        extra_json={
            "retention_source": "upsell",
            "source_client_id": str(client.id),
            "source_first_proposal_id": (str(client.first_proposal_id) if client.first_proposal_id else None),
        },
    )

    evt = ClientRetentionEvent(
        org_id=client.org_id,
        client_id=client.id,
        avenue_slug=client.avenue_slug,
        event_type="upsell_offered",
        previous_state=client.retention_state,
        new_state=client.retention_state,
        triggered_by_actor_type=actor_type,
        triggered_by_actor_id=actor_id,
        source_proposal_id=client.first_proposal_id,
        target_proposal_id=proposal.id,
        details_json={
            "package_slug": package_slug,
            "total_amount_cents": proposal.total_amount_cents,
            "avenue_slug": client.avenue_slug,
        },
    )
    db.add(evt)
    await db.flush()

    await emit_event(
        db,
        domain="fulfillment",
        event_type="client.retention.upsell_offered",
        summary=(
            f"Upsell proposal for {client.display_name or client.primary_email}: "
            f"${proposal.total_amount_cents / 100:,.2f}"
        ),
        org_id=client.org_id,
        brand_id=client.brand_id,
        entity_type="client",
        entity_id=client.id,
        actor_type=actor_type,
        actor_id=actor_id,
        details={
            "client_id": str(client.id),
            "proposal_id": str(proposal.id),
            "avenue_slug": client.avenue_slug,
            "package_slug": package_slug,
            "retention_event_id": str(evt.id),
        },
    )
    logger.info(
        "retention.upsell_offered",
        client_id=str(client.id),
        proposal_id=str(proposal.id),
        avenue_slug=client.avenue_slug,
    )
    return {
        "triggered": True,
        "retention_event_id": str(evt.id),
        "proposal_id": str(proposal.id),
        "total_amount_cents": proposal.total_amount_cents,
        "avenue_slug": client.avenue_slug,
    }


async def cancel_subscription(
    db: AsyncSession,
    *,
    client: Client,
    reason: str,
    effective_at: datetime | None = None,
    notes: str | None = None,
    actor_type: str = "operator",
    actor_id: str | None = None,
) -> dict:
    """Cancel a client's recurring relationship. Terminal — flips
    retention_state to 'churned' and is_recurring to False. Idempotent
    (returns the existing event if already cancelled).
    """
    if client.retention_state == "churned":
        existing = await _recent_retention_event(
            db,
            client_id=client.id,
            event_type="subscription_cancelled",
            within_hours=24 * 365,
        )
        return {
            "triggered": False,
            "reason": "already_churned",
            "retention_event_id": (str(existing.id) if existing is not None else None),
        }

    prior_state = client.retention_state
    client.retention_state = "churned"
    client.is_recurring = False
    client.next_renewal_at = None
    client.last_retention_check_at = datetime.now(timezone.utc)
    await db.flush()

    evt = ClientRetentionEvent(
        org_id=client.org_id,
        client_id=client.id,
        avenue_slug=client.avenue_slug,
        event_type="subscription_cancelled",
        previous_state=prior_state,
        new_state="churned",
        triggered_by_actor_type=actor_type,
        triggered_by_actor_id=actor_id,
        details_json={
            "reason": reason,
            "effective_at": (effective_at.isoformat() if effective_at else None),
            "notes": notes,
        },
    )
    db.add(evt)
    await db.flush()

    await emit_event(
        db,
        domain="fulfillment",
        event_type="client.retention.subscription_cancelled",
        summary=(f"Subscription cancelled for {client.display_name or client.primary_email}: {reason}"),
        org_id=client.org_id,
        brand_id=client.brand_id,
        entity_type="client",
        entity_id=client.id,
        previous_state=prior_state,
        new_state="churned",
        actor_type=actor_type,
        actor_id=actor_id,
        details={
            "client_id": str(client.id),
            "avenue_slug": client.avenue_slug,
            "reason": reason,
            "retention_event_id": str(evt.id),
        },
    )
    logger.info(
        "retention.subscription_cancelled",
        client_id=str(client.id),
        reason=reason,
    )
    return {
        "triggered": True,
        "retention_event_id": str(evt.id),
        "previous_state": prior_state,
        "new_state": "churned",
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Rollup for GM read layer (§6 of the scope)
# ═══════════════════════════════════════════════════════════════════════════


async def compute_retention_book(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
) -> dict:
    """Per-avenue rollup of retention states for the GM dashboard.

    Returns ``{by_avenue: {avenue_slug: {state: count, ...}, ...},
              totals: {state: count}}``.
    """
    from sqlalchemy import func

    q = (
        select(
            Client.avenue_slug,
            Client.retention_state,
            func.count(Client.id).label("n"),
        )
        .where(
            Client.org_id == org_id,
            Client.is_active.is_(True),
        )
        .group_by(Client.avenue_slug, Client.retention_state)
    )
    rows = (await db.execute(q)).all()

    by_avenue: dict[str, dict[str, int]] = {}
    totals: dict[str, int] = {s: 0 for s in RETENTION_STATES}
    for avenue_slug, state, n in rows:
        key = avenue_slug or "_unattributed"
        by_avenue.setdefault(key, {s: 0 for s in RETENTION_STATES})
        by_avenue[key][state] = (by_avenue[key].get(state) or 0) + int(n)
        totals[state] = totals.get(state, 0) + int(n)

    return {"by_avenue": by_avenue, "totals": totals}
