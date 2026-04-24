"""ProofHook Revenue-Ops doctrine tests.

These 18 tests enforce the non-negotiables of the package-first, no-call,
broad-market, signal-based creative services revenue machine. They are
deliberately pure-Python unit tests (no DB fixtures, no network, no LLM
calls) so they run on every commit in under a second and fail loudly if
anyone reintroduces legacy creator-growth / call-first / free-spec doctrine.

Test groups:
    Positioning      (2)
    Package routing  (4)
    No-call          (3)
    No-free-work     (3)
    Reply quality    (3)
    Trace / audit    (3)
"""

from __future__ import annotations

from apps.api.services.package_recommender import (
    PackageRecommendation,
    recommend_package,
)
from apps.api.services.reply_engine import _build_reply_body
from apps.api.services.reply_policy import (
    DecisionTrace,
    ReplyPolicySettings,
    decide_reply_mode,
    detect_forced_draft,
)
from packages.clients.email_templates import FIRST_TOUCH, PACKAGES

# ── Helpers ─────────────────────────────────────────────────────────────────

FORBIDDEN_VERTICAL_WORDS = [
    "beauty brand",
    "beauty brands",
    "fitness brand",
    "fitness brands",
    "software brand",
    "software brands",
    "supplement brand",
    "ecom brand",  # too narrow
]

FORBIDDEN_CALL_PHRASES = [
    "hop on a call",
    "hop on a quick call",
    "jump on a call",
    "schedule a call",
    "book a call",
    "quick call",
    "phone call",
    "calendly",
    "zoom meeting",
    "zoom link",
    "discovery call",
    "strategy session",
    "walkthrough",
    "get on a call",
]

FORBIDDEN_FREE_WORK_PHRASES = [
    "2 sample angles",
    "2 free sample",
    "test run",
    "test runs",
    "free samples",
    "sample angles",
    "free preview",
    "free pre-work",
    "spec work",
    "free work",
    "no charge",
    "for free",
    "complimentary",
]


def _contains_any(text: str, needles: list[str]) -> list[str]:
    """Return the list of forbidden phrases present in text (lowercased)."""
    if not text:
        return []
    low = text.lower()
    return [n for n in needles if n.lower() in low]


# ═══════════════════════════════════════════════════════════════════════════
#  POSITIONING (2 tests)
# ═══════════════════════════════════════════════════════════════════════════


class TestPositioning:
    def test_01_inbound_reply_is_broad_market(self):
        """Every inbound reply template must be broad-market — no vertical words."""
        for intent in (
            "warm_interest",
            "proof_request",
            "pricing_request",
            "objection",
            "negotiation",
            "meeting_request",
            "not_now",
        ):
            reply = _build_reply_body(
                intent=intent,
                first_name="Alex",
                company="Acme",
                thread_subject="test",
            )
            hits = _contains_any(reply["body_text"], FORBIDDEN_VERTICAL_WORDS)
            assert not hits, (
                f"Inbound reply for intent={intent} contained vertical framing: {hits}\nBody:\n{reply['body_text']}"
            )
            assert reply.get("broad_market_positioning") is True

    def test_02_first_touch_broad_market_default(self):
        """FIRST_TOUCH templates must default to broad-market copy.

        Legacy vertical keys (aesthetic-theory, body-theory, tool-signal) must
        now resolve to the same broad-market template as fallback.
        """
        fallback_body = FIRST_TOUCH["fallback"]["body"]
        for key in ("aesthetic-theory", "body-theory", "tool-signal", "fallback"):
            tpl = FIRST_TOUCH[key]
            assert tpl["body"] == fallback_body, f"FIRST_TOUCH[{key!r}] drifted from fallback"
            hits = _contains_any(tpl["body"], FORBIDDEN_VERTICAL_WORDS)
            assert not hits, f"FIRST_TOUCH[{key!r}] contained vertical framing: {hits}"
            hits_nc = _contains_any(tpl["body_no_company"], FORBIDDEN_VERTICAL_WORDS)
            assert not hits_nc, f"FIRST_TOUCH[{key!r}].body_no_company contained vertical framing: {hits_nc}"


# ═══════════════════════════════════════════════════════════════════════════
#  PACKAGE ROUTING (4 tests)
# ═══════════════════════════════════════════════════════════════════════════


