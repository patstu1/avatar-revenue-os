"""test_record_guard — live-payment safety guardrail.

Provides three pure (no-DB, no-IO) functions that block test, synthetic,
fixture, and internal records from reaching any live payment-link creation
or outbound customer email path.

Functions
---------
is_test_or_synthetic_email(email) -> bool
    True  → email matches a blocked pattern (do NOT send / charge).
    False → email is safe to use.

is_test_or_synthetic_text(value) -> bool
    True  → the raw string value matches a blocked marker.

is_test_or_synthetic_record(email, source, metadata) -> tuple[bool, str]
    Combines both checks across email + source + metadata values.
    Returns (blocked: bool, reason: str).

Usage
-----
    from apps.api.services.test_record_guard import is_test_or_synthetic_record

    blocked, reason = is_test_or_synthetic_record(
        email=client.primary_email,
        source=client.avenue_slug,
        metadata={"source_client_id": str(client.id)},
    )
    if blocked:
        logger.warning("guard.blocked", reason=reason, email=client.primary_email)
        continue

Design notes
------------
- Pure functions; no imports from the rest of the codebase.
- Patterns are lower-cased before matching so case variants are caught.
- Extend _BLOCKED_EMAIL_DOMAINS / _BLOCKED_MARKERS to add new patterns;
  no call-site changes required.
"""

from __future__ import annotations

import re

# ── Blocked email domain suffixes / full domains ──────────────────────────────
_BLOCKED_EMAIL_DOMAINS: tuple[str, ...] = (
    "@test.com",
    "@internal.test",
    "@example.com",
    "@localhost",
    "@b10test.com",  # batch-10 test domain found in draft proposals
    ".test",  # any *.test TLD
    ".example",
    ".invalid",
    ".localhost",
)

# ── Blocked substring markers (checked against email local-part, source,
#    and any string value in metadata) ─────────────────────────────────────────
_BLOCKED_MARKERS: tuple[str, ...] = (
    "testreplier",
    "synth",
    "synthetic",
    "fixture",
    "proof_test",
    "b11",
    "b12",
    # batch fixture markers
    "batch_fixture",
    "batchfixture",
    # demo used as fixture / source marker (not the word "demo" in a URL slug)
    "demo_client",
    "democlient",
    "demo_fixture",
    "demofixture",
    # localhost literal in email local-part
    "localhost",
)

# Pre-compiled for performance
_BLOCKED_MARKERS_RE = re.compile(
    "|".join(re.escape(m) for m in _BLOCKED_MARKERS),
    re.IGNORECASE,
)


def is_test_or_synthetic_email(email: str) -> bool:
    """Return True if the email address matches any blocked pattern.

    Examples that return True (blocked):
        user@test.com, ops@internal.test, hello@example.com,
        testreplier@domain.com, synth_user@brand.com,
        b11_client@company.com, proof_test@x.com

    Examples that return False (allowed):
        founder@company.com, client@realagency.io, user@gmail.com
    """
    if not email or not isinstance(email, str):
        return True  # empty / non-string is always blocked

    lower = email.lower().strip()

    if not lower:
        return True  # whitespace-only

    # Domain check
    for blocked_domain in _BLOCKED_EMAIL_DOMAINS:
        if lower.endswith(blocked_domain):
            return True

    # Marker check against the full email string
    if _BLOCKED_MARKERS_RE.search(lower):
        return True

    return False


def is_test_or_synthetic_text(value: str) -> bool:
    """Return True if the string value contains any blocked marker.

    Use this to check source fields, metadata values, slugs, etc.
    """
    if not value or not isinstance(value, str):
        return False  # empty / None text is not itself a blocker

    return bool(_BLOCKED_MARKERS_RE.search(value.lower()))


def is_test_or_synthetic_record(
    email: str,
    source: str | None = None,
    metadata: dict | None = None,
) -> tuple[bool, str]:
    """Combined guard for payment-path records.

    Checks email first, then source slug, then every string value in
    the metadata dict.  Returns on the first match.

    Returns
    -------
    (blocked: bool, reason: str)
        blocked=True  → do NOT create payment link or send email.
        reason        → human-readable explanation for audit logs.
    """
    # 1. Email check
    if is_test_or_synthetic_email(email):
        return True, f"email blocked by test_record_guard: {email!r}"

    # 2. Source check
    if source and is_test_or_synthetic_text(source):
        return True, f"source blocked by test_record_guard: {source!r}"

    # 3. Metadata value check
    if metadata:
        for key, val in metadata.items():
            if isinstance(val, str) and is_test_or_synthetic_text(val):
                return True, f"metadata[{key!r}] blocked by test_record_guard: {val!r}"

    return False, ""
