"""ProofHook avatar follow-up doctrine tests.

These 20 tests enforce that the avatar follow-up system is a legitimate
conversion accelerator — not a gimmick — and that it respects every
Revenue-Ops doctrine rule that governs the text reply engine:

    • broad-market positioning
    • package-first selling
    • no-call funnel
    • no-free-work
    • no starter-pack default anchor
    • premium visual quality enforcement

Pure-Python unit tests — no DB, no network, no LLM, no real provider
calls. Everything runs against apps.api.services.avatar_followup
with a FakeAvatarProvider test double.

Test groups:
    Visual / quality       (3)
    Trigger eligibility    (5)
    Script doctrine        (4)
    Send routing           (4)
    Tracking / state       (3)
    Sanity                 (1)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from apps.api.services.avatar_followup import (
    _FORBIDDEN_SCRIPT_PATTERNS,
    AvatarAssetState,
    AvatarFollowupRecord,
    AvatarTrigger,
    FakeAvatarProvider,
    build_avatar_script,
    decide_avatar_eligibility,
    decide_avatar_send_mode,
    default_premium_spec,
    generate_avatar_followup,
    score_avatar_quality_spec,
)
from apps.api.services.reply_policy import ReplyPolicySettings

# ── Helpers ─────────────────────────────────────────────────────────────────

FORBIDDEN_CALL_PHRASES = [
    "hop on a call", "jump on a call", "schedule a call", "book a call",
    "quick call", "phone call", "zoom meeting", "let's chat",
    "happy to chat", "let me walk you through", "calendly",
]

FORBIDDEN_FREE_WORK_PHRASES = [
    "free sample", "free samples", "free test run", "free preview",
    "trial creative", "sample angles", "spec work",
]

FORBIDDEN_NICHE_WORDS = [
    "beauty brand", "beauty brands", "fitness brand", "fitness brands",
    "supplement brands", "saas brands", "ecommerce brands",
]

FORBIDDEN_AI_LABELS = [
    "ai-powered", "ai avatar", "cool ai video", "ai-generated avatar",
]


def _warm_settings() -> ReplyPolicySettings:
    return ReplyPolicySettings()


def _warm_recommendation(slug: str = "performance-creative-pack"):
    """Synthesize a recommendation that the real recommender would produce
    for a paid-media lead — used to test script building deterministically."""
    from apps.api.services.package_recommender import PackageRecommendation
    return PackageRecommendation(
        slug=slug,
        rationale="paid-media scaling signals detected",
        signals=["paid_media_active", "creative_rotation"],
        confidence=0.88,
        anchor_avoided=slug != "ugc-starter-pack",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  GROUP 1 — Visual / quality
# ═══════════════════════════════════════════════════════════════════════════

class TestVisualQuality:
    def test_01_default_premium_spec_passes_all_gates(self):
        """default_premium_spec() must satisfy every premium field + safety rail."""
        spec = default_premium_spec(
            avatar_id="proofhook_founder_01",
            voice_id="proofhook_founder_voice_01",
        )
        passes, issues = score_avatar_quality_spec(spec, quality_mode="premium")
        assert passes, f"default premium spec failed: {issues}"
        assert issues == []
        # Every enum field is populated
        assert spec.lighting_profile == "soft_contrast_cinematic"
        assert spec.background_type == "dark_premium"
        assert spec.wardrobe_tier == "founder_operator"
        assert spec.facial_expression == "confident_calm"
        # Safety rails ON
        assert spec.forbid_over_animation
        assert spec.forbid_cartoon_style
        assert spec.forbid_aggressive_energy

    def test_02_invalid_enum_fails_premium_gate(self):
        """Any field outside the allowed enum must fail the gate."""
        spec = default_premium_spec("a", "v")
        spec.lighting_profile = "harsh_flat"  # not in allowed set
        spec.wardrobe_tier = "cartoonish_loud"
        passes, issues = score_avatar_quality_spec(spec, quality_mode="premium")
        assert not passes
        assert any("invalid_enum:lighting_profile" in i for i in issues)
        assert any("invalid_enum:wardrobe_tier" in i for i in issues)

    def test_03_safety_rails_off_fails_premium_gate(self):
        """Disabling any safety rail in premium mode must fail the gate."""
        spec = default_premium_spec("a", "v")
        spec.forbid_over_animation = False
        spec.forbid_cartoon_style = False
        passes, issues = score_avatar_quality_spec(spec, quality_mode="premium")
        assert not passes
        assert any("safety_off:forbid_over_animation" in i for i in issues)
        assert any("safety_off:forbid_cartoon_style" in i for i in issues)


# ═══════════════════════════════════════════════════════════════════════════
#  GROUP 2 — Trigger eligibility
# ═══════════════════════════════════════════════════════════════════════════

class TestTriggerEligibility:
    def test_04_warm_interest_is_eligible(self):
        result = decide_avatar_eligibility(
            trigger=AvatarTrigger.WARM_INTEREST,
            lead_confidence=0.90,
            lead_score=80,
        )
        assert result.eligible
        assert "trigger_allowlist:HIT:warm_interest" in result.rules_evaluated

    def test_05_pricing_and_proof_and_checkout_abandon_all_eligible(self):
        for trig in (
            AvatarTrigger.PRICING_REQUEST,
            AvatarTrigger.PROOF_REQUEST,
            AvatarTrigger.CHECKOUT_STARTED_NO_PAYMENT,
            AvatarTrigger.INTAKE_STARTED_NOT_COMPLETED,
        ):
            result = decide_avatar_eligibility(
                trigger=trig, lead_confidence=0.85, lead_score=70,
            )
            assert result.eligible, f"{trig} should be eligible: {result.reason}"

    def test_06_cold_first_touch_is_blocked_by_default(self):
        """Avatar is a warm-lead conversion asset — not a cold opener."""
        result = decide_avatar_eligibility(
            trigger=AvatarTrigger.WARM_INTEREST,
            lead_confidence=0.95,
            lead_score=90,
            is_cold_first_touch=True,
        )
        assert not result.eligible
        assert "cold_first_touch:BLOCKED" in result.rules_evaluated

    def test_07_cooldown_respected(self):
        settings = ReplyPolicySettings()
        now = datetime.now(timezone.utc)
        recent = now - timedelta(hours=settings.avatar_send_cooldown_hours - 1)
        result = decide_avatar_eligibility(
            trigger=AvatarTrigger.WARM_INTEREST,
            lead_confidence=0.90,
            lead_score=80,
            last_avatar_sent_at=recent,
            now=now,
        )
        assert not result.eligible
        assert any("cooldown:HIT" in r for r in result.rules_evaluated)

    def test_08_low_confidence_and_low_score_blocked(self):
        result_low_conf = decide_avatar_eligibility(
            trigger=AvatarTrigger.WARM_INTEREST,
            lead_confidence=0.40,
            lead_score=80,
        )
        assert not result_low_conf.eligible
        assert "lead_confidence:MISS" in " ".join(result_low_conf.rules_evaluated)

        result_low_score = decide_avatar_eligibility(
            trigger=AvatarTrigger.WARM_INTEREST,
            lead_confidence=0.90,
            lead_score=30,
        )
        assert not result_low_score.eligible
        assert "lead_score:MISS" in " ".join(result_low_score.rules_evaluated)


# ═══════════════════════════════════════════════════════════════════════════
#  GROUP 3 — Script doctrine
# ═══════════════════════════════════════════════════════════════════════════

class TestScriptDoctrine:
    def test_09_script_never_contains_call_language(self):
        """Every trigger × every package combination must produce a call-free script."""
        packages_to_test = [
            "performance-creative-pack",
            "creative-strategy-funnel-upgrade",
            "growth-content-pack",
            "launch-sprint",
            "full-creative-retainer",
            "ugc-starter-pack",
        ]
        for trig in AvatarTrigger:
            for slug in packages_to_test:
                rec = _warm_recommendation(slug=slug)
                script = build_avatar_script(
                    trigger=trig, recommendation=rec, brand_name="Example Co",
                )
                text = script.full_text.lower()
                for phrase in FORBIDDEN_CALL_PHRASES:
                    assert phrase not in text, (
                        f"call language {phrase!r} in script for "
                        f"{trig.value}/{slug}: {script.full_text}"
                    )
                assert not script.doctrine_issues, (
                    f"doctrine issues on {trig.value}/{slug}: {script.doctrine_issues}"
                )

    def test_10_script_never_contains_free_work_language(self):
        for trig in AvatarTrigger:
            rec = _warm_recommendation(slug="growth-content-pack")
            script = build_avatar_script(
                trigger=trig, recommendation=rec, brand_name="Orbit Labs",
            )
            text = script.full_text.lower()
            for phrase in FORBIDDEN_FREE_WORK_PHRASES:
                assert phrase not in text, f"free-work phrase in {trig.value}: {text}"

    def test_11_script_contains_best_fit_package_name_and_price(self):
        """Package name + price must both appear verbatim in the script."""
        from packages.clients.email_templates import PACKAGES
        for slug, pkg in PACKAGES.items():
            rec = _warm_recommendation(slug=slug)
            script = build_avatar_script(
                trigger=AvatarTrigger.WARM_INTEREST,
                recommendation=rec, brand_name="Example Co",
            )
            assert pkg["name"] in script.full_text, (
                f"package name missing from script for {slug}: {script.full_text}"
            )
            assert pkg["price"] in script.full_text, (
                f"package price missing from script for {slug}: {script.full_text}"
            )

    def test_12_script_is_broad_market_no_niche_framing(self):
        for trig in AvatarTrigger:
            rec = _warm_recommendation(slug="performance-creative-pack")
            script = build_avatar_script(
                trigger=trig, recommendation=rec, brand_name="Example Co",
            )
            text = script.full_text.lower()
            for niche in FORBIDDEN_NICHE_WORDS:
                assert niche not in text, f"niche word {niche!r} in {trig.value}: {text}"
            # Also no "AI avatar" style self-references
            for label in FORBIDDEN_AI_LABELS:
                assert label not in text, f"AI label {label!r} in {trig.value}"


# ═══════════════════════════════════════════════════════════════════════════
#  GROUP 4 — Send routing (auto / draft / escalate)
# ═══════════════════════════════════════════════════════════════════════════

class TestSendRouting:
    def test_13_safe_case_auto_sends(self):
        """Clean inbound, clean script, premium spec, high confidence → auto_send."""
        rec = _warm_recommendation(slug="performance-creative-pack")
        script = build_avatar_script(
            trigger=AvatarTrigger.WARM_INTEREST,
            recommendation=rec, brand_name="Northfield",
        )
        spec = default_premium_spec("a", "v")
        decision = decide_avatar_send_mode(
            script=script,
            inbound_subject="creative rotation for Meta ads",
            inbound_body="We're scaling paid spend and need fresh creative.",
            recommendation_confidence=0.90,
            quality_spec=spec,
        )
        assert decision.mode == "auto_send", decision.rationale
        assert decision.source == "all_checks_passed"

    def test_14_ambiguous_enterprise_case_drafts(self):
        """Enterprise / custom-scope / high-value signals → draft."""
        rec = _warm_recommendation(slug="performance-creative-pack")
        script = build_avatar_script(
            trigger=AvatarTrigger.WARM_INTEREST, recommendation=rec,
        )
        spec = default_premium_spec("a", "v")

        for body, expected_label in [
            ("We need a custom scope for our brand — enterprise procurement required.", "custom_scope"),
            ("Looking for a partnership with revenue share.", "custom_scope"),
        ]:
            decision = decide_avatar_send_mode(
                script=script, inbound_subject="inquiry", inbound_body=body,
                recommendation_confidence=0.90, quality_spec=spec,
            )
            assert decision.mode == "draft", f"body: {body!r}"

    def test_15_hostile_legal_case_escalates(self):
        rec = _warm_recommendation(slug="growth-content-pack")
        script = build_avatar_script(
            trigger=AvatarTrigger.WARM_INTEREST, recommendation=rec,
        )
        spec = default_premium_spec("a", "v")
        for body in [
            "I'm getting my lawyer involved — this is unacceptable.",
            "I want a refund and I'm filing a chargeback.",
            "This is absolutely fraudulent, I'm furious.",
        ]:
            decision = decide_avatar_send_mode(
                script=script, inbound_subject="urgent", inbound_body=body,
                recommendation_confidence=0.90, quality_spec=spec,
            )
            assert decision.mode == "escalate", f"body: {body!r}"

    def test_16_explicit_call_ask_drafts_even_on_clean_script(self):
        """Inbound asks to hop on a call → draft (even with premium script)."""
        rec = _warm_recommendation(slug="performance-creative-pack")
        script = build_avatar_script(
            trigger=AvatarTrigger.WARM_INTEREST, recommendation=rec,
        )
        spec = default_premium_spec("a", "v")
        decision = decide_avatar_send_mode(
            script=script,
            inbound_subject="chat?",
            inbound_body="Can we hop on a quick call to discuss creative?",
            recommendation_confidence=0.90,
            quality_spec=spec,
        )
        assert decision.mode == "draft"
        assert decision.forced_draft_match == "call_request"


# ═══════════════════════════════════════════════════════════════════════════
#  GROUP 5 — Tracking / state
# ═══════════════════════════════════════════════════════════════════════════

class TestTrackingAndState:
    def test_17_record_links_contact_opportunity_thread(self):
        """AvatarFollowupRecord must carry contact/opportunity/thread ids."""
        record = generate_avatar_followup(
            trigger=AvatarTrigger.WARM_INTEREST,
            inbound_subject="creative rotation for Meta ads",
            inbound_body="scaling paid spend, need fresh creative rotation",
            from_email="mike@northfielddtc.com",
            brand_name="Northfield DTC",
            lead_confidence=0.92,
            lead_score=80,
            contact_id="contact_abc",
            opportunity_id="opp_xyz",
            thread_id="thread_123",
            provider=FakeAvatarProvider(),
        )
        d = record.to_dict()
        assert d["contact_id"] == "contact_abc"
        assert d["opportunity_id"] == "opp_xyz"
        assert d["thread_id"] == "thread_123"
        assert d["package_slug"] == "performance-creative-pack"
        assert d["state"] == "sent"
        assert d["video_url"].startswith("https://fake.proofhook.test/avatars/")

    def test_18_state_transitions_are_gated(self):
        """Illegal transitions must raise; legal transitions must succeed."""
        rec = AvatarFollowupRecord()
        # queued → ready is illegal (must go through generating)
        with pytest.raises(ValueError):
            rec.transition(AvatarAssetState.READY)
        # Valid path
        rec.transition(AvatarAssetState.GENERATING)
        rec.transition(AvatarAssetState.READY)
        rec.transition(AvatarAssetState.SENT)
        rec.transition(AvatarAssetState.VIEWED)
        assert rec.state == AvatarAssetState.VIEWED
        assert rec.sent_at is not None
        assert rec.viewed_at is not None
        assert len(rec.state_history) == 4

    def test_19_downstream_attribution_linkage_present(self):
        """Record must carry checkout + intake urls so downstream purchase
        / intake resumption is attributable back to the avatar send."""
        record = generate_avatar_followup(
            trigger=AvatarTrigger.CHECKOUT_STARTED_NO_PAYMENT,
            inbound_subject="monthly content engine",
            # Three recurring signals → growth-content-pack at 0.95 confidence
            inbound_body=(
                "We need a monthly content engine — ongoing output every month. "
                "Outgrown freelancers. Looking for a content calendar we can trust."
            ),
            from_email="dana@harborgoods.com",
            brand_name="Harbor Goods",
            lead_confidence=0.88,
            lead_score=75,
            contact_id="c1",
            thread_id="t1",
            provider=FakeAvatarProvider(),
        )
        d = record.to_dict()
        assert d["checkout_url"].endswith("/growth-content-pack")
        assert d["intake_url"].endswith("/growth-content-pack")
        assert d["send_mode"] == "auto_send"
        assert d["package_name"] == "Growth Content Pack"
        # Provider info is present so downstream can inspect the generation
        assert d["provider"] == "fake"
        assert d["provider_job_id"].startswith("fake_")


# ═══════════════════════════════════════════════════════════════════════════
#  GROUP 6 — Sanity
# ═══════════════════════════════════════════════════════════════════════════

def test_20_forbidden_pattern_lists_are_non_empty():
    """Guardrail: someone emptying the forbidden-pattern lists must fail CI."""
    assert len(_FORBIDDEN_SCRIPT_PATTERNS) >= 12, (
        "forbidden-pattern list has been shrunk below the safe floor"
    )
    assert len(FORBIDDEN_CALL_PHRASES) >= 5
    assert len(FORBIDDEN_FREE_WORK_PHRASES) >= 4
    assert len(FORBIDDEN_NICHE_WORDS) >= 3
