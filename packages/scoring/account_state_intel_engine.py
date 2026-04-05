"""Account-State Intelligence Engine — classify, transition, recommend.

Pure functions. No I/O.
"""
from __future__ import annotations
from typing import Any, Optional

ACCOUNT_STATES = [
    "newborn", "warming", "early_signal", "scaling", "monetizing",
    "authority_building", "trust_repair", "saturated", "cooling",
    "weak", "suppressed", "blocked",
]

STATE_POLICIES = {
    "newborn":            {"monetization_intensity": "none",   "posting_cadence": "slow",      "expansion_eligible": False, "content_forms": ["short_video", "text_post"],              "blocked_actions": ["aggressive_monetization", "paid_amplification"]},
    "warming":            {"monetization_intensity": "low",    "posting_cadence": "normal",    "expansion_eligible": False, "content_forms": ["short_video", "carousel", "text_post"],  "blocked_actions": ["aggressive_monetization"]},
    "early_signal":       {"monetization_intensity": "low",    "posting_cadence": "normal",    "expansion_eligible": False, "content_forms": ["short_video", "carousel", "story"],      "blocked_actions": []},
    "scaling":            {"monetization_intensity": "medium",  "posting_cadence": "aggressive","expansion_eligible": True,  "content_forms": ["short_video", "long_video", "carousel", "live_stream"], "blocked_actions": []},
    "monetizing":         {"monetization_intensity": "high",   "posting_cadence": "aggressive","expansion_eligible": True,  "content_forms": ["short_video", "long_video", "carousel", "story"],       "blocked_actions": []},
    "authority_building": {"monetization_intensity": "medium",  "posting_cadence": "normal",    "expansion_eligible": True,  "content_forms": ["long_video", "carousel", "text_post"],  "blocked_actions": ["hard_sell_cta"]},
    "trust_repair":       {"monetization_intensity": "none",   "posting_cadence": "slow",      "expansion_eligible": False, "content_forms": ["text_post", "story"],                   "blocked_actions": ["aggressive_monetization", "paid_amplification", "new_offer_launch"]},
    "saturated":          {"monetization_intensity": "low",    "posting_cadence": "reduced",   "expansion_eligible": False, "content_forms": ["short_video", "text_post"],              "blocked_actions": ["volume_increase"]},
    "cooling":            {"monetization_intensity": "low",    "posting_cadence": "reduced",   "expansion_eligible": False, "content_forms": ["short_video", "text_post", "story"],     "blocked_actions": ["aggressive_monetization"]},
    "weak":               {"monetization_intensity": "none",   "posting_cadence": "minimal",   "expansion_eligible": False, "content_forms": ["text_post"],                            "blocked_actions": ["aggressive_monetization", "paid_amplification", "volume_increase"]},
    "suppressed":         {"monetization_intensity": "none",   "posting_cadence": "paused",    "expansion_eligible": False, "content_forms": [],                                       "blocked_actions": ["all"]},
    "blocked":            {"monetization_intensity": "none",   "posting_cadence": "paused",    "expansion_eligible": False, "content_forms": [],                                       "blocked_actions": ["all"]},
}


def classify_account_state(inputs: dict[str, Any]) -> dict[str, Any]:
    """Classify an account into one of the 12 states based on real signals."""
    age_days = int(inputs.get("age_days", 0) or 0)
    post_count = int(inputs.get("post_count", 0) or 0)
    impressions = float(inputs.get("impressions", 0) or 0)
    engagement_rate = float(inputs.get("engagement_rate", 0) or 0)
    conversion_rate = float(inputs.get("conversion_rate", 0) or 0)
    fatigue = float(inputs.get("fatigue_score", 0) or 0)
    saturation = float(inputs.get("saturation_score", 0) or 0)
    health = str(inputs.get("account_health", "healthy") or "healthy")
    revenue = float(inputs.get("total_revenue", 0) or 0)
    profit = float(inputs.get("total_profit", 0) or 0)
    blocker = str(inputs.get("blocker_state", "") or "")

    if blocker in ("blocked", "banned", "suspended"):
        return _result("blocked", 0.95, inputs, "Account is blocked or suspended")
    if health == "suspended":
        return _result("suppressed", 0.90, inputs, "Account health is suspended")

    if health == "critical":
        return _result("trust_repair", 0.85, inputs, "Account health critical — needs trust repair")

    if age_days < 7 and post_count < 5:
        return _result("newborn", 0.90, inputs, f"Account is {age_days} days old with {post_count} posts")

    if age_days < 30 and impressions == 0:
        return _result("warming", 0.80, inputs, "Account in warm-up phase — no impressions yet")

    if saturation > 0.7:
        return _result("saturated", 0.80, inputs, f"Saturation score {saturation:.2f} is high")

    if fatigue > 0.6 and engagement_rate < 0.03:
        return _result("cooling", 0.75, inputs, "High fatigue with declining engagement")

    if health == "warning" and engagement_rate < 0.02:
        return _result("weak", 0.75, inputs, "Warning health with very low engagement")

    if revenue > 0 and conversion_rate > 0 and profit > 0:
        return _result("monetizing", 0.85, inputs, f"Actively monetizing — ${revenue:.0f} revenue, {conversion_rate:.1%} CVR")

    if profit > 0 and engagement_rate > 0.03:
        return _result("scaling", 0.80, inputs, "Profitable with strong engagement — scaling")

    if engagement_rate > 0.04 and age_days > 60:
        return _result("authority_building", 0.70, inputs, "Solid engagement over time — building authority")

    if engagement_rate > 0.02 or impressions > 0:
        return _result("early_signal", 0.65, inputs, "Showing early positive signals")

    if age_days >= 30:
        return _result("warming", 0.60, inputs, "Active but still warming up")

    return _result("newborn", 0.50, inputs, "Insufficient signal to classify further")


