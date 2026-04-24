"""Reply Ingestion — detects, classifies, and acts on email replies.

Closes the outreach loop: send email → detect reply → classify intent →
advance deal stage → create next action.

Supports two ingestion modes:
1. IMAP polling: connects to inbox, reads unread replies, matches to outreach
2. Webhook: receives forwarded replies via API endpoint

Reply classifications:
- interested: positive signal, advance deal stage
- meeting_request: schedule signal, create meeting action
- question: needs response, create follow-up action
- not_interested: negative signal, mark deal as lost/cold
- out_of_office: neutral, reschedule follow-up
- unclassifiable: manual review needed
"""

from __future__ import annotations

import os
import re
import uuid

import structlog
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_action, emit_event
from packages.db.models.offers import SponsorOpportunity, SponsorProfile
from packages.db.models.saas_metrics import HighTicketDeal

logger = structlog.get_logger()

# Classification patterns (keyword-based, fast, no ML dependency)
INTERESTED_PATTERNS = [
    r"(?i)\b(interested|love to|sounds great|let\'s do|count me in|i\'m in|sign me up|"
    r"let\'s chat|let\'s talk|would love|happy to|excited|looking forward)\b",
]
MEETING_PATTERNS = [
    r"(?i)\b(schedule|calendar|meet|call|zoom|availability|free on|available|"
    r"book a time|set up a call|hop on a call|quick chat)\b",
]
NOT_INTERESTED_PATTERNS = [
    r"(?i)\b(not interested|no thanks|pass|not a fit|not right now|"
    r"unsubscribe|remove me|don\'t contact|not looking)\b",
]
OOO_PATTERNS = [
    r"(?i)\b(out of office|on vacation|away from|auto.?reply|returning on|"
    r"limited access|away until)\b",
]
QUESTION_PATTERNS = [
    r"(?i)\b(how much|what\'s the|can you|could you|pricing|rates|"
    r"more info|details|tell me more|what does|how does)\b",
]


def classify_reply(subject: str, body: str) -> dict:
    """Classify a reply by intent. Returns classification + confidence."""
    text = f"{subject} {body}".lower()

    for pattern in NOT_INTERESTED_PATTERNS:
        if re.search(pattern, text):
            return {"classification": "not_interested", "confidence": 0.85}

    for pattern in OOO_PATTERNS:
        if re.search(pattern, text):
            return {"classification": "out_of_office", "confidence": 0.90}

    for pattern in MEETING_PATTERNS:
        if re.search(pattern, text):
            return {"classification": "meeting_request", "confidence": 0.80}

    for pattern in INTERESTED_PATTERNS:
        if re.search(pattern, text):
            return {"classification": "interested", "confidence": 0.75}

    for pattern in QUESTION_PATTERNS:
        if re.search(pattern, text):
            return {"classification": "question", "confidence": 0.70}

    return {"classification": "unclassifiable", "confidence": 0.30}


