"""Email Campaign Worker — send nurture sequences, weekly digests, and monetization emails."""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import select, update

from workers.base_task import TrackedTask

from packages.db.session import async_session_factory
from packages.db.models.core import Brand

logger = logging.getLogger(__name__)


async def _send_pending_emails():
    """Process pending email send requests queued in the email_send_requests table."""
    from packages.clients.external_clients import SmtpEmailClient
    from packages.db.models.live_execution import EmailSendRequest

    client = SmtpEmailClient()
    if not client._is_configured():
        return {"sent": 0, "failed": 0, "reason": "SMTP not configured — set SMTP_HOST and SMTP_FROM_EMAIL env vars"}

    total_sent = 0
    total_failed = 0

    async with async_session_factory() as db:
        pending = (await db.execute(
            select(EmailSendRequest).where(
                EmailSendRequest.status == "queued",
                EmailSendRequest.is_active.is_(True),
                EmailSendRequest.retry_count < 3,
            ).order_by(EmailSendRequest.created_at).limit(100)
        )).scalars().all()

        for req in pending:
            try:
                result = await client.send_email(
                    to_email=req.to_email,
                    subject=req.subject,
                    body_html=req.body_html or "",
                    body_text=req.body_text or "",
                )
                if result.get("success"):
                    req.status = "sent"
                    req.sent_at = datetime.now(timezone.utc).isoformat()
                    req.error_message = None
                    total_sent += 1
                    logger.info("email sent to %s (request %s)", req.to_email, req.id)
                else:
                    req.retry_count += 1
                    req.error_message = result.get("error", "Unknown SMTP error")
                    if req.retry_count >= 3:
                        req.status = "failed"
                    total_failed += 1
                    logger.warning("email failed for %s: %s", req.to_email, req.error_message)
            except Exception as e:
                req.retry_count += 1
                req.error_message = str(e)
                if req.retry_count >= 3:
                    req.status = "failed"
                total_failed += 1
                logger.exception("email send exception for request %s", req.id)

        await db.commit()

    async with async_session_factory() as db:
        brands = list((await db.execute(select(Brand.id).where(Brand.is_active.is_(True)))).scalars().all())

    for bid in brands:
        try:
            async with async_session_factory() as db:
                from apps.api.services.lead_magnet_service import identify_lead_magnet_opportunities, generate_lead_magnet
                opportunities = await identify_lead_magnet_opportunities(db, bid)
                for opp in opportunities[:1]:
                    result = await generate_lead_magnet(db, bid, opp["topic"], opp["magnet_type"])
                    if result.get("success"):
                        logger.info("lead magnet created: brand=%s topic=%s", bid, opp["topic"])
                await db.commit()
        except Exception:
            logger.exception("lead magnet generation failed for brand %s", bid)

    return {"brands_processed": len(brands), "total_sent": total_sent, "total_failed": total_failed}


@shared_task(name="workers.email_campaign_worker.tasks.process_email_campaigns", base=TrackedTask)
def process_email_campaigns():
    return asyncio.run(_send_pending_emails())


# ── Inbox Sync + Classification + Reply Drafts ────────────────────────────


