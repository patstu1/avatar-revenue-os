"""ProofHook outbound email templates.

RULES (first-touch):
- No hero image, no logo block, no package card, no brochure structure
- Plain-text-feel HTML only
- Founder/operator note feel — sharp, high-status, private message
- No over-marketing language, no "wow-factor", no generic pitch phrases
- No multiple links, no image-heavy layout
- One CTA only
"""
from __future__ import annotations

import os

DOMAIN = os.environ.get("DOMAIN", "proofhook.com")

# ---------------------------------------------------------------------------
# Secure-package link + intake link helpers
# ---------------------------------------------------------------------------
#
# Reply templates push leads toward a no-call automated funnel:
#   reply → proof / sample angles → payment link → intake → production
#
# These helpers return the per-package checkout + intake URLs that appear
# inline in auto-send replies. Base URLs are env-configurable so you can
# point at Stripe Payment Links, a landing page, a custom checkout flow,
# or a typeform intake without touching template code.
#
# Env vars (override defaults):
#   PROOFHOOK_CHECKOUT_BASE  e.g. "https://buy.stripe.com/test_abc"
#   PROOFHOOK_INTAKE_BASE    e.g. "https://proofhook.com/start"

def package_checkout_url(slug: str | None) -> str:
    """Return the secure checkout URL for a package slug (no trailing slash)."""
    base = os.environ.get("PROOFHOOK_CHECKOUT_BASE", f"https://{DOMAIN}/pay").rstrip("/")
    return f"{base}/{slug or 'ugc-starter-pack'}"


def package_intake_url(slug: str | None) -> str:
    """Return the intake-start URL for a package slug (no trailing slash)."""
    base = os.environ.get("PROOFHOOK_INTAKE_BASE", f"https://{DOMAIN}/start").rstrip("/")
    return f"{base}/{slug or 'ugc-starter-pack'}"


# ---------------------------------------------------------------------------
# Package catalog (for later emails / landing pages, NOT for first touch)
# ---------------------------------------------------------------------------

PACKAGES = {
    "ugc-starter-pack": {
        "name": "UGC Starter Pack",
        "price": "$1,500",
        "tagline": "Low-commitment entry point for explicit test / early-stage leads.",
        "description": (
            "Built for brands that want a single no-retainer entry point — not the "
            "default recommendation. The package_recommender only routes to the "
            "starter when the lead explicitly signals test / one-off / early-stage. "
            "4 short-form video assets, 3 hook variations, 1 CTA angle."
        ),
        "bullets": [
            "4 short-form video assets",
            "3 hook variations",
            "1 CTA angle",
            "Light editing and packaging",
            "One-time engagement, no retainer",
        ],
        "best_for": "Leads with explicit test / one-off / early-stage / low-budget signals. NOT the default recommendation.",
    },
    "growth-content-pack": {
        "name": "Growth Content Pack",
        "price": "Starting at $2,500/month",
        "tagline": "A monthly content engine for brands that have outgrown freelancers.",
        "description": (
            "8-12 short-form assets per month with multiple hook and caption variations, "
            "2 CTA angles, and a monthly creative refresh."
        ),
        "bullets": [
            "8-12 short-form assets per month",
            "Multiple hook and caption variations",
            "2 CTA angles",
            "Monthly creative refresh",
        ],
        "best_for": "Growing brands that need consistent content output.",
    },
    "creative-strategy-funnel-upgrade": {
        "name": "Creative Strategy + Funnel Upgrade",
        "price": "Starting at $3,500",
        "tagline": "A creative audit and funnel overhaul.",
        "description": (
            "We audit your current creative, identify what is underperforming and why, "
            "then rebuild your top-of-funnel assets with new hooks, angles, and offer alignment."
        ),
        "bullets": [
            "Full creative audit",
            "Hook and angle rebuild",
            "Offer alignment review",
            "Landing page recommendations",
            "Creative roadmap",
        ],
        "best_for": "Brands that are spending but not converting.",
    },
    "performance-creative-pack": {
        "name": "Performance Creative Pack",
        "price": "Starting at $4,500/month",
        "tagline": "For brands running paid media that need creative rotation.",
        "description": (
            "12-20 short-form assets per month with hook and angle testing variations, "
            "offer and landing page support, and a monthly optimization pass."
        ),
        "bullets": [
            "12-20 short-form assets per month",
            "Hook and angle testing variations",
            "Offer and landing page support",
            "Monthly optimization pass",
        ],
        "best_for": "Brands running paid media that need consistent creative rotation.",
    },
    "launch-sprint": {
        "name": "Launch Sprint",
        "price": "Starting at $5,000",
        "tagline": "Fast-turn creative for launches and funding moments.",
        "description": (
            "A compressed-timeline creative sprint built for speed. "
            "Everything you need to launch strong without waiting on a retainer cycle."
        ),
        "bullets": [
            "Fast-turn asset batch",
            "Launch-focused hook set",
            "CTA alignment",
            "Compressed delivery timeline",
        ],
        "best_for": "Product launches, seasonal pushes, funding announcements.",
    },
    "full-creative-retainer": {
        "name": "Full Creative Retainer",
        "price": "Starting at $7,500/month",
        "tagline": "A full creative partner for brands scaling spend.",
        "description": (
            "Recurring creative production with multi-angle hook development, "
            "offer and landing support, reporting and strategy layer, and priority turnaround."
        ),
        "bullets": [
            "Recurring creative production",
            "Multi-angle hook development",
            "Offer and landing support",
            "Reporting and strategy layer",
            "Priority turnaround",
        ],
        "best_for": "Brands scaling spend that need a full creative partner.",
    },
}


