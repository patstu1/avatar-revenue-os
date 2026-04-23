"""API behavior / pipeline integration tests for Expansion Pack 2 — Phase A engines.

These tests exercise the pure-function scoring engines directly — no database,
no HTTP client, no async fixtures.  They validate the end-to-end signal logic,
keyword-driven scoring formulas, and the cross-function qualification pipeline
from a product / integration perspective.
"""

import pytest

from packages.scoring.expansion_pack2_phase_a_engines import (
    EP2A,
    detect_offer_opportunities,
    generate_closer_actions,
    score_lead,
)


# ---------------------------------------------------------------------------
# End-to-end lead qualification pipeline
# ---------------------------------------------------------------------------

def test_lead_qualification_full_pipeline():
    """score_lead followed by generate_closer_actions must produce a hot tier
    and an action list that includes a discovery-call / booking step when the
    lead arrives via call_booked with high-urgency language."""
    r = score_lead(
        "call_booked",
        "finance",
        (
            "I need this urgently today ASAP ready to invest serious budget premium "
            "I trust your proven framework and follow your strategy results — "
            "been watching your community book a call now struggling to scale"
        ),
        50_000,
        1_000,
        0.08,
        0.12,
        8,
    )
    assert r["qualification_tier"] == "hot", (
        f"Expected hot tier; composite={r['composite_score']:.3f}"
    )

    actions = generate_closer_actions(
        r["qualification_tier"],
        "call_booked",
        "finance",
        r["composite_score"],
        r["urgency_score"],
        r["budget_proxy_score"],
        r["trust_readiness_score"],
        500,
        "WealthPath",
    )
    assert isinstance(actions, list) and len(actions) >= 1

    # At least one action should be a discovery-call or booking step
    action_types = [a["action_type"] for a in actions]
    booking_actions = [
        t for t in action_types
        if any(kw in t for kw in ("book", "discovery", "call"))
    ]
    assert len(booking_actions) >= 1, (
        f"No booking/discovery action found; action_types present: {action_types}"
    )


# ---------------------------------------------------------------------------
# Offer opportunity — signal pattern detection
# ---------------------------------------------------------------------------

def test_offer_opportunity_repeated_question_pattern():
    """Comment themes that are clearly repeated how-to questions must surface at
    least one row whose signal_type is 'repeated_question'."""
    result = detect_offer_opportunities(
        niche="marketing",
        brand_name="FunnelCo",
        top_comment_themes=["how to build a funnel", "where do I start"],
        top_objections=[],
        content_engagement_signals=[],
        audience_segments=[],
        existing_offer_types=[],
        total_audience_size=8_000,
        avg_monthly_revenue=3_000.0,
    )
    signal_types = [r["signal_type"] for r in result]
    assert "repeated_question" in signal_types, (
        f"'repeated_question' not found; signal_types present: {signal_types}"
    )


def test_offer_opportunity_manual_request_template_detection():
    """Themes that are explicit requests for templates or checklists must trigger
    either 'manual_request_pattern' or 'repeated_question' — both indicate
    a clear gap between existing content and a packaged deliverable."""
    result = detect_offer_opportunities(
        niche="productivity",
        brand_name="ToolBrand",
        top_comment_themes=["template please", "checklist for this"],
        top_objections=[],
        content_engagement_signals=[],
        audience_segments=[],
        existing_offer_types=[],
        total_audience_size=6_000,
        avg_monthly_revenue=1_500.0,
    )
    signal_types = [r["signal_type"] for r in result]
    target = {"manual_request_pattern", "repeated_question"}
    assert any(st in target for st in signal_types), (
        f"Neither 'manual_request_pattern' nor 'repeated_question' found; "
        f"signal_types present: {signal_types}"
    )


def test_offer_opportunity_high_trust_weak_affiliate():
    """A brand whose only monetization is affiliate yet has a high-LTV audience
    segment must receive a 'high_trust_weak_affiliate' signal row — the engine
    should flag the monetization gap."""
    result = detect_offer_opportunities(
        niche="finance",
        brand_name="WealthPath",
        top_comment_themes=[],
        top_objections=[],
        content_engagement_signals=[],
        audience_segments=[
            {
                "name": "fans",
                "avg_ltv": 500,
                "conversion_rate": 0.01,
                "estimated_size": 2_000,
            }
        ],
        existing_offer_types=["affiliate"],
        total_audience_size=10_000,
        avg_monthly_revenue=5_000.0,
    )
    signal_types = [r["signal_type"] for r in result]
    assert "high_trust_weak_affiliate" in signal_types, (
        f"'high_trust_weak_affiliate' not found; signal_types present: {signal_types}"
    )


