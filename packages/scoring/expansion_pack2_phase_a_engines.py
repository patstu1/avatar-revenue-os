"""Expansion Pack 2 Phase A — lead qualification, closer actions, owned offer detection
(pure functions, no I/O, no SQLAlchemy)."""
from __future__ import annotations

import math
from typing import Any

EP2A = "expansion_pack2_phase_a"

# ---------------------------------------------------------------------------
# Keyword banks
# ---------------------------------------------------------------------------

_URGENCY_KW: list[str] = [
    "need", "asap", "urgent", "today", "now", "help", "struggling",
    "can't", "fix", "problem", "ready", "when can",
]

_BUDGET_KW: list[str] = [
    "invest", "budget", "spend", "afford", "worth", "pay", "cost",
    "price", "premium", "serious",
]

_SOPHISTICATION_KW: list[str] = [
    "strategy", "funnel", "roi", "conversion", "cpm", "epc", "scale",
    "optimize", "proven", "framework", "system", "process", "automate",
]

_TRUST_KW: list[str] = [
    "recommend", "trust", "follow", "fan", "love", "been watching",
    "long time", "community", "already", "proof", "results",
]

_REQUEST_KW: tuple[str, ...] = ("help", "tool", "template", "checklist", "resource")
_EDU_KW: tuple[str, ...] = ("how", "tutorial", "guide")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _h(s: str) -> int:
    """Deterministic hash bucket (0–999), stable across processes."""
    import hashlib
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16) % 1000


def _log_norm(value: float, scale: float = 6.0) -> float:
    """Log10-normalise a large number to [0, 1].  1 000 000 → 1.0 at scale=6."""
    return min(1.0, math.log10(max(1.0, float(value))) / scale)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _kw_score(text: str, keywords: list[str]) -> float:
    """Count keyword hits in *text*; finding 1/3 of keywords → ~1.0.

    Formula: min(1.0, found / max(1, len(keywords)) * 3.0)
    """
    found = sum(1 for kw in keywords if kw in text)
    return min(1.0, found / max(1, len(keywords)) * 3.0)


def _slug(text: str) -> str:
    """Stable alphanumeric slug (no regex dependency)."""
    parts: list[str] = []
    for ch in text.lower():
        parts.append(ch if ch.isalnum() else "_")
    raw = "".join(parts)
    # collapse repeated underscores
    while "__" in raw:
        raw = raw.replace("__", "_")
    return raw.strip("_")


# ---------------------------------------------------------------------------
# Engine 1 — Lead Qualification Scorer
# ---------------------------------------------------------------------------

