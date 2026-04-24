"""Unit tests for Expansion Pack 2 Phase A scoring engines.

Covers:
  - score_lead            (lead qualification)
  - generate_closer_actions (sales / follow-up playbook)
  - detect_offer_opportunities (owned-offer demand signals)

NOTE: content_engagement_signals must be a list[dict], not a plain dict.
"""

from packages.scoring.expansion_pack2_phase_a_engines import (
    EP2A,
    detect_offer_opportunities,
    generate_closer_actions,
    score_lead,
)

# ---------------------------------------------------------------------------
# Shared helpers / fixtures
# ---------------------------------------------------------------------------

_REQUIRED_LEAD_KEYS = (
    "urgency_score",
    "budget_proxy_score",
    "sophistication_score",
    "offer_fit_score",
    "trust_readiness_score",
    "composite_score",
    "qualification_tier",
    "recommended_action",
    "expected_value",
    "likelihood_to_close",
    "channel_preference",
    "confidence",
)

_FLOAT_SCORE_KEYS = (
    "urgency_score",
    "budget_proxy_score",
    "sophistication_score",
    "offer_fit_score",
    "trust_readiness_score",
    "composite_score",
    "confidence",
)

_DEFAULT_LEAD_KWARGS = dict(
    lead_source="comment",
    niche="finance",
    message_text="I need help urgently today",
    audience_size=10_000,
    avg_offer_aov=200,
    avg_offer_cvr=0.03,
    content_engagement_rate=0.05,
    existing_offer_count=3,
)

_HOT_ACTION_KWARGS = dict(
    qualification_tier="hot",
    lead_source="call_booked",
    niche="finance",
    composite_score=0.80,
    urgency_score=0.85,
    budget_proxy_score=0.75,
    trust_readiness_score=0.70,
    avg_offer_aov=500,
    brand_name="WealthPath",
)

_DEFAULT_DETECT_KWARGS = dict(
    niche="finance",
    brand_name="WealthPath",
    top_comment_themes=["how do I start", "need a checklist"],
    top_objections=["too expensive", "not sure it works"],
    content_engagement_signals=[
        {
            "content_id": "c1",
            "title": "How to grow your finance portfolio fast",
            "impressions": 8_000,
            "engagement_rate": 0.06,
            "revenue": 20.0,
        },
        {
            "content_id": "c2",
            "title": "Beginner guide to investing",
            "impressions": 3_000,
            "engagement_rate": 0.04,
            "revenue": 5.0,
        },
    ],
    audience_segments=[
        {
            "name": "beginners",
            "avg_ltv": 200,
            "conversion_rate": 0.02,
            "estimated_size": 3_000,
        }
    ],
    existing_offer_types=["affiliate"],
    total_audience_size=10_000,
    avg_monthly_revenue=5_000.0,
)


# ===========================================================================
# 0. Module constant
# ===========================================================================


def test_ep2a_constant_is_string():
    assert isinstance(EP2A, str)
    assert len(EP2A) > 0


# ===========================================================================
# 1. Lead-scoring engine — score_lead
# ===========================================================================


def test_score_lead_has_required_fields():
    r = score_lead("comment", "finance", "I need help urgently today", 10_000, 200, 0.03, 0.05, 3)
    for key in _REQUIRED_LEAD_KEYS:
        assert key in r, f"Missing key: {key}"


def test_score_lead_scores_in_range():
    r = score_lead(**_DEFAULT_LEAD_KWARGS)
    for key in _FLOAT_SCORE_KEYS:
        val = r[key]
        assert 0 <= val <= 1, f"{key}={val} out of [0, 1]"


