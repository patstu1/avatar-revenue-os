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
# Package catalog (for later emails / landing pages, NOT for first touch)
# ---------------------------------------------------------------------------

PACKAGES = {
    "ugc-starter-pack": {
        "name": "UGC Starter Pack",
        "price": "$1,500",
        "tagline": "The fastest way to get usable short-form creative live.",
        "description": (
            "Built for brands that need content now without committing to a retainer. "
            "You get 4 short-form video assets, 3 hook variations, and 1 CTA angle "
            "— edited, packaged, and delivered in 7 days."
        ),
        "bullets": [
            "4 short-form video assets",
            "3 hook variations",
            "1 CTA angle",
            "Light editing and packaging",
            "7-day turnaround",
        ],
        "best_for": "Founders who need proof-of-concept assets fast. Brands testing short-form for the first time.",
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
# First-touch outbound templates — sharp, private, no marketing feel
# ---------------------------------------------------------------------------

# Vertical-specific body copy — tension + curiosity, not a pitch
FIRST_TOUCH = {
    "aesthetic-theory": {
        "subject_with_company": "{first_name}, quick note about {company}",
        "subject_without_company": "{first_name}, quick note",
        "body": (
            "{company} looks like the kind of brand where the product is stronger "
            "than the creative around it.\n\n"
            "That gap usually costs attention first, then trust, then conversions.\n\n"
            "We build short-form creative for beauty brands that makes the offer "
            "land harder — sharper hooks, tighter angles, better proof.\n\n"
            "Want me to send 2 angles I'd test for {company}?"
        ),
        "body_no_company": (
            "Your brand looks like the product is stronger than the creative around it.\n\n"
            "That gap usually costs attention first, then trust, then conversions.\n\n"
            "We build short-form creative for beauty brands that makes the offer "
            "land harder — sharper hooks, tighter angles, better proof.\n\n"
            "Want me to send 2 angles I'd test?"
        ),
    },
    "body-theory": {
        "subject_with_company": "{first_name}, quick note about {company}",
        "subject_without_company": "{first_name}, quick note",
        "body": (
            "{company} feels like a brand where the offer is stronger than the creative around it.\n\n"
            "In fitness that gap shows up fast — weak creative gets scrolled past "
            "no matter how good the product is.\n\n"
            "We build short-form content for fitness brands that makes the offer "
            "impossible to ignore — sharper hooks, real proof, tighter angles.\n\n"
            "Want me to send 2 angles I'd test for {company}?"
        ),
        "body_no_company": (
            "Your brand feels like the offer is stronger than the creative around it.\n\n"
            "In fitness that gap shows up fast — weak creative gets scrolled past "
            "no matter how good the product is.\n\n"
            "We build short-form content for fitness brands that makes the offer "
            "impossible to ignore — sharper hooks, real proof, tighter angles.\n\n"
            "Want me to send 2 angles I'd test?"
        ),
    },
    "tool-signal": {
        "subject_with_company": "{first_name}, quick note about {company}",
        "subject_without_company": "{first_name}, quick note",
        "body": (
            "{company}'s creative is probably making the product look smaller than it should.\n\n"
            "That is usually not a product problem. It is a presentation problem.\n\n"
            "We build short-form creative for software brands that makes the offer feel "
            "sharper, cleaner, and harder to ignore.\n\n"
            "Want me to send 2 angles I'd test for {company}?"
        ),
        "body_no_company": (
            "Your creative is probably making the product look smaller than it should.\n\n"
            "That is usually not a product problem. It is a presentation problem.\n\n"
            "We build short-form creative for software brands that makes the offer feel "
            "sharper, cleaner, and harder to ignore.\n\n"
            "Want me to send 2 angles I'd test?"
        ),
    },
    "fallback": {
        "subject_with_company": "{first_name}, quick note about {company}",
        "subject_without_company": "{first_name}, quick note",
        "body": (
            "{company} looks like the kind of brand where the offer is stronger "
            "than the creative around it.\n\n"
            "That gap usually costs attention first, then trust, then conversion.\n\n"
            "ProofHook builds sharper short-form creative that makes the offer land harder.\n\n"
            "Want me to send 2 angles I'd test for {company}?"
        ),
        "body_no_company": (
            "Your brand looks like the offer is stronger than the creative around it.\n\n"
            "That gap usually costs attention first, then trust, then conversion.\n\n"
            "ProofHook builds sharper short-form creative that makes the offer land harder.\n\n"
            "Want me to send 2 angles I'd test?"
        ),
    },
}


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