class TestPackageRouting:
    def test_03_starter_is_not_the_default_recommendation(self):
        """A vague warm-interest message with no signals must NOT route to starter."""
        rec = recommend_package(
            intent="warm_interest",
            body_text="Hey, sounds interesting, tell me more.",
            subject="Re: quick note",
            from_email="buyer@acme.co",
        )
        assert rec.slug != "ugc-starter-pack", (
            "Starter pack was picked as default for a signal-less lead — this is the exact bug the user called out."
        )
        assert rec.anchor_avoided is True

    def test_04_paid_media_routes_to_performance_pack(self):
        """Explicit paid-media + scaling language must route to performance-creative-pack."""
        rec = recommend_package(
            intent="warm_interest",
            body_text=(
                "We're running Meta ads and Google ads at $50k/month and need "
                "creative rotation — our current creatives are fatiguing and "
                "we need to test new hooks and angles."
            ),
            from_email="marketing@acme.co",
        )
        assert rec.slug == "performance-creative-pack", (
            f"Expected performance-creative-pack, got {rec.slug}. Signals: {rec.signals}"
        )
        assert any("paid_media" in s or "creative_rotation" in s or "scaling_spend" in s for s in rec.signals)

    def test_05_recurring_need_routes_to_growth_pack(self):
        """Monthly / ongoing / retainer-friendly language must route to growth-content-pack."""
        rec = recommend_package(
            intent="warm_interest",
            body_text=(
                "We need ongoing monthly content for our brand. We're posting "
                "daily and burning through creative every month. Looking for "
                "a consistent content engine."
            ),
            from_email="founder@brand.co",
        )
        assert rec.slug == "growth-content-pack", (
            f"Expected growth-content-pack, got {rec.slug}. Signals: {rec.signals}"
        )
        assert any("monthly_content" in s or "recurring" in s.lower() or "always_posting" in s for s in rec.signals)

    def test_06_strategy_ask_routes_to_strategy_pack(self):
        """Audit / strategy / funnel-weakness must route to creative-strategy-funnel-upgrade."""
        rec = recommend_package(
            intent="warm_interest",
            body_text=(
                "Our funnel isn't converting. We've been running ads but the "
                "landing page is dropping off hard. We need a creative audit "
                "and strategy review on what's broken."
            ),
            from_email="cmo@brand.co",
        )
        assert rec.slug == "creative-strategy-funnel-upgrade", (
            f"Expected creative-strategy-funnel-upgrade, got {rec.slug}. Signals: {rec.signals}"
        )


# ═══════════════════════════════════════════════════════════════════════════
#  NO-CALL (3 tests)
# ═══════════════════════════════════════════════════════════════════════════


class TestNoCall:
    def test_07_reply_body_has_no_call_language(self):
        """No default reply template may contain call / meeting / Calendly language."""
        for intent in (
            "warm_interest",
            "proof_request",
            "pricing_request",
            "objection",
            "negotiation",
            "not_now",
        ):
            reply = _build_reply_body(
                intent=intent,
                first_name="Alex",
                company="Acme",
                thread_subject="test",
                recommendation=PackageRecommendation(
                    slug="growth-content-pack",
                    rationale="Established brand with recurring content need.",
                    signals=["monthly_content"],
                    confidence=0.8,
                ),
            )
            hits = _contains_any(reply["body_text"], FORBIDDEN_CALL_PHRASES)
            assert not hits, f"Call language leaked into intent={intent}: {hits}\n{reply['body_text']}"

    def test_08_meeting_request_template_has_no_call_offer(self):
        """The meeting_request template must soft-redirect without proposing a call."""
        reply = _build_reply_body(
            intent="meeting_request",
            first_name="Alex",
            company="Acme",
            thread_subject="Re: call?",
            recommendation=PackageRecommendation(
                slug="growth-content-pack",
                rationale="Established brand.",
                signals=[],
                confidence=0.5,
            ),
        )
        hits = _contains_any(reply["body_text"], FORBIDDEN_CALL_PHRASES)
        assert not hits, f"meeting_request template proposed a call: {hits}"
        # Must still push the package + checkout link
        assert (
            "secure link" in reply["body_text"].lower()
            or "checkout" in reply["body_text"].lower()
            or "https://" in reply["body_text"]
        )

    def test_09_call_request_pattern_forces_draft(self):
        """FORCED_DRAFT 'call_request' regex must catch explicit call asks."""
        label, pat = detect_forced_draft(
            subject="Re: your cold email",
            body="Can we hop on a quick call this week to discuss?",
        )
        assert label == "call_request", (
            f"'hop on a quick call' should be caught by FORCED_DRAFT call_request, got label={label}"
        )

        # Also verify that decide_reply_mode routes it to draft, not auto_send
        trace = decide_reply_mode(
            intent="warm_interest",
            confidence=0.95,
            subject="Re: test",
            body="Can we jump on a zoom call to walk through this?",
            from_email="buyer@acme.co",
            reply_will_use_standard_template=True,
            recent_auto_reply_in_thread=False,
            settings=ReplyPolicySettings(),
        )
        assert trace.final_mode == "draft"
        assert trace.mode_source == "forced_draft"
        assert trace.forced_draft_match == "call_request"


