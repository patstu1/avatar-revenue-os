"""Email validation for the AI Buyer Trust Test form.

Cheap format check + rejection of obvious throwaway / no-reply / example
addresses. Not a full SMTP-verify (which would require an external service);
the goal is to keep the lead funnel clean and the operator's inbox sane.
"""

from __future__ import annotations

import re

_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

# Domains that are clearly throwaways or documentation-reserved.
_BLOCKED_DOMAINS = frozenset(
    {
        "example.com",
        "example.net",
        "example.org",
        "test.com",
        "test.test",
        "mailinator.com",
        "throwaway.email",
        "sharklasers.com",
        "guerrillamail.com",
        "10minutemail.com",
        "tempmail.com",
        "yopmail.com",
        "trashmail.com",
        "dispostable.com",
        "fakeinbox.com",
        "mvrht.net",
        "localhost",
        "internal",
    }
)

# Local-parts that signal "I'm not a real prospect".
_BLOCKED_LOCAL_PARTS = frozenset(
    {
        "test",
        "noreply",
        "no-reply",
        "donotreply",
        "do-not-reply",
        "postmaster",
        "mailer-daemon",
        "abuse",
    }
)


class EmailValidationError(ValueError):
    """Raised when an email fails validation. Message is operator-safe."""


def validate_contact_email(raw: str) -> str:
    """Return the normalized lowercase email or raise EmailValidationError."""
    if not raw or not isinstance(raw, str):
        raise EmailValidationError("Email is required.")

    email = raw.strip().lower()

    if not _EMAIL_RE.match(email):
        raise EmailValidationError("Email format is not valid.")

    local_part, domain = email.split("@", 1)

    if local_part in _BLOCKED_LOCAL_PARTS:
        raise EmailValidationError("Use your real work email — not a no-reply address.")

    if domain in _BLOCKED_DOMAINS:
        raise EmailValidationError("Use your real work email — that domain looks like a placeholder.")

    return email