def score_lead(
    lead_source: str,
    niche: str,
    message_text: str,
    audience_size: int,
    avg_offer_aov: float,
    avg_offer_cvr: float,
    content_engagement_rate: float,
    existing_offer_count: int,
) -> dict[str, Any]:
    """Score an inbound lead across five signal dimensions and return a qualification tier.

    Parameters
    ----------
    lead_source:
        Channel of origination — "comment" | "dm" | "email" | "call_booked" | "form" | "chat"
    niche:
        Brand niche string (may contain spaces or dashes).
    message_text:
        Raw lead message / comment / inquiry text.
    audience_size:
        Total follower count across brand platforms.
    avg_offer_aov:
        Brand average AOV across active offers.
    avg_offer_cvr:
        Brand average conversion rate across active offers.
    content_engagement_rate:
        Brand average content engagement rate (0..1).
    existing_offer_count:
        Number of live brand offers.

    Returns
    -------
    dict with urgency_score, budget_proxy_score, sophistication_score, offer_fit_score,
    trust_readiness_score, channel_preference, expected_value, likelihood_to_close,
    composite_score, qualification_tier, recommended_action, confidence, explanation,
    plus EP2A: True.
    """
    text = message_text.lower()

    # ------------------------------------------------------------------ urgency
    urgency = _kw_score(text, _URGENCY_KW)
    if lead_source == "call_booked":
        urgency += 0.20
    elif lead_source == "dm":
        urgency += 0.10
    urgency_score = round(_clamp(urgency), 3)

    # ------------------------------------------------------------------ budget proxy
    budget = _kw_score(text, _BUDGET_KW)
    aov_signal = _log_norm(avg_offer_aov, scale=4.0)  # log-normalised: $10k AOV → 1.0
    budget += aov_signal * 0.30
    if lead_source == "call_booked":
        budget += 0.15
    budget_proxy_score = round(_clamp(budget), 3)

    # ------------------------------------------------------------------ sophistication
    soph = _kw_score(text, _SOPHISTICATION_KW)
    if len(message_text) > 100:
        soph += 0.10
    if lead_source in ("email", "form"):
        soph += 0.10
    sophistication_score = round(_clamp(soph), 3)

    # ------------------------------------------------------------------ offer fit
    niche_words = [w for w in niche.lower().replace("-", " ").split() if w]
    niche_hits = sum(1 for w in niche_words if w in text)
    niche_overlap = min(1.0, niche_hits / max(1, len(niche_words)))
    offer_count_signal = _clamp(existing_offer_count / 5.0, 0.0, 0.30)
    engagement_bonus = _clamp(content_engagement_rate * 10.0, 0.0, 0.20)
    offer_fit_score = round(_clamp(niche_overlap * 0.50 + offer_count_signal + engagement_bonus), 3)

    # ------------------------------------------------------------------ trust readiness
    trust = _kw_score(text, _TRUST_KW)
    if lead_source == "call_booked":
        trust += 0.25
    elif lead_source == "dm":
        trust += 0.10
    trust_readiness_score = round(_clamp(trust), 3)

    # ------------------------------------------------------------------ composite outputs
    channel_preference: str = lead_source

    expected_value = round(urgency_score * budget_proxy_score * avg_offer_aov * 0.35, 2)

    likelihood_to_close = round(
        _clamp(
            urgency_score * 0.25
            + budget_proxy_score * 0.20
            + offer_fit_score * 0.20
            + trust_readiness_score * 0.20
            + sophistication_score * 0.15
        ),
        3,
    )

    composite_score = round(
        _clamp(
            urgency_score * 0.20
            + budget_proxy_score * 0.20
            + sophistication_score * 0.15
            + offer_fit_score * 0.20
            + trust_readiness_score * 0.25
        ),
        3,
    )

    # ------------------------------------------------------------------ tier & action
    if composite_score >= 0.65:
        qualification_tier = "hot"
        recommended_action = "book_call"
    elif composite_score >= 0.40:
        qualification_tier = "warm"
        recommended_action = "nurture_sequence"
    else:
        qualification_tier = "cold"
        recommended_action = "low_priority_follow_up"

    # ------------------------------------------------------------------ confidence
    confidence = round(
        _clamp(0.35 + composite_score * 0.45 + min(0.20, len(message_text) / 500.0)),
        3,
    )

    # ------------------------------------------------------------------ explanation
    signal_map = {
        "urgency": urgency_score,
        "budget": budget_proxy_score,
        "sophistication": sophistication_score,
        "offer_fit": offer_fit_score,
        "trust": trust_readiness_score,
    }
    top_two = sorted(signal_map.items(), key=lambda kv: kv[1], reverse=True)[:2]
    top_str = ", ".join(f"{k} {v:.2f}" for k, v in top_two)
    explanation = (
        f"Lead via '{lead_source}' scored as '{qualification_tier}' "
        f"(composite {composite_score:.2f}, confidence {confidence:.2f}). "
        f"Top signals: {top_str}. "
        f"Expected value ${expected_value:,.2f}; "
        f"likelihood to close {likelihood_to_close:.2f}. "
        f"Action: {recommended_action}."
    )

    return {
        "urgency_score": urgency_score,
        "budget_proxy_score": budget_proxy_score,
        "sophistication_score": sophistication_score,
        "offer_fit_score": offer_fit_score,
        "trust_readiness_score": trust_readiness_score,
        "channel_preference": channel_preference,
        "expected_value": expected_value,
        "likelihood_to_close": likelihood_to_close,
        "composite_score": composite_score,
        "qualification_tier": qualification_tier,
        "recommended_action": recommended_action,
        "confidence": confidence,
        "explanation": explanation,
        EP2A: True,
    }


# ---------------------------------------------------------------------------
# Engine 2 — Sales Closer Action Generator
# ---------------------------------------------------------------------------