# ---------------------------------------------------------------------------
# First-touch outbound templates — broad-market, package-first, no free work
# ---------------------------------------------------------------------------
#
# ProofHook Revenue-Ops doctrine:
#   • Broad-market positioning — these templates NEVER name a vertical.
#     Vertical keys below are tactical routing labels only; the copy is
#     category-agnostic so the same template is safe for any inbox.
#   • No free spec work — the CTA is "reply here" and the follow-up is
#     the package + checkout link, not "2 sample angles" or "free test run".
#   • No call language — no meetings, no Calendly, no walkthroughs.
#   • Private note feel — sharp, high-status, one CTA only.
#
# First-touch replies route the lead into the inbound email pipeline, where
# classifier → package_recommender → reply_engine picks the best-fit package
# based on whatever signals the lead sent back. We do not commit to a specific
# package in the first touch — we open the door and let signals do the rest.
FIRST_TOUCH = {
    "fallback": {
        "subject_with_company": "{first_name}, quick note about {company}",
        "subject_without_company": "{first_name}, quick note",
        "body": (
            "{company} looks like the kind of brand where the offer is stronger "
            "than the creative around it.\n\n"
            "That gap usually costs attention first, then trust, then conversion.\n\n"
            "ProofHook builds sharper short-form creative, packaged and priced up "
            "front — no retainers, no custom scoping cycles, no call needed to get "
            "moving.\n\n"
            "Worth a quick reply to see if there's a fit?"
        ),
        "body_no_company": (
            "Your brand looks like the offer is stronger than the creative around it.\n\n"
            "That gap usually costs attention first, then trust, then conversion.\n\n"
            "ProofHook builds sharper short-form creative, packaged and priced up "
            "front — no retainers, no custom scoping cycles, no call needed to get "
            "moving.\n\n"
            "Worth a quick reply to see if there's a fit?"
        ),
    },
}

# Vertical aliases — every legacy routing key resolves to the same broad-market
# template above. If operators want tactical vertical framing in the future,
# they can add entries here WITHOUT changing the default behavior. The
# `broad_market_positioning_enabled` flag on ReplyPolicySettings controls
# whether vertical aliases are honored at all.
FIRST_TOUCH["aesthetic-theory"] = FIRST_TOUCH["fallback"]
FIRST_TOUCH["body-theory"] = FIRST_TOUCH["fallback"]
FIRST_TOUCH["tool-signal"] = FIRST_TOUCH["fallback"]


def _plain_html(body_text: str, sender_name: str = "Patrick") -> str:
    """Wrap plain text in minimal HTML that looks like a private message.

    No images. No colors. No cards. No marketing layout.
    Just a clean message that renders well in every email client.
    """
    # Convert newlines to <br> for HTML
    body_html = body_text.replace("\n\n", "</p><p style=\"margin:0 0 14px;\">").replace("\n", "<br>")

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#ffffff;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#ffffff;">
<tr><td style="padding:20px;max-width:580px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;font-size:14px;line-height:1.6;color:#222222;">

