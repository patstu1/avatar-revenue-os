"""Client activation + onboarding orchestration (Batch 3B).

Bridges the conversion backbone (``Payment``) to the fulfillment
backbone (``Client`` + ``IntakeRequest`` + ``IntakeSubmission``).

Fires the canonical events:
  - ``client.created``       (first payment from a given email)
  - ``onboarding.started``   (intake request created for the client)
  - ``intake.sent``          (intake request status → sent)
  - ``intake.completed``     (intake submission persisted with
                              is_complete=True)
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_event
from packages.db.models.clients import (
    Client,
    ClientOnboardingEvent,
    IntakeRequest,
    IntakeSubmission,
)
from packages.db.models.proposals import Payment, Proposal

logger = structlog.get_logger()

DEFAULT_INTAKE_SCHEMA = {
    "fields": [
        {"field_id": "company_name", "label": "Company / brand name", "type": "text", "required": True},
        {"field_id": "primary_contact", "label": "Primary point of contact", "type": "text", "required": True},
        {"field_id": "target_audience", "label": "Who are you selling to?", "type": "textarea", "required": True},
        {"field_id": "brand_voice", "label": "Describe your brand voice", "type": "textarea", "required": False},
        {"field_id": "assets_url", "label": "Link to brand assets (logo, colors, fonts)", "type": "text", "required": False},
        {"field_id": "goals", "label": "What are you trying to achieve?", "type": "textarea", "required": True},
        {"field_id": "start_date_pref", "label": "Preferred start date", "type": "text", "required": False},
    ],
}


# ═══════════════════════════════════════════════════════════════════════════
#  Entry points
# ═══════════════════════════════════════════════════════════════════════════


async def activate_client_from_payment(
    db: AsyncSession,
    *,
    payment: Payment,
) -> tuple[Client, bool, Optional[IntakeRequest]]:
    """Create (or reuse) the Client for this payment and auto-start onboarding.

    Returns ``(client, is_new_client, intake_request)``.

    Idempotent: if a Client already exists for (org_id, primary_email),
    it is reused and its total_paid_cents/last_paid_at are updated, but
    neither the ``client.created`` event nor a duplicate IntakeRequest
    is created.
    """
    recipient_email = (payment.customer_email or "").strip().lower()
    if not recipient_email:
        recipient_email = await _recover_email_from_proposal(db, payment.proposal_id)

    if not recipient_email:
        logger.warning(
            "client_activation.no_email",
            payment_id=str(payment.id),
            reason="no customer_email on payment and no proposal.recipient_email",
        )
        return (None, False, None)  # type: ignore

    display_name = (payment.customer_name or "").strip()
    proposal = None
    if payment.proposal_id is not None:
        proposal = (
            await db.execute(select(Proposal).where(Proposal.id == payment.proposal_id))
        ).scalar_one_or_none()
        if proposal is not None:
            display_name = display_name or (proposal.recipient_name or "")

    display_name = display_name or recipient_email.split("@", 1)[0]

    existing = (
        await db.execute(
            select(Client).where(
                Client.org_id == payment.org_id,
                Client.primary_email == recipient_email,
            )
        )
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if existing is not None:
        existing.total_paid_cents = (existing.total_paid_cents or 0) + (payment.amount_cents or 0)
        existing.last_paid_at = now
        await db.flush()
        return (existing, False, None)

    # Batch 9: propagate avenue_slug from payment → client (and back-fill
    # from the proposal if Stripe metadata didn't carry it).
    avenue_slug = payment.avenue_slug or (proposal.avenue_slug if proposal else None)

    # Batch 11: set is_recurring + recurring_period_days from the
    # source proposal's package_slug so the retention scanner can key
    # renewal detection on is_recurring alone.
    from apps.api.services.retention_service import recurring_period_for_package
    src_pkg = proposal.package_slug if proposal else None
    period_days = recurring_period_for_package(src_pkg)

    client = Client(
        org_id=payment.org_id,
        brand_id=payment.brand_id,
        primary_email=recipient_email[:255],
        display_name=display_name[:255],
        company_name=(proposal.recipient_company if proposal else "")[:255],
        first_proposal_id=payment.proposal_id,
        first_payment_id=payment.id,
        status="active",
        activated_at=now,
        last_paid_at=now,
        total_paid_cents=payment.amount_cents or 0,
        avenue_slug=avenue_slug,
        # Batch 11 retention fields
        is_recurring=period_days is not None,
        recurring_period_days=period_days,
        retention_state="active",
    )
    db.add(client)
    await db.flush()

    await emit_event(
        db,
        domain="fulfillment",
        event_type="client.created",
        summary=f"Client activated: {display_name} <{recipient_email}>",
        org_id=client.org_id,
        brand_id=client.brand_id,
        entity_type="client",
        entity_id=client.id,
        new_state="active",
        actor_type="system",
        actor_id="client_activation",
        details={
            "client_id": str(client.id),
            "primary_email": recipient_email,
            "display_name": display_name,
            "proposal_id": str(payment.proposal_id) if payment.proposal_id else None,
            "payment_id": str(payment.id),
            "amount_cents": payment.amount_cents,
        },
    )
    logger.info(
        "client.created",
        client_id=str(client.id),
        org_id=str(client.org_id),
        primary_email=recipient_email,
    )
    try:
        from apps.api.services.stage_controller import mark_stage
        await mark_stage(
            db, org_id=client.org_id,
            entity_type="client", entity_id=client.id, stage="active",
        )
    except Exception as stage_exc:
        logger.warning("stage_controller.mark_failed",
                        entity="client", error=str(stage_exc)[:150])

    intake = await start_onboarding(
        db,
        client=client,
        proposal_id=payment.proposal_id,
        payment_id=payment.id,
    )
    return (client, True, intake)


async def start_onboarding(
    db: AsyncSession,
    *,
    client: Client,
    proposal_id: Optional[uuid.UUID] = None,
    payment_id: Optional[uuid.UUID] = None,
    schema: Optional[dict] = None,
    title: Optional[str] = None,
    instructions: Optional[str] = None,
) -> IntakeRequest:
    """Create the first IntakeRequest for a client and mark it sent.

    Writes:
      - IntakeRequest (status=sent, sent_at=now)
      - ClientOnboardingEvent (event_type=onboarding.started)
      - ClientOnboardingEvent (event_type=intake.sent)

    Emits:
      - onboarding.started
      - intake.sent
    """
    existing = (
        await db.execute(
            select(IntakeRequest).where(
                IntakeRequest.client_id == client.id,
                IntakeRequest.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(24)

    # Batch 12 / Batch 13: avenue-specific intake schema selection.
    # For high_ticket Clients, swap in HIGH_TICKET_INTAKE_SCHEMA (12
    # scoping fields) and create ClientHighTicketProfile.
    # For sponsor_deals Clients, swap in SPONSOR_INTAKE_SCHEMA (12
    # sponsor-scoping fields) and create SponsorCampaign.
    # Other avenues get the 7-field generic default.
    if schema is None and client.avenue_slug == "high_ticket":
        from apps.api.services.high_ticket_onboarding import (
            HIGH_TICKET_INTAKE_SCHEMA, ensure_profile,
        )
        schema_to_use = HIGH_TICKET_INTAKE_SCHEMA
        instructions_to_use = (
            instructions
            or HIGH_TICKET_INTAKE_SCHEMA.get("instructions")
            or "Please complete the following to scope your contract."
        )
        title_to_use = title or (
            f"High-ticket scoping — {client.display_name or client.primary_email}"
        )
        await ensure_profile(db, client=client)
    elif schema is None and client.avenue_slug == "sponsor_deals":
        from apps.api.services.sponsor_onboarding_service import (
            SPONSOR_INTAKE_SCHEMA, ensure_campaign,
        )
        schema_to_use = SPONSOR_INTAKE_SCHEMA
        instructions_to_use = (
            instructions
            or SPONSOR_INTAKE_SCHEMA.get("instructions")
            or "Please complete the following to scope your sponsor campaign."
        )
        title_to_use = title or (
            f"Sponsor campaign scoping — {client.display_name or client.primary_email}"
        )
        await ensure_campaign(db, client=client)
    else:
        schema_to_use = schema or DEFAULT_INTAKE_SCHEMA
        instructions_to_use = (
            instructions or "Please complete the following to kick off production."
        )
        title_to_use = title or f"Intake for {client.display_name}"

    intake = IntakeRequest(
        org_id=client.org_id,
        client_id=client.id,
        proposal_id=proposal_id,
        payment_id=payment_id,
        token=token,
        status="sent",
        title=title_to_use[:500],
        instructions=instructions_to_use,
        schema_json=schema_to_use,
        sent_at=now,
        # Batch 9: carry avenue attribution from the client.
        avenue_slug=client.avenue_slug,
    )
    db.add(intake)
    await db.flush()

    db.add(
        ClientOnboardingEvent(
            client_id=client.id,
            org_id=client.org_id,
            event_type="onboarding.started",
            proposal_id=proposal_id,
            payment_id=payment_id,
            intake_request_id=intake.id,
            details_json={"intake_token": token, "title": intake.title},
            actor_type="system",
            actor_id="client_activation",
        )
    )
    db.add(
        ClientOnboardingEvent(
            client_id=client.id,
            org_id=client.org_id,
            event_type="intake.sent",
            proposal_id=proposal_id,
            payment_id=payment_id,
            intake_request_id=intake.id,
            details_json={"intake_token": token},
            actor_type="system",
            actor_id="client_activation",
        )
    )
    await db.flush()

    await emit_event(
        db,
        domain="fulfillment",
        event_type="onboarding.started",
        summary=f"Onboarding started for {client.display_name}",
        org_id=client.org_id,
        brand_id=client.brand_id,
        entity_type="client",
        entity_id=client.id,
        new_state="onboarding",
        actor_type="system",
        actor_id="client_activation",
        details={
            "client_id": str(client.id),
            "intake_request_id": str(intake.id),
            "intake_token": token,
            "proposal_id": str(proposal_id) if proposal_id else None,
            "payment_id": str(payment_id) if payment_id else None,
        },
    )
    await emit_event(
        db,
        domain="fulfillment",
        event_type="intake.sent",
        summary=f"Intake request sent to {client.primary_email}",
        org_id=client.org_id,
        brand_id=client.brand_id,
        entity_type="intake_request",
        entity_id=intake.id,
        previous_state="pending",
        new_state="sent",
        actor_type="system",
        actor_id="client_activation",
        details={
            "client_id": str(client.id),
            "intake_request_id": str(intake.id),
            "intake_token": token,
            "recipient_email": client.primary_email,
        },
    )
    logger.info(
        "onboarding.started",
        client_id=str(client.id),
        intake_request_id=str(intake.id),
    )
    try:
        from apps.api.services.stage_controller import mark_stage
        await mark_stage(
            db, org_id=intake.org_id,
            entity_type="intake_request", entity_id=intake.id, stage="sent",
        )
    except Exception as stage_exc:
        logger.warning("stage_controller.mark_failed",
                        entity="intake_request", error=str(stage_exc)[:150])

    # Batch 9: actually email the buyer the intake link. Before this,
    # start_onboarding created the IntakeRequest row but sent nothing
    # to the buyer — every paying customer hit a silent wall.
    try:
        await send_intake_invite(db, client=client, intake_request=intake)
    except Exception as email_exc:
        logger.warning(
            "intake.email_send_failed",
            intake_request_id=str(intake.id),
            error=str(email_exc)[:200],
        )


    # Phase 3: analytics_events emission.
    try:
        _b_id = getattr(client, "brand_id", None)
        if _b_id is not None:
            from packages.clients.analytics_emitter import emit_analytics_event
            await emit_analytics_event(
                db, brand_id=_b_id,
                source="client_activation",
                event_type="onboarding.started",
                metric_value=1.0, truth_level="verified",
                raw_json={"client_id": str(client.id),
                          "client_email": getattr(client, "primary_email", None),
                          "intake_request_id": str(intake.id) if intake else None},
            )
            await db.flush()
    except Exception as _aexc:
        import structlog as _sl
        _sl.get_logger().warning("analytics_emit_failed",
                                  source="client_activation",
                                  error=str(_aexc)[:200])
    return intake


async def send_intake_invite(
    db: AsyncSession,
    *,
    client: Client,
    intake_request: IntakeRequest,
    reminder: bool = False,
) -> dict:
    """Send the transactional intake-invite email to a client.

    Called automatically from ``start_onboarding`` and also invocable
    directly via the ``/gm/write/intake/{id}/resend`` endpoint when a
    buyer loses the first one. Uses the DB-managed SMTP credentials
    (``integration_providers.smtp``). If no SMTP config exists for the
    org, returns a structured failure dict rather than raising — the
    IntakeRequest row is still valid and GM can surface the failure.

    Returns ``{"success": bool, "provider": str, "error": str|None}``.
    Emits ``intake.email_sent`` on success or
    ``intake.email_send_failed`` on failure.
    """
    from packages.clients.email_templates import build_intake_invite
    from packages.clients.external_clients import SmtpEmailClient
    from apps.api.services.event_bus import emit_event

    smtp = await SmtpEmailClient.from_db(db, client.org_id)
    if smtp is None:
        result = {"success": False, "error": "no_smtp_configured", "provider": None}
    else:
        built = build_intake_invite(
            display_name=client.display_name or client.primary_email,
            intake_title=intake_request.title,
            intake_token=intake_request.token,
            package_slug=(
                intake_request.schema_json or {}
            ).get("package_slug"),
            avenue_slug=client.avenue_slug,
        )
        result = await smtp.send_email(
            to_email=client.primary_email,
            subject=built["subject"],
            body_html=built["html"],
            body_text=built["text"],
        )

    now = datetime.now(timezone.utc)
    if result.get("success"):
        intake_request.sent_at = intake_request.sent_at or now
        if reminder:
            intake_request.reminder_count = (intake_request.reminder_count or 0) + 1
            intake_request.last_reminder_at = now
        db.add(
            ClientOnboardingEvent(
                client_id=client.id,
                org_id=client.org_id,
                event_type="intake.reminder_sent" if reminder else "intake.email_sent",
                intake_request_id=intake_request.id,
                details_json={
                    "provider": result.get("provider", "smtp"),
                    "to_email": client.primary_email,
                    "reminder": reminder,
                },
                actor_type="system",
                actor_id="client_activation.send_intake_invite",
            )
        )
        await emit_event(
            db,
            domain="fulfillment",
            event_type="intake.email_sent" if not reminder else "intake.reminder_sent",
            summary=(
                f"Intake invite email sent to {client.primary_email}"
                if not reminder
                else f"Intake reminder #{intake_request.reminder_count} to {client.primary_email}"
            ),
            org_id=client.org_id,
            brand_id=client.brand_id,
            entity_type="intake_request",
            entity_id=intake_request.id,
            actor_type="system",
            actor_id="client_activation.send_intake_invite",
            details={
                "client_id": str(client.id),
                "intake_request_id": str(intake_request.id),
                "provider": result.get("provider", "smtp"),
                "reminder_count": intake_request.reminder_count,
            },
        )
        logger.info(
            "intake.email_sent",
            client_id=str(client.id),
            intake_request_id=str(intake_request.id),
            reminder=reminder,
        )
    else:
        # Still log the failure as an onboarding event so GM can see it
        # and the operator can retry via /gm/write/intake/{id}/resend.
        db.add(
            ClientOnboardingEvent(
                client_id=client.id,
                org_id=client.org_id,
                event_type="intake.email_send_failed",
                intake_request_id=intake_request.id,
                details_json={
                    "error": result.get("error", "unknown"),
                    "provider": result.get("provider"),
                    "reminder": reminder,
                },
                actor_type="system",
                actor_id="client_activation.send_intake_invite",
            )
        )
        await emit_event(
            db,
            domain="fulfillment",
            event_type="intake.email_send_failed",
            summary=f"Intake invite send failed for {client.primary_email}: {result.get('error')}",
            org_id=client.org_id,
            brand_id=client.brand_id,
            entity_type="intake_request",
            entity_id=intake_request.id,
            actor_type="system",
            actor_id="client_activation.send_intake_invite",
            severity="warning",
            details={
                "client_id": str(client.id),
                "intake_request_id": str(intake_request.id),
                "error": result.get("error"),
                "provider": result.get("provider"),
            },
        )
        logger.warning(
            "intake.email_send_failed",
            client_id=str(client.id),
            intake_request_id=str(intake_request.id),
            error=result.get("error"),
        )
    await db.flush()
    return result


async def submit_intake(
    db: AsyncSession,
    *,
    intake_request: IntakeRequest,
    responses: dict,
    submitter_email: str = "",
    submitter_ip: Optional[str] = None,
    submitted_via: str = "form",
) -> IntakeSubmission:
    """Persist an IntakeSubmission, compute completeness, emit intake.completed
    when all required schema fields are present."""
    schema = intake_request.schema_json or DEFAULT_INTAKE_SCHEMA
    required = [
        f["field_id"]
        for f in schema.get("fields", [])
        if f.get("required") and f.get("field_id")
    ]
    missing = [
        fid for fid in required
        if not str(responses.get(fid, "")).strip()
    ]
    is_complete = not missing

    now = datetime.now(timezone.utc)
    submission = IntakeSubmission(
        intake_request_id=intake_request.id,
        client_id=intake_request.client_id,
        org_id=intake_request.org_id,
        submitted_at=now,
        responses_json=responses,
        is_complete=is_complete,
        missing_fields_json={"missing": missing} if missing else None,
        submitted_via=submitted_via,
        submitter_email=submitter_email[:255],
        submitter_ip=submitter_ip,
    )
    db.add(submission)
    await db.flush()

    if is_complete:
        intake_request.status = "completed"
        intake_request.completed_at = now
        await db.flush()

    db.add(
        ClientOnboardingEvent(
            client_id=intake_request.client_id,
            org_id=intake_request.org_id,
            event_type="intake.completed" if is_complete else "intake.partial_submission",
            proposal_id=intake_request.proposal_id,
            payment_id=intake_request.payment_id,
            intake_request_id=intake_request.id,
            intake_submission_id=submission.id,
            details_json={
                "submitter_email": submitter_email,
                "submitted_via": submitted_via,
                "is_complete": is_complete,
                "missing_fields": missing,
            },
            actor_type="client",
            actor_id=submitter_email or str(intake_request.client_id),
        )
    )
    await db.flush()

    if is_complete:
        await emit_event(
            db,
            domain="fulfillment",
            event_type="intake.completed",
            summary=f"Intake completed by {submitter_email or intake_request.client_id}",
            org_id=intake_request.org_id,
            entity_type="intake_request",
            entity_id=intake_request.id,
            previous_state="sent",
            new_state="completed",
            actor_type="client",
            actor_id=submitter_email or str(intake_request.client_id),
            details={
                "client_id": str(intake_request.client_id),
                "intake_request_id": str(intake_request.id),
                "intake_submission_id": str(submission.id),
                "field_count": len(responses or {}),
            },
        )
        logger.info(
            "intake.completed",
            client_id=str(intake_request.client_id),
            intake_submission_id=str(submission.id),
        )
        # ── Cascade: intake.completed → project → brief → production ──
        try:
            from apps.api.services.fulfillment_service import (
                cascade_intake_to_production,
            )
            cascade_result = await cascade_intake_to_production(
                db, intake_submission=submission
            )
            logger.info(
                "intake.cascade_ok",
                intake_submission_id=str(submission.id),
                **cascade_result,
            )
        except Exception as cascade_exc:
            logger.warning(
                "intake.cascade_failed",
                intake_submission_id=str(submission.id),
                error=str(cascade_exc)[:200],
            )
    else:
        logger.info(
            "intake.partial_submission",
            intake_request_id=str(intake_request.id),
            missing_fields=missing,
        )

    return submission


# ═══════════════════════════════════════════════════════════════════════════
#  Internal helpers
# ═══════════════════════════════════════════════════════════════════════════


async def _recover_email_from_proposal(
    db: AsyncSession, proposal_id: Optional[uuid.UUID]
) -> str:
    if proposal_id is None:
        return ""
    proposal = (
        await db.execute(select(Proposal).where(Proposal.id == proposal_id))
    ).scalar_one_or_none()
    if proposal is None:
        return ""
    return (proposal.recipient_email or "").strip().lower()