def test_score_lead_urgent_message_yields_higher_urgency():
    """A message with clear urgency keywords must score higher urgency than a
    neutral browsing message, all else equal."""
    base = dict(
        lead_source="comment",
        niche="finance",
        audience_size=5_000,
        avg_offer_aov=100,
        avg_offer_cvr=0.02,
        content_engagement_rate=0.04,
        existing_offer_count=2,
    )
    urgent = score_lead(**base, message_text="need this ASAP urgent today help")
    browsing = score_lead(**base, message_text="just browsing")
    assert urgent["urgency_score"] > browsing["urgency_score"]


def test_score_lead_hot_tier_qualification():
    """call_booked source combined with high-intent keywords must produce a hot tier.

    Message deliberately includes urgency, budget, trust, AND sophistication keywords
    so that all five composite dimensions contribute and the 0.65 threshold is reached.
    """
    r = score_lead(
        "call_booked",
        "finance",
        (
            "I need this urgently today ASAP ready to invest serious budget premium "
            "I trust your results I have been watching your proven framework and "
            "follow your strategy — book a call now"
        ),
        20_000,
        500,
        0.05,
        0.08,
        5,
    )
    assert r["qualification_tier"] == "hot", (
        f"Expected hot; composite={r['composite_score']:.3f} "
        f"(urgency={r['urgency_score']:.2f}, budget={r['budget_proxy_score']:.2f}, "
        f"soph={r['sophistication_score']:.2f}, fit={r['offer_fit_score']:.2f}, "
        f"trust={r['trust_readiness_score']:.2f})"
    )


def test_score_lead_cold_tier_qualification():
    """Minimal signal across every dimension must yield a cold qualification tier."""
    r = score_lead("comment", "finance", "ok", 1_000, 50, 0.01, 0.01, 0)
    assert r["qualification_tier"] == "cold"


def test_score_lead_channel_preference_matches_source():
    """channel_preference must always echo the lead_source that was supplied."""
    for source in ("comment", "call_booked", "dm", "email"):
        r = score_lead(source, "finance", "interested in this", 5_000, 100, 0.02, 0.04, 2)
        assert r["channel_preference"] == source, (
            f"Expected channel_preference='{source}', got '{r['channel_preference']}'"
        )


def test_score_lead_expected_value_positive_when_strong_signals():
    """Strong lead signals must produce a strictly positive expected value."""
    r = score_lead(
        "call_booked",
        "finance",
        "ready to invest and book now urgent premium",
        20_000,
        500,
        0.05,
        0.08,
        4,
    )
    assert r["expected_value"] > 0


def test_score_lead_recommended_action_valid():
    """recommended_action must be drawn from the known action vocabulary."""
    valid_actions = {"book_call", "nurture_sequence", "low_priority_follow_up"}
    r = score_lead(**_DEFAULT_LEAD_KWARGS)
    assert r["recommended_action"] in valid_actions, f"Unexpected recommended_action: '{r['recommended_action']}'"


def test_score_lead_composite_drives_tier():
    """qualification_tier must be consistent with composite_score thresholds:
    >= 0.65 → hot, 0.40 ≤ x < 0.65 → warm, < 0.40 → cold."""
    test_cases = [
        # (source, message, aov, cvr, eng, count)
        (
            "call_booked",
            "urgent invest today book ASAP premium serious budget ready",
            1_000,
            0.05,
            0.10,
            5,
        ),
        (
            "dm",
            "I am interested in learning more, sounds like a good fit for me",
            200,
            0.02,
            0.04,
            2,
        ),
        ("comment", "ok", 50, 0.01, 0.01, 0),
    ]
    for source, msg, aov, cvr, eng, count in test_cases:
        r = score_lead(source, "finance", msg, 10_000, aov, cvr, eng, count)
        cs = r["composite_score"]
        tier = r["qualification_tier"]
        if cs >= 0.65:
            assert tier == "hot", f"composite={cs:.3f} expected hot, got {tier}"
        elif cs >= 0.40:
            assert tier == "warm", f"composite={cs:.3f} expected warm, got {tier}"
        else:
            assert tier == "cold", f"composite={cs:.3f} expected cold, got {tier}"


