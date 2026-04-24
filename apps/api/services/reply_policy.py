"""Reply Policy — explicit decision engine for inbound email auto-send.

Implements the confidence-gated auto-send policy for ProofHook's inbound
email pipeline. The goal is:

    Do not require manual review for safe, standard, high-confidence sales
    replies. Do not blindly auto-send risky, ambiguous, negotiation-heavy,
    or commercially sensitive messages.

Decision order (evaluated top-to-bottom, first match wins):

    1. Automation-sender loop safety          → suppress (never reply)
    2. Forced escalation keyword match        → escalate
    3. Classifier declared escalation         → escalate
    4. Forced draft keyword match             → draft
    5. Auto-send globally disabled             → draft
    6. Intent not in auto-send allowlist      → draft
    7. Confidence below threshold             → draft
    8. Reply not using standard template      → draft
    9. Thread cooldown (already auto-replied) → draft
    10. All checks passed                      → auto_send

Every decision produces a DecisionTrace with the rule path, which is
persisted as JSONB on email_reply_drafts.decision_trace for audit.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

# ═══════════════════════════════════════════════════════════════════════════
#  Settings
# ═══════════════════════════════════════════════════════════════════════════

# Intents the classifier uses today that map to safe, standard, pre-approved
# reply templates. Anything outside this set can never auto-send regardless
# of confidence or settings.
STANDARD_TEMPLATE_INTENTS: frozenset[str] = frozenset(
    {
        "warm_interest",  # spec alias: simple_interest / send_more_info
        "proof_request",  # spec alias: proof_request
        "pricing_request",  # spec: only when reply uses standard package pricing
        "intake_reply",  # spec alias: onboarding_reply
        "not_now",  # operational — safe acknowledgement
        "unsubscribe",  # operational — safe confirmation
        "referral",  # operational — safe thank + redirect
    }
)

# Intents the classifier uses today that must ALWAYS be escalated.
CLASSIFIER_ESCALATION_INTENTS: frozenset[str] = frozenset(
    {
        "escalation",  # legal / refund / fraud / angry
        "revision_request",  # operator must process actual change
    }
)


@dataclass
class ReplyPolicySettings:
    """Org-level or system-level policy configuration.

    Load via `get_reply_policy(db, org_id)`. Defaults apply when no DB row
    exists, letting the system run out of the box without configuration.

    ProofHook Revenue-Ops doctrine (these defaults enforce it system-wide):
      • calls_enabled=False — no "hop on a call", no meeting CTAs, no
        Calendly. Every warm lead routes through the no-call funnel:
        reply → proof → secure package → payment → intake → production.
      • free_preview_enabled=False — replies do NOT default to offering
        "2 sample angles" or any unpaid spec work. The machine sells the
        package first. Previews are off unless an operator flips the
        flag for a specific org.
      • package_recommendation_mode="signal_based" — package routing is
        derived from lead signals (brand maturity, paid-media, recurring
        need, funnel weakness), not hardcoded to the $1,500 starter.
      • broad_market_positioning_enabled=True — public reply copy is
        category-agnostic. Niche framing is a tactical outbound-only
        lever, never leaks into inbound replies.
      • front_end_speed_language_mode="none" — "24-48 hours" and other
        speed promises are removed from reply copy by default.
    """

    auto_send_enabled: bool = True
    auto_send_min_confidence: float = 0.85
    auto_send_intent_allowlist: frozenset[str] = frozenset(
        {
            "proof_request",  # "show me examples" → portfolio
            "warm_interest",  # "love to hear more" → interest + CTA
            "pricing_request",  # standard package list only (template-gated)
            "intake_reply",  # "here's the brief" → acknowledge
            "not_now",  # "circle back later" → acknowledge + timer
            "unsubscribe",  # "remove me" → confirm removal
            "referral",  # "know someone who" → thank + redirect
        }
    )
    thread_cooldown_hours: int = 24

    # ── Revenue-Ops doctrine flags ──────────────────────────────────────
    # No-call default: every lead lands in the automated funnel.
    calls_enabled: bool = False

    # Free preview default off: the machine sells the package, not
    # unpaid spec work. If an operator flips this to True, previews
    # are still limited to the intents in preview_fallback_allowed_intents
    # and are framed as "recommended angles" / "creative directions" —
    # never "samples", "test runs", or "free work".
    free_preview_enabled: bool = False
    preview_fallback_allowed_intents: frozenset[str] = frozenset(
        {
            "proof_request",
            "objection",
        }
    )

    # Package recommendation mode:
    #   signal_based  → route via package_recommender (default)
    #   starter_default → anchor every reply to ugc-starter-pack (legacy)
    package_recommendation_mode: str = "signal_based"

    # Speed-promise language mode:
    #   none    → strip all "24-48 hours", "7 days", "fast turnaround" copy
    #   rare    → allow only when lead explicitly asks about timeline
    #   allowed → allow speed language in any reply
    front_end_speed_language_mode: str = "none"

    # Broad-market positioning: inbound replies never name verticals
    # (no "beauty brands", "fitness brands", "software brands"). Vertical
    # framing is a tactical outbound-only lever.
    broad_market_positioning_enabled: bool = True

    # ── Avatar follow-up doctrine (Revenue-Ops conversion accelerator) ──
    # The avatar is a warm-lead conversion asset, not a cold-opener gimmick.
    # It pushes attention/trust toward the best-fit package and respects
    # every no-call / no-free-work / broad-market rule that governs the
    # text reply engine. Defaults below enforce the premium doctrine.
    avatar_followup_enabled: bool = True
    avatar_cold_first_touch_enabled: bool = False  # NEVER the default opener
    avatar_allowed_triggers: frozenset[str] = frozenset(
        {
            "warm_interest",
            "pricing_request",
            "proof_request",
            "clicked_package_link_no_purchase",
            "checkout_started_no_payment",
            "intake_started_not_completed",
            "stalled_after_pricing",
            "stalled_after_proof",
            "high_value_lead_trust_acceleration",
        }
    )
    avatar_min_confidence: float = 0.70  # below → draft for review
    avatar_min_lead_score: int = 60  # below → suppress
    avatar_send_cooldown_hours: int = 48  # no re-send within window
    avatar_quality_mode: str = "premium"  # premium | standard | basic
    avatar_calls_enabled: bool = False  # no call language in scripts
    avatar_preview_enabled: bool = False  # no free-work language in scripts
    avatar_max_words: int = 90  # ~30-45s at natural pace
    avatar_max_cta_count: int = 1
    # Allowed CTA directions in avatar scripts (checkout / intake / proof only)
    avatar_allowed_cta_verbs: frozenset[str] = frozenset(
        {
            "secure",
            "finish",
            "complete",
            "review",
            "proceed",
        }
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Forced rules — safety rails that override the classifier
# ═══════════════════════════════════════════════════════════════════════════

# Forced-escalation patterns — legal, refund, angry, hostile, harassment.
# These ALWAYS force escalate, regardless of intent or confidence.
FORCED_ESCALATION_PATTERNS: list[tuple[str, str]] = [
    (
        r"(?i)\b(lawyer|attorney|legal\s+action|legal\s+counsel|legal\s+team|counsel\b|sue\b|suing|lawsuit|litigation|cease\s+and\s+desist)\b",
        "legal_threat",
    ),
    (
        r"(?i)\b(refund|chargeback|dispute\s+(the\s+)?charge|money\s+back|return\s+my\s+money|reverse\s+(the\s+)?payment)\b",
        "refund_dispute",
    ),
    (
        r"(?i)\b(fraud(?:ulent)?|scam|scammed|deceptive|deceived|misled|mislead|ripped\s+off|con\s+artist)\b",
        "fraud_accusation",
    ),
    (
        r"(?i)\b(furious|outraged|livid|appalled|disgusted|unacceptable|unprofessional|incompetent|disgraceful|shameful)\b",
        "hostile_tone",
    ),
    (
        r"(?i)\b(harass(?:ment|ing)?|threat(?:en|ening)?|intimidat(?:e|ing|ion)|retaliat(?:e|ion)|stalking)\b",
        "harassment",
    ),
    (
        r"(?i)\b(fuck|f\*+ck|shit|bullshit|asshole|a\*+hole|bastard|piss\s+off|screw\s+you|go\s+to\s+hell)\b",
        "profanity",
    ),
    (
        r"(?i)\b(report\s+you|file\s+(a\s+)?complaint|better\s+business\s+bureau|\bbbb\b|consumer\s+protection|ftc\b)\b",
        "complaint_threat",
    ),
]

# Forced-draft patterns — ambiguous commercial signals that require a human.
# These force DRAFT mode even when the classifier is confident and the
# intent is on the allowlist.
FORCED_DRAFT_PATTERNS: list[tuple[str, str]] = [
    # Budget / affordability pushback
    (
        r"(?i)\b(over\s+budget|out\s+of\s+budget|no\s+budget|tight\s+budget|limited\s+budget|shoestring|strapped\s+for\s+cash)\b",
        "budget_pushback",
    ),
    (
        r"(?i)\b(too\s+expensive|too\s+much|too\s+pricey|too\s+costly|cost\s+too\s+much|can'?t\s+afford|out\s+of\s+(our\s+)?price\s+range)\b",
        "pricing_objection",
    ),
    # Custom scope / tailoring asks
    (
        r"(?i)\b(customi[sz]e|customi[sz]ation|custom\s+(scope|package|quote|plan|bundle|offer|proposal|project)|tailor(ed)?|bespoke)\b",
        "custom_scope",
    ),
    (
        r"(?i)\b(something\s+(smaller|simpler|different|else|custom|more\s+basic)|scaled\s+down|mini\s+version|stripped\s+down|light\s+version)\b",
        "custom_scope",
    ),
    (
        r"(?i)\bcan\s+you\s+(do|make|offer|throw\s+in|include|add)\s+(something|a\s+smaller|a\s+custom|more|less|less\s+expensive)\b",
        "custom_request",
    ),
    (
        r"(?i)\b(what\s+if\s+we|would\s+you\s+(be\s+)?willing\s+to|any\s+room\s+to|flexible\s+on|wiggle\s+room|negotiate\b)\b",
        "negotiation_signal",
    ),
    (
        r"(?i)\b(discount|reduce(d)?\s+(price|rate|cost)|lower\s+(the\s+)?(price|rate|cost)|price\s+break|price\s+cut|deal\s+on\s+the\s+price)\b",
        "discount_ask",
    ),
    # Phone / call / meeting asks — operator handles these by hand
    (
        r"(?i)\b(hop\s+on\s+(a\s+)?(quick\s+)?(call|chat|zoom)|jump\s+on\s+(a\s+)?(call|chat|zoom)|quick\s+(phone\s+)?call|phone\s+call|zoom\s+(link|call|meeting)|schedule\s+a\s+call|book\s+a\s+call|get\s+on\s+(a\s+)?call)\b",
        "call_request",
    ),
    # Enterprise / partnership / revenue share
    (
        r"(?i)\b(enterprise\s+(deal|contract|agreement|plan|pricing|inquiry|account)|corporate\s+agreement|master\s+service\s+agreement|\bmsa\b|legal\s+review|procurement)\b",
        "enterprise_inquiry",
    ),
    (
        r"(?i)\b(partnership|partner\s+(with|up)|strategic\s+partner|joint\s+venture|co.?brand(?:ing)?|affiliate\s+program|referral\s+program|white.?label)\b",
        "partnership_inquiry",
    ),
    (
        r"(?i)\b(revenue\s+share|rev\s+share|revshare|profit\s+share|equity\s+(split|share|stake)|commission\s+structure|royalty)\b",
        "revenue_share_inquiry",
    ),
    # High-value / unusual commercial
    (
        r"(?i)\b(six.?figure|seven.?figure|\$\s*\d{1,3}[,.]?\d{3}[,.]?\d{3}|large\s+(contract|deal|project|engagement)|big\s+(project|budget))\b",
        "high_value_inquiry",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
#  Automation-sender loop safety (bots, bounces, OOO, self-loop)
# ═══════════════════════════════════════════════════════════════════════════

_AUTOMATION_SENDER_PATTERNS = [
    r"^(no[._-]?reply|noreply|donotreply|do[._-]?not[._-]?reply)@",
    r"^(mailer[._-]?daemon|postmaster|bounces?|bounce[._-]?notification|return[._-]?path)@",
    r"^(notifications?|alerts?|updates?|news|newsletter|digest|info|system|root|admin|webmaster)@",
    r"^(automated|auto|robot|bot|cron|daemon)@",
    r"@(bounce|bounces|mailer|mailgun|sendgrid|amazonses|postmark)\.",
    r"@(.*\.)?(mailchimp|constantcontact|convertkit|activecampaign|hubspot|marketo|drip|klaviyo)\.",
    r"@(.*\.)?(salesforce|outreach|salesloft|apollo|lemlist|mailshake|reply\.io)\.",
]

_AUTOMATION_SUBJECT_PATTERNS = [
    (
        r"(?i)^(re:\s*)?(undeliverable|delivery\s+status|mail\s+delivery|returned\s+mail|delivery\s+(failure|has\s+failed))",
        "bounce_subject",
    ),
    (
        r"(?i)\b(auto[._-]?reply|automatic\s+reply|auto\s+response|out\s+of\s+(the\s+)?office|currently\s+(out|away)|away\s+from\s+(the\s+)?office|maternity|paternity|annual\s+leave)\b",
        "ooo_subject",
    ),
    (
        r"(?i)^(re:\s*)?(welcome\s+to|verify\s+your|confirm\s+your|activate\s+your|your\s+.+\s+(receipt|invoice|statement))",
        "transactional_subject",
    ),
]


def _is_automation_sender(from_email: str, subject: str) -> tuple[bool, str | None]:
    """Check if sender looks like a bot/bounce/OOO — returns (is_auto, reason)."""
    if not from_email:
        return True, "empty_from_email"

    addr = from_email.strip().lower()

    # Self-loop: never reply to our own domain
    if addr.endswith("@proofhook.com"):
        return True, "self_loop_proofhook"

    for pat in _AUTOMATION_SENDER_PATTERNS:
        if re.search(pat, addr):
            return True, f"sender_pattern:{pat[:40]}"

    if subject:
        for pat, label in _AUTOMATION_SUBJECT_PATTERNS:
            if re.search(pat, subject):
                return True, f"subject_pattern:{label}"

    return False, None


# ═══════════════════════════════════════════════════════════════════════════
#  Decision trace — structured audit output
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class DecisionTrace:
    """Full audit trail of a reply-mode decision.

    Every create_reply_draft call produces one of these and it's persisted
    as JSONB on email_reply_drafts.decision_trace so every decision path is
    inspectable in logs and thread history.

    The Revenue-Ops doctrine fields (recommended_package, lead_signals_used,
    call_path_suppressed, preview_fallback_allowed, broad_market_positioning)
    are populated even when the decision is not auto_send — they record what
    the machine *would have* recommended so drafts in human review still
    carry the package routing and doctrine state.
    """

    intent: str
    confidence: float
    final_mode: str = "draft"  # auto_send | draft | escalate | suppress
    mode_source: str = ""  # which rule produced final_mode

    # Per-check results — None means "not evaluated yet" or "passed"
    automation_loop_match: str | None = None  # bot/bounce/OOO reason
    forced_escalation_match: str | None = None  # keyword rule label
    classifier_escalation: str | None = None  # intent name if classifier forced escalate
    forced_draft_match: str | None = None  # keyword rule label
    auto_send_disabled: bool = False  # settings gate
    allowlist_check: str | None = None  # "hit" | "miss:<intent>"
    confidence_check: str | None = None  # "pass" | "miss:0.80<0.85"
    template_check: str | None = None  # "standard" | "custom"
    thread_cooldown: str | None = None  # "pass" | "hit"

    # ── Revenue-Ops doctrine audit fields ───────────────────────────────
    # Package routing: what the signal-based recommender chose, why, and
    # what signals drove the decision. These are always populated so the
    # audit trail shows the full reasoning even when the reply is drafted
    # or escalated rather than auto-sent.
    recommended_package: str | None = None  # e.g. "performance-creative-pack"
    recommendation_rationale: str = ""  # one-sentence why
    lead_signals_used: list[str] = field(default_factory=list)  # ["paid_media", "recurring_need"]
    signal_confidence: float = 0.0  # 0.0–1.0, how strong the signal set was
    package_default_anchor_avoided: bool = True  # did we NOT default to ugc-starter-pack?

    # No-call doctrine: True when a call-path pattern was detected and
    # the machine suppressed it (routed to package path instead of call).
    call_path_suppressed: bool = False

    # Free-preview doctrine: whether preview fallback was offered in the
    # final reply copy. By default this is False (sell-the-package mode).
    preview_fallback_allowed: bool = False
    preview_fallback_used: bool = False
    preview_fallback_framing: str = ""  # "" | "recommended_angles" | "creative_directions"

    # Broad-market positioning: True when the reply contains no vertical
    # framing. Inbound replies MUST always be True. First-touch outbound
    # can flip this to False when a vertical template is used tactically.
    broad_market_positioning: bool = True
    niche_framing_used: bool = False  # True if the reply mentions a specific vertical

    # Speed-language doctrine: what the reply copy says about timing.
    # "none" means no speed promise appears in the reply.
    speed_language_mode: str = "none"  # none | rare | allowed

    rules_evaluated: list[str] = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> dict:
        """Serialize for JSONB persistence.

        Strips None and empty strings but preserves booleans and numeric
        zero, because the doctrine audit fields (`call_path_suppressed=False`,
        `preview_fallback_used=False`, `signal_confidence=0.0`) carry
        meaning even when they're at their default values.
        """
        out: dict = {}
        for k, v in asdict(self).items():
            if v is None:
                continue
            if isinstance(v, str) and v == "":
                continue
            if isinstance(v, list) and not v:
                continue
            out[k] = v
        # Always include rules_evaluated and rationale even if empty — they
        # are the audit trail spine and downstream tooling expects them.
        out["rules_evaluated"] = self.rules_evaluated
        out["rationale"] = self.rationale
        return out


# ═══════════════════════════════════════════════════════════════════════════
#  Keyword-rule helpers
# ═══════════════════════════════════════════════════════════════════════════


def _match_first(patterns: list[tuple[str, str]], text: str) -> tuple[str | None, str | None]:
    """Return (label, pattern) of first matching rule, or (None, None)."""
    for pat, label in patterns:
        if re.search(pat, text):
            return label, pat
    return None, None


def detect_forced_escalation(subject: str, body: str) -> tuple[str | None, str | None]:
    """Return (label, pattern) if text matches an escalation safety rail."""
    return _match_first(FORCED_ESCALATION_PATTERNS, f"{subject}\n{body}")


def detect_forced_draft(subject: str, body: str) -> tuple[str | None, str | None]:
    """Return (label, pattern) if text matches a forced-draft safety rail."""
    return _match_first(FORCED_DRAFT_PATTERNS, f"{subject}\n{body}")


def is_standard_template_intent(intent: str) -> bool:
    """Return True if the intent has a pre-approved, static reply template.

    For pricing_request this is True when the reply uses the standard package
    list (no custom quote, no altered terms). The template itself is static
    in reply_engine._build_reply_body, so intent membership is sufficient.
    """
    return intent in STANDARD_TEMPLATE_INTENTS


# ═══════════════════════════════════════════════════════════════════════════
#  Main decision function
# ═══════════════════════════════════════════════════════════════════════════


def decide_reply_mode(
    *,
    intent: str,
    confidence: float,
    subject: str,
    body: str,
    from_email: str,
    reply_will_use_standard_template: bool,
    recent_auto_reply_in_thread: bool = False,
    settings: ReplyPolicySettings | None = None,
) -> DecisionTrace:
    """Run the 10-step decision engine and return a DecisionTrace.

    This is the ONLY place reply-mode decisions are made. Callers must use
    the trace's final_mode and persist the full trace as audit.
    """
    settings = settings or ReplyPolicySettings()
    trace = DecisionTrace(intent=intent, confidence=confidence)

    # ── Step 1: automation loop safety ──────────────────────────────────
    is_auto, auto_reason = _is_automation_sender(from_email, subject)
    if is_auto:
        trace.final_mode = "suppress"
        trace.mode_source = "automation_loop"
        trace.automation_loop_match = auto_reason
        trace.rules_evaluated.append(f"automation_loop:HIT:{auto_reason}")
        trace.rationale = f"automation loop risk ({auto_reason}) — never auto-reply"
        return trace
    trace.rules_evaluated.append("automation_loop:PASS")

    # ── Step 2: forced escalation (highest priority safety rail) ────────
    esc_label, esc_pat = detect_forced_escalation(subject, body)
    if esc_label:
        trace.final_mode = "escalate"
        trace.mode_source = "forced_escalation"
        trace.forced_escalation_match = esc_label
        trace.rules_evaluated.append(f"forced_escalation:HIT:{esc_label}")
        trace.rationale = f"forced escalation triggered: {esc_label}"
        return trace
    trace.rules_evaluated.append("forced_escalation:PASS")

    # ── Step 3: classifier-declared escalation intent ───────────────────
    if intent in CLASSIFIER_ESCALATION_INTENTS:
        trace.final_mode = "escalate"
        trace.mode_source = "classifier_escalation"
        trace.classifier_escalation = intent
        trace.rules_evaluated.append(f"classifier_escalation:HIT:{intent}")
        trace.rationale = f"classifier declared {intent} as escalation intent"
        return trace
    trace.rules_evaluated.append("classifier_escalation:PASS")

    # ── Step 4: forced-draft keyword rules ──────────────────────────────
    draft_label, draft_pat = detect_forced_draft(subject, body)
    if draft_label:
        trace.final_mode = "draft"
        trace.mode_source = "forced_draft"
        trace.forced_draft_match = draft_label
        trace.rules_evaluated.append(f"forced_draft:HIT:{draft_label}")
        trace.rationale = f"forced draft triggered: {draft_label}"
        return trace
    trace.rules_evaluated.append("forced_draft:PASS")

    # ── Step 5: is auto-send globally enabled? ──────────────────────────
    if not settings.auto_send_enabled:
        trace.final_mode = "draft"
        trace.mode_source = "auto_send_disabled"
        trace.auto_send_disabled = True
        trace.rules_evaluated.append("auto_send_enabled:FALSE")
        trace.rationale = "auto_send_enabled=false — default to draft"
        return trace
    trace.rules_evaluated.append("auto_send_enabled:TRUE")

    # ── Step 6: is intent on the auto-send allowlist? ───────────────────
    if intent not in settings.auto_send_intent_allowlist:
        trace.final_mode = "draft"
        trace.mode_source = "allowlist_miss"
        trace.allowlist_check = f"miss:{intent}"
        trace.rules_evaluated.append(f"allowlist:MISS:{intent}")
        trace.rationale = f"{intent} not in auto-send allowlist"
        return trace
    trace.allowlist_check = f"hit:{intent}"
    trace.rules_evaluated.append(f"allowlist:HIT:{intent}")

    # ── Step 7: does confidence clear the threshold? ────────────────────
    if confidence < settings.auto_send_min_confidence:
        trace.final_mode = "draft"
        trace.mode_source = "confidence_below_threshold"
        trace.confidence_check = f"miss:{confidence:.2f}<{settings.auto_send_min_confidence:.2f}"
        trace.rules_evaluated.append(f"confidence:MISS:{confidence:.2f}<{settings.auto_send_min_confidence:.2f}")
        trace.rationale = f"confidence {confidence:.2f} below {settings.auto_send_min_confidence:.2f}"
        return trace
    trace.confidence_check = f"pass:{confidence:.2f}>={settings.auto_send_min_confidence:.2f}"
    trace.rules_evaluated.append(f"confidence:PASS:{confidence:.2f}>={settings.auto_send_min_confidence:.2f}")

    # ── Step 8: reply uses a standard pre-approved template? ────────────
    if not reply_will_use_standard_template:
        trace.final_mode = "draft"
        trace.mode_source = "non_standard_template"
        trace.template_check = "custom"
        trace.rules_evaluated.append("template:MISS:custom_reply")
        trace.rationale = "reply content is not a standard pre-approved template"
        return trace
    trace.template_check = "standard"
    trace.rules_evaluated.append("template:PASS:standard")

    # ── Step 9: thread cooldown — one auto-reply per thread per 24h ─────
    if recent_auto_reply_in_thread:
        trace.final_mode = "draft"
        trace.mode_source = "thread_cooldown"
        trace.thread_cooldown = f"hit:{settings.thread_cooldown_hours}h"
        trace.rules_evaluated.append(f"thread_cooldown:HIT:{settings.thread_cooldown_hours}h")
        trace.rationale = f"thread already has an auto-reply in last {settings.thread_cooldown_hours}h"
        return trace
    trace.thread_cooldown = "pass"
    trace.rules_evaluated.append("thread_cooldown:PASS")

    # ── Step 10: all checks passed — auto-send ──────────────────────────
    trace.final_mode = "auto_send"
    trace.mode_source = "all_checks_passed"
    trace.rationale = f"intent={intent} conf={confidence:.2f} standard template — all safety rails passed"
    return trace


# ═══════════════════════════════════════════════════════════════════════════
#  Settings loader (DB-backed, with defaults fallback)
# ═══════════════════════════════════════════════════════════════════════════


async def get_reply_policy(db, org_id) -> ReplyPolicySettings:
    """Load policy settings for an org, falling back to defaults.

    Future extension: read from an `email_reply_policy` settings row keyed
    by org_id. For now returns defaults so the system runs without any
    configuration required.
    """
    return ReplyPolicySettings()