# ═══════════════════════════════════════════════════════════════════════════
#  NO-FREE-WORK (3 tests)
# ═══════════════════════════════════════════════════════════════════════════


class TestNoFreeWork:
    def test_10_default_reply_has_no_sample_angles_offer(self):
        """With free_preview_enabled=False (default), no reply may offer sample angles."""
        settings = ReplyPolicySettings()  # default: free_preview_enabled=False
        for intent in (
            "warm_interest",
            "proof_request",
            "pricing_request",
            "objection",
            "meeting_request",
        ):
            reply = _build_reply_body(
                intent=intent,
                first_name="Alex",
                company="Acme",
                thread_subject="test",
                settings=settings,
                recommendation=PackageRecommendation(
                    slug="growth-content-pack",
                    rationale="Established brand with recurring need.",
                    signals=["monthly_content"],
                    confidence=0.8,
                ),
            )
            hits = _contains_any(reply["body_text"], FORBIDDEN_FREE_WORK_PHRASES)
            assert not hits, (
                f"Free-work language leaked into intent={intent} with defaults: {hits}\n{reply['body_text']}"
            )
            assert reply.get("preview_fallback_used") is False

    def test_11_free_preview_off_by_default_in_settings(self):
        """ReplyPolicySettings default: free_preview_enabled=False."""
        settings = ReplyPolicySettings()
        assert settings.free_preview_enabled is False
        assert settings.calls_enabled is False
        assert settings.broad_market_positioning_enabled is True
        assert settings.package_recommendation_mode == "signal_based"
        assert settings.front_end_speed_language_mode == "none"

    def test_12_enabled_preview_uses_recommended_angles_framing(self):
        """When free_preview_enabled=True, the framing must be 'recommended angles' — not 'samples' or 'test runs'."""
        settings = ReplyPolicySettings(
            free_preview_enabled=True,
            preview_fallback_allowed_intents=frozenset({"proof_request"}),
        )
        reply = _build_reply_body(
            intent="proof_request",
            first_name="Alex",
            company="Acme",
            thread_subject="test",
            settings=settings,
            recommendation=PackageRecommendation(
                slug="growth-content-pack",
                rationale="Established brand.",
                signals=[],
                confidence=0.5,
            ),
        )
        # Must mention "recommended angles" or "creative directions", never "samples/test runs"
        body_low = reply["body_text"].lower()
        assert "recommended angles" in body_low or "creative directions" in body_low, (
            f"Preview fallback did not use 'recommended angles' framing:\n{reply['body_text']}"
        )
        forbidden = [
            "samples",
            "sample angles",
            "test run",
            "test runs",
            "free preview",
            "spec work",
            "free work",
        ]
        for f in forbidden:
            assert f not in body_low, f"Preview framing used forbidden word: {f!r}"
        assert reply.get("preview_fallback_used") is True


# ═══════════════════════════════════════════════════════════════════════════
#  REPLY QUALITY (3 tests)
# ═══════════════════════════════════════════════════════════════════════════