async def _sync_inbox_impl(connection_id: str | None = None) -> dict:
    """Sync inbox: ingest messages, classify, advance sales stages, create reply drafts.

    Full loop:
    1. Connect to IMAP
    2. Fetch unread messages
    3. Dedup by provider_message_id
    4. Create EmailThread + EmailMessage
    5. Link to CrmContact + LeadOpportunity
    6. Classify inbound by intent
    7. Advance sales stage
    8. Create reply draft (auto_send / draft / escalate)
    9. Send approved auto-replies
    """
    import os
    import hashlib
    import email as email_lib
    import imaplib
    from email.utils import parseaddr, parsedate_to_datetime

    from packages.db.models.email_pipeline import (
        InboxConnection, EmailThread, EmailMessage, EmailClassification,
        SalesStageTransition,
    )
    from packages.db.models.live_execution import CrmContact
    from packages.db.models.expansion_pack2_phase_a import LeadOpportunity
    from packages.db.models.core import Organization, Brand
    from apps.api.services.email_classifier import classify_email, compute_stage_transition
    from apps.api.services.reply_engine import create_reply_draft, send_approved_drafts

    total_ingested = 0
    total_classified = 0
    total_drafts = 0
    total_sent = 0
    errors = []

    async with async_session_factory() as db:
        # Get connections
        if connection_id:
            connections = (await db.execute(
                select(InboxConnection).where(
                    InboxConnection.id == uuid.UUID(connection_id),
                    InboxConnection.is_active.is_(True),
                )
            )).scalars().all()
        else:
            connections = (await db.execute(
                select(InboxConnection).where(
                    InboxConnection.status.in_(["active", "error"]),
                    InboxConnection.is_active.is_(True),
                )
            )).scalars().all()

        # Env fallback: auto-create connection if none exist
        if not connections:
            host = os.environ.get("IMAP_HOST", "")
            user = os.environ.get("IMAP_USER", "")
            pw = os.environ.get("IMAP_PASSWORD", "")
            if not (host and user and pw):
                return {"synced": 0, "error": "No inbox configured. Set IMAP_HOST/IMAP_USER/IMAP_PASSWORD or create InboxConnection."}

            org = (await db.execute(select(Organization).limit(1))).scalar_one_or_none()
            if not org:
                return {"synced": 0, "error": "No organization in database"}

            conn = InboxConnection(
                org_id=org.id, email_address=user, display_name="Primary Inbox",
                provider="imap", host=host, port=int(os.environ.get("IMAP_PORT", "993")),
                status="active",
            )
            db.add(conn)
            await db.flush()
            connections = [conn]

        for conn in connections:
            try:
                result = await _sync_one_inbox(db, conn)
                total_ingested += result.get("ingested", 0)
                total_classified += result.get("classified", 0)
                total_drafts += result.get("drafts", 0)

                conn.last_sync_at = datetime.now(timezone.utc)
                conn.consecutive_failures = 0
                conn.status = "active"

                if result.get("error"):
                    errors.append(f"{conn.email_address}: {result['error']}")
            except Exception as e:
                logger.error("inbox_sync_failed conn=%s err=%s", conn.email_address, str(e), exc_info=True)
                conn.consecutive_failures = (conn.consecutive_failures or 0) + 1
                conn.last_error = str(e)[:500]
                if conn.consecutive_failures >= 5:
                    conn.status = "error"
                errors.append(f"{conn.email_address}: {str(e)[:200]}")

        # Send approved auto-replies
        for conn in connections:
            try:
                sr = await send_approved_drafts(db, conn.org_id)
                total_sent += sr.get("sent", 0)
            except Exception as e:
                logger.error("auto_reply_failed org=%s err=%s", conn.org_id, str(e))

        await db.commit()

    return {
        "connections": len(connections),
        "ingested": total_ingested,
        "classified": total_classified,
        "drafts": total_drafts,
        "auto_sent": total_sent,
        "errors": errors or None,
    }


