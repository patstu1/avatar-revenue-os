"""Avatar follow-up system — ProofHook Revenue-Ops conversion accelerator.

This is NOT a gimmick. The avatar is a warm-lead conversion asset that
pushes attention and trust toward the best-fit package and keeps the
lead on the no-call, package-first funnel:

    lead → reply → best-fit package → secure package → intake → production

DOCTRINE (non-negotiable):
  • Broad-market positioning — no vertical framing, ever.
  • Package-first selling — every script names the best-fit package.
  • No-call funnel — scripts NEVER offer a call, chat, walkthrough,
    or meeting. Call asks in the inbound body route to draft, not auto.
  • No free-work — scripts NEVER offer "free sample angles",
    "trial creative", or any unpaid spec work.
  • No starter-pack anchor — package picks come from the signal-based
    recommender. Starter fires ONLY on explicit test / early-stage leads.
  • Premium quality — every request to the provider stack must carry
    the premium visual spec (lighting, wardrobe, framing, expression,
    environment). A regression that flips quality_mode to "basic" fails
    the quality gate.

Module surface (everything here is pure Python — no DB, no network,
no LLM calls — so unit tests run in milliseconds):

    AvatarFollowupPolicy        — frozen config bundle (settings snapshot)
    AvatarTrigger                — enum of approved triggers
    AvatarAssetState             — queued → generating → ready → sent → viewed
    AvatarScript                 — structured script with doctrine gates
    AvatarQualitySpec            — premium visual/voice specification
    AvatarFollowupRecord         — full tracked artifact (DB-ready dict)
    AvatarProviderAdapter        — protocol any real provider must satisfy
    FakeAvatarProvider           — in-memory test double
    build_avatar_script()        — scripts from signals + package
    decide_avatar_eligibility()  — is this trigger+lead state eligible?
    decide_avatar_send_mode()    — auto-send / draft / escalate
    build_avatar_delivery_email()— short delivery note for the inbox send
    score_avatar_quality_spec()  — enforce premium checklist
    generate_avatar_followup()   — end-to-end orchestrator
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional, Protocol

from apps.api.services.package_recommender import (
    PackageRecommendation,
    recommend_package,
)
from apps.api.services.reply_policy import (
    FORCED_ESCALATION_PATTERNS,
    ReplyPolicySettings,
    detect_forced_draft,
    detect_forced_escalation,
)
from packages.clients.email_templates import (
    PACKAGES,
    package_checkout_url,
    package_intake_url,
)


# ═══════════════════════════════════════════════════════════════════════════
#  Approved triggers
# ═══════════════════════════════════════════════════════════════════════════

class AvatarTrigger(str, Enum):
    """The only states that may produce an avatar follow-up.

    These map to either an inbound intent (`warm_interest` etc.) or a
    lead lifecycle event (`checkout_started_no_payment`) emitted by the
    CRM / worker side.
    """
    WARM_INTEREST = "warm_interest"
    PRICING_REQUEST = "pricing_request"
    PROOF_REQUEST = "proof_request"
    CLICKED_PACKAGE_LINK_NO_PURCHASE = "clicked_package_link_no_purchase"
    CHECKOUT_STARTED_NO_PAYMENT = "checkout_started_no_payment"
    INTAKE_STARTED_NOT_COMPLETED = "intake_started_not_completed"
    STALLED_AFTER_PRICING = "stalled_after_pricing"
    STALLED_AFTER_PROOF = "stalled_after_proof"
    HIGH_VALUE_LEAD_TRUST_ACCELERATION = "high_value_lead_trust_acceleration"


# Triggers that use the short personalized opener style
_WARM_OPEN_TRIGGERS = frozenset({
    AvatarTrigger.WARM_INTEREST,
    AvatarTrigger.PRICING_REQUEST,
    AvatarTrigger.PROOF_REQUEST,
    AvatarTrigger.HIGH_VALUE_LEAD_TRUST_ACCELERATION,
})

# Triggers that use the "you got close — here's the path" re-engagement style
_REENGAGE_TRIGGERS = frozenset({
    AvatarTrigger.CLICKED_PACKAGE_LINK_NO_PURCHASE,
    AvatarTrigger.CHECKOUT_STARTED_NO_PAYMENT,
    AvatarTrigger.INTAKE_STARTED_NOT_COMPLETED,
    AvatarTrigger.STALLED_AFTER_PRICING,
    AvatarTrigger.STALLED_AFTER_PROOF,
})


# ═══════════════════════════════════════════════════════════════════════════
#  State machine
# ═══════════════════════════════════════════════════════════════════════════

class AvatarAssetState(str, Enum):
    """Lifecycle states tracked on every AvatarFollowupRecord."""
    QUEUED = "queued"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"
    SENT = "sent"
    VIEWED = "viewed"


_VALID_TRANSITIONS: dict[AvatarAssetState, frozenset[AvatarAssetState]] = {
    AvatarAssetState.QUEUED: frozenset({AvatarAssetState.GENERATING, AvatarAssetState.FAILED}),
    AvatarAssetState.GENERATING: frozenset({AvatarAssetState.READY, AvatarAssetState.FAILED}),
    AvatarAssetState.READY: frozenset({AvatarAssetState.SENT, AvatarAssetState.FAILED}),
    AvatarAssetState.SENT: frozenset({AvatarAssetState.VIEWED}),
    AvatarAssetState.FAILED: frozenset(),
    AvatarAssetState.VIEWED: frozenset(),
}


def can_transition(src: AvatarAssetState, dst: AvatarAssetState) -> bool:
    """Return True if `src → dst` is a valid lifecycle transition."""
    return dst in _VALID_TRANSITIONS.get(src, frozenset())


# ═══════════════════════════════════════════════════════════════════════════
#  Premium quality spec — the visual/voice contract handed to the provider
# ═══════════════════════════════════════════════════════════════════════════

_PREMIUM_REQUIRED_FIELDS: frozenset[str] = frozenset({
    "avatar_id",
    "voice_id",
    "lighting_profile",
    "background_type",
    "framing",
    "wardrobe_tier",
    "facial_expression",
    "pacing_style",
    "resolution",
})

# Allowed enum values per field — anything else fails the quality gate.
_PREMIUM_ENUMS: dict[str, frozenset[str]] = {
    "lighting_profile": frozenset({"soft_contrast_cinematic", "clean_studio_key", "natural_window"}),
    "background_type": frozenset({"dark_premium", "clean_studio", "subtle_environment"}),
    "framing": frozenset({"medium_close_up", "chest_up", "eye_level"}),
    "wardrobe_tier": frozenset({"founder_operator", "premium_minimal", "tailored_neutral"}),
    "facial_expression": frozenset({"confident_calm", "warm_composed", "neutral_intent"}),
    "pacing_style": frozenset({"measured_premium", "steady_confident"}),
    "resolution": frozenset({"1080p", "4k"}),
}


@dataclass
class AvatarQualitySpec:
    """Visual + voice presentation contract for the provider stack.

    This is the premium checklist. Every field must be populated with
    an allowed enum value OR score_avatar_quality_spec() returns `False`
    and the orchestrator refuses to send the request.

    The user is explicit: a low-quality avatar HURTS trust. So the
    system fails closed — if premium cannot be guaranteed, we draft
    for review instead of shipping something cheesy or uncanny.
    """
    avatar_id: str                             # real provider avatar id
    voice_id: str                              # real provider voice id
    lighting_profile: str = "soft_contrast_cinematic"
    background_type: str = "dark_premium"
    framing: str = "chest_up"
    wardrobe_tier: str = "founder_operator"
    facial_expression: str = "confident_calm"
    pacing_style: str = "measured_premium"
    resolution: str = "1080p"
    # Safety rails — these are forbidden across every field value.
    forbid_over_animation: bool = True
    forbid_cartoon_style: bool = True
    forbid_aggressive_energy: bool = True

    def to_provider_config(self) -> dict:
        """Serialize for MediaRequest.config."""
        return {
            "avatar_id": self.avatar_id,
            "voice_id": self.voice_id,
            "visual": {
                "lighting_profile": self.lighting_profile,
                "background_type": self.background_type,
                "framing": self.framing,
                "wardrobe_tier": self.wardrobe_tier,
                "facial_expression": self.facial_expression,
            },
            "delivery": {
                "pacing_style": self.pacing_style,
                "resolution": self.resolution,
            },
            "safety": {
                "forbid_over_animation": self.forbid_over_animation,
                "forbid_cartoon_style": self.forbid_cartoon_style,
                "forbid_aggressive_energy": self.forbid_aggressive_energy,
            },
            "quality_tier": "premium",
        }


def score_avatar_quality_spec(
    spec: AvatarQualitySpec,
    quality_mode: str = "premium",
) -> tuple[bool, list[str]]:
    """Return (passes, issues). Premium mode is strict on every field.

    Called before the provider request is submitted. If this fails, the
    orchestrator does NOT generate — it drops to draft for review so no
    low-end / uncanny / cheesy output ever ships.
    """
    issues: list[str] = []

    # Required non-empty fields
    for f in _PREMIUM_REQUIRED_FIELDS:
        val = getattr(spec, f, "")
        if not val or not isinstance(val, str):
            issues.append(f"missing_field:{f}")

    # Enum gates on premium mode only — standard / basic skip these
    if quality_mode == "premium":
        for field_name, allowed in _PREMIUM_ENUMS.items():
            val = getattr(spec, field_name, "")
            if val and val not in allowed:
                issues.append(f"invalid_enum:{field_name}:{val}")

        # Safety rails MUST be on in premium mode
        if not spec.forbid_over_animation:
            issues.append("safety_off:forbid_over_animation")
        if not spec.forbid_cartoon_style:
            issues.append("safety_off:forbid_cartoon_style")
        if not spec.forbid_aggressive_energy:
            issues.append("safety_off:forbid_aggressive_energy")

    return (len(issues) == 0, issues)


def default_premium_spec(avatar_id: str, voice_id: str) -> AvatarQualitySpec:
    """Build the ProofHook-standard premium spec for a given avatar/voice."""
    return AvatarQualitySpec(
        avatar_id=avatar_id,
        voice_id=voice_id,
        lighting_profile="soft_contrast_cinematic",
        background_type="dark_premium",
        framing="chest_up",
        wardrobe_tier="founder_operator",
        facial_expression="confident_calm",
        pacing_style="measured_premium",
        resolution="1080p",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Script builder — doctrine-gated, package-first, under 90 words
# ═══════════════════════════════════════════════════════════════════════════

# Forbidden phrases in any avatar script (surface: match as regex, case-insensitive).
# These mirror the text reply doctrine — if any of these fire, the script is
# rejected and the follow-up is marked failed.
_FORBIDDEN_SCRIPT_PATTERNS: list[tuple[str, str]] = [
    (r"(?i)\bai[-\s]?powered\b", "ai_powered"),
    (r"(?i)\bai\s+avatar\b", "ai_avatar_label"),
    (r"(?i)\bcool\s+ai\s+video\b", "cool_ai_video"),
    (r"(?i)\bbook\s+a\s+call\b", "book_call"),
    (r"(?i)\bhop\s+on\s+a\s+call\b", "hop_on_call"),
    (r"(?i)\bjump\s+on\s+a\s+(call|chat|zoom)\b", "jump_on_call"),
    (r"(?i)\bquick\s+call\b", "quick_call"),
    (r"(?i)\bschedule\s+a\s+call\b", "schedule_call"),
    (r"(?i)\blet'?s\s+chat\b", "lets_chat"),
    (r"(?i)\blet\s+me\s+walk\s+you\s+through\b", "walk_through"),
    (r"(?i)\bhappy\s+to\s+chat\b", "happy_to_chat"),
    (r"(?i)\bfree\s+(sample|test\s+run|trial|preview)\b", "free_sample"),
    (r"(?i)\btrial\s+creative\b", "trial_creative"),
    (r"(?i)\bsample\s+angles\b", "sample_angles"),
    (r"(?i)\bspec\s+work\b", "spec_work"),
    # Vertical framing (broad-market guard)
    (r"(?i)\b(beauty|fitness|supplement|saas|ecom(merce)?)\s+brands?\b", "niche_framing"),
]


_ALLOWED_CTA_LINES: dict[str, str] = {
    AvatarTrigger.WARM_INTEREST.value:
        "Secure it here and intake starts immediately: {checkout_url}",
    AvatarTrigger.PRICING_REQUEST.value:
        "Secure the package here — pricing is locked: {checkout_url}",
    AvatarTrigger.PROOF_REQUEST.value:
        "Secure the package here — the first proof point ships against your actual offer: {checkout_url}",
    AvatarTrigger.CLICKED_PACKAGE_LINK_NO_PURCHASE.value:
        "Finish checkout here and we move straight into intake: {checkout_url}",
    AvatarTrigger.CHECKOUT_STARTED_NO_PAYMENT.value:
        "Finish checkout here and intake starts immediately: {checkout_url}",
    AvatarTrigger.INTAKE_STARTED_NOT_COMPLETED.value:
        "Complete intake here and we start production: {intake_url}",
    AvatarTrigger.STALLED_AFTER_PRICING.value:
        "Secure the package here whenever you're ready: {checkout_url}",
    AvatarTrigger.STALLED_AFTER_PROOF.value:
        "Proceed now and we begin production: {checkout_url}",
    AvatarTrigger.HIGH_VALUE_LEAD_TRUST_ACCELERATION.value:
        "Secure the fit here and we move immediately: {checkout_url}",
}


@dataclass
class AvatarScript:
    """A fully-assembled avatar script, pre-checked against doctrine.

    The script is structured — not free text — so every doctrine gate
    runs on exactly the fields the provider will speak.
    """
    trigger: str
    package_slug: str
    package_name: str
    package_price: str
    brand_name: str                  # "" if unknown
    opener: str
    observation: str
    recommendation: str
    cta: str
    checkout_url: str
    intake_url: str

    # Safety audit populated by build_avatar_script()
    doctrine_issues: list[str] = field(default_factory=list)
    word_count: int = 0
    cta_count: int = 0

    @property
    def full_text(self) -> str:
        """The text the voice engine will actually speak."""
        parts = [self.opener, self.observation, self.recommendation, self.cta]
        return " ".join(p.strip() for p in parts if p.strip())

    def passes_doctrine(self, settings: ReplyPolicySettings) -> bool:
        return (
            not self.doctrine_issues
            and self.word_count <= settings.avatar_max_words
            and self.cta_count <= settings.avatar_max_cta_count
        )


def _count_ctas(text: str) -> int:
    """Count CTA-style imperative lines in the spoken text."""
    # A CTA = exactly one of the allowed action verbs in imperative position.
    verbs = r"secure|finish|complete|review|proceed"
    hits = re.findall(rf"(?i)\b({verbs})\b", text)
    return len(hits)


def _doctrine_scan(text: str) -> list[str]:
    """Return list of doctrine labels the text violates."""
    issues: list[str] = []
    for pat, label in _FORBIDDEN_SCRIPT_PATTERNS:
        if re.search(pat, text):
            issues.append(label)
    return issues


def build_avatar_script(
    *,
    trigger: AvatarTrigger,
    recommendation: PackageRecommendation,
    brand_name: str = "",
    settings: Optional[ReplyPolicySettings] = None,
) -> AvatarScript:
    """Build a doctrine-compliant avatar script.

    Structure (always in this order):
      1. short personalized opener
      2. one specific observation about the creative situation
      3. best-fit package recommendation (verbatim package name + price)
      4. one direct next step (one CTA, allowed verbs only)
    """
    settings = settings or ReplyPolicySettings()
    pkg = PACKAGES.get(recommendation.slug)
    if not pkg:
        raise ValueError(f"unknown package slug: {recommendation.slug}")

    pkg_name = pkg["name"]
    pkg_price = pkg["price"]
    checkout_url = package_checkout_url(recommendation.slug)
    intake_url = package_intake_url(recommendation.slug)

    brand_label = brand_name.strip() or "your brand"

    # ── Opener (warm vs re-engage) ─────────────────────────────────────
    if trigger in _REENGAGE_TRIGGERS:
        opener = f"Quick note for {brand_label}."
    else:
        opener = f"Took a look at {brand_label}."

    # ── Observation — short, signal-driven, no hype, no niche ──────────
    observation = _build_observation(trigger, recommendation)

    # ── Recommendation — verbatim package name + price, one sentence ──
    recommendation_line = (
        f"Best fit is {pkg_name} at {pkg_price} — built for exactly this situation."
    )

    # ── CTA — one line, from the approved table ────────────────────────
    cta_template = _ALLOWED_CTA_LINES[trigger.value]
    cta_line = cta_template.format(checkout_url=checkout_url, intake_url=intake_url)

    script = AvatarScript(
        trigger=trigger.value,
        package_slug=recommendation.slug,
        package_name=pkg_name,
        package_price=pkg_price,
        brand_name=brand_name,
        opener=opener,
        observation=observation,
        recommendation=recommendation_line,
        cta=cta_line,
        checkout_url=checkout_url,
        intake_url=intake_url,
    )

    # Post-build doctrine scan
    full_text = script.full_text
    script.doctrine_issues = _doctrine_scan(full_text)
    script.word_count = len(full_text.split())
    script.cta_count = _count_ctas(full_text)

    return script


def _build_observation(
    trigger: AvatarTrigger,
    recommendation: PackageRecommendation,
) -> str:
    """One-sentence observation tied to the signal set.

    Kept deliberately short and broad-market — no vertical framing, no
    "beauty brands", no audience-metric language.
    """
    slug = recommendation.slug
    if slug == "performance-creative-pack":
        return "The paid side is moving but the creative is the bottleneck."
    if slug == "creative-strategy-funnel-upgrade":
        return "The offer is strong, the funnel around it is leaking trust."
    if slug == "growth-content-pack":
        return "There's a consistent output gap — and it's costing momentum."
    if slug == "launch-sprint":
        return "The window is narrow — the creative has to land the first time."
    if slug == "full-creative-retainer":
        return "The spend is scaling faster than the creative is refreshing."
    if slug == "ugc-starter-pack":
        return "The right move is a tight first proof point — no retainer pressure."
    return "The offer is strong, the creative around it can do more work."


# ═══════════════════════════════════════════════════════════════════════════
#  Eligibility — can this trigger + lead produce an avatar at all?
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AvatarEligibility:
    """Result of the pre-generation eligibility check."""
    eligible: bool
    trigger: str
    reason: str
    rules_evaluated: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "eligible": self.eligible,
            "trigger": self.trigger,
            "reason": self.reason,
            "rules_evaluated": self.rules_evaluated,
        }


def decide_avatar_eligibility(
    *,
    trigger: AvatarTrigger | str,
    lead_confidence: float,
    lead_score: int,
    last_avatar_sent_at: Optional[datetime] = None,
    is_cold_first_touch: bool = False,
    settings: Optional[ReplyPolicySettings] = None,
    now: Optional[datetime] = None,
) -> AvatarEligibility:
    """Deterministic rule stack — first miss returns not-eligible.

    Order:
      1. feature flag (avatar_followup_enabled)
      2. cold first touch gate (only if explicitly enabled)
      3. trigger in allowed set
      4. cooldown window respected
      5. lead score above floor
      6. lead confidence above floor
    """
    settings = settings or ReplyPolicySettings()
    now = now or datetime.now(timezone.utc)
    trigger_value = trigger.value if isinstance(trigger, AvatarTrigger) else str(trigger)
    evaluated: list[str] = []

    # ── Step 1: feature flag ───────────────────────────────────────────
    if not settings.avatar_followup_enabled:
        evaluated.append("feature_flag:OFF")
        return AvatarEligibility(False, trigger_value, "avatar_followup_enabled=false", evaluated)
    evaluated.append("feature_flag:ON")

    # ── Step 2: cold first-touch gate ──────────────────────────────────
    if is_cold_first_touch and not settings.avatar_cold_first_touch_enabled:
        evaluated.append("cold_first_touch:BLOCKED")
        return AvatarEligibility(
            False, trigger_value,
            "cold first touch disabled — avatar is warm-lead only by default",
            evaluated,
        )
    evaluated.append("cold_first_touch:PASS")

    # ── Step 3: trigger in allowed set ─────────────────────────────────
    if trigger_value not in settings.avatar_allowed_triggers:
        evaluated.append(f"trigger_allowlist:MISS:{trigger_value}")
        return AvatarEligibility(
            False, trigger_value,
            f"trigger {trigger_value} not in avatar_allowed_triggers",
            evaluated,
        )
    evaluated.append(f"trigger_allowlist:HIT:{trigger_value}")

    # ── Step 4: cooldown ───────────────────────────────────────────────
    if last_avatar_sent_at is not None:
        window = timedelta(hours=settings.avatar_send_cooldown_hours)
        if now - last_avatar_sent_at < window:
            evaluated.append(f"cooldown:HIT:{settings.avatar_send_cooldown_hours}h")
            return AvatarEligibility(
                False, trigger_value,
                f"within {settings.avatar_send_cooldown_hours}h cooldown",
                evaluated,
            )
    evaluated.append("cooldown:PASS")

    # ── Step 5: lead score ─────────────────────────────────────────────
    if lead_score < settings.avatar_min_lead_score:
        evaluated.append(f"lead_score:MISS:{lead_score}<{settings.avatar_min_lead_score}")
        return AvatarEligibility(
            False, trigger_value,
            f"lead_score {lead_score} below floor {settings.avatar_min_lead_score}",
            evaluated,
        )
    evaluated.append(f"lead_score:PASS:{lead_score}>={settings.avatar_min_lead_score}")

    # ── Step 6: lead confidence ────────────────────────────────────────
    if lead_confidence < settings.avatar_min_confidence:
        evaluated.append(
            f"lead_confidence:MISS:{lead_confidence:.2f}<{settings.avatar_min_confidence:.2f}"
        )
        return AvatarEligibility(
            False, trigger_value,
            f"lead_confidence {lead_confidence:.2f} below floor",
            evaluated,
        )
    evaluated.append(
        f"lead_confidence:PASS:{lead_confidence:.2f}>={settings.avatar_min_confidence:.2f}"
    )

    return AvatarEligibility(True, trigger_value, "all eligibility checks passed", evaluated)


# ═══════════════════════════════════════════════════════════════════════════
#  Send-mode decider — auto / draft / escalate
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AvatarSendDecision:
    """Routing decision for an avatar follow-up once it's built.

    mode is one of: auto_send | draft | escalate
    """
    mode: str
    source: str
    rationale: str
    rules_evaluated: list[str] = field(default_factory=list)
    # Mirror reply_policy traces so we can audit the full path
    forced_escalation_match: Optional[str] = None
    forced_draft_match: Optional[str] = None
    quality_gate_issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        out = {
            "mode": self.mode,
            "source": self.source,
            "rationale": self.rationale,
            "rules_evaluated": self.rules_evaluated,
        }
        if self.forced_escalation_match:
            out["forced_escalation_match"] = self.forced_escalation_match
        if self.forced_draft_match:
            out["forced_draft_match"] = self.forced_draft_match
        if self.quality_gate_issues:
            out["quality_gate_issues"] = self.quality_gate_issues
        return out


# Enterprise / high-ambiguity signals that force draft even when the script
# is clean — we want a human eye on large deals, custom scope, procurement.
_AVATAR_AMBIGUITY_PATTERNS: list[tuple[str, str]] = [
    (r"(?i)\b(enterprise|procurement|legal\s+review|master\s+service\s+agreement|\bmsa\b|security\s+review)\b", "enterprise_ambiguous"),
    (r"(?i)\b(custom\s+(scope|package|quote|proposal)|bespoke|tailor(ed)?)\b", "custom_scope"),
    (r"(?i)\b(six.?figure|seven.?figure|\$\s*\d{1,3}[,.]?\d{3}[,.]?\d{3})\b", "high_value_ambiguous"),
    (r"(?i)\b(partnership|joint\s+venture|rev\s*share|equity)\b", "partnership"),
]


def decide_avatar_send_mode(
    *,
    script: AvatarScript,
    inbound_subject: str,
    inbound_body: str,
    recommendation_confidence: float,
    quality_spec: AvatarQualitySpec,
    settings: Optional[ReplyPolicySettings] = None,
) -> AvatarSendDecision:
    """Route the built avatar to auto / draft / escalate.

    Order (first match wins):
      1. script failed doctrine gates → draft (never ship bad copy)
      2. quality spec failed premium gate → draft (never ship cheesy video)
      3. inbound body matches forced-escalation (legal, hostile, fraud) → escalate
      4. inbound body matches explicit call ask / custom scope → draft
      5. inbound body matches avatar ambiguity patterns → draft
      6. package confidence below threshold → draft
      7. all passed → auto_send
    """
    settings = settings or ReplyPolicySettings()
    evaluated: list[str] = []
    decision = AvatarSendDecision(mode="draft", source="pending", rationale="", rules_evaluated=evaluated)

    # ── Step 1: script doctrine ────────────────────────────────────────
    if not script.passes_doctrine(settings):
        evaluated.append(f"script_doctrine:MISS:{','.join(script.doctrine_issues) or 'length_or_cta'}")
        decision.mode = "draft"
        decision.source = "script_doctrine_failed"
        decision.rationale = (
            f"script violated doctrine: issues={script.doctrine_issues} "
            f"words={script.word_count}/{settings.avatar_max_words} "
            f"ctas={script.cta_count}/{settings.avatar_max_cta_count}"
        )
        return decision
    evaluated.append("script_doctrine:PASS")

    # ── Step 2: quality spec gate ──────────────────────────────────────
    passed, issues = score_avatar_quality_spec(quality_spec, settings.avatar_quality_mode)
    if not passed:
        evaluated.append(f"quality_gate:MISS:{','.join(issues)}")
        decision.mode = "draft"
        decision.source = "quality_gate_failed"
        decision.quality_gate_issues = issues
        decision.rationale = (
            "premium quality spec failed — refusing to ship low-end/uncanny output"
        )
        return decision
    evaluated.append("quality_gate:PASS")

    # ── Step 3: forced escalation on inbound text ──────────────────────
    esc_label, _ = detect_forced_escalation(inbound_subject, inbound_body)
    if esc_label:
        evaluated.append(f"forced_escalation:HIT:{esc_label}")
        decision.mode = "escalate"
        decision.source = "forced_escalation"
        decision.forced_escalation_match = esc_label
        decision.rationale = f"forced escalation triggered: {esc_label}"
        return decision
    evaluated.append("forced_escalation:PASS")

    # ── Step 4: forced draft on inbound text (call asks, custom scope) ─
    draft_label, _ = detect_forced_draft(inbound_subject, inbound_body)
    if draft_label:
        evaluated.append(f"forced_draft:HIT:{draft_label}")
        decision.mode = "draft"
        decision.source = "forced_draft"
        decision.forced_draft_match = draft_label
        decision.rationale = f"forced draft triggered: {draft_label}"
        return decision
    evaluated.append("forced_draft:PASS")

    # ── Step 5: avatar-specific ambiguity patterns ─────────────────────
    combined = f"{inbound_subject}\n{inbound_body}"
    for pat, label in _AVATAR_AMBIGUITY_PATTERNS:
        if re.search(pat, combined):
            evaluated.append(f"avatar_ambiguity:HIT:{label}")
            decision.mode = "draft"
            decision.source = "avatar_ambiguity"
            decision.forced_draft_match = label
            decision.rationale = f"avatar ambiguity signal: {label}"
            return decision
    evaluated.append("avatar_ambiguity:PASS")

    # ── Step 6: package confidence ─────────────────────────────────────
    if recommendation_confidence < settings.avatar_min_confidence:
        evaluated.append(
            f"recommendation_confidence:MISS:{recommendation_confidence:.2f}"
            f"<{settings.avatar_min_confidence:.2f}"
        )
        decision.mode = "draft"
        decision.source = "recommendation_confidence_low"
        decision.rationale = (
            f"package confidence {recommendation_confidence:.2f} below "
            f"{settings.avatar_min_confidence:.2f}"
        )
        return decision
    evaluated.append(
        f"recommendation_confidence:PASS:{recommendation_confidence:.2f}"
        f">={settings.avatar_min_confidence:.2f}"
    )

    # ── Step 7: all checks passed ──────────────────────────────────────
    decision.mode = "auto_send"
    decision.source = "all_checks_passed"
    decision.rationale = "doctrine clean, quality premium, no ambiguity — auto_send"
    return decision


# ═══════════════════════════════════════════════════════════════════════════
#  Delivery email — the short reply the avatar is attached to
# ═══════════════════════════════════════════════════════════════════════════

_DELIVERY_NOTES: dict[str, str] = {
    AvatarTrigger.WARM_INTEREST.value:
        "Made this quick breakdown for you — shows the best-fit package and next step.",
    AvatarTrigger.PRICING_REQUEST.value:
        "This shows the fit and the locked pricing in one short clip.",
    AvatarTrigger.PROOF_REQUEST.value:
        "This is the fastest way I'd approach it — package and next step inside.",
    AvatarTrigger.CLICKED_PACKAGE_LINK_NO_PURCHASE.value:
        "Noticed you got close to the package — short clip to finish the path.",
    AvatarTrigger.CHECKOUT_STARTED_NO_PAYMENT.value:
        "Short clip on the best-fit package and the fastest path to finish checkout.",
    AvatarTrigger.INTAKE_STARTED_NOT_COMPLETED.value:
        "Short clip to make the intake step obvious and quick to complete.",
    AvatarTrigger.STALLED_AFTER_PRICING.value:
        "Short clip with the best-fit package and the no-friction next step.",
    AvatarTrigger.STALLED_AFTER_PROOF.value:
        "Short clip showing the best-fit package and how we'd move.",
    AvatarTrigger.HIGH_VALUE_LEAD_TRUST_ACCELERATION.value:
        "Short clip with the best-fit package and exactly how I'd approach it.",
}


@dataclass
class AvatarDeliveryEmail:
    subject: str
    body_text: str
    video_url: str
    recipient_first_name: str

    @property
    def body_html(self) -> str:
        # Plain text only — Graph ContentType=Text, same as inbound reply path.
        return ""


def build_avatar_delivery_email(
    *,
    trigger: AvatarTrigger,
    script: AvatarScript,
    video_url: str,
    recipient_first_name: str,
    original_subject: str = "",
) -> AvatarDeliveryEmail:
    """Short plain-text delivery note for the avatar asset.

    This is what the prospect reads in their inbox. It MUST NOT label
    the video as "AI video", MUST NOT offer a call, MUST NOT offer
    free work, and MUST route to the package checkout URL.
    """
    note = _DELIVERY_NOTES[trigger.value]
    subject = (
        f"Re: {original_subject}"
        if original_subject and not original_subject.lower().startswith("re:")
        else (original_subject or f"Quick note — {script.package_name}")
    )

    body_lines = [
        f"Hi {recipient_first_name or 'there'},",
        "",
        note,
        "",
        f"Video: {video_url}",
        "",
        f"Package path: {script.checkout_url}",
        "",
        "Patrick",
    ]
    return AvatarDeliveryEmail(
        subject=subject,
        body_text="\n".join(body_lines),
        video_url=video_url,
        recipient_first_name=recipient_first_name,
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Provider protocol + fake
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AvatarGenerationResult:
    status: str                # queued | generating | ready | failed
    provider: str
    provider_job_id: str
    video_url: str = ""
    error_message: str = ""
    duration_seconds: float = 0.0
    cost_usd: float = 0.0
    raw_metadata: dict = field(default_factory=dict)


class AvatarProviderAdapter(Protocol):
    """Contract any real provider (HeyGen / D-ID / Tavus / Synthesia) must satisfy.

    The live stack wraps packages.provider_clients.media_providers adapters.
    Tests use FakeAvatarProvider below so they can run without network.
    """
    name: str

    def generate(
        self,
        *,
        script: AvatarScript,
        quality_spec: AvatarQualitySpec,
    ) -> AvatarGenerationResult:
        ...


@dataclass
class FakeAvatarProvider:
    """Deterministic test double — pretends to queue, generate, and deliver.

    Used by the runtime proof and pytest. Never touches network. Records
    every request so tests can assert on what the live provider would
    have been asked to produce.
    """
    name: str = "fake"
    base_url: str = "https://fake.proofhook.test/avatars"
    fail_next: bool = False
    recorded_requests: list[dict] = field(default_factory=list)

    def generate(
        self,
        *,
        script: AvatarScript,
        quality_spec: AvatarQualitySpec,
    ) -> AvatarGenerationResult:
        request = {
            "script_full_text": script.full_text,
            "script_word_count": script.word_count,
            "package_slug": script.package_slug,
            "quality_config": quality_spec.to_provider_config(),
        }
        self.recorded_requests.append(request)

        if self.fail_next:
            self.fail_next = False
            return AvatarGenerationResult(
                status="failed",
                provider=self.name,
                provider_job_id=f"{self.name}_{uuid.uuid4().hex[:10]}",
                error_message="simulated provider failure",
            )

        job_id = f"{self.name}_{uuid.uuid4().hex[:10]}"
        video_url = f"{self.base_url}/{job_id}.mp4"
        return AvatarGenerationResult(
            status="ready",
            provider=self.name,
            provider_job_id=job_id,
            video_url=video_url,
            duration_seconds=float(min(script.word_count / 2.5, 45.0)),
            cost_usd=0.35,
            raw_metadata={"quality_tier": quality_spec.to_provider_config()["quality_tier"]},
        )


# ═══════════════════════════════════════════════════════════════════════════
#  Full tracked follow-up record
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AvatarFollowupRecord:
    """DB-ready tracked artifact — links to contact/opportunity/thread.

    This is the object downstream attribution walks: "which leads saw
    an avatar follow-up, what package did it push, did they come back
    through checkout / intake, did the send land in sent/viewed states."
    """
    record_id: uuid.UUID = field(default_factory=uuid.uuid4)
    # Linkage
    contact_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    thread_id: Optional[str] = None
    # Routing
    trigger: str = ""
    package_slug: str = ""
    package_name: str = ""
    recommendation_confidence: float = 0.0
    # Script + doctrine audit
    script_full_text: str = ""
    script_word_count: int = 0
    script_cta_count: int = 0
    script_doctrine_issues: list[str] = field(default_factory=list)
    # Quality spec
    quality_mode: str = "premium"
    quality_issues: list[str] = field(default_factory=list)
    # Send decision
    send_mode: str = ""                         # auto_send | draft | escalate
    send_mode_source: str = ""
    send_rationale: str = ""
    # Provider / state
    provider: str = ""
    provider_job_id: str = ""
    video_url: str = ""
    state: AvatarAssetState = AvatarAssetState.QUEUED
    state_history: list[tuple[str, str]] = field(default_factory=list)
    error_message: str = ""
    # Commercial linkage
    checkout_url: str = ""
    intake_url: str = ""
    # Eligibility trace
    eligibility: Optional[AvatarEligibility] = None
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sent_at: Optional[datetime] = None
    viewed_at: Optional[datetime] = None

    def transition(self, new_state: AvatarAssetState, reason: str = "") -> None:
        if not can_transition(self.state, new_state):
            raise ValueError(
                f"illegal state transition: {self.state.value} → {new_state.value}"
            )
        self.state_history.append((f"{self.state.value}->{new_state.value}", reason))
        self.state = new_state
        if new_state == AvatarAssetState.SENT:
            self.sent_at = datetime.now(timezone.utc)
        elif new_state == AvatarAssetState.VIEWED:
            self.viewed_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        return {
            "record_id": str(self.record_id),
            "contact_id": self.contact_id,
            "opportunity_id": self.opportunity_id,
            "thread_id": self.thread_id,
            "trigger": self.trigger,
            "package_slug": self.package_slug,
            "package_name": self.package_name,
            "recommendation_confidence": round(self.recommendation_confidence, 3),
            "script_word_count": self.script_word_count,
            "script_cta_count": self.script_cta_count,
            "script_doctrine_issues": self.script_doctrine_issues,
            "quality_mode": self.quality_mode,
            "quality_issues": self.quality_issues,
            "send_mode": self.send_mode,
            "send_mode_source": self.send_mode_source,
            "send_rationale": self.send_rationale,
            "provider": self.provider,
            "provider_job_id": self.provider_job_id,
            "video_url": self.video_url,
            "state": self.state.value,
            "state_history": self.state_history,
            "error_message": self.error_message,
            "checkout_url": self.checkout_url,
            "intake_url": self.intake_url,
            "eligibility": self.eligibility.to_dict() if self.eligibility else None,
            "created_at": self.created_at.isoformat(),
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "viewed_at": self.viewed_at.isoformat() if self.viewed_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════
#  End-to-end orchestrator
# ═══════════════════════════════════════════════════════════════════════════

def generate_avatar_followup(
    *,
    trigger: AvatarTrigger,
    inbound_subject: str,
    inbound_body: str,
    from_email: str = "",
    brand_name: str = "",
    lead_confidence: float = 0.85,
    lead_score: int = 75,
    last_avatar_sent_at: Optional[datetime] = None,
    is_cold_first_touch: bool = False,
    contact_id: Optional[str] = None,
    opportunity_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    avatar_id: str = "proofhook_founder_01",
    voice_id: str = "proofhook_founder_voice_01",
    provider: Optional[AvatarProviderAdapter] = None,
    settings: Optional[ReplyPolicySettings] = None,
) -> AvatarFollowupRecord:
    """Full pipeline: eligibility → package → script → quality → send → generate.

    Returns a single AvatarFollowupRecord with every decision stamped on
    it. Callers can persist it as JSONB, push the video on sent, listen
    for view events, and attribute downstream checkout/intake back to
    the record.

    This function does NOT send email. It produces the record and (on
    auto_send) generates the video. Wiring the delivery email into
    reply_engine / Graph is done at the caller level — see
    build_avatar_delivery_email().
    """
    settings = settings or ReplyPolicySettings()
    provider = provider or FakeAvatarProvider()

    record = AvatarFollowupRecord(
        contact_id=contact_id,
        opportunity_id=opportunity_id,
        thread_id=thread_id,
        trigger=trigger.value,
        quality_mode=settings.avatar_quality_mode,
    )

    # ── Step 1: eligibility ────────────────────────────────────────────
    eligibility = decide_avatar_eligibility(
        trigger=trigger,
        lead_confidence=lead_confidence,
        lead_score=lead_score,
        last_avatar_sent_at=last_avatar_sent_at,
        is_cold_first_touch=is_cold_first_touch,
        settings=settings,
    )
    record.eligibility = eligibility
    if not eligibility.eligible:
        record.send_mode = "suppressed"
        record.send_mode_source = "eligibility_failed"
        record.send_rationale = eligibility.reason
        record.error_message = eligibility.reason
        # State stays QUEUED → move to FAILED so no one tries to send it
        record.transition(AvatarAssetState.FAILED, reason=eligibility.reason)
        return record

    # ── Step 2: package recommendation ─────────────────────────────────
    recommendation = recommend_package(
        intent=trigger.value if trigger.value in {"warm_interest", "pricing_request", "proof_request"} else "warm_interest",
        body_text=inbound_body,
        subject=inbound_subject,
        from_email=from_email,
        mode=settings.package_recommendation_mode,
    )
    record.package_slug = recommendation.slug
    record.package_name = PACKAGES[recommendation.slug]["name"]
    record.recommendation_confidence = recommendation.confidence
    record.checkout_url = package_checkout_url(recommendation.slug)
    record.intake_url = package_intake_url(recommendation.slug)

    # ── Step 3: script ─────────────────────────────────────────────────
    script = build_avatar_script(
        trigger=trigger,
        recommendation=recommendation,
        brand_name=brand_name,
        settings=settings,
    )
    record.script_full_text = script.full_text
    record.script_word_count = script.word_count
    record.script_cta_count = script.cta_count
    record.script_doctrine_issues = list(script.doctrine_issues)

    # ── Step 4: quality spec ───────────────────────────────────────────
    spec = default_premium_spec(avatar_id=avatar_id, voice_id=voice_id)

    # ── Step 5: send-mode routing ──────────────────────────────────────
    decision = decide_avatar_send_mode(
        script=script,
        inbound_subject=inbound_subject,
        inbound_body=inbound_body,
        recommendation_confidence=recommendation.confidence,
        quality_spec=spec,
        settings=settings,
    )
    record.send_mode = decision.mode
    record.send_mode_source = decision.source
    record.send_rationale = decision.rationale
    record.quality_issues = list(decision.quality_gate_issues)

    if decision.mode == "escalate":
        record.transition(AvatarAssetState.FAILED, reason=f"escalated:{decision.source}")
        return record

    if decision.mode == "draft":
        # We still generate the asset so a reviewer can watch it, but we
        # do NOT transition to SENT. The record stays READY for review.
        # For draft mode we ALSO skip generation if the script failed
        # doctrine — there's nothing worth generating.
        if decision.source in ("script_doctrine_failed", "quality_gate_failed"):
            record.transition(AvatarAssetState.FAILED, reason=decision.source)
            return record

    # ── Step 6: provider generation ────────────────────────────────────
    record.transition(AvatarAssetState.GENERATING, reason="submitted to provider")
    result = provider.generate(script=script, quality_spec=spec)
    record.provider = result.provider
    record.provider_job_id = result.provider_job_id

    if result.status == "ready":
        record.video_url = result.video_url
        record.transition(AvatarAssetState.READY, reason="provider returned asset")
        if decision.mode == "auto_send":
            record.transition(AvatarAssetState.SENT, reason="auto_send dispatched")
    else:
        record.error_message = result.error_message or "provider did not return ready"
        record.transition(AvatarAssetState.FAILED, reason=record.error_message)

    return record