def generate_closer_actions(
    qualification_tier: str,
    lead_source: str,
    niche: str,
    composite_score: float,
    urgency_score: float,
    budget_proxy_score: float,
    trust_readiness_score: float,
    avg_offer_aov: float,
    brand_name: str,
) -> list[dict[str, Any]]:
    """Generate a prioritised list of 3–6 sales closer actions for a qualified lead.

    Parameters
    ----------
    qualification_tier:
        "hot" | "warm" | "cold"
    lead_source:
        Original channel — "comment" | "dm" | "email" | "call_booked" | "form" | "chat"
    niche:
        Brand niche string.
    composite_score:
        Lead composite score from score_lead (0..1).
    urgency_score:
        From score_lead (0..1).
    budget_proxy_score:
        From score_lead (0..1).
    trust_readiness_score:
        From score_lead (0..1).
    avg_offer_aov:
        Brand average offer AOV.
    brand_name:
        Brand display name for personalised openers.

    Returns
    -------
    list[dict] — each dict: action_type, priority, channel, subject_or_opener,
    timing, rationale, expected_outcome.
    """
    _niche = niche.title()
    _brand = brand_name

    # --- personalised opener map ---
    _openers: dict[str, str] = {
        "book_discovery_call": (
            f"Hi! I'd love to explore how {_brand} can help with your {_niche} goals — "
            f"when are you free for a quick discovery call?"
        ),
        "send_proposal": (
            f"Here's a custom {_niche} proposal from {_brand} tailored to exactly what you described."
        ),
        "handle_objection": (
            f"I wanted to address a few common questions about {_brand}'s {_niche} offerings "
            f"before we move forward together."
        ),
        "send_case_study": (
            f"Check out how {_brand} helped another {_niche} creator achieve real results — "
            f"full case study inside."
        ),
        "send_pricing": (
            f"Here's the full {_brand} pricing breakdown for {_niche} — "
            f"transparent and worth every dollar."
        ),
        "premium_service_pitch": (
            f"I think you're a strong fit for {_brand}'s premium {_niche} program — here's why."
        ),
        "send_testimonials": (
            f"Don't just take our word for it — here's what {_niche} creators are saying about {_brand}."
        ),
        "offer_trial": (
            f"Would you like to try {_brand}'s {_niche} solution risk-free before fully committing?"
        ),
        "qualify_consult": (
            f"Let's hop on a quick call to confirm {_brand} is the perfect fit for your {_niche} situation."
        ),
        "follow_up_chat": (
            f"Hey! Just checking in — still interested in how {_brand} can support your {_niche} growth?"
        ),
        "sponsor_negotiation_prep": (
            f"Before our call, here's {_brand}'s {_niche} sponsorship value overview "
            f"so we can maximise every minute together."
        ),
    }

    def _action(
        action_type: str,
        channel: str,
        timing: str,
        priority: int,
        rationale: str = "",
        expected_outcome: str = "",
    ) -> dict[str, Any]:
        return {
            "action_type": action_type,
            "priority": priority,
            "channel": channel,
            "subject_or_opener": _openers.get(
                action_type,
                f"{_brand} — next step for your {_niche} journey.",
            ),
            "timing": timing,
            "rationale": rationale or f"Drive momentum for {_niche} lead at {qualification_tier} tier.",
            "expected_outcome": expected_outcome or f"Move lead closer to conversion in {_brand}'s {_niche} pipeline.",
        }

    # ------------------------------------------------------------------ action matrix
    actions: list[dict[str, Any]] = []

    if qualification_tier == "hot":
        if lead_source == "call_booked":
            actions = [
                _action(
                    "book_discovery_call", "call", "immediate", 1,
                    "Hot lead has already signalled intent by booking — confirm and build rapport immediately.",
                    "Discovery call confirmed; trust established; proposal pathway opened.",
                ),
                _action(
                    "send_proposal", "email", "24h", 2,
                    "Strike while hot — deliver a tailored proposal within 24 h of the discovery call.",
                    "Prospect receives a personalised offer before urgency fades.",
                ),
                _action(
                    "handle_objection", "email", "48h", 3,
                    "Proactively address blockers to prevent the deal from stalling post-proposal.",
                    "Key objections removed; decision confidence increased.",
                ),
                _action(
                    "send_case_study", "email", "48h", 4,
                    "Reinforce social proof after objection handling to lock in conversion.",
                    "Trust deepened; close probability increases.",
                ),
            ]
        elif lead_source in ("dm", "chat"):
            actions = [
                _action(
                    "send_pricing", "dm", "immediate", 1,
                    "DM/chat leads expect fast, direct, transparent responses.",
                    "Pricing clarity delivered; intent captured immediately.",
                ),
                _action(
                    "premium_service_pitch", "dm", "24h", 2,
                    "Upsell to premium tier while intent and channel momentum is highest.",
                    "Higher-AOV conversion opportunity opened.",
                ),
                _action(
                    "book_discovery_call", "call", "24h", 3,
                    "Move high-value conversation to a higher-signal call environment.",
                    "Stronger qualification and close environment secured.",
                ),
                _action(
                    "send_case_study", "email", "48h", 4,
                    "Follow up with tangible proof to reinforce the pitch after call.",
                    "Long-term trust built; converts fence-sitters.",
                ),
            ]
        else:
            actions = [
                _action(
                    "book_discovery_call", "email", "immediate", 1,
                    "Hot lead requires immediate personal outreach to secure conversation.",
                    "Discovery call booked while interest is at peak.",
                ),
                _action(
                    "send_proposal", "email", "24h", 2,
                    "Deliver tailored proposal to capture momentum post-call.",
                    "Lead reviews a personalised offer before urgency window closes.",
                ),
                _action(
                    "send_case_study", "email", "48h", 3,
                    "Provide social proof to support the proposal and reduce hesitation.",
                    "Conversion confidence increased; close rate improved.",
                ),
            ]

    elif qualification_tier == "warm":
        if lead_source == "call_booked":
            actions = [
                _action(
                    "qualify_consult", "call", "24h", 1,
                    "Warm + call booked — validate budget, timeline, and decision authority before pitching.",
                    "Fit confirmed; wasted pitch cycles avoided.",
                ),
                _action(
                    "send_testimonials", "email", "24h", 2,
                    "Prime prospect with peer social proof ahead of the consult call.",
                    "Credibility raised; objections reduced before call.",
                ),
                _action(
                    "handle_objection", "email", "48h", 3,
                    "Address common hesitations post-consult to keep pipeline momentum.",
                    "Lead moves forward with fewer blockers.",
                ),
                _action(
                    "follow_up_chat", "chat", "72h", 4,
                    "Light-touch follow-up to keep a warm connection alive through the decision window.",
                    "Lead stays engaged and does not go cold before deciding.",
                ),
            ]
        else:
            actions = [
                _action(
                    "send_case_study", "email", "24h", 1,
                    "Educate and warm up the lead with relevant {_niche} success stories.",
                    "Lead gains confidence in the solution and brand authority.",
                ),
                _action(
                    "send_testimonials", "email", "48h", 2,
                    "Layer in peer validation to grow trust across the decision window.",
                    "Readiness to buy increases with compounding social proof.",
                ),
                _action(
                    "follow_up_chat", "chat", "72h", 3,
                    "Soft re-engagement touch to stay top-of-mind without pressure.",
                    "Lead re-engages and moves toward a decision.",
                ),
                _action(
                    "offer_trial", "email", "72h", 4,
                    "Lower the commitment barrier with a trial or risk-reversal offer.",
                    "Primary objection removed; initial commitment secured.",
                ),
            ]

    else:  # cold
        actions = [
            _action(
                "send_case_study", "email", "48h", 1,
                "Plant seeds of awareness and authority with relevant proof for a cold lead.",
                "Lead begins to recognise brand value and moves toward warm territory.",
            ),
            _action(
                "follow_up_chat", "chat", "72h", 2,
                "Low-cost touch to test whether intent has updated since first contact.",
                "Dormant interest surfaced; lead re-scored if response received.",
            ),
            _action(
                "offer_trial", "email", "72h", 3,
                "Risk-reversal trial offer lowers entry barrier for hesitant cold leads.",
                "A fraction of cold leads convert via reduced-commitment pathway.",
            ),
        ]

    # ------------------------------------------------------------------ high-AOV sponsor prep
    if avg_offer_aov >= 500.0 and qualification_tier == "hot":
        sponsor_action = _action(
            "sponsor_negotiation_prep", "call", "immediate", 1,
            f"High AOV (${avg_offer_aov:,.0f}) warrants full sponsorship negotiation preparation "
            f"to maximise deal value before any call.",
            "Negotiation enters with a clear value anchor; deal size protected.",
        )
        # shift existing priorities down by 1 to make room at the top
        for a in actions:
            a["priority"] += 1
        actions.insert(0, sponsor_action)

    return actions


