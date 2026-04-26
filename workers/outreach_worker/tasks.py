"""Outreach Worker — sends outreach emails, follow-ups, and polls inbox for replies.

Wires the full outreach pipeline:
  1. send_outreach_email: loads outreach record, sends via SMTP, updates status, schedules follow-ups
  2. send_follow_up: sends follow-up emails in a sequence, drafts via LLM or template
  3. poll_inbox_for_replies: connects IMAP, fetches unread, matches to outreach, classifies, advances deals

Credentials loaded EXCLUSIVELY from integration_manager (encrypted DB).
No .env fallback — dashboard/provider config is the source of truth.
If SMTP/IMAP credentials are missing from integration_providers, the task
skips with a structured log and does not fall back to environment variables.
"""

from __future__ import annotations

import asyncio
import email as email_lib
import imaplib
import logging
import uuid
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import select

from packages.db.session import get_async_session_factory, run_async

async_session_factory = get_async_session_factory()
from workers.base_task import TrackedTask

logger = logging.getLogger(__name__)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _run_async(coro):
    """Run an async coroutine from sync Celery task context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(run_async, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return run_async(coro)


async def _get_smtp_credentials(db, org_id: uuid.UUID) -> dict:
    """Load SMTP credentials from integration_manager (DB-only, no env fallback).

    Expected integration_providers row:
        provider_key = "smtp"
        api_key      = <SMTP password>
        extra_config = {"host": "...", "port": 465, "username": "...", "from_email": "..."}
    """
    from apps.api.services.integration_manager import get_credential_full

    creds = await get_credential_full(db, org_id, "smtp")
    extra = creds.get("extra_config") or {}
    host = extra.get("host", "")
    port = int(extra.get("port", 465))
    username = extra.get("username", "")
    password = creds.get("api_key", "")
    from_email = extra.get("from_email", "") or username
    # Optional Reply-To — does NOT change From, SMTP auth, SPF/DKIM/DMARC.
    # When set, outbound messages include a Reply-To header so recipient
    # replies route to an inbound-parse subdomain (e.g. reply@reply.proofhook.com)
    # instead of the sending mailbox.  When absent, outbound behavior is
    # identical to before this change.
    reply_to = extra.get("reply_to", "")

    configured = bool(host and username and password)
    if not configured:
        logger.warning(
            "outreach.smtp_not_configured org_id=%s hint=%s",
            str(org_id),
            "Add SMTP credentials via Settings > Integrations (provider_key='smtp')",
        )

    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "from_email": from_email,
        "reply_to": reply_to,
        "configured": configured,
    }


async def _get_imap_credentials(db, org_id: uuid.UUID) -> dict:
    """Load IMAP credentials from integration_manager (DB-only, no env fallback).

    Expected integration_providers row:
        provider_key = "imap"
        api_key      = <IMAP password>
        extra_config = {"host": "...", "port": 993, "username": "..."}
    """
    from apps.api.services.integration_manager import get_credential_full

    creds = await get_credential_full(db, org_id, "imap")
    extra = creds.get("extra_config") or {}
    host = extra.get("host", "")
    port = int(extra.get("port", 993))
    username = extra.get("username", "")
    password = creds.get("api_key", "")

    configured = bool(host and username and password)
    if not configured:
        logger.warning(
            "outreach.imap_not_configured org_id=%s hint=%s",
            str(org_id),
            "Add IMAP credentials via Settings > Integrations (provider_key='imap')",
        )

    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "configured": configured,
    }


async def _send_smtp_email(
    smtp_creds: dict,
    to_email: str,
    subject: str,
    body_html: str,
    body_text: str = "",
) -> dict:
    """Send an email via SMTP. Uses aiosmtplib (same as EmailAdapter).

    Cold-outbound safety patch:
      - Refuses to send commercial outreach without a configured physical
        mailing address (CAN-SPAM § 5(a)(5)). Operator sets
        ``PROOFHOOK_MAILING_ADDRESS`` env. If unset, returns a structured
        ``{success: False, blocked: True, error: 'missing_physical_mailing_address'}``
        result; the caller treats it as a non-send.
      - Always appends a visible footer with the address + an explicit
        opt-out line. Idempotent on the sentinel "Reply UNSUBSCRIBE to opt
        out." so re-applying the footer does not duplicate it.
      - Always sets the ``List-Unsubscribe`` header (parity with the
        API-side SmtpEmailClient.send_email path).
    """
    import html as _html
    import os
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    import aiosmtplib

    if not smtp_creds.get("configured"):
        return {
            "success": False,
            "error": "SMTP not configured — add credentials via Settings > Integrations (provider_key='smtp')",
        }

    # ── Compliance gate: physical mailing address required ──────────
    mailing_address = os.environ.get("PROOFHOOK_MAILING_ADDRESS", "").strip()
    if not mailing_address:
        return {
            "success": False,
            "blocked": True,
            "error": "missing_physical_mailing_address",
            "hint": (
                "Set PROOFHOOK_MAILING_ADDRESS env to the operator's verified "
                "physical mailing address (CAN-SPAM § 5(a)(5))."
            ),
        }

    # ── Footer enforcement: visible address + opt-out line ──────────
    UNSUB_SENTINEL = "Reply UNSUBSCRIBE to opt out."
    footer_text_block = (
        "\n\n--\n"
        "ProofHook\n"
        f"{mailing_address}\n"
        f"{UNSUB_SENTINEL}\n"
    )
    address_html = _html.escape(mailing_address).replace("\n", "<br>")
    footer_html_block = (
        '<hr style="margin-top:24px;border:none;border-top:1px solid #ccc">'
        '<p style="font-size:12px;color:#666;line-height:1.5">'
        "ProofHook<br>"
        f"{address_html}<br>"
        f"{UNSUB_SENTINEL}"
        "</p>"
    )
    if UNSUB_SENTINEL not in (body_text or ""):
        body_text = (body_text or "") + footer_text_block
    if UNSUB_SENTINEL not in (body_html or ""):
        body_html = (body_html or "") + footer_html_block

    msg = MIMEMultipart("alternative")
    msg["From"] = smtp_creds["from_email"]
    msg["To"] = to_email
    msg["Subject"] = subject
    # Optional Reply-To for inbound capture via SendGrid Inbound Parse.
    # Presence of this header does NOT affect From, SPF, DKIM, DMARC,
    # or the SMTP auth path — it only tells the recipient's mail client
    # which address to populate when they hit Reply.
    if smtp_creds.get("reply_to"):
        msg["Reply-To"] = smtp_creds["reply_to"]
    # List-Unsubscribe header parity with the API-side SmtpEmailClient
    # path (intake invite, dunning, retention, delivery emails). Bulk
    # mailbox providers honor this; mailto fallback satisfies RFC 2369.
    msg["List-Unsubscribe"] = f"<mailto:{smtp_creds['from_email']}?subject=unsubscribe>"

    if body_text:
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))
    if not body_text and not body_html:
        msg.attach(MIMEText("(empty)", "plain", "utf-8"))

    try:
        use_tls = smtp_creds["port"] == 465
        if use_tls:
            await aiosmtplib.send(
                msg,
                hostname=smtp_creds["host"],
                port=smtp_creds["port"],
                username=smtp_creds["username"] or None,
                password=smtp_creds["password"] or None,
                use_tls=True,
            )
        else:
            await aiosmtplib.send(
                msg,
                hostname=smtp_creds["host"],
                port=smtp_creds["port"],
                username=smtp_creds["username"] or None,
                password=smtp_creds["password"] or None,
                start_tls=True,
            )
        return {"success": True, "message_id": msg.get("Message-ID")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _text_to_html(text: str) -> str:
    """Convert plain text to simple HTML."""
    import html as html_mod

    escaped = html_mod.escape(text)
    paragraphs = escaped.split("\n\n")
    html_parts = []
    for p in paragraphs:
        lines = p.split("\n")
        html_parts.append("<p>" + "<br>".join(lines) + "</p>")
    return "\n".join(html_parts)


# ── Task 1: Send Outreach Email ─────────────────────────────────────────────


async def _send_outreach_email_impl(outreach_id: str, brand_id: str, org_id: str) -> dict:
    """Core implementation for sending an outreach email."""
    from apps.api.services.event_bus import emit_action, emit_event
    from packages.db.models.expansion_pack2_phase_c import SponsorOutreachSequence, SponsorTarget

    org_uuid = uuid.UUID(org_id)
    brand_uuid = uuid.UUID(brand_id)
    outreach_uuid = uuid.UUID(outreach_id)

    async with get_async_session_factory()() as db:
        # Load outreach sequence record
        outreach = (
            await db.execute(select(SponsorOutreachSequence).where(SponsorOutreachSequence.id == outreach_uuid))
        ).scalar_one_or_none()

        if not outreach:
            return {"error": f"Outreach record {outreach_id} not found"}

        # Load the sponsor target
        target = (
            await db.execute(select(SponsorTarget).where(SponsorTarget.id == outreach.sponsor_target_id))
        ).scalar_one_or_none()

        if not target:
            return {"error": f"Sponsor target not found for outreach {outreach_id}"}

        # Extract contact info and draft from steps
        contact_info = target.contact_info or {}
        to_email = contact_info.get("email", "")
        if not to_email:
            return {"error": f"No contact email for target '{target.target_company_name}'"}

        # Cold-outbound safety: never send to test/synthetic addresses.
        # Catches @example.com, @test.com, @b10test.com, *.invalid,
        # *.localhost, and the test/fixture/synth marker patterns. Runs
        # BEFORE the autonomous gate so test addresses don't even create
        # OperatorActions for review — the existing 122 sponsor_targets
        # in production are all @b10test.com fixtures.
        from apps.api.services.test_record_guard import is_test_or_synthetic_email

        if is_test_or_synthetic_email(to_email):
            logger.warning(
                "outreach.blocked_test_email to=%s outreach_id=%s target=%s",
                to_email,
                outreach_id,
                target.target_company_name,
            )
            await emit_event(
                db,
                domain="outreach",
                event_type="outreach.blocked_test_email",
                summary=f"Outreach blocked: test/synthetic email {to_email}",
                org_id=org_uuid,
                brand_id=brand_uuid,
                severity="warning",
                details={
                    "outreach_id": outreach_id,
                    "to_email": to_email,
                    "target": target.target_company_name,
                    "reason": "test_or_synthetic_email",
                },
            )
            await db.commit()
            return {
                "status": "blocked",
                "reason": "test_or_synthetic_email",
                "to_email": to_email,
            }

        steps = outreach.steps or []
        if not steps:
            return {"error": "Outreach sequence has no steps defined"}

        # Idempotency check — refuse to re-send a step that's already been
        # sent or is currently in flight on another worker. Prevents
        # duplicates when Celery redelivers a task after a worker dies
        # between SMTP-220-OK and the post-send commit
        # (task_acks_late + task_reject_on_worker_lost).
        status0 = (steps[0] or {}).get("status")
        if status0 == "sent" or steps[0].get("sent_at"):
            return {
                "status": "duplicate_skipped",
                "reason": "step_already_sent",
                "sent_at": steps[0].get("sent_at"),
            }
        if status0 == "sending":
            return {
                "status": "duplicate_skipped",
                "reason": "step_in_flight",
                "sending_started_at": steps[0].get("sending_started_at"),
            }

        # First step is the initial outreach
        first_step = steps[0]
        subject = first_step.get("subject", f"Partnership Opportunity with {target.target_company_name}")
        body_text = first_step.get("body", "")
        body_html = first_step.get("body_html") or _text_to_html(body_text)

        # Autonomous mode check
        autonomous_send = first_step.get("autonomous_send", False)
        confidence = outreach.confidence or 0.0

        if not autonomous_send or confidence < 0.7:
            # Gate: create OperatorAction for review instead of sending
            action = await emit_action(
                db,
                org_id=org_uuid,
                action_type="send_outreach_email",
                title=f"Review & Send: {subject[:60]}",
                description=f"To: {to_email}. Outreach to {target.target_company_name}. Confidence: {confidence:.0%}",
                category="monetization",
                priority="high",
                brand_id=brand_uuid,
                source_module="outreach_worker",
                action_payload={
                    "autonomy_level": "assisted",
                    "confidence": confidence,
                    "outreach_id": outreach_id,
                    "to_email": to_email,
                    "subject": subject,
                    "body_preview": body_text[:300],
                },
            )
            await db.commit()
            return {
                "status": "awaiting_approval",
                "action_id": str(action.id),
                "to_email": to_email,
                "subject": subject,
            }

        # Autonomous: send directly
        # Pre-send marker — committed BEFORE SMTP so a kill between
        # SMTP-OK and the post-send commit makes the redelivered task
        # skip rather than re-send.
        steps[0]["status"] = "sending"
        steps[0]["sending_started_at"] = datetime.now(timezone.utc).isoformat()
        outreach.steps = steps
        await db.commit()

        smtp_creds = await _get_smtp_credentials(db, org_uuid)
        result = await _send_smtp_email(smtp_creds, to_email, subject, body_html, body_text)

        if not result.get("success"):
            logger.error("outreach_send_failed target=%s error=%s", target.target_company_name, result.get("error"))
            return {"status": "send_failed", "error": result.get("error"), "to_email": to_email}

        # Update outreach record: mark step 0 as sent
        now_iso = datetime.now(timezone.utc).isoformat()
        if steps:
            steps[0]["status"] = "sent"
            steps[0]["sent_at"] = now_iso
            steps[0]["send_result"] = {"provider": "smtp", "ok": True}
        outreach.steps = steps  # trigger JSONB update
        await db.flush()

        # Schedule follow-up for step 2 (if exists)
        if len(steps) > 1:
            delay_days = steps[1].get("delay_days", 7)
            send_follow_up.apply_async(
                kwargs={
                    "outreach_id": outreach_id,
                    "sequence_step": 1,
                    "org_id": org_id,
                },
                countdown=delay_days * 86400,
            )

        # Emit event
        await emit_event(
            db,
            domain="outreach",
            event_type="outreach.email_sent",
            summary=f"Outreach sent to {to_email} ({target.target_company_name})",
            org_id=org_uuid,
            brand_id=brand_uuid,
            details={
                "outreach_id": outreach_id,
                "to_email": to_email,
                "subject": subject,
                "autonomous": True,
            },
        )

        await db.commit()

        logger.info("outreach_email_sent to=%s target=%s", to_email, target.target_company_name)
        return {
            "status": "sent",
            "to_email": to_email,
            "subject": subject,
            "sent_at": now_iso,
            "follow_up_scheduled": len(steps) > 1,
        }


@shared_task(base=TrackedTask, bind=True, name="workers.outreach_worker.tasks.send_outreach_email")
def send_outreach_email(self, outreach_id: str, brand_id: str, org_id: str) -> dict:
    """Send an outreach email. If not autonomous, creates approval action instead."""
    return _run_async(_send_outreach_email_impl(outreach_id, brand_id, org_id))


# ── Task 2: Send Follow-Up ──────────────────────────────────────────────────


async def _send_follow_up_impl(outreach_id: str, sequence_step: int, org_id: str) -> dict:
    """Send a follow-up email in an outreach sequence."""
    from apps.api.services.event_bus import emit_event
    from packages.db.models.expansion_pack2_phase_c import SponsorOutreachSequence, SponsorTarget

    org_uuid = uuid.UUID(org_id)
    outreach_uuid = uuid.UUID(outreach_id)

    async with get_async_session_factory()() as db:
        outreach = (
            await db.execute(select(SponsorOutreachSequence).where(SponsorOutreachSequence.id == outreach_uuid))
        ).scalar_one_or_none()

        if not outreach:
            return {"error": f"Outreach record {outreach_id} not found"}

        target = (
            await db.execute(select(SponsorTarget).where(SponsorTarget.id == outreach.sponsor_target_id))
        ).scalar_one_or_none()

        if not target:
            return {"error": "Sponsor target not found"}

        steps = outreach.steps or []
        if sequence_step >= len(steps):
            return {"status": "skipped", "reason": f"Step {sequence_step} does not exist (only {len(steps)} steps)"}

        # Check if already replied (skip follow-up if they responded)
        current_step = steps[sequence_step]
        if current_step.get("status") == "replied":
            return {"status": "skipped", "reason": "Target already replied — follow-up cancelled"}

        # Check if any earlier step got a reply
        for s in steps[:sequence_step]:
            if s.get("status") == "replied":
                return {"status": "skipped", "reason": "Reply received on earlier step — follow-up cancelled"}

        # Idempotency check — refuse to re-send a follow-up step that's
        # already been sent or is currently in flight on another worker.
        # Prevents duplicates on Celery task redelivery after a worker
        # dies between SMTP-220-OK and the post-send commit.
        status_now = current_step.get("status")
        if status_now == "sent" or current_step.get("sent_at"):
            return {
                "status": "duplicate_skipped",
                "reason": "step_already_sent",
                "step": sequence_step,
                "sent_at": current_step.get("sent_at"),
            }
        if status_now == "sending":
            return {
                "status": "duplicate_skipped",
                "reason": "step_in_flight",
                "step": sequence_step,
                "sending_started_at": current_step.get("sending_started_at"),
            }

        contact_info = target.contact_info or {}
        to_email = contact_info.get("email", "")
        if not to_email:
            return {"error": "No contact email for target"}

        # Cold-outbound safety: never follow up on test/synthetic addresses.
        # Same guard as initial outreach — even if step 0 was somehow sent
        # past the guard, every subsequent step re-checks before sending.
        from apps.api.services.test_record_guard import is_test_or_synthetic_email

        if is_test_or_synthetic_email(to_email):
            logger.warning(
                "outreach.follow_up.blocked_test_email to=%s outreach_id=%s step=%d target=%s",
                to_email,
                outreach_id,
                sequence_step,
                target.target_company_name,
            )
            await emit_event(
                db,
                domain="outreach",
                event_type="outreach.blocked_test_email",
                summary=f"Follow-up blocked: test/synthetic email {to_email}",
                org_id=org_uuid,
                severity="warning",
                details={
                    "outreach_id": outreach_id,
                    "sequence_step": sequence_step,
                    "to_email": to_email,
                    "target": target.target_company_name,
                    "reason": "test_or_synthetic_email",
                },
            )
            await db.commit()
            return {
                "status": "blocked",
                "reason": "test_or_synthetic_email",
                "to_email": to_email,
                "step": sequence_step,
            }

        subject = current_step.get("subject", f"Following up — {target.target_company_name}")
        body_text = current_step.get("body", "")

        # If no body in step, use a template follow-up
        if not body_text:
            body_text = _generate_follow_up_text(target.target_company_name, sequence_step)

        body_html = current_step.get("body_html") or _text_to_html(body_text)

        # Pre-send marker — committed BEFORE SMTP so a kill between
        # SMTP-OK and the post-send commit makes the redelivered task
        # skip rather than re-send.
        steps[sequence_step]["status"] = "sending"
        steps[sequence_step]["sending_started_at"] = datetime.now(timezone.utc).isoformat()
        outreach.steps = steps
        await db.commit()

        # Send via SMTP
        smtp_creds = await _get_smtp_credentials(db, org_uuid)
        result = await _send_smtp_email(smtp_creds, to_email, subject, body_html, body_text)

        if not result.get("success"):
            logger.error("follow_up_send_failed step=%d error=%s", sequence_step, result.get("error"))
            return {"status": "send_failed", "step": sequence_step, "error": result.get("error")}

        # Update step state
        now_iso = datetime.now(timezone.utc).isoformat()
        steps[sequence_step]["status"] = "sent"
        steps[sequence_step]["sent_at"] = now_iso
        steps[sequence_step]["send_result"] = {"provider": "smtp", "ok": True}
        outreach.steps = steps
        await db.flush()

        # Schedule next follow-up if more steps remain
        next_step = sequence_step + 1
        if next_step < len(steps):
            delay_days = steps[next_step].get("delay_days", 7)
            send_follow_up.apply_async(
                kwargs={
                    "outreach_id": outreach_id,
                    "sequence_step": next_step,
                    "org_id": org_id,
                },
                countdown=delay_days * 86400,
            )

        await emit_event(
            db,
            domain="outreach",
            event_type="outreach.follow_up_sent",
            summary=f"Follow-up #{sequence_step + 1} sent to {to_email} ({target.target_company_name})",
            org_id=org_uuid,
            details={
                "outreach_id": outreach_id,
                "sequence_step": sequence_step,
                "to_email": to_email,
                "next_step_scheduled": next_step < len(steps),
            },
        )

        await db.commit()

        logger.info("follow_up_sent step=%d to=%s", sequence_step, to_email)
        return {
            "status": "sent",
            "step": sequence_step,
            "to_email": to_email,
            "subject": subject,
            "sent_at": now_iso,
            "next_step_scheduled": next_step < len(steps),
        }


def _generate_follow_up_text(company_name: str, step: int) -> str:
    """Generate follow-up text from templates when no LLM draft is available."""
    templates = {
        1: (
            f"Hi {company_name} team,\n\n"
            f"Just following up on my earlier message about a potential partnership. "
            f"I'd love to hear your thoughts — happy to jump on a quick call at your convenience.\n\n"
            f"Best regards"
        ),
        2: (
            f"Hi {company_name} team,\n\n"
            f"Wanted to circle back one more time on the partnership opportunity I mentioned. "
            f"If the timing isn't right, I completely understand — just let me know.\n\n"
            f"Best regards"
        ),
    }
    # For steps beyond our templates, use the last template
    return templates.get(step, templates[max(templates.keys())])


@shared_task(base=TrackedTask, bind=True, name="workers.outreach_worker.tasks.send_follow_up")
def send_follow_up(self, outreach_id: str, sequence_step: int, org_id: str) -> dict:
    """Send a follow-up email in an outreach sequence. Skips if target already replied."""
    return _run_async(_send_follow_up_impl(outreach_id, sequence_step, org_id))


# ── Task 3: Poll Inbox for Replies ──────────────────────────────────────────


async def _poll_inbox_impl(org_id: str) -> dict:
    """Connect to IMAP, fetch unread emails, match to outreach, classify replies."""
    from apps.api.services.reply_ingestion import ingest_reply

    org_uuid = uuid.UUID(org_id)

    async with get_async_session_factory()() as db:
        imap_creds = await _get_imap_credentials(db, org_uuid)

        if not imap_creds["configured"]:
            return {
                "configured": False,
                "error": "IMAP credentials not configured — set via Settings > Integrations or IMAP_HOST/IMAP_USER/IMAP_PASSWORD env",
            }

        try:
            mail = imaplib.IMAP4_SSL(imap_creds["host"], imap_creds["port"])
            mail.login(imap_creds["username"], imap_creds["password"])
            mail.select("INBOX")

            # Fetch unread emails — cap per-cycle to avoid OOM on large inboxes
            _, message_numbers = mail.search(None, "UNSEEN")
            nums = message_numbers[0].split() if message_numbers[0] else []
            nums = nums[:50]  # Process at most 50 per beat cycle; remainder caught next run

            ingested = 0
            errors = 0

            for num in nums:
                try:
                    _, msg_data = mail.fetch(num, "(RFC822)")
                    raw_email = msg_data[0][1]
                    msg = email_lib.message_from_bytes(raw_email)

                    sender = email_lib.utils.parseaddr(msg.get("From", ""))[1]
                    subject = msg.get("Subject", "")
                    in_reply_to = msg.get("In-Reply-To", "")

                    # Extract body
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            if content_type == "text/plain":
                                payload = part.get_payload(decode=True)
                                if payload:
                                    body = payload.decode("utf-8", errors="replace")
                                    break
                    else:
                        payload = msg.get_payload(decode=True)
                        if payload:
                            body = payload.decode("utf-8", errors="replace")

                    if not sender:
                        continue

                    # Ingest the reply — classify it, match to deals, advance stages
                    await ingest_reply(
                        db,
                        org_uuid,
                        sender_email=sender,
                        subject=subject,
                        body=body,
                        in_reply_to=in_reply_to,
                    )

                    # Also try to match against SponsorOutreachSequence records
                    await _match_reply_to_outreach(db, org_uuid, sender, subject, body)

                    ingested += 1

                except Exception as e:
                    logger.error("inbox_message_process_error num=%s error=%s", num, str(e))
                    errors += 1

            # Mark all processed as seen (IMAP already marks fetched as seen in most configs)
            mail.close()
            mail.logout()

            await db.commit()

            logger.info("inbox_poll_complete ingested=%d errors=%d total_unread=%d", ingested, errors, len(nums))
            return {
                "configured": True,
                "emails_processed": ingested,
                "errors": errors,
                "total_unread": len(nums),
            }

        except imaplib.IMAP4.error as e:
            logger.error("imap_auth_error error=%s", str(e))
            return {"configured": True, "error": f"IMAP authentication failed: {str(e)[:200]}"}
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error("imap_connection_error error=%s", str(e))
            return {"configured": True, "error": f"IMAP connection failed: {str(e)[:200]}"}
        except Exception as e:
            logger.error("inbox_poll_failed error=%s", str(e))
            return {"configured": True, "error": str(e)[:200]}


async def _match_reply_to_outreach(
    db,
    org_uuid: uuid.UUID,
    sender: str,
    subject: str,
    body: str,
) -> None:
    """Try to match an incoming reply to a SponsorOutreachSequence record.

    If matched, mark the relevant step as 'replied' so follow-ups are cancelled.
    """
    from apps.api.services.event_bus import emit_event
    from apps.api.services.reply_ingestion import classify_reply
    from packages.db.models.expansion_pack2_phase_c import SponsorOutreachSequence, SponsorTarget

    # Find sponsor targets whose contact email matches the sender
    targets = (
        (
            await db.execute(
                select(SponsorTarget).where(
                    SponsorTarget.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )

    matched_target = None
    for t in targets:
        contact = t.contact_info or {}
        if contact.get("email", "").lower() == sender.lower():
            matched_target = t
            break

    if not matched_target:
        return

    # Find active outreach sequences for this target
    sequences = (
        (
            await db.execute(
                select(SponsorOutreachSequence).where(
                    SponsorOutreachSequence.sponsor_target_id == matched_target.id,
                    SponsorOutreachSequence.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )

    if not sequences:
        return

    classification = classify_reply(subject, body)

    for seq in sequences:
        steps = seq.steps or []
        # Mark the latest sent step as replied
        for i in range(len(steps) - 1, -1, -1):
            if steps[i].get("status") == "sent":
                steps[i]["status"] = "replied"
                steps[i]["reply_classification"] = classification["classification"]
                steps[i]["reply_confidence"] = classification["confidence"]
                steps[i]["replied_at"] = datetime.now(timezone.utc).isoformat()
                seq.steps = steps
                break

    await emit_event(
        db,
        domain="outreach",
        event_type="outreach.reply_received",
        summary=f"Reply from {sender} matched to {matched_target.target_company_name}: {classification['classification']}",
        org_id=org_uuid,
        details={
            "sender": sender,
            "target_company": matched_target.target_company_name,
            "classification": classification["classification"],
            "confidence": classification["confidence"],
        },
    )

    await db.flush()


@shared_task(base=TrackedTask, bind=True, name="workers.outreach_worker.tasks.poll_inbox_for_replies")
def poll_inbox_for_replies(self, org_id: str) -> dict:
    """Poll IMAP inbox for unread replies. Matches to outreach records, classifies, advances deals."""
    return _run_async(_poll_inbox_impl(org_id))


# ── Task 4: Process All Orgs (beat-friendly entry point) ────────────────────


async def _poll_all_orgs_impl() -> dict:
    """Poll inbox for every org that has IMAP configured."""
    from sqlalchemy import select as sa_select

    from packages.db.models.core import Organization

    async with get_async_session_factory()() as db:
        orgs = (await db.execute(sa_select(Organization.id))).scalars().all()

    results = {}
    for oid in orgs:
        result = await _poll_inbox_impl(str(oid))
        results[str(oid)] = result

    return {"orgs_polled": len(results), "results": results}


@shared_task(base=TrackedTask, bind=True, name="workers.outreach_worker.tasks.poll_all_inboxes")
def poll_all_inboxes(self) -> dict:
    """Beat-schedule entry: poll inbox for all orgs with IMAP configured."""
    return _run_async(_poll_all_orgs_impl())


# ── Task 4: Execute Lead CloserActions ─────────────────────────────────────


async def _execute_closer_actions_impl() -> dict:
    """Process pending CloserAction records and send real follow-up emails/SMS.

    Reads CloserActions where is_active=True and is_completed=False,
    sends via SMTP (email) or Twilio (SMS), marks completed.
    """
    from sqlalchemy import select

    from packages.clients.external_clients import SmtpEmailClient, TwilioSmsClient
    from packages.db.models.expansion_pack2_phase_a import CloserAction, LeadOpportunity

    sent = 0
    failed = 0
    skipped = 0

    async with async_session_factory() as db:
        # Get all pending closer actions
        actions = (
            (
                await db.execute(
                    select(CloserAction)
                    .where(
                        CloserAction.is_active.is_(True),
                        CloserAction.is_completed.is_(False),
                    )
                    .order_by(CloserAction.priority.asc())
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )

        for ca in actions:
            try:
                # Load the associated lead to get contact info
                lead = None
                if ca.lead_opportunity_id:
                    lead = (
                        await db.execute(select(LeadOpportunity).where(LeadOpportunity.id == ca.lead_opportunity_id))
                    ).scalar_one_or_none()

                if not lead:
                    skipped += 1
                    continue

                # Parse contact info from lead's message_text
                contact_info = _parse_lead_contact(lead.message_text or "")
                if not contact_info.get("email") and not contact_info.get("phone"):
                    skipped += 1
                    continue

                channel = (ca.channel or "email").lower()
                subject = ca.subject_or_opener or "Following up on your inquiry"
                body = _build_closer_email_body(ca, lead, contact_info)

                if channel == "email" and contact_info.get("email"):
                    smtp = SmtpEmailClient()
                    if smtp._is_configured():
                        result = await smtp.send_email(
                            to_email=contact_info["email"],
                            subject=subject,
                            body_html=body,
                            body_text=body,
                        )
                        if result.get("sent"):
                            ca.is_completed = True
                            sent += 1
                            log.info(
                                "closer_action.email_sent",
                                lead_id=str(ca.lead_opportunity_id),
                                to=contact_info["email"],
                            )
                        else:
                            failed += 1
                            log.warning("closer_action.email_failed", error=result.get("error", "unknown"))
                    else:
                        skipped += 1

                elif channel == "sms" and contact_info.get("phone"):
                    twilio = TwilioSmsClient()
                    if twilio._is_configured():
                        sms_body = f"{subject}\n\n{ca.rationale or ''}"
                        result = await twilio.send_sms(
                            to_phone=contact_info["phone"],
                            message_body=sms_body[:1600],
                        )
                        if result.get("sent"):
                            ca.is_completed = True
                            sent += 1
                            log.info("closer_action.sms_sent", lead_id=str(ca.lead_opportunity_id))
                        else:
                            failed += 1
                    else:
                        skipped += 1
                else:
                    skipped += 1

            except Exception as e:
                log.warning("closer_action.execution_error", action_id=str(ca.id), error=str(e))
                failed += 1

        await db.commit()

    return {"sent": sent, "failed": failed, "skipped": skipped}


def _parse_lead_contact(message_text: str) -> dict:
    """Extract email and phone from lead message_text (format: Name: X\\nEmail: Y\\n...)."""
    contact = {}
    for line in message_text.split("\n"):
        line = line.strip()
        if line.lower().startswith("email:"):
            contact["email"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("name:"):
            contact["name"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("phone:"):
            contact["phone"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("company:"):
            contact["company"] = line.split(":", 1)[1].strip()
    return contact


def _build_closer_email_body(ca, lead, contact_info: dict) -> str:
    """Build a follow-up email body from CloserAction + Lead data."""
    name = contact_info.get("name", "there")
    company = contact_info.get("company", "")
    company_line = f" at {company}" if company else ""

    return f"""<p>Hi {name},</p>

<p>Thank you for your interest{company_line}. {ca.rationale or "We wanted to follow up on your recent inquiry."}</p>

<p>{ca.expected_outcome or "We would love to discuss how we can help you achieve your goals."}</p>

<p>Looking forward to connecting.</p>

<p>Best regards</p>"""


log = logging.getLogger(__name__)


@shared_task(base=TrackedTask, bind=True, name="workers.outreach_worker.tasks.execute_closer_actions")
def execute_closer_actions(self) -> dict:
    """Beat-schedule entry: process pending CloserActions (lead follow-up)."""
    return _run_async(_execute_closer_actions_impl())