async def _sync_one_inbox(db, conn) -> dict:
    """Sync one IMAP inbox: fetch, dedup, thread, classify, advance, draft."""
    import os
    import hashlib
    import email as email_lib
    import imaplib
    from email.utils import parseaddr, parsedate_to_datetime

    from packages.db.models.email_pipeline import (
        EmailThread, EmailMessage, EmailClassification, SalesStageTransition,
    )
    from packages.db.models.live_execution import CrmContact
    from packages.db.models.expansion_pack2_phase_a import LeadOpportunity
    from packages.db.models.core import Brand
    from apps.api.services.email_classifier import classify_email, compute_stage_transition
    from apps.api.services.reply_engine import create_reply_draft

    host = conn.host or os.environ.get("IMAP_HOST", "")
    port = conn.port or int(os.environ.get("IMAP_PORT", "993"))
    username = conn.email_address or os.environ.get("IMAP_USER", "")
    auth_method = (conn.auth_method or "password").lower()

    if not (host and username):
        return {"error": "IMAP credentials incomplete (host/user)", "ingested": 0}

    # ── Establish authenticated IMAP session ──────────────────────────────
    try:
        mail = imaplib.IMAP4_SSL(host, port)
    except (ConnectionError, TimeoutError, OSError) as e:
        return {"error": f"IMAP connection failed: {str(e)[:200]}", "ingested": 0}

    if auth_method == "xoauth2":
        # OAuth2 SASL flow — used for Microsoft 365 / Gmail
        from packages.clients.microsoft_oauth import ensure_valid_token
        try:
            access_token = await ensure_valid_token(db, conn)
        except Exception as e:
            try:
                mail.logout()
            except Exception:
                pass
            return {"error": f"OAuth token refresh failed: {str(e)[:200]}", "ingested": 0}

        ctrl_a = "\x01"
        auth_string = "user=" + username + ctrl_a + "auth=Bearer " + access_token + ctrl_a + ctrl_a
        try:
            mail.authenticate("XOAUTH2", lambda _: auth_string.encode("utf-8"))
        except imaplib.IMAP4.error as e:
            try:
                mail.logout()
            except Exception:
                pass
            return {"error": f"IMAP XOAUTH2 auth failed: {str(e)[:200]}", "ingested": 0}
    else:
        # Legacy password auth — for Gmail App Passwords, etc.
        password = os.environ.get("IMAP_PASSWORD", "")
        if not password:
            return {"error": "IMAP password missing (auth_method=password)", "ingested": 0}
        try:
            mail.login(username, password)
        except imaplib.IMAP4.error as e:
            return {"error": f"IMAP auth failed: {str(e)[:200]}", "ingested": 0}

    mail.select("INBOX")
    _, message_numbers = mail.search(None, "UNSEEN")
    nums = message_numbers[0].split() if message_numbers[0] else []

    ingested = classified = drafts = 0
    our_email = conn.email_address.lower()

    for num in nums:
        try:
            _, msg_data = mail.fetch(num, "(RFC822)")
            raw = msg_data[0][1]
            msg = email_lib.message_from_bytes(raw)

            mid = msg.get("Message-ID", "") or f"gen-{hashlib.sha256(raw[:1000]).hexdigest()[:32]}"

            # Dedup
            exists = (await db.execute(
                select(EmailMessage.id).where(EmailMessage.provider_message_id == mid)
            )).scalar_one_or_none()
            if exists:
                continue

            from_name, from_email = parseaddr(msg.get("From", ""))
            to_list = [parseaddr(a)[1] for a in (msg.get("To", "")).split(",") if parseaddr(a)[1]]
            cc_list = [parseaddr(a)[1] for a in (msg.get("Cc", "") or "").split(",") if parseaddr(a)[1]]
            subject = msg.get("Subject", "(no subject)")
            in_reply_to = msg.get("In-Reply-To", "")
            references = msg.get("References", "")
            direction = "outbound" if from_email.lower() == our_email else "inbound"

            try:
                message_date = parsedate_to_datetime(msg.get("Date", ""))
            except Exception:
                message_date = datetime.now(timezone.utc)

            body_text = body_html = ""
            if msg.is_multipart():
                for part in msg.walk():
                    pl = part.get_payload(decode=True)
                    if not pl:
                        continue
                    dec = pl.decode("utf-8", errors="replace")
                    if part.get_content_type() == "text/plain" and not body_text:
                        body_text = dec
                    elif part.get_content_type() == "text/html" and not body_html:
                        body_html = dec
            else:
                pl = msg.get_payload(decode=True)
                if pl:
                    body_text = pl.decode("utf-8", errors="replace")

            snippet = (body_text or "")[:300].replace("\n", " ").strip()

            # Thread resolution
            import re
            _clean_subj = re.sub(r"^(Re|Fwd|Fw)\s*:\s*", "", subject, flags=re.IGNORECASE).strip()
            _subj_hash = hashlib.sha256(_clean_subj.encode()).hexdigest()[:24]
            if references:
                thread_key = references.strip().split()[0]
            elif in_reply_to:
                thread_key = in_reply_to.strip()
            else:
                thread_key = "subj:" + _subj_hash

            thread = (await db.execute(
                select(EmailThread).where(
                    EmailThread.inbox_connection_id == conn.id,
                    EmailThread.provider_thread_id == thread_key,
                )
            )).scalar_one_or_none()

            if not thread:
                thread = EmailThread(
                    inbox_connection_id=conn.id, org_id=conn.org_id,
                    provider_thread_id=thread_key, subject=subject,
                    direction=direction, from_email=from_email, from_name=from_name,
                    to_emails=to_list, first_message_at=message_date,
                    last_message_at=message_date, sales_stage="new_lead",
                    reply_status="pending", message_count=0,
                )
                db.add(thread)
                await db.flush()

            thread.message_count = (thread.message_count or 0) + 1
            thread.last_message_at = message_date
            if direction == "inbound":
                thread.last_inbound_at = message_date
                if thread.direction == "outbound":
                    thread.direction = "mixed"

            email_msg = EmailMessage(
                thread_id=thread.id, inbox_connection_id=conn.id, org_id=conn.org_id,
                provider_message_id=mid, in_reply_to=in_reply_to, references=references,
                direction=direction, from_email=from_email, from_name=from_name,
                to_emails=to_list, cc_emails=cc_list, subject=subject,
                body_text=body_text, body_html=body_html, snippet=snippet,
                message_date=message_date,
                has_attachments=any(p.get_content_disposition() == "attachment" for p in msg.walk()) if msg.is_multipart() else False,
                size_bytes=len(raw),
            )
            db.add(email_msg)
            await db.flush()

            conn.messages_synced_total = (conn.messages_synced_total or 0) + 1
            ingested += 1

            # Link contact
            contact = (await db.execute(
                select(CrmContact).where(CrmContact.email == from_email.lower()).limit(1)
            )).scalar_one_or_none()

            if not contact:
                brand = (await db.execute(select(Brand).limit(1))).scalar_one_or_none()
                if brand:
                    contact = CrmContact(
                        brand_id=brand.id, email=from_email.lower(), name=from_name or "",
                        source="email_inbound", lifecycle_stage="lead", sync_status="synced",
                    )
                    db.add(contact)
                    await db.flush()

            if contact and not thread.contact_id:
                thread.contact_id = contact.id

            # Link lead
            if contact and not thread.lead_opportunity_id:
                lead = (await db.execute(
                    select(LeadOpportunity).where(
                        LeadOpportunity.is_active.is_(True),
                        LeadOpportunity.message_text.ilike(f"%{contact.email}%"),
                    ).limit(1)
                )).scalar_one_or_none()
                if lead:
                    thread.lead_opportunity_id = lead.id

            # Classify + advance + draft (inbound only)
            if direction == "inbound":
                cls_result = classify_email(subject, body_text or snippet)

                ec = EmailClassification(
                    message_id=email_msg.id, thread_id=thread.id,
                    intent=cls_result.intent, confidence=cls_result.confidence,
                    rationale=cls_result.rationale,
                    secondary_intent=cls_result.secondary_intent,
                    secondary_confidence=cls_result.secondary_confidence,
                    classifier_version="keyword_v1", reply_mode=cls_result.reply_mode,
                )
                db.add(ec)
                await db.flush()
                thread.latest_classification = cls_result.intent
                classified += 1

                # Stage transition
                current = thread.sales_stage or "new_lead"
                new_stage = compute_stage_transition(current, cls_result.intent)
                if new_stage:
                    thread.sales_stage = new_stage
                    if thread.lead_opportunity_id:
                        lead = (await db.execute(
                            select(LeadOpportunity).where(LeadOpportunity.id == thread.lead_opportunity_id)
                        )).scalar_one_or_none()
                        if lead:
                            lead.sales_stage = new_stage
                    db.add(SalesStageTransition(
                        thread_id=thread.id, lead_opportunity_id=thread.lead_opportunity_id,
                        org_id=conn.org_id, from_stage=current, to_stage=new_stage,
                        trigger_type="email_inbound", trigger_id=str(email_msg.id),
                        rationale=f"{cls_result.intent} ({cls_result.confidence:.0%})",
                    ))

                # Reply if we were contacted first
                if in_reply_to and current == "contacted" and not new_stage:
                    thread.sales_stage = "replied"

                # Draft reply
                if cls_result.intent not in ("unknown", "escalation", "unsubscribe"):
                    lead_first = (from_name.split()[0] if from_name else "")
                    lead_co = ""
                    if contact:
                        lead_first = (contact.name or "").split()[0] or lead_first
                        lead_co = (contact.metadata_json or {}).get("company", "")
                    dr = await create_reply_draft(
                        db, thread_id=thread.id, message_id=email_msg.id,
                        classification=cls_result, org_id=conn.org_id,
                        to_email=from_email, first_name=lead_first, company=lead_co,
                        thread_subject=subject, classification_id=ec.id,
                    )
                    drafts += 1
                elif cls_result.intent == "unsubscribe":
                    # Auto-handle: mark contact as unsubscribed
                    if contact:
                        contact.lifecycle_stage = "unsubscribed"
                        contact.tags_json = list(set((contact.tags_json or []) + ["unsubscribed"]))

            await db.flush()

        except Exception as e:
            logger.error("msg_process_error num=%s err=%s", num, str(e), exc_info=True)

    try:
        mail.close()
        mail.logout()
    except Exception:
        pass

    return {"ingested": ingested, "classified": classified, "drafts": drafts}


@shared_task(name="workers.email_campaign_worker.tasks.sync_all_inboxes", base=TrackedTask)
def sync_all_inboxes():
    """Beat entry: sync all active inbox connections, classify, draft replies."""
    return asyncio.run(_sync_inbox_impl())


@shared_task(name="workers.email_campaign_worker.tasks.sync_inbox", base=TrackedTask)
def sync_inbox(connection_id: str):
    """Sync a specific inbox connection."""
    return asyncio.run(_sync_inbox_impl(connection_id))
