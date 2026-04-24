"""Audience State Engine — infer segment states and recommend state-driven actions."""

from __future__ import annotations

from typing import Any

AUDIENCE_STATE = "audience_state_engine"

STATES = [
    "unaware",
    "curious",
    "evaluating",
    "objection_heavy",
    "ready_to_buy",
    "bought_once",
    "repeat_buyer",
    "high_ltv",
    "churn_risk",
    "advocate",
    "sponsor_friendly",
]

_TRANSITION_MAP: dict[str, dict[str, float]] = {
    "unaware": {"curious": 0.35, "unaware": 0.60, "evaluating": 0.05},
    "curious": {"evaluating": 0.40, "unaware": 0.15, "curious": 0.35, "objection_heavy": 0.10},
    "evaluating": {"ready_to_buy": 0.30, "objection_heavy": 0.25, "curious": 0.15, "evaluating": 0.30},
    "objection_heavy": {"evaluating": 0.20, "ready_to_buy": 0.15, "unaware": 0.10, "objection_heavy": 0.55},
    "ready_to_buy": {"bought_once": 0.55, "evaluating": 0.10, "ready_to_buy": 0.30, "churn_risk": 0.05},
    "bought_once": {"repeat_buyer": 0.35, "churn_risk": 0.20, "bought_once": 0.35, "advocate": 0.10},
    "repeat_buyer": {"high_ltv": 0.30, "advocate": 0.20, "churn_risk": 0.10, "repeat_buyer": 0.40},
    "high_ltv": {"advocate": 0.30, "sponsor_friendly": 0.15, "churn_risk": 0.05, "high_ltv": 0.50},
    "churn_risk": {"unaware": 0.25, "curious": 0.15, "churn_risk": 0.50, "bought_once": 0.10},
    "advocate": {"sponsor_friendly": 0.20, "high_ltv": 0.15, "advocate": 0.55, "churn_risk": 0.10},
    "sponsor_friendly": {"advocate": 0.15, "high_ltv": 0.10, "sponsor_friendly": 0.70, "churn_risk": 0.05},
}

_STATE_ACTIONS: dict[str, dict[str, str]] = {
    "unaware": {
        "content_type": "awareness_short_form",
        "offer_approach": "none",
        "channel": "social_organic",
    },
    "curious": {
        "content_type": "educational_explainer",
        "offer_approach": "lead_magnet",
        "channel": "social_organic",
    },
    "evaluating": {
        "content_type": "case_study_comparison",
        "offer_approach": "free_trial_or_demo",
        "channel": "email",
    },
    "objection_heavy": {
        "content_type": "objection_handling_faq",
        "offer_approach": "guarantee_risk_reversal",
        "channel": "email",
    },
    "ready_to_buy": {
        "content_type": "urgency_scarcity",
        "offer_approach": "direct_sale_cta",
        "channel": "email",
    },
    "bought_once": {
        "content_type": "onboarding_quick_win",
        "offer_approach": "upsell_complement",
        "channel": "email",
    },
    "repeat_buyer": {
        "content_type": "loyalty_exclusive",
        "offer_approach": "vip_bundle",
        "channel": "email",
    },
    "high_ltv": {
        "content_type": "premium_insider",
        "offer_approach": "high_ticket_coaching",
        "channel": "direct_outreach",
    },
    "churn_risk": {
        "content_type": "re_engagement_win_back",
        "offer_approach": "discount_incentive",
        "channel": "email",
    },
    "advocate": {
        "content_type": "referral_program_invite",
        "offer_approach": "ambassador_commission",
        "channel": "community",
    },
    "sponsor_friendly": {
        "content_type": "co_branded_content",
        "offer_approach": "sponsor_package",
        "channel": "direct_outreach",
    },
}


def _infer_state(segment: dict[str, Any], engagement: dict[str, Any]) -> tuple[str, float]:
    """Determine best-fit state and score from segment + engagement signals."""
    engagement_rate = float(engagement.get("engagement_rate", 0.0))
    purchase_count = int(engagement.get("purchase_count", 0))
    ltv = float(engagement.get("ltv", 0.0))
    recency_days = int(engagement.get("recency_days", 999))
    frequency = float(engagement.get("frequency", 0.0))
    sentiment = float(engagement.get("feedback_sentiment", 0.5))

    if purchase_count == 0 and engagement_rate < 0.01:
        return "unaware", round(0.75 + (1.0 - min(1.0, engagement_rate * 100)) * 0.2, 3)

    if purchase_count == 0 and engagement_rate < 0.05:
        return "curious", round(0.55 + engagement_rate * 5, 3)

    if purchase_count == 0 and engagement_rate >= 0.05 and sentiment < 0.4:
        return "objection_heavy", round(0.60 + (1.0 - sentiment) * 0.3, 3)

    if purchase_count == 0 and engagement_rate >= 0.05:
        return "evaluating", round(0.50 + engagement_rate * 3, 3)

    if purchase_count >= 1 and recency_days > 90:
        return "churn_risk", round(0.55 + min(0.4, recency_days / 365), 3)

    if purchase_count == 1 and recency_days <= 90:
        return "bought_once", round(0.60 + min(0.3, frequency * 0.5), 3)

    if purchase_count >= 3 and ltv > 0 and sentiment > 0.7:
        return "advocate", round(min(0.95, 0.65 + sentiment * 0.25), 3)

    if purchase_count >= 3 and ltv > 0:
        return "high_ltv", round(min(0.95, 0.60 + min(0.3, purchase_count * 0.05)), 3)

    if purchase_count >= 2:
        return "repeat_buyer", round(0.55 + min(0.35, frequency * 0.3), 3)

    if engagement_rate >= 0.08 and purchase_count == 0:
        return "ready_to_buy", round(0.50 + engagement_rate * 2, 3)

    return "curious", 0.50