class TestReplyQuality:
    def test_13_package_first_reply_contains_checkout_link(self):
        """Every package-first reply must include a secure checkout URL."""
        for intent in ("warm_interest", "proof_request", "pricing_request", "objection"):
            reply = _build_reply_body(
                intent=intent,
                first_name="Alex",
                company="Acme",
                thread_subject="test",
                recommendation=PackageRecommendation(
                    slug="growth-content-pack",
                    rationale="Established brand with recurring need.",
                    signals=["monthly_content"],
                    confidence=0.8,
                ),
            )
            assert "https://" in reply["body_text"], f"{intent} reply has no checkout URL:\n{reply['body_text']}"
            assert "growth-content-pack" in reply["body_text"]

    def test_14_reply_contains_package_name_and_price(self):
        """Every warm-interest / pricing reply must surface the actual package + price."""
        for slug in ("growth-content-pack", "performance-creative-pack", "launch-sprint"):
            pkg = PACKAGES[slug]
            reply = _build_reply_body(
                intent="pricing_request",
                first_name="Alex",
                company="Acme",
                thread_subject="test",
                recommendation=PackageRecommendation(
                    slug=slug,
                    rationale="Signal-matched package.",
                    signals=[],
                    confidence=0.8,
                ),
            )
            assert pkg["name"] in reply["body_text"], f"{slug} reply missing package name"
            assert pkg["price"] in reply["body_text"], f"{slug} reply missing price"

    def test_15_reply_body_under_150_words(self):
        """Reply bodies must stay short — this is a private operator note, not a brochure."""
        reply = _build_reply_body(
            intent="warm_interest",
            first_name="Alex",
            company="Acme Inc",
            thread_subject="test",
            recommendation=PackageRecommendation(
                slug="growth-content-pack",
                rationale="Established brand with recurring content need.",
                signals=["monthly_content", "professional_domain"],
                confidence=0.82,
            ),
        )
        word_count = len(reply["body_text"].split())
        assert word_count <= 150, f"Reply body is {word_count} words — over the 150-word ceiling.\n{reply['body_text']}"
        # Also: no HTML wrapper, plain text only
        assert reply["body_html"] == "", "Reply must be plain text only (empty body_html)"


# ═══════════════════════════════════════════════════════════════════════════
#  TRACE / AUDIT (3 tests)
# ═══════════════════════════════════════════════════════════════════════════


class TestTraceAudit:
    def test_16_decision_trace_has_recommended_package(self):
        """DecisionTrace dataclass must carry the recommended package + signals in audit."""
        trace = DecisionTrace(
            intent="warm_interest",
            confidence=0.92,
            recommended_package="performance-creative-pack",
            recommendation_rationale="Paid media + creative rotation signals.",
            lead_signals_used=["paid_media_active", "creative_rotation"],
            signal_confidence=0.85,
            package_default_anchor_avoided=True,
        )
        d = trace.to_dict()
        assert d["recommended_package"] == "performance-creative-pack"
        assert "paid_media_active" in d["lead_signals_used"]
        assert d["signal_confidence"] == 0.85
        assert d["package_default_anchor_avoided"] is True

    def test_17_decision_trace_call_path_suppressed_by_default(self):
        """With default settings (calls_enabled=False), call_path_suppressed must be True on every trace."""
        # DecisionTrace itself starts at False — it's the reply_engine's job to
        # flip it to True based on settings. But the DEFAULT ReplyPolicySettings
        # must have calls_enabled=False, which means every real trace produced
        # by create_reply_draft gets call_path_suppressed=True.
        settings = ReplyPolicySettings()
        assert settings.calls_enabled is False
        # Simulate what reply_engine does:
        trace = DecisionTrace(intent="warm_interest", confidence=0.9)
        trace.call_path_suppressed = not settings.calls_enabled
        assert trace.call_path_suppressed is True
        d = trace.to_dict()
        assert d["call_path_suppressed"] is True

    def test_18_decision_trace_broad_market_positioning_true(self):
        """Every inbound reply trace must record broad_market_positioning=True."""
        trace = DecisionTrace(
            intent="warm_interest",
            confidence=0.9,
            broad_market_positioning=True,
            niche_framing_used=False,
            preview_fallback_allowed=False,
            preview_fallback_used=False,
            speed_language_mode="none",
        )
        d = trace.to_dict()
        assert d["broad_market_positioning"] is True
        assert d["niche_framing_used"] is False
        assert d["preview_fallback_allowed"] is False
        assert d["preview_fallback_used"] is False
        assert d["speed_language_mode"] == "none"


# ═══════════════════════════════════════════════════════════════════════════
#  SANITY: the forbidden-word lists themselves must be non-empty and consistent
# ═══════════════════════════════════════════════════════════════════════════


def test_forbidden_word_lists_are_non_empty():
    """Guardrail against someone accidentally clearing the forbidden lists."""
    assert len(FORBIDDEN_VERTICAL_WORDS) >= 5
    assert len(FORBIDDEN_CALL_PHRASES) >= 10
    assert len(FORBIDDEN_FREE_WORK_PHRASES) >= 10