def _result(state: str, confidence: float, inputs: dict, explanation: str) -> dict[str, Any]:
    policy = STATE_POLICIES.get(state, STATE_POLICIES["newborn"])
    return {
        "current_state": state,
        "confidence": round(confidence, 3),
        "next_best_move": _next_move(state, inputs),
        "blocked_actions": policy["blocked_actions"],
        "suitable_content_forms": policy["content_forms"],
        "monetization_intensity": policy["monetization_intensity"],
        "posting_cadence": policy["posting_cadence"],
        "expansion_eligible": policy["expansion_eligible"],
        "explanation": explanation,
    }


def _next_move(state: str, inputs: dict) -> str:
    moves = {
        "newborn": "Publish 5+ posts to establish presence",
        "warming": "Focus on consistency and engagement — avoid monetization",
        "early_signal": "Double down on what's getting engagement",
        "scaling": "Increase posting volume and test monetization",
        "monetizing": "Optimize conversion paths and expand offers",
        "authority_building": "Create trust-building long-form content",
        "trust_repair": "Pause monetization, focus on value-first content",
        "saturated": "Reduce volume, refresh creative, test new formats",
        "cooling": "Lower posting cadence, investigate engagement drop",
        "weak": "Audit content quality, consider creative pivot",
        "suppressed": "Investigate suppression cause, await platform resolution",
        "blocked": "Contact platform support, prepare backup account",
    }
    return moves.get(state, "Monitor and reassess")


def detect_transition(
    previous_state: str,
    current_state: str,
    inputs: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """Detect if a meaningful state transition occurred."""
    if previous_state == current_state:
        return None

    positive = {"newborn": 0, "warming": 1, "early_signal": 2, "scaling": 3, "monetizing": 4, "authority_building": 3}
    negative = {"trust_repair": -1, "saturated": -1, "cooling": -2, "weak": -3, "suppressed": -4, "blocked": -5}

    prev_rank = positive.get(previous_state, negative.get(previous_state, 0))
    curr_rank = positive.get(current_state, negative.get(current_state, 0))
    direction = "upgrade" if curr_rank > prev_rank else "downgrade" if curr_rank < prev_rank else "lateral"

    return {
        "from_state": previous_state,
        "to_state": current_state,
        "direction": direction,
        "trigger": f"State changed from {previous_state} to {current_state} based on current signals",
    }


def generate_actions(state: str, inputs: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate recommended actions for the current state."""
    actions: list[dict[str, Any]] = []

    if state == "newborn":
        actions.append({"action_type": "publish_content", "action_detail": "Publish 5+ initial posts across primary content forms", "priority": "high"})
    elif state == "warming":
        actions.append({"action_type": "consistency_check", "action_detail": "Maintain daily posting cadence", "priority": "high"})
        actions.append({"action_type": "engagement_focus", "action_detail": "Reply to comments, engage with niche accounts", "priority": "medium"})
    elif state == "early_signal":
        actions.append({"action_type": "amplify_winners", "action_detail": "Identify top-performing content and create variations", "priority": "high"})
    elif state == "scaling":
        actions.append({"action_type": "volume_increase", "action_detail": "Increase posting volume to 2-3x baseline", "priority": "high"})
        actions.append({"action_type": "monetization_test", "action_detail": "Test soft monetization on high-engagement content", "priority": "medium"})
    elif state == "monetizing":
        actions.append({"action_type": "conversion_optimize", "action_detail": "A/B test CTAs and offer angles", "priority": "high"})
        actions.append({"action_type": "expand_offers", "action_detail": "Add complementary offers to the stack", "priority": "medium"})
    elif state == "authority_building":
        actions.append({"action_type": "long_form_content", "action_detail": "Create authority-building long-form content", "priority": "high"})
    elif state == "trust_repair":
        actions.append({"action_type": "pause_monetization", "action_detail": "Remove all monetization until trust metrics recover", "priority": "critical"})
        actions.append({"action_type": "value_content", "action_detail": "Publish value-first, no-ask content", "priority": "high"})
    elif state == "saturated":
        actions.append({"action_type": "creative_refresh", "action_detail": "Test completely new content formats and hooks", "priority": "high"})
        actions.append({"action_type": "reduce_volume", "action_detail": "Drop posting volume by 30-50%", "priority": "medium"})
    elif state == "cooling":
        actions.append({"action_type": "investigate_decline", "action_detail": "Analyze what changed — algorithm, content quality, or audience", "priority": "high"})
    elif state == "weak":
        actions.append({"action_type": "audit_quality", "action_detail": "Full content quality audit", "priority": "critical"})
        actions.append({"action_type": "consider_pivot", "action_detail": "Evaluate niche or format pivot", "priority": "high"})
    elif state in ("suppressed", "blocked"):
        actions.append({"action_type": "platform_appeal", "action_detail": "Contact platform support for resolution", "priority": "critical"})

    return actions
