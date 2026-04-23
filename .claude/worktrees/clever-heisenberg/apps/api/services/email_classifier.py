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
    "warm_interest": [
        (r"(?i)\b(interested|love to|sounds great|let'?s do|count me in|i'?m in|let'?s chat|let'?s talk|would love|happy to|excited|looking forward|tell me more|sounds interesting|intrigued)\b", 0.80),
    ],
    "proof_request": [
        (r"(?i)\b(examples?|portfolio|case stud|samples?|show me|see your work|demo|proof|previous work|past work|results you'?ve)\b", 0.82),
    ],
    "pricing_request": [
        (r"(?i)\b(how much|pricing|rates?|cost|price|(?<!not in )budget|investment|quote|proposal|what do you charge|packages?|plans?)\b", 0.82),
    ],
    "meeting_request": [
        (r"(?i)\b(schedule|calendar|meet|call|zoom|availability|free on|available|book a time|set up a call|hop on|quick chat|15 min|30 min)\b", 0.80),
    ],
    "objection": [
        (r"(?i)\b(too expensive|can'?t afford|not in budget|not a priority|bad timing|already have|using someone|don'?t need|not sure|skeptical|risky|concerned about)\b", 0.85),
    ],
    "negotiation": [
        (r"(?i)\b(discount|lower price|negotiate|flexible|deal|counter.?offer|can you do|what if we|volume|bulk|commit to|long.?term)\b", 0.75),
    ],
    "not_now": [
        (r"(?i)\b(not right now|maybe later|reach out later|next quarter|not a good time|circle back|revisit|touch base later|few months|not yet)\b", 0.82),
    ],
    "unsubscribe": [
        (r"(?i)\b(unsubscribe|remove me|stop.?email|don'?t contact|opt.?out|take me off|no more emails|stop sending)\b", 0.95),
    ],
    "support": [
        (r"(?i)\b(help with|issue|problem|broken|not working|bug|error|support|trouble|fix|resolve)\b", 0.75),
    ],
    "intake_reply": [
        (r"(?i)\b(here'?s the|attached|brand guide|assets?|logos?|brief|intake|onboarding|filled out|completed the|here you go)\b", 0.78),
    ],
    "revision_request": [
        (r"(?i)\b(revision|change|update|modify|adjust|tweak|redo|different|not quite|close but|almost|feedback on)\b", 0.78),
    ],
    "payment_question": [
        (r"(?i)\b(invoice|pay|payment|stripe|billing|charge|receipt|paid|wire|transfer)\b", 0.80),
    ],
    "referral": [
        (r"(?i)\b(refer|recommend|friend|colleague|someone who|know someone|introduce you|connect you with)\b", 0.72),
    ],
    "escalation": [
        (r"(?i)\b(legal|lawyer|attorney|sue|lawsuit|refund|chargeback|fraud|scam|furious|outraged|unacceptable|threatening|demand)\b", 0.90),
    ],
}

# Out-of-office detection (special case — always check first)
_OOO_PATTERN = re.compile(
    r"(?i)\b(out of office|on vacation|away from|auto.?reply|returning on|"
    r"limited access|away until|currently out|annual leave|maternity|paternity)\b"
)


# ── Reply mode rules ─────────────────────────────────────────────────────

# Auto-send: low-risk operational replies
AUTO_SEND_INTENTS = {"proof_request", "not_now", "unsubscribe"}

# Escalate-only: high-risk
ESCALATE_INTENTS = {"escalation"}

# Everything else: draft-for-approval
# (warm_interest, pricing_request, objection, negotiation, meeting_request, etc.)


def _determine_reply_mode(intent: str, confidence: float) -> str:
    """Determine reply mode based on intent and confidence."""
    if intent in ESCALATE_INTENTS:
        return "escalate"
    if confidence < 0.60:
        return "escalate"  # too uncertain — human review
    if intent in AUTO_SEND_INTENTS and confidence >= 0.75:
        return "auto_send"
    return "draft"


# ── Public API ────────────────────────────────────────────────────────────


def classify_email(subject: str, body: str) -> ClassificationResult:
    """Classify an inbound email by intent.

    Returns classification with intent, confidence, rationale, and reply_mode.
    Idempotent — same input always produces same output.
    """
    # Strip inherited Re:/Fwd: subjects — they're from the original thread, not the reply
    clean_subject = re.sub(r"^(?:Re|Fwd?)\s*:\s*", "", subject, flags=re.IGNORECASE).strip()
    text = f"{clean_subject}\n{body}"

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
            body_match = re.search(pattern_str, body)
            if body_match:
                scores.append((intent, base_confidence, f"Matched: '{body_match.group(0)}'"))
            elif clean_subject and re.search(pattern_str, clean_subject):
                # Subject-only match — discount confidence since subjects are often inherited
                scores.append((intent, base_confidence * 0.7, f"Matched in subject only"))

    if not scores:
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