# ---------------------------------------------------------------------------
# Engine 3 — Owned Offer Recommendation Engine
# ---------------------------------------------------------------------------

def detect_offer_opportunities(
    niche: str,
    brand_name: str,
    top_comment_themes: list[str],
    top_objections: list[str],
    content_engagement_signals: list[dict[str, Any]],
    audience_segments: list[dict[str, Any]],
    existing_offer_types: list[str],
    total_audience_size: int,
    avg_monthly_revenue: float,
) -> list[dict[str, Any]]:
    """Detect up to 8 owned-offer opportunities from audience signals and content data.

    Parameters
    ----------
    niche:
        Brand niche string.
    brand_name:
        Brand display name.
    top_comment_themes:
        Most common comment topics / recurring questions from the audience.
    top_objections:
        Most common sales objections heard across the funnel.
    content_engagement_signals:
        List of dicts: {content_id, title, engagement_rate, revenue, impressions}.
    audience_segments:
        List of dicts: {name, avg_ltv, conversion_rate, estimated_size}.
    existing_offer_types:
        Current offer type strings in brand portfolio, e.g. ["affiliate", "course"].
    total_audience_size:
        Total follower / subscriber count across all platforms.
    avg_monthly_revenue:
        Brand average monthly revenue (USD).

    Returns
    -------
    list[dict] — up to 8 OwnedOfferOpportunity dicts, each with opportunity_key,
    signal_type, detected_signal, recommended_offer_type, offer_name_suggestion,
    price_point_min, price_point_max, estimated_demand_score, estimated_first_month_revenue,
    audience_fit, confidence, explanation, build_priority, EP2A: True.
    """
    _niche = niche.title()
    _brand = brand_name
    results: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    # ------------------------------------------------------------------ helpers
    def _demand(key: str) -> float:
        """estimated_demand_score: audience size + revenue signal + hash-spread."""
        return round(
            _clamp(
                _log_norm(total_audience_size) * 0.40
                + _clamp(avg_monthly_revenue / max(avg_monthly_revenue + 1, 1)) * 0.30  # Self-relative
                + (_h(key) / 1000.0) * 0.30
            ),
            3,
        )

    def _build_priority(demand: float) -> str:
        if demand > 0.60:
            return "high"
        if demand > 0.35:
            return "medium"
        return "low"

    def _add(
        signal_type: str,
        detected_signal: str,
        recommended_offer_type: str,
        offer_name_suggestion: str,
        price_min: float,
        price_max: float,
        audience_fit: str,
        explanation: str,
        slug_suffix: str,
    ) -> None:
        if len(results) >= 8:
            return
        key = _slug(f"{signal_type}_{slug_suffix}")
        if key in seen_keys:
            return
        seen_keys.add(key)
        demand = _demand(key)
        first_month_rev = round(demand * float(max(0, total_audience_size)) * 0.001 * price_min, 2)
        confidence = round(
            _clamp(
                0.35
                + demand * 0.45
                + _clamp(avg_monthly_revenue / 20_000.0) * 0.20
            ),
            3,
        )
        results.append(
            {
                "opportunity_key": key,
                "signal_type": signal_type,
                "detected_signal": detected_signal,
                "recommended_offer_type": recommended_offer_type,
                "offer_name_suggestion": offer_name_suggestion,
                "price_point_min": price_min,
                "price_point_max": price_max,
                "estimated_demand_score": demand,
                "estimated_first_month_revenue": first_month_rev,
                "audience_fit": audience_fit,
                "confidence": confidence,
                "explanation": explanation,
                "build_priority": _build_priority(demand),
                EP2A: True,
            }
        )

    # ------------------------------------------------------------------
    # Rule 1 — repeated_question
    # Triggers when at least 2 comment themes exist; up to 3 offers.
    # ------------------------------------------------------------------
    if len(top_comment_themes) >= 2:
        for idx, theme in enumerate(top_comment_themes[:3]):
            offer_type = "template_pack" if _h(theme) % 2 == 0 else "digital_course"
            offer_label = offer_type.replace("_", " ").title()
            _add(
                signal_type="repeated_question",
                detected_signal=f"Repeated audience question: '{theme}'",
                recommended_offer_type=offer_type,
                offer_name_suggestion=f"{_brand} {theme.title()} {offer_label}",
                price_min=47.0,
                price_max=297.0,
                audience_fit=f"{_niche} audience consistently asking about '{theme}'",
                explanation=(
                    f"Question theme '{theme}' appears repeatedly across comments, signalling "
                    f"unmet demand. A {offer_label.lower()} that directly answers this question "
                    f"can convert organic curiosity into paid value."
                ),
                slug_suffix=f"{idx}_{_slug(theme)}",
            )

    # ------------------------------------------------------------------
    # Rule 2 — repeated_objection
    # Triggers when at least 1 objection exists; up to 2 offers.
    # ------------------------------------------------------------------
    if len(top_objections) >= 1:
        for idx, objection in enumerate(top_objections[:2]):
            _add(
                signal_type="repeated_objection",
                detected_signal=f"Repeated sales objection: '{objection}'",
                recommended_offer_type="coaching_program",
                offer_name_suggestion=(
                    f"{_brand} {_niche} Coaching: Overcome '{objection[:40].title()}'"
                ),
                price_min=297.0,
                price_max=1497.0,
                audience_fit=f"{_niche} prospects who raise the objection: '{objection[:60]}'",
                explanation=(
                    f"Objection '{objection}' surfaces frequently in the sales funnel. "
                    f"A structured coaching program that directly addresses and resolves this "
                    f"objection converts hesitant prospects at a premium price point."
                ),
                slug_suffix=f"{idx}_{_slug(objection)}",
            )

    # ------------------------------------------------------------------
    # Rule 3 — high_interest_low_conversion
    # Engagement > 5 % but revenue < $50 on a piece of content.
    # ------------------------------------------------------------------
    for sig in content_engagement_signals:
        eng = float(sig.get("engagement_rate", 0.0))
        rev = float(sig.get("revenue", 0.0))
        if eng > 0.05 and rev < 50.0:
            content_id = str(sig.get("content_id", ""))
            title = str(sig.get("title", "content"))
            _add(
                signal_type="high_interest_low_conversion",
                detected_signal=(
                    f"High engagement ({eng:.1%}) but low revenue (${rev:.0f}) on '{title[:60]}'"
                ),
                recommended_offer_type="digital_course",
                offer_name_suggestion=(
                    f"{_brand} {_niche} Digital Course: {title[:40].title()}"
                ),
                price_min=97.0,
                price_max=497.0,
                audience_fit=(
                    f"{_niche} audience already engaging with '{title[:40]}' content topic"
                ),
                explanation=(
                    f"Content '{title[:60]}' generates strong engagement ({eng:.1%}) "
                    f"but only ${rev:.0f} in revenue. A digital course built around this "
                    f"topic can monetise demonstrated audience interest at scale."
                ),
                slug_suffix=content_id if content_id else _slug(title),
            )

    # ------------------------------------------------------------------
    # Rule 4 — high_trust_weak_affiliate
    # Segments with low CVR (<2 %) but high LTV (>$200).
    # ------------------------------------------------------------------
    for seg in audience_segments:
        cvr = float(seg.get("conversion_rate", 0.0))
        ltv = float(seg.get("avg_ltv", 0.0))
        seg_name = str(seg.get("name", "segment"))
        if cvr < 0.02 and ltv > 0:
            offer_type = "membership" if _h(seg_name) % 2 == 0 else "consulting_retainer"
            offer_label = offer_type.replace("_", " ").title()
            price_min = 29.0 if offer_type == "membership" else 297.0
            price_max = 97.0 if offer_type == "membership" else 997.0
            _add(
                signal_type="high_trust_weak_affiliate",
                detected_signal=(
                    f"Segment '{seg_name}': high LTV (${ltv:.0f}) but low affiliate CVR ({cvr:.1%})"
                ),
                recommended_offer_type=offer_type,
                offer_name_suggestion=f"{_brand} {seg_name.title()} {offer_label}",
                price_min=price_min,
                price_max=price_max,
                audience_fit=(
                    f"High-LTV {_niche} segment '{seg_name}' not converting on affiliate offers"
                ),
                explanation=(
                    f"Segment '{seg_name}' shows high lifetime value (${ltv:.0f}) but "
                    f"low affiliate conversion ({cvr:.1%}). An owned {offer_label.lower()} "
                    f"gives full funnel control and captures the trust already built."
                ),
                slug_suffix=_slug(seg_name),
            )

    # ------------------------------------------------------------------
    # Rule 5 — strong_owned_engagement
    # Any segment >1 000 members with no membership in portfolio.
    # ------------------------------------------------------------------
    if "membership" not in existing_offer_types:
        for seg in audience_segments:
            size = int(seg.get("estimated_size", 0))
            seg_name = str(seg.get("name", "segment"))
            if size > 1000:
                _add(
                    signal_type="strong_owned_engagement",
                    detected_signal=(
                        f"Segment '{seg_name}' has {size:,} members with no existing membership offer"
                    ),
                    recommended_offer_type="membership",
                    offer_name_suggestion=f"{_brand} {_niche} Membership Community",
                    price_min=19.0,
                    price_max=97.0,
                    audience_fit=(
                        f"Engaged {_niche} audience segment '{seg_name}' "
                        f"ready for a recurring community product"
                    ),
                    explanation=(
                        f"Segment '{seg_name}' contains {size:,} members with no membership "
                        f"product in the current offer stack. A community membership unlocks "
                        f"predictable MRR and deepens long-term audience loyalty."
                    ),
                    slug_suffix=_slug(seg_name),
                )
                break  # one membership opportunity per evaluation run

    # ------------------------------------------------------------------
    # Rule 6 — educational_traffic
    # How-to / tutorial / guide content with >5 000 impressions.
    # ------------------------------------------------------------------
    for sig in content_engagement_signals:
        title = str(sig.get("title", ""))
        impressions = int(sig.get("impressions", 0))
        if any(kw in title.lower() for kw in _EDU_KW) and impressions > 5_000:
            offer_type = "template_pack" if _h(title) % 2 == 0 else "swipe_file"
            offer_label = offer_type.replace("_", " ").title()
            content_id = str(sig.get("content_id", ""))
            _add(
                signal_type="educational_traffic",
                detected_signal=(
                    f"Educational content '{title[:60]}' driving {impressions:,} impressions"
                ),
                recommended_offer_type=offer_type,
                offer_name_suggestion=(
                    f"{_brand} {_niche} {offer_label}: {title[:40].title()}"
                ),
                price_min=27.0,
                price_max=97.0,
                audience_fit=f"{_niche} audience seeking how-to or tutorial content",
                explanation=(
                    f"Educational content '{title[:60]}' drives {impressions:,} impressions, "
                    f"indicating a large audience seeking structured guidance. "
                    f"A {offer_label.lower()} gives this traffic a paid, deeper resource "
                    f"they can act on immediately."
                ),
                slug_suffix=content_id if content_id else _slug(title),
            )

    # ------------------------------------------------------------------
    # Rule 7 — manual_request_pattern
    # Any comment theme containing an explicit resource request keyword.
    # ------------------------------------------------------------------
    if top_comment_themes:
        for theme in top_comment_themes:
            if any(kw in theme.lower() for kw in _REQUEST_KW):
                _add(
                    signal_type="manual_request_pattern",
                    detected_signal=f"Comment theme '{theme}' contains a direct resource request",
                    recommended_offer_type="swipe_file",
                    offer_name_suggestion=f"{_brand} {_niche} Swipe File & Resource Kit",
                    price_min=17.0,
                    price_max=47.0,
                    audience_fit=(
                        f"{_niche} audience explicitly asking for resources, tools, or templates"
                    ),
                    explanation=(
                        f"Comment theme '{theme}' signals the audience is actively asking for "
                        f"tangible resources. A swipe file is the fastest, lowest-barrier offer "
                        f"to build and delivers immediate perceived value."
                    ),
                    slug_suffix=_slug(theme),
                )
                break  # one swipe-file opportunity per evaluation run

    return results