# ===========================================================================
# 2. Closer-action generation — generate_closer_actions
# ===========================================================================


def test_generate_closer_actions_hot_tier_returns_actions():
    """A hot lead via call_booked must produce at least three actionable steps."""
    actions = generate_closer_actions(**_HOT_ACTION_KWARGS)
    assert len(actions) >= 3


def test_generate_closer_actions_action_fields():
    """Every action in the list must carry all seven required keys."""
    required = {
        "action_type",
        "priority",
        "channel",
        "subject_or_opener",
        "timing",
        "rationale",
        "expected_outcome",
    }
    actions = generate_closer_actions(**_HOT_ACTION_KWARGS)
    assert len(actions) >= 1
    for i, action in enumerate(actions):
        for key in required:
            assert key in action, f"Action[{i}] missing key: {key}"


def test_generate_closer_actions_cold_tier_minimum_actions():
    """Even a cold lead must receive at least two follow-up actions."""
    actions = generate_closer_actions(
        "cold",
        "comment",
        "fitness",
        0.25,
        0.20,
        0.15,
        0.20,
        50,
        "FitLife",
    )
    assert len(actions) >= 2


def test_generate_closer_actions_priority_ordering():
    """The highest-priority action must be assigned priority == 1."""
    actions = generate_closer_actions(**_HOT_ACTION_KWARGS)
    priorities = [a["priority"] for a in actions]
    assert 1 in priorities, f"Priority 1 not found in: {priorities}"


def test_generate_closer_actions_high_aov_adds_sponsor_prep():
    """A hot lead with avg_offer_aov >= 500 must include a sponsor_negotiation_prep action."""
    actions = generate_closer_actions(
        "hot",
        "call_booked",
        "finance",
        0.80,
        0.85,
        0.80,
        0.75,
        1_000,
        "WealthPath",
    )
    types = [a["action_type"] for a in actions]
    assert "sponsor_negotiation_prep" in types, f"sponsor_negotiation_prep not found; action_types present: {types}"


def test_generate_closer_actions_timing_valid():
    """All action timings must belong to the allowed timing vocabulary."""
    valid_timings = {"immediate", "24h", "48h", "72h"}
    actions = generate_closer_actions(**_HOT_ACTION_KWARGS)
    for i, action in enumerate(actions):
        assert action["timing"] in valid_timings, f"Action[{i}] has invalid timing: '{action['timing']}'"


def test_generate_closer_actions_channels_valid():
    """All action channels must belong to the allowed channel vocabulary."""
    valid_channels = {"email", "dm", "call", "chat"}
    actions = generate_closer_actions(**_HOT_ACTION_KWARGS)
    for i, action in enumerate(actions):
        assert action["channel"] in valid_channels, f"Action[{i}] has invalid channel: '{action['channel']}'"


# ===========================================================================
# 3. Offer opportunity detection — detect_offer_opportunities
# ===========================================================================

_REQUIRED_OPPORTUNITY_KEYS = (
    "opportunity_key",
    "signal_type",
    "detected_signal",
    "recommended_offer_type",
    "offer_name_suggestion",
    "price_point_min",
    "price_point_max",
    "estimated_demand_score",
    "estimated_first_month_revenue",
    "confidence",
    "build_priority",
)


def test_detect_offer_opportunities_returns_list():
    result = detect_offer_opportunities(**_DEFAULT_DETECT_KWARGS)
    assert isinstance(result, list)


def test_detect_offer_opportunities_has_required_fields():
    """Every returned opportunity row must carry all eleven required fields."""
    result = detect_offer_opportunities(**_DEFAULT_DETECT_KWARGS)
    assert len(result) >= 1, "Expected at least one opportunity row"
    for i, item in enumerate(result):
        for key in _REQUIRED_OPPORTUNITY_KEYS:
            assert key in item, f"Row[{i}] missing key: {key}"