def test_offer_opportunity_membership_trigger():
    """An audience segment with 2 000+ members and no existing membership offer
    must surface at least one row recommending a 'membership' product type."""
    result = detect_offer_opportunities(
        niche="fitness",
        brand_name="FitPro",
        top_comment_themes=[],
        top_objections=[],
        content_engagement_signals=[],
        audience_segments=[
            {
                "name": "loyal",
                "avg_ltv": 300,
                "conversion_rate": 0.02,
                "estimated_size": 2_000,
            }
        ],
        existing_offer_types=["affiliate", "course"],
        total_audience_size=10_000,
        avg_monthly_revenue=4_000.0,
    )
    offer_types = [r["recommended_offer_type"] for r in result]
    assert "membership" in offer_types, (
        f"'membership' not found; recommended_offer_types present: {offer_types}"
    )


# ---------------------------------------------------------------------------
# Lead scoring — keyword-driven sub-scores
# ---------------------------------------------------------------------------

def test_lead_scoring_budget_keywords_raise_budget_score():
    """A message containing explicit budget-intent keywords must produce a higher
    budget_proxy_score than an identical lead with an empty message."""
    base = dict(
        lead_source="comment",
        niche="finance",
        audience_size=10_000,
        avg_offer_aov=200,
        avg_offer_cvr=0.03,
        content_engagement_rate=0.05,
        existing_offer_count=3,
    )
    with_budget = score_lead(**base, message_text="invest serious budget premium")
    without_budget = score_lead(**base, message_text="")
    assert with_budget["budget_proxy_score"] > without_budget["budget_proxy_score"], (
        f"budget with keywords={with_budget['budget_proxy_score']:.3f} "
        f"should exceed budget without={without_budget['budget_proxy_score']:.3f}"
    )


def test_lead_scoring_sophistication_keywords():
    """A message packed with marketing-sophistication vocabulary must produce a
    sophistication_score of at least 0.3 — signalling an audience-aware buyer."""
    r = score_lead(
        "comment",
        "finance",
        "roi funnel conversion optimize scale",
        10_000,
        200,
        0.03,
        0.05,
        3,
    )
    assert r["sophistication_score"] >= 0.3, (
        f"sophistication_score={r['sophistication_score']:.3f} < 0.3 "
        f"for message with explicit sophistication keywords"
    )


# ---------------------------------------------------------------------------
# Closer actions — tier-specific playbook paths
# ---------------------------------------------------------------------------

def test_closer_actions_warm_lead_nurture_path():
    """A warm lead arriving via email should receive at least one nurture-type
    action (case study, testimonials, or follow-up chat) in the playbook."""
    actions = generate_closer_actions(
        "warm",
        "email",
        "business",
        0.52,
        0.50,
        0.45,
        0.55,
        200,
        "GrowthCo",
    )
    action_types = {a["action_type"] for a in actions}
    nurture_types = {"send_case_study", "send_testimonials", "follow_up_chat"}
    assert action_types & nurture_types, (
        f"No nurture action found; action_types present: {action_types}"
    )


def test_closer_action_opener_contains_niche():
    """The subject_or_opener of the first (highest-priority) action for a
    hot finance lead must reference the niche so the outreach feels relevant."""
    actions = generate_closer_actions(
        "hot",
        "call_booked",
        "finance",
        0.80,
        0.75,
        0.70,
        0.80,
        500,
        "WealthPath",
    )
    assert len(actions) >= 1
    # Sort by priority to ensure we're inspecting the priority-1 action
    sorted_actions = sorted(actions, key=lambda a: a["priority"])
    opener = sorted_actions[0]["subject_or_opener"].lower()
    assert "finance" in opener, (
        f"Niche 'finance' not found in first action opener: '{opener}'"
    )


# ---------------------------------------------------------------------------
# Source-channel effect on lead scores
# ---------------------------------------------------------------------------

def test_lead_call_booked_source_boosts_scores():
    """A call_booked lead must have urgency_score and trust_readiness_score that
    are at least as high as the same lead arriving via a plain comment — the
    engine should reward the intentional booking signal."""
    shared_kwargs = dict(
        niche="finance",
        message_text="I need help with this",
        audience_size=10_000,
        avg_offer_aov=200,
        avg_offer_cvr=0.03,
        content_engagement_rate=0.05,
        existing_offer_count=3,
    )
    call_booked = score_lead("call_booked", **shared_kwargs)
    comment = score_lead("comment", **shared_kwargs)

    assert call_booked["urgency_score"] >= comment["urgency_score"], (
        f"call_booked urgency={call_booked['urgency_score']:.3f} "
        f"should be >= comment urgency={comment['urgency_score']:.3f}"
    )
    assert call_booked["trust_readiness_score"] >= comment["trust_readiness_score"], (
        f"call_booked trust={call_booked['trust_readiness_score']:.3f} "
        f"should be >= comment trust={comment['trust_readiness_score']:.3f}"
    )