async def ingest_reply(
    db: AsyncSession,
    org_id: uuid.UUID,
    *,
    sender_email: str,
    subject: str,
    body: str,
    brand_id: uuid.UUID | None = None,
    in_reply_to: str | None = None,
) -> dict:
    """Ingest an email reply: classify it, match to outreach, advance deal stage.

    This is the core function. Called by IMAP poller or webhook endpoint.
    """
    # Classify the reply
    classification = classify_reply(subject, body)
    reply_type = classification["classification"]
    confidence = classification["confidence"]

    # Try to match reply to a sponsor outreach
    matched_sponsor = None
    matched_deal = None

    if sender_email:
        # Match by sender email → sponsor profile
        sponsor = (
            await db.execute(
                select(SponsorProfile)
                .where(
                    SponsorProfile.contact_email == sender_email,
                )
                .limit(1)
            )
        ).scalar_one_or_none()

        if sponsor:
            matched_sponsor = sponsor
            brand_id = brand_id or sponsor.brand_id

            # Find active deal for this sponsor
            deal = (
                await db.execute(
                    select(SponsorOpportunity)
                    .where(
                        SponsorOpportunity.sponsor_id == sponsor.id,
                    )
                    .order_by(desc(SponsorOpportunity.created_at))
                    .limit(1)
                )
            ).scalar_one_or_none()
            if deal:
                matched_deal = deal

    # Try to match to a service deal by customer email
    matched_service_deal = None
    if sender_email and not matched_sponsor:
        htd = (
            await db.execute(
                select(HighTicketDeal)
                .where(
                    HighTicketDeal.customer_email == sender_email,
                )
                .order_by(desc(HighTicketDeal.created_at))
                .limit(1)
            )
        ).scalar_one_or_none()
        if htd:
            matched_service_deal = htd
            brand_id = brand_id or htd.brand_id

    # ── Advance deal stage based on classification ──
    stage_changes = []

    if reply_type == "interested" and matched_deal:
        if matched_deal.status in ("prospect", "outreach"):
            old = matched_deal.status
            matched_deal.status = "negotiation"
            stage_changes.append(f"Sponsor deal '{matched_deal.title}': {old} → negotiation")

    elif reply_type == "meeting_request" and matched_deal:
        if matched_deal.status in ("prospect", "outreach", "negotiation"):
            old = matched_deal.status
            matched_deal.status = "negotiation"
            stage_changes.append(f"Sponsor deal '{matched_deal.title}': {old} → negotiation (meeting requested)")

    elif reply_type == "interested" and matched_service_deal:
        if matched_service_deal.stage in ("awareness", "interest", "consideration"):
            old = matched_service_deal.stage
            matched_service_deal.stage = "proposal" if old == "consideration" else "consideration"
            stage_changes.append(
                f"Service deal '{matched_service_deal.customer_name}': {old} → {matched_service_deal.stage}"
            )

    elif reply_type == "not_interested":
        if matched_deal:
            old = matched_deal.status
            matched_deal.status = "lost"
            stage_changes.append(f"Sponsor deal '{matched_deal.title}': {old} → lost")
        if matched_service_deal:
            old = matched_service_deal.stage
            matched_service_deal.stage = "closed_lost"
            stage_changes.append(f"Service deal '{matched_service_deal.customer_name}': {old} → closed_lost")

    # ── AUTO-CREATE floor-tier proposal when a cold sponsor_target
    # replies with warm intent (interested | meeting_request).
    # Matches by lower(contact_info->>'email').  Idempotent: skipped
    # if any active proposal already carries this sponsor_target_id
    # in extra_json.
    proposal_created_id = None
    if reply_type in ("interested", "meeting_request") and sender_email:
        from sqlalchemy import text as _text

        target_row = (
            await db.execute(
                _text(
                    "SELECT id, brand_id, target_company_name, contact_info "
                    "FROM sponsor_targets WHERE is_active=true "
                    "AND lower(contact_info->>'email') = lower(:e) LIMIT 1"
                ),
                {"e": sender_email},
            )
        ).first()
        if target_row:
            target_id, target_brand_id, target_company, target_ci = target_row
            from packages.db.models.proposals import Proposal

            existing = (
                await db.execute(
                    select(Proposal)
                    .where(
                        Proposal.is_active.is_(True),
                        Proposal.extra_json["sponsor_target_id"].astext == str(target_id),
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if existing is None:
                from apps.api.services.proposals_service import (
                    LineItemInput,
                    create_proposal,
                )

                company = target_company or "your business"
                name = (target_ci or {}).get("name", "") or ""
                prop = await create_proposal(
                    db,
                    org_id=org_id,
                    brand_id=brand_id or target_brand_id,
                    recipient_email=sender_email,
                    recipient_name=name[:255],
                    recipient_company=company[:255],
                    title=f"ProofHook \u2014 Signal Entry for {company}"[:500],
                    summary=(
                        f"Signal Entry package auto-created from {reply_type} "
                        f"reply to cold outreach. Operator to review + send."
                    ),
                    avenue_slug="b2b_services",
                    package_slug="signal_entry",
                    line_items=[
                        LineItemInput(
                            description="Signal Entry \u2014 landing page + ad hook + proof layer",
                            unit_amount_cents=150000,
                            quantity=1,
                            currency="usd",
                            position=0,
                        )
                    ],
                    created_by_actor_type="system",
                    created_by_actor_id="reply_ingestion.warm_auto",
                    extra_json={
                        "sponsor_target_id": str(target_id),
                        "reply_type": reply_type,
                        "auto_created_from_reply": True,
                    },
                )
                proposal_created_id = str(prop.id)

    # ── Create next action based on classification ──
    action_created = None

    if reply_type == "interested":
        action_created = await emit_action(
            db,
            org_id=org_id,
            action_type="send_proposal" if matched_service_deal else "advance_sponsor_deal",
            title=f"Reply: interested — {sender_email[:40]}",
            description=f"Positive reply from {sender_email}. {subject[:100]}",
            category="monetization",
            priority="high",
            brand_id=brand_id,
            source_module="reply_ingestion",
            action_payload={
                "reply_type": reply_type,
                "sender": sender_email,
                "confidence": confidence,
                "body_preview": body[:200],
            },
        )

    elif reply_type == "meeting_request":
        action_created = await emit_action(
            db,
            org_id=org_id,
            action_type="schedule_meeting",
            title=f"Meeting request — {sender_email[:40]}",
            description=f"Reply requests a meeting. {subject[:100]}",
            category="monetization",
            priority="high",
            brand_id=brand_id,
            source_module="reply_ingestion",
            action_payload={
                "reply_type": reply_type,
                "sender": sender_email,
                "confidence": confidence,
                "body_preview": body[:200],
            },
        )

    elif reply_type == "question":
        action_created = await emit_action(
            db,
            org_id=org_id,
            action_type="respond_to_question",
            title=f"Question from {sender_email[:40]}",
            description=f"Reply contains a question. {subject[:100]}",
            category="monetization",
            priority="medium",
            brand_id=brand_id,
            source_module="reply_ingestion",
            action_payload={
                "reply_type": reply_type,
                "sender": sender_email,
                "confidence": confidence,
                "body_preview": body[:200],
            },
        )

    elif reply_type == "out_of_office":
        action_created = await emit_action(
            db,
            org_id=org_id,
            action_type="reschedule_follow_up",
            title=f"OOO: {sender_email[:40]} — reschedule",
            description="Auto-reply detected. Reschedule follow-up.",
            category="monetization",
            priority="low",
            brand_id=brand_id,
            source_module="reply_ingestion",
        )

    elif reply_type == "not_interested":
        # No action needed — deal already marked lost
        pass

    else:
        action_created = await emit_action(
            db,
            org_id=org_id,
            action_type="review_reply",
            title=f"Unclassified reply — {sender_email[:40]}",
            description=f"Could not auto-classify. Manual review needed. {subject[:100]}",
            category="monetization",
            priority="medium",
            brand_id=brand_id,
            source_module="reply_ingestion",
            action_payload={"reply_type": reply_type, "sender": sender_email, "body_preview": body[:300]},
        )

    # Emit event
    await emit_event(
        db,
        domain="monetization",
        event_type=f"reply.{reply_type}",
        summary=f"Reply from {sender_email[:30]}: {reply_type} (confidence {confidence:.0%})",
        org_id=org_id,
        brand_id=brand_id,
        details={
            "sender": sender_email,
            "reply_type": reply_type,
            "confidence": confidence,
            "stage_changes": stage_changes,
            "matched_sponsor": matched_sponsor.sponsor_name if matched_sponsor else None,
            "matched_deal": matched_deal.title if matched_deal else None,
        },
    )

    await db.flush()

    # Phase 3: emit analytics event for reply received.
    try:
        from packages.clients.analytics_emitter import emit_analytics_event

        _brand_id = brand_id
        if _brand_id is None and sender_email:
            from sqlalchemy import text as _atxt

            _brow = (
                await db.execute(
                    _atxt(
                        "SELECT brand_id FROM sponsor_targets WHERE is_active=true "
                        "AND lower(contact_info->>'email') = lower(:e) LIMIT 1"
                    ),
                    {"e": sender_email},
                )
            ).first()
            if _brow:
                _brand_id = _brow[0]
        if _brand_id is not None:
            await emit_analytics_event(
                db,
                brand_id=_brand_id,
                source="reply_ingestion",
                event_type=f"reply.{reply_type}",
                metric_value=1.0,
                truth_level="verified",
                raw_json={
                    "sender": sender_email,
                    "confidence": confidence,
                    "proposal_created_id": proposal_created_id,
                },
            )
            await db.flush()
    except Exception as _aexc:
        import structlog as _sl

        _sl.get_logger().warning("analytics_emit_failed", error=str(_aexc)[:200])

    return {
        "classification": reply_type,
        "confidence": confidence,
        "sender": sender_email,
        "proposal_created_id": proposal_created_id,
        "matched_sponsor": matched_sponsor.sponsor_name if matched_sponsor else None,
        "matched_deal": matched_deal.title if matched_deal else None,
        "matched_service_deal": matched_service_deal.customer_name if matched_service_deal else None,
        "stage_changes": stage_changes,
        "action_created": str(action_created.id) if action_created else None,
    }


async def poll_imap_inbox(db: AsyncSession, org_id: uuid.UUID) -> dict:
    """Poll IMAP inbox for unread replies. Requires IMAP credentials."""
    import email as email_lib
    import imaplib

    host = os.getenv("IMAP_HOST", "")
    user = os.getenv("IMAP_USER", "")
    password = os.getenv("IMAP_PASSWORD", "")

    if not host or not user or not password:
        return {
            "configured": False,
            "error": "IMAP_HOST/IMAP_USER/IMAP_PASSWORD not set",
            "message": "Configure IMAP credentials to enable automatic reply ingestion",
        }

    try:
        mail = imaplib.IMAP4_SSL(host)
        mail.login(user, password)
        mail.select("INBOX")

        _, message_numbers = mail.search(None, "UNSEEN")
        nums = message_numbers[0].split()

        ingested = 0
        for num in nums[:50]:  # Process max 50 per poll
            _, msg_data = mail.fetch(num, "(RFC822)")
            msg = email_lib.message_from_bytes(msg_data[0][1])

            sender = email_lib.utils.parseaddr(msg["From"])[1]
            subject = msg["Subject"] or ""
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

            await ingest_reply(db, org_id, sender_email=sender, subject=subject, body=body)
            ingested += 1

        mail.logout()
        await db.commit()
        return {"configured": True, "emails_processed": ingested, "total_unread": len(nums)}

    except Exception as e:
        logger.error("imap_poll.failed", error=str(e))
        return {"configured": True, "error": str(e)[:200]}
