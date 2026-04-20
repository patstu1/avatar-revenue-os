"""Email Classifier — intent detection for inbound sales emails.

Classifies inbound messages and determines reply mode (auto_send / draft / escalate).
Uses keyword patterns first (fast, no API cost), with optional LLM upgrade for ambiguous cases.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ClassificationResult:
    intent: str
    confidence: float
    rationale: str
    secondary_intent: str | None = None
    secondary_confidence: float | None = None
    reply_mode: str = "draft"  # auto_send, draft, escalate


# ── Pattern definitions ───────────────────────────────────────────────────

_PATTERNS: dict[str, list[tuple[str, float]]] = {
    # Base confidences calibrated so that a body match of a clear phrase
    # clears the auto_send_min_confidence=0.85 gate in reply_policy. A
    # subject-only match is penalized to 0.7x in classify_email(), which
    # keeps noisy Re:/Fwd: subject matches out of auto_send.
    "warm_interest": [
        (r"(?i)\b(interested|love to|sounds great|let'?s do|count me in|i'?m in|let'?s chat|let'?s talk|would love|happy to|excited|looking forward|tell me more|sounds interesting|intrigued)\b", 0.88),
    ],
    "proof_request": [
        (r"(?i)\b(examples?|portfolio|case stud|samples?|show me|see your work|demo|proof|previous work|past work|results you'?ve)\b", 0.88),
    ],
    "pricing_request": [
        (r"(?i)\b(how much|pricing|rates?|cost|price|(?<!not in )budget|investment|quote|proposal|what do you charge|packages?|plans?)\b", 0.88),
    ],
    "meeting_request": [
        (r"(?i)\b(schedule|calendar|meet|call|zoom|availability|free on|available|book a time|set up a call|hop on|quick chat|15 min|30 min)\b", 0.84),
    ],
    "objection": [
        (r"(?i)\b(too expensive|can'?t afford|not in budget|not a priority|bad timing|already have|using someone|don'?t need|not sure|skeptical|risky|concerned about)\b", 0.87),
    ],
    "negotiation": [
        (r"(?i)\b(discount|lower price|negotiate|flexible|deal|counter.?offer|can you do|what if we|volume|bulk|commit to|long.?term)\b", 0.80),
    ],
    "not_now": [
        (r"(?i)\b(not right now|maybe later|reach out later|next quarter|not a good time|circle back|revisit|touch base later|few months|not yet)\b", 0.88),
    ],
    "unsubscribe": [
        (r"(?i)\b(unsubscribe|remove me|stop.?email|don'?t contact|opt.?out|take me off|no more emails|stop sending)\b", 0.95),
    ],
    "support": [
        (r"(?i)\b(help with|issue|problem|broken|not working|bug|error|support|trouble|fix|resolve)\b", 0.80),
    ],
    "intake_reply": [
        (r"(?i)\b(here'?s the|attached|brand guide|assets?|logos?|brief|intake|onboarding|filled out|completed the|here you go)\b", 0.86),
    ],
    "revision_request": [
        (r"(?i)\b(revision|change|update|modify|adjust|tweak|redo|different|not quite|close but|almost|feedback on)\b", 0.82),
    ],
    "payment_question": [
        (r"(?i)\b(invoice|pay|payment|stripe|billing|charge|receipt|paid|wire|transfer)\b", 0.84),
    ],
    "referral": [
        (r"(?i)\b(refer|recommend|friend|colleague|someone who|know someone|introduce you|connect you with)\b", 0.86),
    ],
    "escalation": [
        (r"(?i)\b(legal|lawyer|attorney|sue|lawsuit|refund|chargeback|fraud|scam|furious|outraged|unacceptable|threatening|demand)\b", 0.92),
    ],
}

# Out-of-office detection (special case — always check first)
_OOO_PATTERN = re.compile(
    r"(?i)\b(out of office|on vacation|away from|auto.?reply|returning on|"
    r"limited access|away until|currently out|annual leave|maternity|paternity)\b"
)


# ── Quoted-content stripping ─────────────────────────────────────────────
# Inbound replies almost always carry the entire prior thread underneath.
# If we classify the RAW body we end up scoring keywords from our own past
# outbound (e.g. "$1,500", "pricing", "portfolio"), which produces false
# high-confidence intents. The stripper below removes the quoted section
# BEFORE scoring so intent is only derived from what the lead actually
# typed in this reply.

# 1. "On <date>, <person> wrote:" preamble (Gmail, Apple Mail, most clients)
_QUOTE_PREAMBLE_PATTERN = re.compile(
    r"(?is)\n\s*(?:on\s+[^\n]{1,200}\s+wrote\s*:|"
    r"on\s+\w{3,9}\s*,?\s+\w{3,9}\s+\d{1,2}\s*,?\s+\d{4}[^\n]*wrote\s*:|"
    r"-{2,}\s*original\s+message\s*-{2,}|"
    r"_{2,}\s*\n\s*from\s*:|"
    r"from\s*:\s*[^\n]{1,200}\n\s*sent\s*:|"
    r"begin forwarded message:|"
    r"forwarded\s+message)"
)

# 2. "Sent from my iPhone / Android / Outlook" signature markers
_SIGNATURE_MARKERS = re.compile(
    r"(?im)^\s*(?:--\s*$|"
    r"sent\s+from\s+my\s+(?:iphone|ipad|android|samsung|mobile|phone)|"
    r"get\s+outlook\s+for|"
    r"this\s+email\s+was\s+sent\s+from)"
)


def _strip_quoted_content(body: str) -> str:
    """Remove quoted reply history, forwarded content, and signatures.

    Returns just what the lead wrote in THIS reply. Used as input to the
    intent classifier so we don't score keywords from our own outbound.
    """
    if not body:
        return ""

    # Find the earliest "On ... wrote:" / "---Original Message---" marker and
    # truncate everything from there down.
    preamble_match = _QUOTE_PREAMBLE_PATTERN.search(body)
    if preamble_match:
        body = body[: preamble_match.start()]

    # Strip lines that begin with '>' (quoted text) — line by line
    kept_lines = []
    for raw_line in body.split("\n"):
        line = raw_line.rstrip("\r")
        # Quoted line: starts with optional whitespace + one or more '>'
        if re.match(r"^\s*>+", line):
            continue
        kept_lines.append(line)
    body = "\n".join(kept_lines)

    # Truncate at signature markers ("--", "Sent from my iPhone")
    sig_match = _SIGNATURE_MARKERS.search(body)
    if sig_match:
        body = body[: sig_match.start()]

    return body.strip()


# ── Reply mode hints ─────────────────────────────────────────────────────
# NOTE: this classifier only produces an initial *hint* at reply mode.
# The authoritative decision is made by apps/api/services/reply_policy.py
# which runs the full 10-step gate (forced escalation → forced draft →
# allowlist → confidence → standard template → cooldown). Callers should
# never trust the classifier's reply_mode directly — always pass the
# classification through reply_policy.decide_reply_mode.

# Classifier-level escalation hint: these intents ALWAYS force escalate
# in the policy engine regardless of any other signal. Keep in sync with
# reply_policy.CLASSIFIER_ESCALATION_INTENTS.
ESCALATE_INTENTS = {
    "escalation",        # legal / refund / fraud / threats
    "revision_request",  # needs the operator to process actual change
}


def _determine_reply_mode(intent: str, confidence: float) -> str:
    """Return a coarse reply-mode hint. Policy engine makes final decision."""
    if intent in ESCALATE_INTENTS:
        return "escalate"
    if confidence < 0.60:
        return "draft"  # uncertain — policy engine will gate
    return "draft"  # default — policy engine decides auto_send vs draft


# ── Public API ────────────────────────────────────────────────────────────


def classify_email(subject: str, body: str) -> ClassificationResult:
    """Classify an inbound email by intent.

    Returns classification with intent, confidence, rationale, and reply_mode.
    Idempotent — same input always produces same output.

    Quoted reply history and forwarded content are stripped before scoring
    so the classifier only reacts to what the lead typed in THIS reply.
    Otherwise our own past outbound (with words like "pricing", "$1,500")
    would produce false high-confidence intents on every thread reply.
    """
    # Strip inherited Re:/Fwd: subjects — they're from the original thread, not the reply
    clean_subject = re.sub(r"^(?:Re|Fwd?)\s*:\s*", "", subject, flags=re.IGNORECASE).strip()

    # Strip quoted history / forwarded content from the body BEFORE scoring
    clean_body = _strip_quoted_content(body or "")

    text = f"{clean_subject}\n{clean_body}"

    # Check OOO first (special case — not really a sales intent)
    if _OOO_PATTERN.search(text):
        return ClassificationResult(
            intent="not_now",
            confidence=0.92,
            rationale="Auto-reply or out-of-office detected",
            reply_mode="auto_send",
        )

    # Score each intent — body matches get full confidence, subject-only matches are penalized
    scores: list[tuple[str, float, str]] = []

    for intent, patterns in _PATTERNS.items():
        for pattern_str, base_confidence in patterns:
            body_match = re.search(pattern_str, clean_body)
            if body_match:
                scores.append((intent, base_confidence, f"Matched: '{body_match.group(0)}'"))
            elif clean_subject and re.search(pattern_str, clean_subject):
                # Subject-only match — discount confidence since subjects are often inherited
                scores.append((intent, base_confidence * 0.7, f"Matched in subject only"))

    if not scores:
        # Nothing matched post-strip. Two sub-cases:
        #
        #   (a) Short bare reply (e.g. "Hi", "Thanks", "Sounds good",
        #       "Interested") to our outbound pitch. This IS warm
        #       engagement — the lead bothered to reply. The warm_interest
        #       template is pre-approved + safe, so score high enough to
        #       clear the 0.85 auto_send gate.
        #
        #   (b) Longer bare reply without any keyword hit. More likely
        #       a custom question / ambiguous content. Score low so the
        #       policy engine drafts for operator review.
        bare = clean_body.strip() if clean_body else ""
        if bare:
            if len(bare) <= 60:
                return ClassificationResult(
                    intent="warm_interest",
                    confidence=0.86,
                    rationale=f"Short bare reply (warm engagement): '{bare[:60]}'",
                    reply_mode="draft",
                )
            return ClassificationResult(
                intent="warm_interest",
                confidence=0.55,
                rationale=f"Long bare reply (no keyword match): '{bare[:80]}'",
                reply_mode="draft",
            )
        return ClassificationResult(
            intent="unknown",
            confidence=0.20,
            rationale="No intent patterns matched",
            reply_mode="draft",
        )

    # Sort by confidence descending
    scores.sort(key=lambda x: x[1], reverse=True)

    best = scores[0]
    secondary = scores[1] if len(scores) > 1 else None

    reply_mode = _determine_reply_mode(best[0], best[1])

    return ClassificationResult(
        intent=best[0],
        confidence=best[1],
        rationale=best[2],
        secondary_intent=secondary[0] if secondary else None,
        secondary_confidence=secondary[1] if secondary else None,
        reply_mode=reply_mode,
    )


# ── Sales stage advancement rules ────────────────────────────────────────


STAGE_TRANSITIONS: dict[str, dict[str, str]] = {
    # intent → {current_stage: new_stage}
    "warm_interest": {
        "new_lead": "warm",
        "contacted": "warm",
        "replied": "warm",
    },
    "proof_request": {
        "new_lead": "warm",
        "contacted": "warm",
        "replied": "warm",
        "warm": "proof_sent",  # triggers proof send
    },
    "pricing_request": {
        "new_lead": "warm",
        "contacted": "warm",
        "replied": "warm",
        "warm": "pricing_sent",
        "proof_sent": "pricing_sent",
    },
    "meeting_request": {
        "new_lead": "warm",
        "contacted": "warm",
        "replied": "warm",
    },
    "negotiation": {
        "warm": "pricing_sent",
        "proof_sent": "pricing_sent",
        "pricing_sent": "pricing_sent",
    },
    "objection": {
        # Don't regress — stay at current stage
    },
    "not_now": {
        "new_lead": "dormant",
        "contacted": "dormant",
        "replied": "dormant",
        "warm": "dormant",
    },
    "unsubscribe": {
        "new_lead": "lost",
        "contacted": "lost",
        "replied": "lost",
        "warm": "lost",
        "proof_sent": "lost",
        "pricing_sent": "lost",
        "dormant": "lost",
    },
    "intake_reply": {
        # Client stage transition, not sales stage
    },
    "revision_request": {
        # Client stage transition
    },
}


def compute_stage_transition(
    current_stage: str, intent: str
) -> str | None:
    """Given current sales stage and classified intent, return new stage or None if no change."""
    transitions = STAGE_TRANSITIONS.get(intent, {})
    new_stage = transitions.get(current_stage)
    if new_stage and new_stage != current_stage:
        return new_stage
    return None
