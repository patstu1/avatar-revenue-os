"""AI Reply Engine — generates draft replies based on thread context, deal state, and package catalog.

Reply modes:
- auto_send: low-risk operational (proof requests, scheduling nudges, unsubscribe confirmation)
- draft: sales-critical (warm interest, pricing, objections, negotiation)
- escalate: high-risk (legal, angry, enterprise, ambiguous)

Uses existing AutomationExecutionPolicy confidence thresholds.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.email_classifier import ClassificationResult
from packages.clients.email_templates import PACKAGES

logger = logging.getLogger(__name__)


# ── Reply templates by intent ────────────────────────────────────────────

def _build_reply_body(
    intent: str,
    first_name: str,
    company: str,
    thread_subject: str,
    package_slug: str | None = None,
    sender_name: str = "Patrick",
) -> dict[str, str]:
    """Build reply text + subject based on classified intent.

    Returns dict with 'subject', 'body_text', 'body_html', 'package_offered'.
    """
    pkg = PACKAGES.get(package_slug or "ugc-starter-pack", PACKAGES["ugc-starter-pack"])
    company_ref = company or "your brand"
    greeting = f"Hi {first_name}," if first_name else "Hi,"

    # Re: threading
    re_subject = thread_subject if thread_subject.startswith("Re:") else f"Re: {thread_subject}"

    templates = {
        "warm_interest": {
            "body": (
                f"{greeting}\n\n"
                f"Great to hear from you. Happy to walk you through what we'd build for {company_ref}.\n\n"
                f"The package I'd recommend based on what I'm seeing is our {pkg['name']} ({pkg['price']}). "
                f"It includes:\n\n"
                + "\n".join(f"  - {b}" for b in pkg["bullets"])
                + f"\n\nWant me to put together 2 sample angles for {company_ref}? "
                f"Or if you'd prefer, we can hop on a quick call.\n\n"
                f"{sender_name}\nProofHook"
            ),
            "package_offered": package_slug or "ugc-starter-pack",
        },
        "proof_request": {
            "body": (
                f"{greeting}\n\n"
                f"Absolutely. Here are a few examples of what we've built for brands in a similar space:\n\n"
                f"  - Short-form hook variations with strong CTAs\n"
                f"  - UGC-style creative that drives engagement\n"
                f"  - Performance creative built for paid media rotation\n\n"
                f"I can also put together 2 custom angles specifically for {company_ref} if you'd like to see "
                f"what that would look like.\n\n"
                f"Let me know.\n\n"
                f"{sender_name}\nProofHook"
            ),
            "package_offered": None,
        },
        "pricing_request": {
            "body": (
                f"{greeting}\n\n"
                f"Good question. Here's how our packages break down:\n\n"
                f"  - UGC Starter Pack — $1,500 (one-time, 4 assets, 7-day delivery)\n"
                f"  - Growth Content Pack — from $2,500/mo (8-12 assets/month)\n"
                f"  - Performance Creative Pack — from $4,500/mo (12-20 assets + optimization)\n"
                f"  - Full Creative Retainer — from $7,500/mo (full creative partner)\n\n"
                f"Based on what I know about {company_ref}, I'd suggest starting with the {pkg['name']} "
                f"({pkg['price']}) and scaling from there.\n\n"
                f"Want to talk through which one fits best?\n\n"
                f"{sender_name}\nProofHook"
            ),
            "package_offered": package_slug or "ugc-starter-pack",
        },
        "objection": {
            "body": (
                f"{greeting}\n\n"
                f"Totally understand. Most brands we work with had similar concerns before they started.\n\n"
                f"The reason our starter pack works well as a first step is that it's a one-time $1,500 commitment "
                f"— no retainer, no lock-in. You get 4 usable assets in 7 days and can judge the quality before "
                f"deciding anything else.\n\n"
                f"No pressure either way. If the timing feels better down the road, I'm here.\n\n"
                f"{sender_name}\nProofHook"
            ),
            "package_offered": "ugc-starter-pack",
        },
        "negotiation": {
            "body": (
                f"{greeting}\n\n"
                f"Appreciate you being upfront about that. Let me think about what we can do.\n\n"
                f"I'll put together a few options that might work better for your situation "
                f"and send them over. Give me a day.\n\n"
                f"{sender_name}\nProofHook"
            ),
            "package_offered": None,
        },
        "meeting_request": {
            "body": (
                f"{greeting}\n\n"
                f"Works for me. I'm generally free weekday afternoons — "
                f"pick a time that works and I'll make it happen.\n\n"
                f"Or if easier, just reply with 2-3 times and I'll confirm.\n\n"
                f"{sender_name}\nProofHook"
            ),
            "package_offered": None,
        },
        "not_now": {
            "body": (
                f"{greeting}\n\n"
                f"No worries at all. I'll check back in a few weeks.\n\n"
                f"If anything changes before then, I'm here.\n\n"
                f"{sender_name}\nProofHook"
            ),
            "package_offered": None,
        },
        "unsubscribe": {
            "body": (
                f"{greeting}\n\n"
                f"Done — you won't hear from me again. "
                f"If you ever want to revisit, I'm at hello@proofhook.com.\n\n"
                f"{sender_name}\nProofHook"
            ),
            "package_offered": None,
        },
        "support": {
            "body": (
                f"{greeting}\n\n"
                f"Thanks for reaching out. Let me look into this and get back to you shortly.\n\n"
                f"{sender_name}\nProofHook"
            ),
            "package_offered": None,
        },
        "intake_reply": {
            "body": (
                f"{greeting}\n\n"
                f"Got it — thanks for sending this over. I'll review everything and "
                f"follow up once we're ready to kick off production.\n\n"
                f"{sender_name}\nProofHook"
            ),
            "package_offered": None,
        },
        "revision_request": {
            "body": (
                f"{greeting}\n\n"
                f"Noted. I'll get the revisions started and send an updated version soon.\n\n"
                f"{sender_name}\nProofHook"
            ),
            "package_offered": None,
        },
        "payment_question": {
            "body": (
                f"{greeting}\n\n"
                f"Let me check on that and get back to you with the details.\n\n"
                f"{sender_name}\nProofHook"
            ),
            "package_offered": None,
        },
        "referral": {
            "body": (
                f"{greeting}\n\n"
                f"Really appreciate the referral. Happy to take a look and see if we'd be a good fit. "
                f"Feel free to intro them directly or have them reach out to hello@proofhook.com.\n\n"
                f"{sender_name}\nProofHook"
            ),
            "package_offered": None,
        },
    }

    # Fallback for unknown/escalation — no auto-reply
    default = {
        "body": (
            f"{greeting}\n\n"
            f"Thanks for your message. I'll review this and get back to you.\n\n"
            f"{sender_name}\nProofHook"
        ),
        "package_offered": None,
    }

    template = templates.get(intent, default)
    body_text = template["body"]

    # Convert to minimal HTML
    body_html = "<div style='font-family:-apple-system,sans-serif;font-size:14px;line-height:1.6;color:#222;'>"
    for line in body_text.split("\n\n"):
        body_html += f"<p style='margin:0 0 14px;'>{line.replace(chr(10), '<br>')}</p>"
    body_html += "</div>"

    return {
        "subject": re_subject,
        "body_text": body_text,
        "body_html": body_html,
        "package_offered": template.get("package_offered"),
    }


# ── Draft creation ───────────────────────────────────────────────────────


async def create_reply_draft(
    db: AsyncSession,
    *,
    thread_id: uuid.UUID,
    message_id: uuid.UUID,
    classification: ClassificationResult,
    org_id: uuid.UUID,
    to_email: str,
    first_name: str = "",
    company: str = "",
    thread_subject: str = "",
    package_slug: str | None = None,
    classification_id: uuid.UUID | None = None,
) -> dict:
    """Create an EmailReplyDraft based on classification.

    If reply_mode is auto_send and confidence is high enough, the draft
    is created with status='approved' for immediate sending.
    Otherwise it's 'pending' for operator review.
    """
    from packages.db.models.email_pipeline import EmailReplyDraft

    reply = _build_reply_body(
        intent=classification.intent,
        first_name=first_name,
        company=company,
        thread_subject=thread_subject,
        package_slug=package_slug,
    )

    # Determine initial status
    if classification.reply_mode == "auto_send" and classification.confidence >= 0.75:
        status = "approved"
    elif classification.reply_mode == "escalate":
        status = "pending"  # needs human review
    else:
        status = "pending"

    draft = EmailReplyDraft(
        thread_id=thread_id,
        message_id=message_id,
        classification_id=classification_id,
        org_id=org_id,
        to_email=to_email,
        subject=reply["subject"],
        body_text=reply["body_text"],
        body_html=reply["body_html"],
        reply_mode=classification.reply_mode,
        status=status,
        confidence=classification.confidence,
        reasoning=classification.rationale,
        package_offered=reply.get("package_offered"),
        model_used="template_v1",
    )

    db.add(draft)
    await db.flush()

    logger.info(
        "reply_draft_created thread=%s intent=%s mode=%s status=%s",
        thread_id, classification.intent, classification.reply_mode, status,
    )

    return {
        "draft_id": str(draft.id),
        "reply_mode": classification.reply_mode,
        "status": status,
        "intent": classification.intent,
        "to_email": to_email,
        "subject": reply["subject"],
        "package_offered": reply.get("package_offered"),
    }


async def send_approved_drafts(db: AsyncSession, org_id: uuid.UUID) -> dict:
    """Send all approved drafts that haven't been sent yet.

    Called by the sync worker after processing inbound emails.
    """
    from packages.db.models.email_pipeline import EmailReplyDraft
    from packages.clients.external_clients import SmtpEmailClient

    drafts = (await db.execute(
        select(EmailReplyDraft).where(
            EmailReplyDraft.org_id == org_id,
            EmailReplyDraft.status == "approved",
            EmailReplyDraft.is_active.is_(True),
        )
    )).scalars().all()

    sent = 0
    failed = 0

    smtp = SmtpEmailClient()
    if not smtp._is_configured():
        return {"sent": 0, "failed": 0, "error": "SMTP not configured"}

    for draft in drafts:
        try:
            result = await smtp.send_email(
                to_email=draft.to_email,
                subject=draft.subject,
                body_html=draft.body_html or "",
                body_text=draft.body_text,
            )
            if result.get("success"):
                draft.status = "sent"
                draft.sent_at = datetime.now(timezone.utc)
                sent += 1
            else:
                draft.error_message = result.get("error", "unknown")
                failed += 1
        except Exception as e:
            draft.error_message = str(e)[:500]
            failed += 1

    await db.flush()
    return {"sent": sent, "failed": failed, "total_drafts": len(drafts)}