<p style="margin:0 0 14px;">{body_html}</p>

<p style="margin:24px 0 0;font-size:14px;color:#222222;">{sender_name}<br>
<span style="color:#555555;">ProofHook</span></p>

</td></tr>
</table>
</body>
</html>"""


def build_first_touch(
    *,
    first_name: str,
    company: str = "",
    vertical: str = "fallback",
    sender_name: str = "Patrick",
) -> dict[str, str]:
    """Build a first-touch outbound email.

    Returns dict with 'html', 'text', 'subject' keys.

    Rules:
    - No hero, no logo, no package card, no brochure
    - Feels like a sharp private note from a founder
    - Creates tension + curiosity, does not sell
    - One low-friction CTA only
    """
    template = FIRST_TOUCH.get(vertical, FIRST_TOUCH["fallback"])

    has_company = bool(company and company.strip())

    if has_company:
        subject = template["subject_with_company"].format(
            first_name=first_name, company=company
        )
        body = template["body"].format(
            first_name=first_name, company=company
        )
    else:
        subject = template["subject_without_company"].format(
            first_name=first_name
        )
        body = template["body_no_company"].format(first_name=first_name)

    full_text = f"Hi {first_name},\n\n{body}\n\n{sender_name}\nProofHook"

    html = _plain_html(
        f"Hi {first_name},\n\n{body}",
        sender_name=sender_name,
    )

    return {"html": html, "text": full_text, "subject": subject}


# ---------------------------------------------------------------------------
# Follow-up / proof email (email 2+) — can include branding + package info
# ---------------------------------------------------------------------------

def build_proof_email(
    *,
    first_name: str,
    company: str = "",
    vertical: str = "fallback",
    package_slug: str = "ugc-starter-pack",
    proof_url: str = "",
    sender_name: str = "Patrick",
) -> dict[str, str]:
    """Build a follow-up proof/package email (email 2+).

    This one CAN include package details and a link.
    Still no heavy marketing layout — clean and direct.
    """
    pkg = PACKAGES.get(package_slug, PACKAGES["ugc-starter-pack"])

    if not proof_url:
        vert_prefix = vertical if vertical != "fallback" else "tool-signal"
        proof_url = f"https://{DOMAIN}/offers/{vert_prefix}/{package_slug}"

    company_ref = company if company else "your brand"

    body = (
        f"Hi {first_name},\n\n"
        f"Following up — I put together two angles I think would work for {company_ref}.\n\n"
        f"The format we'd use is our {pkg['name']} ({pkg['price']}):\n\n"
    )
    for b in pkg["bullets"]:
        body += f"  - {b}\n"

    body += (
        f"\nYou can see the full breakdown here: {proof_url}\n\n"
        f"Worth a look?"
    )

    html = _plain_html(body, sender_name=sender_name)

    return {
        "html": html,
        "text": f"{body}\n\n{sender_name}\nProofHook",
        "subject": f"Re: {first_name}, quick note about {company_ref}",
    }


# ---------------------------------------------------------------------------
# Batch 9 — Transactional post-purchase emails
# ---------------------------------------------------------------------------
#
# Intake invite (sent the moment a Client is activated by a successful
# Stripe payment), dunning reminders for unpaid proposals, and delivery
# follow-ups. Same plain-note visual treatment as the outbound templates
# above — a private message from an operator, not a marketing blast.


def _intake_form_url(token: str) -> str:
    """Base URL for the public intake form.

    Override via env var ``INTAKE_FORM_BASE_URL`` — defaults to the
    ARO API host at ``/intake/{token}``. Operators can point this at a
    hosted form page (e.g. Typeform) if they swap the intake surface
    later without touching this code.
    """
    base = os.environ.get(
        "INTAKE_FORM_BASE_URL",
        f"https://app.{DOMAIN.replace('proofhook.com', 'nvironments.com')}/intake",
    ).rstrip("/")
    return f"{base}/{token}"


def build_intake_invite(
    *,
    display_name: str,
    intake_title: str,
    intake_token: str,
    package_slug: str | None = None,
    avenue_slug: str | None = None,
    sender_name: str = "Patrick",
) -> dict[str, str]:
    """Build the transactional intake invite email.

    Fires once per client activation — the moment Stripe webhook creates
    a Client + IntakeRequest, the buyer gets this email containing the
    one-use token URL that unlocks their onboarding form.

    Keep the body short. No sell. Single CTA. The buyer already paid —
    this is the "what's next" message, not a pitch.
    """
    url = _intake_form_url(intake_token)
    first_name = (display_name.split(" ")[0] or display_name).strip() or "there"

    body = (
        f"Hi {first_name},\n\n"
        f"Thanks for your purchase — you're in.\n\n"
        f"The next step is a quick intake so we can kick off production. "
        f"It takes about 10 minutes and asks for your product details, audience, "
        f"and goals.\n\n"
        f"Start here: {url}\n\n"
        f"Once you submit, we begin work within 48 hours. "
        f"Reply to this email if anything blocks you."
    )

    html = _plain_html(body, sender_name=sender_name)
    subject = f"Next step — {intake_title}"

    return {
        "html": html,
        "text": f"{body}\n\n{sender_name}\nProofHook",
        "subject": subject,
    }


def build_dunning_reminder(
    *,
    display_name: str,
    proposal_title: str,
    payment_link_url: str | None = None,
    amount_display: str | None = None,
    reminder_number: int = 1,
    sender_name: str = "Patrick",
) -> dict[str, str]:
    """Build a polite payment reminder for an unpaid proposal.

    Reminder 1 (24h after sent)   : gentle nudge
    Reminder 2 (72h after sent)   : slightly more direct
    Reminder 3 (7d after sent)    : final reminder, then escalate
    """
    first_name = (display_name.split(" ")[0] or display_name).strip() or "there"
    link_block = f"\n\nPayment link: {payment_link_url}" if payment_link_url else ""
    amount_block = f" ({amount_display})" if amount_display else ""

    if reminder_number <= 1:
        body = (
            f"Hi {first_name},\n\n"
            f"Just checking in on {proposal_title}{amount_block}. "
            f"Wanted to make sure nothing got stuck in an inbox.{link_block}\n\n"
            f"Let me know if you need anything clarified — happy to answer."
        )
        subject = f"Re: {proposal_title}"
    elif reminder_number == 2:
        body = (
            f"Hi {first_name},\n\n"
            f"Still holding your slot for {proposal_title}{amount_block}. "
            f"If the timing doesn't work anymore, reply and I'll pull it — "
            f"otherwise the payment link is ready whenever you are.{link_block}"
        )
        subject = f"Re: {proposal_title} — still on?"
    else:
        body = (
            f"Hi {first_name},\n\n"
            f"Last check-in on {proposal_title}{amount_block}. "
            f"If you still want to move forward this week, the link is below. "
            f"If not, no problem — just say the word and I'll close it out "
            f"and free up the slot.{link_block}"
        )
        subject = f"Re: {proposal_title} — final note"

    html = _plain_html(body, sender_name=sender_name)
    return {
        "html": html,
        "text": f"{body}\n\n{sender_name}\nProofHook",
        "subject": subject,
    }


def build_delivery_followup(
    *,
    display_name: str,
    project_title: str,
    deliverable_url: str | None = None,
    sender_name: str = "Patrick",
) -> dict[str, str]:
    """Build a post-delivery follow-up email.

    Fires N days after delivery.status=sent (default 7). Purpose:
    confirm the buyer actually used what we shipped, open the door to
    upsell / next batch. No marketing — just checking in.
    """
    first_name = (display_name.split(" ")[0] or display_name).strip() or "there"
    link_block = f"\n\nQuick access to the files: {deliverable_url}" if deliverable_url else ""
    body = (
        f"Hi {first_name},\n\n"
        f"Checking in on {project_title}. "
        f"Did the creative land? If something missed the mark, tell me plainly — "
        f"we'll fix it or make it right.{link_block}\n\n"
        f"If it's working, happy to talk about what's next."
    )
    html = _plain_html(body, sender_name=sender_name)
    return {
        "html": html,
        "text": f"{body}\n\n{sender_name}\nProofHook",
        "subject": f"Quick check-in on {project_title}",
    }


# Keep backward compat
def build_outreach_for_lead(
    *,
    first_name: str,
    company: str,
    vertical: str,
    package_slug: str = "ugc-starter-pack",
) -> dict[str, str]:
    """Backward-compatible wrapper — now uses first-touch template."""
    return build_first_touch(
        first_name=first_name,
        company=company,
        vertical=vertical,
    )