def infer_audience_states(
    segments: list[dict[str, Any]],
    engagement_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Infer audience state for each segment.

    Parameters
    ----------
    segments:
        List of dicts with segment metadata.
        Expected keys: segment_id, name, estimated_size.
    engagement_data:
        Dict keyed by segment_id, values are dicts with:
        engagement_rate, purchase_count, ltv, recency_days,
        frequency, feedback_sentiment.

    Returns
    -------
    list[dict] — one entry per segment with state_name, state_score,
    transition_probabilities, best_next_action, confidence, explanation.
    """
    results: list[dict[str, Any]] = []

    for segment in segments:
        seg_id = str(segment.get("segment_id", ""))
        seg_name = segment.get("name", "unknown")
        eng = engagement_data.get(seg_id, {})

        state_name, state_score = _infer_state(segment, eng)
        transitions = _TRANSITION_MAP.get(state_name, {})

        action_map = _STATE_ACTIONS.get(state_name, _STATE_ACTIONS["curious"])
        best_next_action = (
            f"{action_map['content_type']} via {action_map['channel']}, offer: {action_map['offer_approach']}"
        )

        confidence = round(
            min(0.95, 0.40 + state_score * 0.35 + min(0.15, float(eng.get("engagement_rate", 0)) * 2)),
            3,
        )

        results.append(
            {
                "segment_id": seg_id,
                "segment_name": seg_name,
                "state_name": state_name,
                "state_score": state_score,
                "transition_probabilities": transitions,
                "best_next_action": best_next_action,
                "confidence": confidence,
                "explanation": (
                    f"Segment '{seg_name}' classified as {state_name} "
                    f"(score {state_score:.3f}). "
                    f"Key signals: engagement {eng.get('engagement_rate', 0):.4f}, "
                    f"purchases {eng.get('purchase_count', 0)}, "
                    f"LTV {eng.get('ltv', 0):.2f}, "
                    f"recency {eng.get('recency_days', 'N/A')}d."
                ),
                AUDIENCE_STATE: True,
            }
        )

    return results


def recommend_state_actions(
    state_report: dict[str, Any],
) -> dict[str, Any]:
    """Recommend content, offer, and channel actions based on audience state.

    Parameters
    ----------
    state_report:
        A single entry from infer_audience_states output.
        Expected keys: state_name, state_score, segment_name.

    Returns
    -------
    dict with recommended_content_type, recommended_offer_approach,
    recommended_channel, expected_conversion_lift, confidence, explanation.
    """
    state_name = state_report.get("state_name", "curious")
    state_score = float(state_report.get("state_score", 0.5))
    seg_name = state_report.get("segment_name", "unknown")

    action = _STATE_ACTIONS.get(state_name, _STATE_ACTIONS["curious"])

    lift_map = {
        "unaware": 0.02,
        "curious": 0.05,
        "evaluating": 0.10,
        "objection_heavy": 0.08,
        "ready_to_buy": 0.18,
        "bought_once": 0.12,
        "repeat_buyer": 0.15,
        "high_ltv": 0.20,
        "churn_risk": 0.06,
        "advocate": 0.14,
        "sponsor_friendly": 0.16,
    }
    base_lift = lift_map.get(state_name, 0.05)
    expected_lift = round(base_lift * (0.8 + state_score * 0.4), 4)

    confidence = round(min(0.95, 0.45 + state_score * 0.30 + base_lift * 1.5), 3)

    return {
        "segment_name": seg_name,
        "state_name": state_name,
        "recommended_content_type": action["content_type"],
        "recommended_offer_approach": action["offer_approach"],
        "recommended_channel": action["channel"],
        "expected_conversion_lift": expected_lift,
        "confidence": confidence,
        "explanation": (
            f"For '{seg_name}' in state {state_name} (score {state_score:.3f}): "
            f"serve {action['content_type']} via {action['channel']}, "
            f"offer {action['offer_approach']}. "
            f"Expected lift {expected_lift:.2%}."
        ),
        AUDIENCE_STATE: True,
    }
