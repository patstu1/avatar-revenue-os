"""Package Recommender — signal-based routing for ProofHook creative packages.

ProofHook Revenue-Ops doctrine: the machine does NOT always anchor to the
$1,500 UGC Starter Pack. It reads the inbound message for maturity / paid-media
/ funnel / recurring-need signals and routes to the best-fit package from the
full catalog.

Public API:
    recommend_package(
        *,
        intent: str,
        body_text: str,
        subject: str = "",
        from_email: str = "",
        thread_context: str = "",
        mode: str = "signal_based",
    ) -> PackageRecommendation

Returns a PackageRecommendation with:
    slug         → best-fit package slug from email_templates.PACKAGES
    rationale    → one-sentence explanation of why this package was picked
    signals      → list of signal labels that drove the decision
    confidence   → 0.0–1.0, how strong the signal evidence was
    anchor_avoided → True if the pick is NOT ugc-starter-pack

Routing hierarchy (first match wins):

    1. Funnel / strategy signals     → creative-strategy-funnel-upgrade
    2. Launch / seasonal signals     → launch-sprint
    3. Full retainer signals         → full-creative-retainer
    4. Paid-media scaling signals    → performance-creative-pack
    5. Recurring-need signals        → growth-content-pack
    6. Explicit test / low-budget    → ugc-starter-pack
    7. No signals (default fallback) → growth-content-pack

The default fallback is NOT the starter pack. A lead with no specific signals
defaults to growth-content-pack because that is the "middle anchor" that filters
for seriousness and aligns with ProofHook's package-first positioning.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ═══════════════════════════════════════════════════════════════════════════
#  Signal detection patterns
# ═══════════════════════════════════════════════════════════════════════════
#
# Each tuple: (signal_label, compiled_pattern). Matched against the
# lowercased concatenation of subject + body + thread_context.


def _PAT(p):
    return re.compile(p, re.IGNORECASE)


# ── Strategy / audit / funnel-weakness signals ──────────────────────────────
STRATEGY_SIGNALS: list[tuple[str, re.Pattern]] = [
    (
        "strategy_ask",
        _PAT(
            r"\b(strategy|strategic|audit|diagnosis|assessment|review\s+(our|my|the)\s+(creative|funnel|content|marketing))\b"
        ),
    ),
    (
        "funnel_weakness",
        _PAT(
            r"\b(funnel|conversion(\s+rate)?|not\s+converting|drop[\s\-]?off|landing\s+page|checkout|bounce\s+rate|customer\s+journey)\b"
        ),
    ),
    (
        "creative_underperforming",
        _PAT(
            r"\b(underperform(ing)?|not\s+working|stopped\s+working|fatigue|creative\s+fatigue|getting\s+scrolled|ignored|flat\s+(results|numbers))\b"
        ),
    ),
    (
        "offer_unclear",
        _PAT(r"\b(our\s+offer\s+is|positioning|message\s+is\s+off|don'?t\s+know\s+(what|how)\s+to\s+say)\b"),
    ),
    ("rebuild_ask", _PAT(r"\b(rebuild|overhaul|redo|fix\s+(our|my|the)\s+(creative|funnel|content))\b")),
]

# ── Launch / campaign / seasonal signals ────────────────────────────────────
# NOTE: `product_launch_phrase` matches explicit launch language like "new
# product" / "soft launch". `launch_word` matches the bare word "launch(ing)"
# but uses a negative lookbehind for "pre-" / "pre " so it does NOT fire on
# "pre-launch MVP" style test-mode leads — those must route to ugc-starter-pack,
# not launch-sprint.
LAUNCH_SIGNALS: list[tuple[str, re.Pattern]] = [
    (
        "product_launch_phrase",
        _PAT(
            r"\b(new\s+product|product\s+drop|new\s+release|soft\s+launch|hard\s+launch|go[\s\-]?live|going\s+live)\b"
        ),
    ),
    ("launch_word", _PAT(r"(?<!pre[\s\-])\blaunch(ing)?\b")),
    (
        "seasonal_push",
        _PAT(
            r"\b(black\s+friday|bfcm|cyber\s+monday|holiday\s+(push|season|launch)|q4\s+(push|campaign)|peak\s+season|seasonal\s+(push|campaign))\b"
        ),
    ),
    ("funding_moment", _PAT(r"\b(raised|fund(ed|ing)|series\s+[a-d]|pre[\s\-]?seed|announce(ment)?|milestone)\b")),
    (
        "campaign_sprint",
        _PAT(r"\b(sprint|compressed\s+timeline|fast\s+turn|need\s+(this|it)\s+(fast|now|asap|quickly))\b"),
    ),
]

# ── Full retainer / creative partner signals ────────────────────────────────
# NOTE: `high_spend_mention` was narrowed — "scaling spend/budget/hard" was
# dropped because it overlaps with paid-media territory (a lead saying
# "scaling spend on Meta ads" is a performance-creative lead, not a retainer
# lead). Only literal dollar figures and seven/six-figure language now fire
# this signal.
FULL_RETAINER_SIGNALS: list[tuple[str, re.Pattern]] = [
    (
        "embedded_partner",
        _PAT(
            r"\b(creative\s+partner|embedded\s+team|dedicated\s+team|in[\s\-]?house\s+(team|equivalent)|full[\s\-]?time\s+creative)\b"
        ),
    ),
    (
        "priority_turnaround",
        _PAT(r"\b(priority|urgent|always\s+on|on[\s\-]?demand|rapid\s+turnaround|need\s+priority)\b"),
    ),
    (
        "multi_brand",
        _PAT(r"\b(multiple\s+brands|portfolio|brand\s+family|sister\s+brands|parent\s+brand|brand\s+portfolio)\b"),
    ),
    (
        "high_spend_mention",
        _PAT(
            r"\b(seven[\s\-]?figure|six[\s\-]?figure\s+budget|spend(ing)?\s+(significant|heavy|big)|\$\s*\d{2,}[,.]?\d{3}\s*(\/|per)\s*(month|mo))\b"
        ),
    ),
]

# ── Paid media / performance creative signals ───────────────────────────────
PAID_MEDIA_SIGNALS: list[tuple[str, re.Pattern]] = [
    (
        "paid_media_active",
        _PAT(
            r"\b(meta\s+ads|facebook\s+ads|fb\s+ads|instagram\s+ads|ig\s+ads|google\s+ads|tiktok\s+ads|youtube\s+ads|ad\s+spend|adspend|paid\s+(media|social|ads)|performance\s+marketing|performance\s+(ads|creative))\b"
        ),
    ),
    ("performance_metrics", _PAT(r"\b(cpm|cpa|roas|mer|ltv|cac|ctr|thumb[\s\-]?stop|hold\s+rate)\b")),
    (
        "creative_rotation",
        _PAT(
            r"\b(creative\s+rotation|rotate\s+(creative|ads)|fresh\s+(creative|ads)|new\s+creative\s+batch|creative\s+refresh)\b"
        ),
    ),
    (
        "scaling_spend",
        _PAT(
            r"\b(scaling\s+(ads|spend|paid)|increase\s+(spend|budget)|more\s+(creative|ad)\s+(volume|variations)|testing\s+(hooks|angles))\b"
        ),
    ),
]

# ── Recurring need / monthly content signals ────────────────────────────────
RECURRING_SIGNALS: list[tuple[str, re.Pattern]] = [
    (
        "monthly_content",
        _PAT(
            r"\b(monthly|every\s+month|per\s+month|\/month|recurring|ongoing|consistent(ly)?|content\s+engine|content\s+machine)\b"
        ),
    ),
    (
        "outgrown_freelancers",
        _PAT(
            r"\b(outgrown\s+freelancers?|too\s+many\s+freelancers?|need\s+(consistency|reliability)|unreliable\s+freelancers?)\b"
        ),
    ),
    (
        "content_calendar",
        _PAT(r"\b(content\s+calendar|editorial\s+calendar|content\s+plan|publishing\s+schedule|content\s+cadence)\b"),
    ),
    (
        "always_posting",
        _PAT(r"\b(always\s+posting|daily\s+content|weekly\s+content|keep\s+up\s+with\s+(posting|content))\b"),
    ),
]

# ── Test / early-stage / low-commitment signals (starter-pack territory) ───
TEST_SIGNALS: list[tuple[str, re.Pattern]] = [
    (
        "one_off_test",
        _PAT(
            r"\b(one[\s\-]?off|just\s+(try|test)|pilot|single\s+project|first\s+project|trial|starting\s+small|dip\s+(our|my)\s+toe)\b"
        ),
    ),
    (
        "no_retainer",
        _PAT(
            r"\b(no\s+retainer|without\s+(a\s+)?retainer|don'?t\s+want\s+(a\s+)?retainer|hate\s+retainers|avoid\s+retainers)\b"
        ),
    ),
    (
        "pre_launch_mvp",
        _PAT(r"\b(pre[\s\-]?launch|mvp|beta|early\s+stage|just\s+(starting|launched)|new\s+brand|brand\s+new)\b"),
    ),
    (
        "budget_low",
        _PAT(r"\b(tight\s+budget|small\s+budget|shoestring|limited\s+budget|bootstrap(ping|ed)?|startup\s+budget)\b"),
    ),
    (
        "proof_of_concept",
        _PAT(r"\b(proof[\s\-]?of[\s\-]?concept|poc|see\s+if\s+(this|it)\s+works|test\s+the\s+waters)\b"),
    ),
]

# ── Established brand signals (nudges away from starter) ───────────────────
ESTABLISHED_SIGNALS: list[tuple[str, re.Pattern]] = [
    (
        "established_brand",
        _PAT(
            r"\b(established|growing\s+brand|scaling\s+brand|our\s+team|our\s+head\s+of|marketing\s+team|creative\s+team)\b"
        ),
    ),
    (
        "agency_transition",
        _PAT(
            r"\b(current\s+agency|former\s+agency|previous\s+agency|switching\s+agencies|leaving\s+(our|my)\s+agency)\b"
        ),
    ),
    ("professional_domain", None),  # Populated at runtime from from_email domain
]


# ═══════════════════════════════════════════════════════════════════════════
#  Output dataclass
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class PackageRecommendation:
    """Signal-based package routing result.

    This is stored on DecisionTrace and surfaced in the audit trail.
    """

    slug: str  # e.g. "performance-creative-pack"
    rationale: str  # one-sentence why
    signals: list[str] = field(default_factory=list)  # ["paid_media_active", "creative_rotation"]
    confidence: float = 0.0  # 0.0–1.0
    anchor_avoided: bool = True  # True when slug != "ugc-starter-pack"
    fallback_reason: str = ""  # populated when routing hit the default

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "rationale": self.rationale,
            "signals": self.signals,
            "confidence": round(self.confidence, 3),
            "anchor_avoided": self.anchor_avoided,
            "fallback_reason": self.fallback_reason,
        }


# ═══════════════════════════════════════════════════════════════════════════
#  Signal detection helpers
# ═══════════════════════════════════════════════════════════════════════════

_PERSONAL_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "yahoo.com",
        "outlook.com",
        "hotmail.com",
        "icloud.com",
        "aol.com",
        "live.com",
        "msn.com",
        "proton.me",
        "protonmail.com",
        "mail.com",
        "gmx.com",
        "yandex.com",
        "zoho.com",
    }
)


def _is_professional_domain(from_email: str) -> bool:
    """True if from_email is NOT a personal webmail provider."""
    if not from_email or "@" not in from_email:
        return False
    domain = from_email.strip().lower().split("@", 1)[-1]
    return domain not in _PERSONAL_EMAIL_DOMAINS


def _match_signals(
    patterns: list[tuple[str, re.Pattern | None]],
    text: str,
) -> list[str]:
    """Return the labels of every pattern that matches."""
    hits: list[str] = []
    for label, pat in patterns:
        if pat is None:
            continue
        if pat.search(text):
            hits.append(label)
    return hits


def _extract_all_signals(
    text: str,
    from_email: str = "",
) -> dict[str, list[str]]:
    """Extract every signal category from the combined input text."""
    signals = {
        "strategy": _match_signals(STRATEGY_SIGNALS, text),
        "launch": _match_signals(LAUNCH_SIGNALS, text),
        "full_retainer": _match_signals(FULL_RETAINER_SIGNALS, text),
        "paid_media": _match_signals(PAID_MEDIA_SIGNALS, text),
        "recurring": _match_signals(RECURRING_SIGNALS, text),
        "test": _match_signals(TEST_SIGNALS, text),
        "established": _match_signals(ESTABLISHED_SIGNALS, text),
    }
    # Sender-domain signal: professional domain is a soft "established" hint
    if _is_professional_domain(from_email):
        signals["established"].append("professional_domain")
    return signals


def _flatten(sig_dict: dict[str, list[str]]) -> list[str]:
    out: list[str] = []
    for v in sig_dict.values():
        out.extend(v)
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  Routing logic
# ═══════════════════════════════════════════════════════════════════════════


def _route(
    intent: str,
    sigs: dict[str, list[str]],
) -> tuple[str, str, list[str], float, str]:
    """Apply routing hierarchy — return (slug, rationale, signals_used, conf, fallback_reason)."""

    # 1. Strategy / funnel / audit signals → creative-strategy-funnel-upgrade
    # ONLY route to strategy when the lead EXPLICITLY asks for a strategy/audit/
    # rebuild. Symptoms alone (creative_underperforming like "fatigue",
    # funnel_weakness like "not converting") do NOT count — they frequently
    # fire on paid-media rotation leads where the right package is Performance
    # Creative Pack, not a strategic audit. The cue for strategy routing must
    # be an explicit ask: strategy_ask or rebuild_ask.
    explicit_strategy_ask = any(s in sigs["strategy"] for s in ("strategy_ask", "rebuild_ask"))
    if explicit_strategy_ask:
        return (
            "creative-strategy-funnel-upgrade",
            "Lead mentioned strategy / funnel / creative audit needs — Creative Strategy + Funnel Upgrade rebuilds underperforming creative at the root.",
            sigs["strategy"] + sigs["paid_media"],
            min(0.60 + 0.10 * len(sigs["strategy"]), 0.95),
            "",
        )

    # 2. Launch / campaign / seasonal signals → launch-sprint
    if sigs["launch"]:
        return (
            "launch-sprint",
            "Lead referenced a launch / campaign / compressed timeline — Launch Sprint is built for exactly this moment.",
            sigs["launch"],
            min(0.60 + 0.10 * len(sigs["launch"]), 0.95),
            "",
        )

    # 3. Full retainer signals (embedded/priority/multi-brand) → full-creative-retainer
    if sigs["full_retainer"]:
        return (
            "full-creative-retainer",
            "Lead signalled priority / embedded / multi-brand needs — Full Creative Retainer is the operational fit.",
            sigs["full_retainer"] + sigs["paid_media"],
            min(0.60 + 0.10 * len(sigs["full_retainer"]), 0.95),
            "",
        )

    # 4. Paid-media scaling → performance-creative-pack
    # Require at least one paid_media signal AND (scaling OR rotation OR >=2 paid signals)
    if sigs["paid_media"]:
        paid_is_scaling = (
            "scaling_spend" in sigs["paid_media"]
            or "creative_rotation" in sigs["paid_media"]
            or len(sigs["paid_media"]) >= 2
        )
        if paid_is_scaling:
            return (
                "performance-creative-pack",
                "Lead mentioned paid media / performance creative / rotation — Performance Creative Pack is built for paid-media volume.",
                sigs["paid_media"] + sigs["recurring"],
                min(0.55 + 0.10 * len(sigs["paid_media"]), 0.92),
                "",
            )

    # 5. Recurring-need signals → growth-content-pack
    if sigs["recurring"]:
        return (
            "growth-content-pack",
            "Lead needs consistent monthly content output — Growth Content Pack is the recurring-engine fit.",
            sigs["recurring"] + sigs["established"] + sigs["paid_media"],
            min(0.55 + 0.10 * len(sigs["recurring"]), 0.90),
            "",
        )

    # 6. Explicit test / low-budget / early-stage → ugc-starter-pack
    # This is the ONLY path that routes to starter without a free-preview offer.
    if sigs["test"]:
        return (
            "ugc-starter-pack",
            "Lead signalled test / early stage / no-retainer preference — UGC Starter Pack is the right low-commitment entry point.",
            sigs["test"],
            min(0.55 + 0.10 * len(sigs["test"]), 0.90),
            "",
        )

    # 7. Established brand with paid media (but not scaling) → growth-content-pack
    if sigs["paid_media"] and sigs["established"]:
        return (
            "growth-content-pack",
            "Established brand running paid media — Growth Content Pack covers the monthly creative supply that paid media needs.",
            sigs["paid_media"] + sigs["established"],
            0.65,
            "",
        )

    # 8. Intent-based tiebreakers when no strong signals exist.
    # warm_interest / proof_request / pricing_request all default to growth
    # rather than starter — starter is ONLY picked when test signals fire.
    if intent in ("warm_interest", "proof_request", "pricing_request"):
        return (
            "growth-content-pack",
            "No specific test / paid-media / funnel signals — defaulting to Growth Content Pack as the package-first middle anchor (not the starter).",
            sigs["established"],
            0.40,
            "default_no_signals",
        )

    # 9. Ultimate fallback: growth pack. Starter is NEVER the default.
    return (
        "growth-content-pack",
        "Default fallback — Growth Content Pack is the package-first middle anchor for unclassified leads.",
        [],
        0.30,
        "default_ultimate_fallback",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════════════


def recommend_package(
    *,
    intent: str,
    body_text: str,
    subject: str = "",
    from_email: str = "",
    thread_context: str = "",
    mode: str = "signal_based",
) -> PackageRecommendation:
    """Return a signal-based package recommendation for a lead message.

    Args:
        intent: Classifier intent label (warm_interest, proof_request, etc.)
        body_text: Cleaned inbound body (quote-stripped if possible)
        subject: Inbound subject (optional, adds to signal surface)
        from_email: Sender address (domain hint for established signal)
        thread_context: Optional — historical thread text to boost signal count
        mode: "signal_based" (default) or "starter_default" (legacy)

    Returns:
        PackageRecommendation with slug, rationale, signals, confidence.

    In "starter_default" mode the function short-circuits and returns the
    legacy $1,500 starter pack with anchor_avoided=False — this is the only
    way to get the old behavior back and exists for config rollback only.
    """
    if mode == "starter_default":
        return PackageRecommendation(
            slug="ugc-starter-pack",
            rationale="Legacy starter-default mode — signal-based routing disabled.",
            signals=[],
            confidence=0.0,
            anchor_avoided=False,
            fallback_reason="legacy_starter_default_mode",
        )

    combined = " ".join([subject or "", body_text or "", thread_context or ""]).strip()
    if not combined:
        # No content to read — return the no-signal default
        return PackageRecommendation(
            slug="growth-content-pack",
            rationale="No inbound body text to read — defaulting to Growth Content Pack middle anchor.",
            signals=[],
            confidence=0.20,
            anchor_avoided=True,
            fallback_reason="empty_body",
        )

    sigs = _extract_all_signals(combined, from_email=from_email)
    slug, rationale, signals_used, confidence, fallback_reason = _route(intent, sigs)

    # Dedupe signals while preserving order
    seen = set()
    deduped: list[str] = []
    for s in signals_used:
        if s and s not in seen:
            seen.add(s)
            deduped.append(s)

    return PackageRecommendation(
        slug=slug,
        rationale=rationale,
        signals=deduped,
        confidence=round(confidence, 3),
        anchor_avoided=(slug != "ugc-starter-pack"),
        fallback_reason=fallback_reason,
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Helper: extract signals for downstream visibility (e.g. reply templates)
# ═══════════════════════════════════════════════════════════════════════════


def extract_lead_signals(
    body_text: str,
    subject: str = "",
    from_email: str = "",
    thread_context: str = "",
) -> dict[str, list[str]]:
    """Return the full signal dictionary for a lead message.

    Reply templates can use this to show the lead "we heard what you said"
    without calling the recommender twice.
    """
    combined = " ".join([subject or "", body_text or "", thread_context or ""]).strip()
    return _extract_all_signals(combined, from_email=from_email)