def test_detect_offer_opportunities_comment_themes_trigger_offer():
    """Supplying how-to / checklist comment themes must generate at least one
    opportunity row even when objections, segments and revenue signals are absent."""
    result = detect_offer_opportunities(
        niche="fitness",
        brand_name="FitPro",
        top_comment_themes=["how do I start", "need a checklist"],
        top_objections=[],
        content_engagement_signals=[],
        audience_segments=[],
        existing_offer_types=[],
        total_audience_size=5_000,
        avg_monthly_revenue=1_000.0,
    )
    assert len(result) >= 1


def test_detect_offer_opportunities_objections_trigger_coaching():
    """Common purchase objections must surface at least one coaching_program
    recommendation — coaching addresses belief gaps directly."""
    result = detect_offer_opportunities(
        niche="finance",
        brand_name="WealthPath",
        top_comment_themes=[],
        top_objections=["too expensive", "not sure it works"],
        content_engagement_signals=[],
        audience_segments=[],
        existing_offer_types=[],
        total_audience_size=8_000,
        avg_monthly_revenue=2_000.0,
    )
    coaching_rows = [r for r in result if r["recommended_offer_type"] == "coaching_program"]
    assert len(coaching_rows) >= 1, (
        f"No coaching_program row found; types present: {[r['recommended_offer_type'] for r in result]}"
    )


def test_detect_offer_opportunities_high_engagement_triggers_course():
    """High engagement paired with low conversion revenue must trigger a
    high_interest_low_conversion signal row."""
    result = detect_offer_opportunities(
        niche="business",
        brand_name="ScaleBrand",
        top_comment_themes=[],
        top_objections=[],
        content_engagement_signals=[
            {
                "content_id": "c1",
                "title": "How to scale your business fast",
                "impressions": 15_000,
                "engagement_rate": 0.08,
                "revenue": 10.0,
            }
        ],
        audience_segments=[],
        existing_offer_types=["affiliate"],
        total_audience_size=10_000,
        avg_monthly_revenue=10.0,
    )
    hi_rows = [r for r in result if r["signal_type"] == "high_interest_low_conversion"]
    assert len(hi_rows) >= 1, f"No high_interest_low_conversion row; signal_types: {[r['signal_type'] for r in result]}"


def test_detect_offer_opportunities_build_priority_valid():
    """build_priority must be one of the three allowed values for every row."""
    valid_priorities = {"high", "medium", "low"}
    result = detect_offer_opportunities(**_DEFAULT_DETECT_KWARGS)
    for i, item in enumerate(result):
        assert item["build_priority"] in valid_priorities, (
            f"Row[{i}] has invalid build_priority: '{item['build_priority']}'"
        )


def test_detect_offer_opportunities_price_min_lte_max():
    """price_point_min must never exceed price_point_max."""
    result = detect_offer_opportunities(**_DEFAULT_DETECT_KWARGS)
    for i, item in enumerate(result):
        assert item["price_point_min"] <= item["price_point_max"], (
            f"Row[{i}] price_point_min {item['price_point_min']} > price_point_max {item['price_point_max']}"
        )


def test_detect_offer_opportunities_demand_score_in_range():
    """estimated_demand_score must be a float in [0, 1] for every row."""
    result = detect_offer_opportunities(**_DEFAULT_DETECT_KWARGS)
    for i, item in enumerate(result):
        val = item["estimated_demand_score"]
        assert 0 <= val <= 1, f"Row[{i}] estimated_demand_score={val} out of [0, 1]"


def test_detect_offer_opportunities_no_duplicate_keys():
    """All opportunity_key values across returned rows must be unique."""
    result = detect_offer_opportunities(**_DEFAULT_DETECT_KWARGS)
    keys = [item["opportunity_key"] for item in result]
    assert len(keys) == len(set(keys)), f"Duplicate opportunity_keys detected: {keys}"
