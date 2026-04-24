"""AI Reply Engine — generates draft replies based on thread context, deal state, and package catalog.

Reply modes are chosen by `apps.api.services.reply_policy.decide_reply_mode`,
which runs a 10-step decision engine (automation loop → forced escalation →
classifier escalation → forced draft → allowlist → confidence → template →
cooldown → auto-send). Every decision is persisted as audit on
email_reply_drafts.decision_trace.

create_reply_draft delegates all decision logic to the policy engine and
only handles: template rendering, draft persistence, and returning the
result dict to the caller.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.email_classifier import ClassificationResult
from apps.api.services.package_recommender import (
    PackageRecommendation,
    recommend_package,
)
from apps.api.services.reply_policy import (
    DecisionTrace,
    ReplyPolicySettings,
    decide_reply_mode,
    get_reply_policy,
    is_standard_template_intent,
)
from packages.clients.email_templates import PACKAGES, package_checkout_url

logger = logging.getLogger(__name__)


async def _recent_auto_reply_exists(
    db: AsyncSession, thread_id: uuid.UUID, cooldown_hours: int = 24
) -> bool:
    """True if thread already has an approved/sent auto-reply in the cooldown window."""
    from packages.db.models.email_pipeline import EmailReplyDraft

    cutoff = datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)
    existing = (await db.execute(
        select(EmailReplyDraft.id).where(
            EmailReplyDraft.thread_id == thread_id,
            EmailReplyDraft.status.in_(["approved", "sent"]),
            EmailReplyDraft.reply_mode == "auto_send",
            EmailReplyDraft.created_at >= cutoff,
        ).limit(1)
    )).first()
    return existing is not None


# ── Reply templates by intent ────────────────────────────────────────────

def _build_reply_body(
    intent: str,
    first_name: str,
    company: str,
    thread_subject: str,
    package_slug: str | None = None,
    sender_name: str = "Patrick",
    *,
    recommendation: PackageRecommendation | None = None,
    settings: ReplyPolicySettings | None = None,
) -> dict[str, str]:
    """Build reply text + subject based on classified intent.

    Returns dict with 'subject', 'body_text', 'body_html', 'package_offered',
    'preview_fallback_used', 'speed_language_mode'.

    POLICY — package-first, no-call, no-free-work (ProofHook Revenue-Ops doctrine):

    1. SELL THE PACKAGE BY DEFAULT.
       The machine recommends the best-fit package (via PackageRecommendation)
       and sends the lead the secure checkout link. It does NOT offer "2 sample
       angles" / "2 test runs" / "free pre-work" unless `free_preview_enabled=True`
       AND the intent is in `preview_fallback_allowed_intents` (default: proof_request,
       objection only). Even then, the framing is "2 recommended angles" or "2
       creative directions" — NEVER "samples" or "test runs" or "free work".

    2. NO CALLS / NO MEETINGS / NO WALKTHROUGHS.
       Every template is no-call. Any explicit call ask is caught upstream by
       the FORCED_DRAFT `call_request` pattern in reply_policy.py. The
       `meeting_request` template below renders only for human-reviewed drafts
       and soft-redirects to the no-call funnel.

    3. SIGNAL-BASED PACKAGE ROUTING.
       The `recommendation` argument is the output of package_recommender.recommend_package
       — it has already picked the best-fit package from the full catalog based
       on lead signals (paid-media, recurring-need, funnel-weakness, launch,
       etc). We NEVER hardcode ugc-starter-pack as the default in this function.

    4. BROAD-MARKET POSITIONING.
       Inbound replies never name a vertical ("beauty brands", "fitness brands",
       "software brands"). Niche framing is tactical outbound-only.

    5. SPEED-LANGUAGE SUPPRESSED BY DEFAULT.
       "24-48 hours" and "7 days" copy is only emitted when
       `settings.front_end_speed_language_mode != "none"`. Default is silent.

    6. PLAIN TEXT ONLY.
       body_html is intentionally empty. Empty body_html triggers
       contentType=Text in microsoft_oauth.send_via_graph_sendmail, so Graph
       posts a pure text/plain message. This is the biggest factor in landing
       in the primary inbox vs Gmail Promotions for cold B2B replies.
    """
    settings = settings or ReplyPolicySettings()

    # ── Resolve the recommended package ─────────────────────────────────────
    # Backwards-compat: if the caller passes package_slug but no recommendation,
    # we still honor the explicit slug. If neither is passed, fall back to the
    # signal-less default (growth-content-pack — NOT the starter pack).
    if recommendation is not None:
        pkg_slug = recommendation.slug
    elif package_slug:
        pkg_slug = package_slug
    else:
        pkg_slug = "growth-content-pack"

    pkg = PACKAGES.get(pkg_slug, PACKAGES["growth-content-pack"])
    checkout_url = package_checkout_url(pkg_slug)
    company_ref = company or "your brand"
    greeting = f"Hi {first_name}," if first_name else "Hi,"

    # Re: threading
    re_subject = thread_subject if thread_subject.startswith("Re:") else f"Re: {thread_subject}"

    # ── Preview-fallback gate ──────────────────────────────────────────────
    # Default: OFF. Only fires when the operator has flipped `free_preview_enabled`
    # to True AND the intent is in the allowlist. Even when allowed, the
    # framing is "2 recommended angles" / "2 creative directions" — never
    # "samples" or "free work".
    preview_allowed = (
        settings.free_preview_enabled
        and intent in settings.preview_fallback_allowed_intents
    )
    preview_used = False
    preview_framing = ""

    # ── Rationale glue (lead-specific one-liner) ───────────────────────────
    if recommendation and recommendation.rationale:
        rationale_short = _shorten_rationale(recommendation.rationale, company_ref)
    else:
        rationale_short = (
            f"based on what you're describing, the {pkg['name']} is the right fit for {company_ref}"
        )

    # ── Template set — EVERY default template is package-first ────────────

    templates: dict[str, dict] = {
        "warm_interest": {
            "body": _compose_package_first_body(
                greeting=greeting,
                opener="Appreciate you reaching out.",
                rationale=rationale_short,
                pkg=pkg,
                checkout_url=checkout_url,
                close=f"Here's the secure link to start: {checkout_url}",
                sender_name=sender_name,
            ),
            "package_offered": pkg_slug,
        },
        "proof_request": {
            # Proof asks default to package + public work reference — NOT free spec.
            "body": _compose_package_first_body(
                greeting=greeting,
                opener="Fair ask.",
                rationale=(
                    f"the {pkg['name']} is the package I'd put against {company_ref}'s "
                    f"situation — {rationale_short}. Every engagement ships real work "
                    f"against your actual offer, not generic mockups"
                ),
                pkg=pkg,
                checkout_url=checkout_url,
                close=f"Secure link to kick it off: {checkout_url}",
                sender_name=sender_name,
            ),
            "package_offered": pkg_slug,
        },
        "pricing_request": {
            "body": _compose_package_first_body(
                greeting=greeting,
                opener="Straight answer:",
                rationale=(
                    f"for {company_ref} the {pkg['name']} ({pkg['price']}) is the fit — "
                    f"{rationale_short}"
                ),
                pkg=pkg,
                checkout_url=checkout_url,
                close=f"Secure link when you're ready: {checkout_url}",
                sender_name=sender_name,
            ),
            "package_offered": pkg_slug,
        },
        "objection": {
            "body": _compose_package_first_body(
                greeting=greeting,
                opener="Understood.",
                rationale=(
                    f"if the concern is commitment, the {pkg['name']} ({pkg['price']}) is "
                    f"the cleanest way in — {rationale_short}, one engagement, no retainer "
                    f"lock-in"
                ),
                pkg=pkg,
                checkout_url=checkout_url,
                close=f"Secure link if you want to move: {checkout_url}",
                sender_name=sender_name,
            ),
            "package_offered": pkg_slug,
        },
        "negotiation": {
            # Negotiation / custom asks get forced to draft by reply_policy anyway.
            # This template exists for human-reviewed drafts only.
            "body": (
                f"{greeting}\n\n"
                f"Appreciate the directness. Standard scope for {company_ref} is the "
                f"{pkg['name']} at {pkg['price']} — {rationale_short}. That's the fixed "
                f"offer, not a retainer.\n\n"
                f"If you want to move: {checkout_url}\n\n"
                f"{sender_name}"
            ),
            "package_offered": pkg_slug,
        },
        "meeting_request": {
            # NOTE: meeting_request is NOT in STANDARD_TEMPLATE_INTENTS, so this
            # template never auto-sends. `call_request` FORCED_DRAFT pattern
            # also catches explicit "hop on a call" asks and force-drafts them.
            # Soft-redirect to the no-call package path.
            "body": (
                f"{greeting}\n\n"
                f"Thanks for the offer to connect. Easier path: everything I'd walk you "
                f"through is already packaged. For {company_ref}, the fit is the "
                f"{pkg['name']} at {pkg['price']} — {rationale_short}.\n\n"
                f"Secure link to move forward: {checkout_url}\n\n"
                f"If you have a specific question I can answer in email, just reply here.\n\n"
                f"{sender_name}"
            ),
            "package_offered": pkg_slug,
        },
        "not_now": {
            "body": (
                f"{greeting}\n\n"
                f"All good. I'll check back when the timing is better.\n\n"
                f"If anything changes, the link to start is here: {checkout_url}\n\n"
                f"{sender_name}"
            ),
            "package_offered": pkg_slug,
        },
        "unsubscribe": {
            "body": (
                f"{greeting}\n\n"
                f"Done — you won't hear from me again. "
                f"If you ever want to revisit, I'm at hello@proofhook.com.\n\n"
                f"{sender_name}"
            ),
            "package_offered": None,
        },
        "support": {
            "body": (
                f"{greeting}\n\n"
                f"Thanks for reaching out. Let me look into this and get back to you shortly.\n\n"
                f"{sender_name}"
            ),
            "package_offered": None,
        },
        "intake_reply": {
            "body": (
                f"{greeting}\n\n"
                f"Got it — thanks for sending this over. I'll review everything and "
                f"follow up once we're ready to kick off production.\n\n"
                f"{sender_name}"
            ),
            "package_offered": None,
        },
        "revision_request": {
            "body": (
                f"{greeting}\n\n"
                f"Noted. I'll get the revisions started and send an updated version soon.\n\n"
                f"{sender_name}"
            ),
            "package_offered": None,
        },
        "payment_question": {
            "body": (
                f"{greeting}\n\n"
                f"Let me check on that and get back to you with the details.\n\n"
                f"{sender_name}"
            ),
            "package_offered": None,
        },
        "referral": {
            "body": (
                f"{greeting}\n\n"
                f"Really appreciate the referral. Feel free to intro them directly or have "
                f"them reach out to hello@proofhook.com and I'll take it from there.\n\n"
                f"{sender_name}"
            ),
            "package_offered": None,
        },
    }

    # Fallback for unknown/escalation — no auto-reply
    default = {
        "body": (
            f"{greeting}\n\n"
            f"Thanks for your message. I'll review this and get back to you.\n\n"
            f"{sender_name}"
        ),
        "package_offered": None,
    }

    template = templates.get(intent, default)
    body_text = template["body"]

    # ── Optional preview-fallback injection ────────────────────────────────
    # Only fires when the operator has explicitly enabled free_preview_enabled
    # AND this intent is in the allowlist. The framing is "2 recommended angles"
    # / "2 creative directions", never "samples" or "test runs" or "free work".
    if preview_allowed and intent in ("proof_request", "objection", "warm_interest"):
        preview_line = _preview_fallback_line(company_ref, settings.front_end_speed_language_mode)
        if preview_line:
            body_text = body_text.replace(
                f"Secure link when you're ready: {checkout_url}\n\n{sender_name}",
                f"Secure link when you're ready: {checkout_url}\n\n"
                f"If you'd rather see the direction first, reply here and I'll share "
                f"{preview_line}\n\n{sender_name}",
            )
            # also handle the other two close strings
            for close_str in (
                f"Here's the secure link to start: {checkout_url}\n\n{sender_name}",
                f"Secure link to kick it off: {checkout_url}\n\n{sender_name}",
                f"Secure link if you want to move: {checkout_url}\n\n{sender_name}",
            ):
                body_text = body_text.replace(
                    close_str,
                    close_str.replace(
                        f"\n\n{sender_name}",
                        f"\n\nIf you'd rather see the direction first, reply here and I'll share "
                        f"{preview_line}\n\n{sender_name}",
                    ),
                )
            preview_used = True
            preview_framing = "recommended_angles"

    # Plain-text only — no HTML wrapper, no inline styles, no multi-part.
    # Empty body_html triggers contentType="Text" in microsoft_oauth.send_via_graph_sendmail
    # (line ~492), so Graph sends a pure text/plain message. This is the single biggest
    # factor in landing in the primary inbox vs Gmail Promotions for cold B2B replies.
    return {
        "subject": re_subject,
        "body_text": body_text,
        "body_html": "",
        "package_offered": template.get("package_offered"),
        "preview_fallback_used": preview_used,
        "preview_fallback_framing": preview_framing,
        "speed_language_mode": settings.front_end_speed_language_mode,
        "broad_market_positioning": True,  # every inbound template is broad-market
    }


def _compose_package_first_body(
    *,
    greeting: str,
    opener: str,
    rationale: str,
    pkg: dict,
    checkout_url: str,
    close: str,
    sender_name: str,
) -> str:
    """Compose a clean package-first reply body.

    Structure: greeting → one-line opener → package + rationale → close with
    secure link → signature. No bullet lists, no emojis, no HTML, no call
    language, no "24-48 hours", no "free samples".
    """
    return (
        f"{greeting}\n\n"
        f"{opener} Short version — {rationale}.\n\n"
        f"{close}\n\n"
        f"{sender_name}"
    )


def _shorten_rationale(rationale: str, company_ref: str) -> str:
    """Trim the recommender's rationale into a conversational clause.

    The recommender returns full sentences like "Lead mentioned strategy /
    funnel / creative audit needs — Creative Strategy + Funnel Upgrade
    rebuilds underperforming creative at the root." For a reply, we want the
    short second-half clause that reads as natural prose.

    IMPORTANT: do NOT lowercase the first letter. The em-dash bridge makes
    it grammatically valid to continue with either case, and more importantly
    the shortened clause frequently STARTS with the package name itself
    ("Performance Creative Pack is built for...") — lowercasing it would
    corrupt the capitalization of the package name in the rendered reply,
    breaking `pkg['name'] in body` doctrine checks.
    """
    text = (rationale or "").strip()
    if not text:
        return f"the fit for {company_ref} is clear"
    # Drop any "Lead mentioned ..." / "Lead referenced ..." / "Lead signalled ..." prefix
    lowered = text.lower()
    for prefix in (
        "lead mentioned ",
        "lead referenced ",
        "lead signalled ",
        "lead signaled ",
        "lead needs ",
    ):
        if lowered.startswith(prefix):
            text = text[len(prefix):]
            break
    # Drop the "— " bridge if the recommender used it
    if "—" in text:
        text = text.split("—", 1)[-1].strip()
    # Strip trailing period so it flows into the next clause.
    # Casing is intentionally preserved (see docstring).
    text = text.rstrip(". ")
    return text


def _preview_fallback_line(company_ref: str, speed_mode: str) -> str:
    """Return the one-line preview-fallback clause (only when enabled).

    Framing rules: "2 recommended angles" / "2 creative directions" only.
    Never "samples", "test runs", "free work", or anything that trains the
    lead to expect unpaid spec work.
    """
    if speed_mode == "allowed":
        return f"2 recommended angles for {company_ref} in 24–48 hours."
    if speed_mode == "rare":
        return f"2 recommended angles for {company_ref} this week."
    # default "none" — no speed promise
    return f"2 recommended angles for {company_ref}."


# ── Draft creation ───────────────────────────────────────────────────────


async def create_reply_draft(
    db: AsyncSession,
    *,
    thread_id: uuid.UUID,
    message_id: uuid.UUID,
    classification: ClassificationResult,
    org_id: uuid.UUID,
    to_email: str,
    body_text: str = "",
    first_name: str = "",
    company: str = "",
    thread_subject: str = "",
    package_slug: str | None = None,
    classification_id: uuid.UUID | None = None,
) -> dict:
    """Create an EmailReplyDraft using the confidence-gated policy engine.

    Flow:
        1. Render the reply body from the standard template library.
        2. Check whether the intent has a standard pre-approved template.
        3. Check thread cooldown.
        4. Call reply_policy.decide_reply_mode — the ONLY place the
           auto_send / draft / escalate / suppress decision is made.
        5. Map final_mode → status:
               auto_send → approved (sent on next beat)
               draft     → pending  (visible in review queue)
               escalate  → pending  (visible in review queue, flagged)
               suppress  → no draft created at all (logged only)
        6. Persist the full DecisionTrace as JSON in draft.reasoning and
           (when column exists) draft.decision_trace JSONB.
    """
    from packages.db.models.email_pipeline import EmailReplyDraft

    settings = await get_reply_policy(db, org_id)

    # 1. SIGNAL-BASED PACKAGE ROUTING — before we render anything, read the
    # lead's signals and pick the best-fit package. This is the core of the
    # Revenue-Ops doctrine: NEVER default to the $1,500 starter pack.
    recommendation = recommend_package(
        intent=classification.intent,
        body_text=body_text or classification.rationale or "",
        subject=thread_subject or "",
        from_email=to_email,
        mode=settings.package_recommendation_mode,
    )

    # Operator can still force a specific package via the explicit slug — it
    # takes precedence over the signal-based recommendation. This is the
    # escape hatch for manual overrides; the automated path always uses the
    # recommender's output.
    if package_slug and package_slug != recommendation.slug:
        logger.info(
            "package_override thread=%s recommender=%s forced=%s",
            thread_id, recommendation.slug, package_slug,
        )
        effective_recommendation = PackageRecommendation(
            slug=package_slug,
            rationale=f"Operator override — forced slug {package_slug}.",
            signals=recommendation.signals,
            confidence=recommendation.confidence,
            anchor_avoided=(package_slug != "ugc-starter-pack"),
            fallback_reason="operator_override",
        )
    else:
        effective_recommendation = recommendation

    # 2. Render reply body with the recommended package + policy settings
    reply = _build_reply_body(
        intent=classification.intent,
        first_name=first_name,
        company=company,
        thread_subject=thread_subject,
        package_slug=effective_recommendation.slug,
        recommendation=effective_recommendation,
        settings=settings,
    )

    # 3. Is this intent served by a standard pre-approved template?
    # (For pricing_request this also guarantees standard package pricing,
    # because _build_reply_body renders from a static template — there is
    # no code path that generates a custom quote here.)
    reply_is_standard = is_standard_template_intent(classification.intent)

    # 4. Thread cooldown check — one auto-reply per thread per window
    cooldown_hit = await _recent_auto_reply_exists(
        db, thread_id, settings.thread_cooldown_hours
    )

    # 5. Decision engine — the single source of truth
    trace = decide_reply_mode(
        intent=classification.intent,
        confidence=classification.confidence,
        subject=thread_subject or "",
        body=body_text or classification.rationale or "",
        from_email=to_email,
        reply_will_use_standard_template=reply_is_standard,
        recent_auto_reply_in_thread=cooldown_hit,
        settings=settings,
    )

    # 6. Populate the Revenue-Ops doctrine audit fields on the trace.
    # These are always populated so the full reasoning is visible in the
    # audit trail even when the reply is drafted/escalated rather than sent.
    trace.recommended_package = effective_recommendation.slug
    trace.recommendation_rationale = effective_recommendation.rationale
    trace.lead_signals_used = list(effective_recommendation.signals)
    trace.signal_confidence = float(effective_recommendation.confidence)
    trace.package_default_anchor_avoided = effective_recommendation.anchor_avoided
    trace.call_path_suppressed = (not settings.calls_enabled)
    trace.preview_fallback_allowed = (
        settings.free_preview_enabled
        and classification.intent in settings.preview_fallback_allowed_intents
    )
    trace.preview_fallback_used = bool(reply.get("preview_fallback_used"))
    trace.preview_fallback_framing = reply.get("preview_fallback_framing", "") or ""
    trace.broad_market_positioning = bool(reply.get("broad_market_positioning", True))
    trace.niche_framing_used = False  # inbound replies are always broad-market
    trace.speed_language_mode = reply.get("speed_language_mode", settings.front_end_speed_language_mode)

    trace_dict = trace.to_dict()

    # 5. Suppress verdict → don't create a draft at all
    if trace.final_mode == "suppress":
        logger.info(
            "reply_suppressed thread=%s intent=%s source=%s reason=%s",
            thread_id, classification.intent, trace.mode_source, trace.rationale,
        )
        return {
            "draft_id": None,
            "reply_mode": "suppress",
            "status": "suppressed",
            "intent": classification.intent,
            "to_email": to_email,
            "decision_trace": trace_dict,
            "rationale": trace.rationale,
        }

    # 5b. Map final_mode → persisted status
    if trace.final_mode == "auto_send":
        status = "approved"         # send on next beat fire
    elif trace.final_mode == "escalate":
        status = "pending"          # flagged for human — reply_mode=escalate marks it
    else:  # "draft"
        status = "pending"          # sits in review queue

    draft = EmailReplyDraft(
        thread_id=thread_id,
        message_id=message_id,
        classification_id=classification_id,
        org_id=org_id,
        to_email=to_email,
        subject=reply["subject"],
        body_text=reply["body_text"],
        body_html=reply["body_html"],
        reply_mode=trace.final_mode,
        status=status,
        confidence=classification.confidence,
        reasoning=json.dumps(trace_dict, separators=(",", ":")),
        package_offered=reply.get("package_offered"),
        model_used="policy_v1",
    )

    # Attach decision_trace JSONB if the column exists (additive schema)
    if hasattr(EmailReplyDraft, "decision_trace"):
        draft.decision_trace = trace_dict

    db.add(draft)
    await db.flush()

    logger.info(
        "reply_draft_created thread=%s intent=%s mode=%s source=%s status=%s",
        thread_id, classification.intent, trace.final_mode, trace.mode_source, status,
    )

    return {
        "draft_id": str(draft.id),
        "reply_mode": trace.final_mode,
        "mode_source": trace.mode_source,
        "status": status,
        "intent": classification.intent,
        "confidence": classification.confidence,
        "to_email": to_email,
        "subject": reply["subject"],
        "package_offered": reply.get("package_offered"),
        "decision_trace": trace_dict,
    }


async def send_approved_drafts(db: AsyncSession, org_id: uuid.UUID) -> dict:
    """Send all approved drafts that haven't been sent yet.

    Routing:
        - If the draft's thread is linked to an M365 InboxConnection
          (auth_method=xoauth2, credential_provider_key=microsoft_oauth_app),
          send via Microsoft Graph POST /me/sendMail using a Graph-scoped
          access token minted from the mailbox's multi-resource refresh
          token. Message lands in the M365 Sent folder automatically.
          (XOAUTH2 SMTP is *not* used — Microsoft disables it at the
          tenant level by default, so Graph is the only reliable path.)
        - Otherwise fall back to the generic env-var SmtpEmailClient
          (Brevo / SendGrid / etc).

    Called by the sync worker after processing inbound emails.
    """
    from packages.db.models.email_pipeline import (
        EmailReplyDraft, EmailThread, EmailMessage, InboxConnection,
    )
    from packages.clients.external_clients import SmtpEmailClient
    from packages.clients.microsoft_oauth import send_via_graph_sendmail

    drafts = (await db.execute(
        select(EmailReplyDraft).where(
            EmailReplyDraft.org_id == org_id,
            EmailReplyDraft.status == "approved",
            EmailReplyDraft.is_active.is_(True),
        )
    )).scalars().all()

    sent = 0
    failed = 0
    fallback_smtp = SmtpEmailClient()

    for draft in drafts:
        # Resolve the mailbox this draft should send FROM
        thread = (await db.execute(
            select(EmailThread).where(EmailThread.id == draft.thread_id)
        )).scalar_one_or_none()
        if not thread:
            draft.error_message = "thread not found"
            failed += 1
            continue

        inbox = (await db.execute(
            select(InboxConnection).where(InboxConnection.id == thread.inbox_connection_id)
        )).scalar_one_or_none()
        if not inbox:
            draft.error_message = "inbox_connection not found"
            failed += 1
            continue

        # Look up inbound message to thread the reply (In-Reply-To + References)
        inbound_msg = (await db.execute(
            select(EmailMessage).where(EmailMessage.id == draft.message_id)
        )).scalar_one_or_none()
        in_reply_to = inbound_msg.provider_message_id if inbound_msg else None
        refs_new = None
        if inbound_msg:
            # "References" = original References + the message we're replying to
            existing_refs = (inbound_msg.references or "").strip()
            if existing_refs:
                refs_new = f"{existing_refs} {inbound_msg.provider_message_id}"
            else:
                refs_new = inbound_msg.provider_message_id

        # Decide send path — M365 → Graph sendMail, everything else → SMTP
        use_graph = (
            inbox.auth_method in ("oauth2", "xoauth2")
            and (inbox.credential_provider_key or "").lower() == "microsoft_oauth_app"
        )

        try:
            if use_graph:
                result = await send_via_graph_sendmail(
                    db, inbox,
                    to_email=draft.to_email,
                    subject=draft.subject,
                    body_text=draft.body_text or "",
                    body_html=draft.body_html or "",
                    reply_to=inbox.email_address,
                    in_reply_to=in_reply_to,
                    references=refs_new,
                )
            else:
                if not fallback_smtp._is_configured():
                    # Represent as a structured send-failure result so the
                    # failure branch below writes error_message AND emits
                    # the reply.draft.send_failed event. Previously this
                    # `continue`d out and silently skipped event emission.
                    result = {
                        "success": False,
                        "error": "inbox is not M365 xoauth2 and fallback SMTP not configured",
                        "provider": "smtp_unconfigured",
                    }
                else:
                    result = await fallback_smtp.send_email(
                        to_email=draft.to_email,
                        subject=draft.subject,
                        body_html=draft.body_html or "",
                        body_text=draft.body_text or "",
                    )

            if result.get("success"):
                draft.status = "sent"
                draft.sent_at = datetime.now(timezone.utc)
                # Store the provider message-id for threading future replies
                mid = result.get("message_id")
                if mid:
                    existing_trace = draft.decision_trace if hasattr(draft, "decision_trace") and draft.decision_trace else {}
                    if isinstance(existing_trace, dict):
                        existing_trace = {**existing_trace, "sent_via": result.get("provider"), "sent_message_id": mid}
                        if hasattr(draft, "decision_trace"):
                            draft.decision_trace = existing_trace
                # Update thread bookkeeping
                if thread:
                    thread.reply_status = "sent"
                sent += 1
                logger.info(
                    "reply_draft_sent draft=%s mode=%s provider=%s to=%s",
                    draft.id, draft.reply_mode, result.get("provider"), draft.to_email,
                )
                await _emit_send_event(
                    db,
                    event_type="reply.draft.sent",
                    draft=draft,
                    thread=thread,
                    severity="info",
                    details={
                        "provider": result.get("provider"),
                        "sent_message_id": mid,
                    },
                )
            else:
                draft.error_message = (result.get("error") or "unknown")[:500]
                failed += 1
                logger.warning(
                    "reply_draft_send_failed draft=%s error=%s",
                    draft.id, draft.error_message,
                )
                await _emit_send_event(
                    db,
                    event_type="reply.draft.send_failed",
                    draft=draft,
                    thread=thread,
                    severity="warning",
                    details={
                        "provider": result.get("provider"),
                        "error": draft.error_message,
                    },
                )
        except Exception as e:
            draft.error_message = str(e)[:500]
            failed += 1
            logger.exception("reply_draft_send_exception draft=%s", draft.id)
            try:
                await _emit_send_event(
                    db,
                    event_type="reply.draft.send_failed",
                    draft=draft,
                    thread=thread,
                    severity="warning",
                    details={"error": str(e)[:500], "exception": True},
                )
            except Exception:
                pass

    await db.flush()
    return {"sent": sent, "failed": failed, "total_drafts": len(drafts)}


async def _emit_send_event(
    db: AsyncSession,
    *,
    event_type: str,
    draft,
    thread,
    severity: str,
    details: dict,
) -> None:
    """Emit a revenue_event for a send-loop state transition. Non-blocking."""
    from apps.api.services.event_bus import emit_event

    try:
        await emit_event(
            db,
            domain="monetization",
            event_type=event_type,
            summary=(
                f"Reply draft {'sent to' if event_type == 'reply.draft.sent' else 'send FAILED to'} "
                f"{(draft.to_email or '')[:60]}"
            ),
            org_id=draft.org_id,
            entity_type="email_reply_draft",
            entity_id=draft.id,
            previous_state="approved",
            new_state=("sent" if event_type == "reply.draft.sent" else "approved"),
            actor_type="worker",
            actor_id="send_approved_reply_drafts",
            severity=severity,
            details={
                "draft_id": str(draft.id),
                "thread_id": str(thread.id) if thread else None,
                "to_email": draft.to_email,
                "reply_mode": draft.reply_mode,
                **details,
            },
        )
    except Exception as evt_exc:
        logger.warning(
            "reply_draft.event_emit_failed draft=%s error=%s",
            draft.id, str(evt_exc)[:200],
        )
