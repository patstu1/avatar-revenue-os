"""Brain Architecture Phase A — deterministic state engines and memory consolidation."""
from __future__ import annotations

from typing import Any

# ── valid states ──────────────────────────────────────────────────────
ACCOUNT_STATES = ["newborn", "warming", "stable", "scaling", "max_output", "saturated", "cooling", "at_risk"]
OPPORTUNITY_STATES = ["monitor", "test", "scale", "suppress", "evergreen_backlog", "blocked"]
EXECUTION_STATES = ["queued", "autonomous", "guarded", "manual", "blocked", "failed", "recovering", "completed"]
AUDIENCE_STATES_V2 = [
    "unaware", "curious", "evaluating", "objection_heavy", "ready_to_buy",
    "bought_once", "repeat_buyer", "high_ltv", "churn_risk", "advocate", "sponsor_friendly",
]

MEMORY_ENTRY_TYPES = [
    "winner", "loser", "saturated_pattern", "best_niche", "best_monetization_route",
    "best_account_type", "best_cta", "best_pacing", "common_blocker", "common_fix",
    "confidence_adjustment", "platform_learning",
]


# ── Account State Engine ──────────────────────────────────────────────

def compute_account_state(ctx: dict[str, Any]) -> dict[str, Any]:
    follower_count = ctx.get("follower_count", 0)
    age_days = ctx.get("age_days", 0)
    avg_engagement = ctx.get("avg_engagement", 0.0)
    profit_per_post = ctx.get("profit_per_post", 0.0)
    fatigue = ctx.get("fatigue_score", 0.0)
    saturation = ctx.get("saturation_score", 0.0)
    health = ctx.get("account_health", "healthy")
    posting_capacity = ctx.get("posting_capacity_per_day", 1)
    output_per_week = ctx.get("output_per_week", 0.0)

    if health in ("critical", "suspended"):
        state, score, reason = "at_risk", 0.15, "Account health critical or suspended"
    elif age_days < 14:
        state, score, reason = "newborn", 0.10, f"Account is {age_days} days old"
    elif age_days < 45 and follower_count < 500:
        state, score, reason = "warming", 0.25, "Low followers in early warmup period"
    elif saturation > 0.75:
        state, score, reason = "saturated", 0.40, f"Saturation at {saturation:.0%}"
    elif fatigue > 0.65:
        state, score, reason = "cooling", 0.35, f"Fatigue at {fatigue:.0%}"
    elif profit_per_post > 15 and avg_engagement > 0.03 and output_per_week >= posting_capacity * 5:
        state, score, reason = "max_output", 0.90, "Profitable at near-capacity"
    elif profit_per_post > 8 and avg_engagement > 0.025:
        state, score, reason = "scaling", 0.75, "Good profit and engagement, scaling"
    elif avg_engagement > 0.015 and follower_count > 200:
        state, score, reason = "stable", 0.55, "Stable engagement and modest audience"
    else:
        state, score, reason = "warming", 0.30, "Still building momentum"

    next_state = _next_account_state(state, score, fatigue, saturation)
    conf = min(1.0, 0.5 + min(age_days, 90) / 180)

    return {
        "current_state": state,
        "state_score": round(score, 3),
        "transition_reason": reason,
        "next_expected_state": next_state,
        "confidence": round(conf, 3),
        "explanation": f"State '{state}' (score {score:.2f}). {reason}. Next: {next_state}.",
    }


def _next_account_state(state: str, score: float, fatigue: float, saturation: float) -> str:
    if state == "newborn":
        return "warming"
    if state == "warming":
        return "stable" if score > 0.3 else "at_risk"
    if state == "stable":
        return "scaling" if score > 0.5 else "cooling"
    if state == "scaling":
        return "max_output" if fatigue < 0.4 else "saturated"
    if state == "max_output":
        return "saturated" if saturation > 0.6 else "max_output"
    if state == "saturated":
        return "cooling"
    if state == "cooling":
        return "stable" if fatigue < 0.3 else "at_risk"
    return "warming"


# ── Opportunity State Engine ──────────────────────────────────────────

def compute_opportunity_state(ctx: dict[str, Any]) -> dict[str, Any]:
    score = ctx.get("opportunity_score", 0.0)
    tests_run = ctx.get("tests_run", 0)
    win_rate = ctx.get("win_rate", 0.0)
    blocker = ctx.get("has_blocker", False)
    suppression_risk = ctx.get("suppression_risk", 0.0)
    urgency = ctx.get("urgency", 0.5)
    readiness = ctx.get("readiness", 0.5)

    if blocker:
        state = "blocked"
        exp = "Opportunity has an active blocker"
    elif suppression_risk > 0.7:
        state = "suppress"
        exp = f"Suppression risk at {suppression_risk:.0%}"
    elif tests_run > 0 and win_rate > 0.5 and score > 0.6:
        state = "scale"
        exp = f"Tested with {win_rate:.0%} win rate — ready to scale"
    elif score > 0.4 and readiness > 0.5:
        state = "test"
        exp = f"Score {score:.2f} with readiness {readiness:.2f} — test phase"
    elif score > 0.2:
        state = "monitor"
        exp = "Moderate signal — keep monitoring"
    else:
        state = "evergreen_backlog"
        exp = "Low urgency backlog item"

    conf = min(1.0, 0.4 + score * 0.4 + readiness * 0.2)
    expected_upside = ctx.get("expected_upside", 0.0)
    expected_cost = ctx.get("expected_cost", 0.0)

    return {
        "current_state": state,
        "urgency": round(urgency, 3),
        "readiness": round(readiness, 3),
        "suppression_risk": round(suppression_risk, 3),
        "expected_upside": round(expected_upside, 2),
        "expected_cost": round(expected_cost, 2),
        "confidence": round(conf, 3),
        "explanation": exp,
    }


# ── Execution State Engine ────────────────────────────────────────────

def compute_execution_state(ctx: dict[str, Any]) -> dict[str, Any]:
    mode = ctx.get("execution_mode", "manual")
    status = ctx.get("run_status", "queued")
    failure_count = ctx.get("failure_count", 0)
    confidence = ctx.get("confidence", 0.5)
    cost = ctx.get("estimated_cost", 0.0)
    cost_threshold = ctx.get("require_approval_above_cost", 75.0)

    if status == "completed":
        state, reason = "completed", "Execution finished successfully"
        rollback = False
        escalation = False
    elif failure_count >= 3:
        state, reason = "failed", f"Failed {failure_count} times"
        rollback = True
        escalation = True
    elif failure_count >= 1:
        state, reason = "recovering", f"Recovering from {failure_count} failure(s)"
        rollback = True
        escalation = False
    elif status == "blocked" or ctx.get("has_blocker", False):
        state, reason = "blocked", "Execution blocked by dependency"
        rollback = False
        escalation = True
    elif mode == "autonomous" and confidence >= 0.7 and cost <= cost_threshold:
        state, reason = "autonomous", f"Auto-executing (confidence {confidence:.2f}, cost ${cost:.0f})"
        rollback = True
        escalation = False
    elif mode in ("guarded", "autonomous") and (confidence < 0.7 or cost > cost_threshold):
        state, reason = "guarded", f"Needs approval (confidence {confidence:.2f}, cost ${cost:.0f})"
        rollback = True
        escalation = True
    elif mode == "manual":
        state, reason = "manual", "Manual execution only"
        rollback = False
        escalation = False
    else:
        state, reason = "queued", "Waiting in queue"
        rollback = False
        escalation = False

    return {
        "current_state": state,
        "transition_reason": reason,
        "rollback_eligible": rollback,
        "escalation_required": escalation,
        "failure_count": failure_count,
        "confidence": round(confidence, 3),
        "explanation": f"State '{state}': {reason}.",
    }


# ── Audience / Customer State Engine (V2) ─────────────────────────────

def compute_audience_state_v2(ctx: dict[str, Any]) -> dict[str, Any]:
    purchase_count = ctx.get("purchase_count", 0)
    ltv = ctx.get("ltv", 0.0)
    engagement_recency_days = ctx.get("engagement_recency_days", 999)
    churn_risk = ctx.get("churn_risk", 0.0)
    objection_signals = ctx.get("objection_signals", 0)
    referral_activity = ctx.get("referral_activity", 0)
    sponsor_fit = ctx.get("sponsor_fit_score", 0.0)
    content_views = ctx.get("content_views_30d", 0)
    cta_clicks = ctx.get("cta_clicks_30d", 0)

    if purchase_count >= 5 and ltv > 500 and referral_activity > 0:
        state, score = "advocate", 0.95
        nba = "Activate referral program; ask for testimonials"
    elif sponsor_fit > 0.7 and purchase_count >= 2:
        state, score = "sponsor_friendly", 0.88
        nba = "Introduce sponsor packages; media kit outreach"
    elif purchase_count >= 3 and ltv > 200:
        state, score = "high_ltv", 0.85
        nba = "Upsell premium tier; personalized offers"
    elif purchase_count >= 2:
        state, score = "repeat_buyer", 0.78
        nba = "Loyalty reward; exclusive early access"
    elif purchase_count == 1 and churn_risk > 0.5:
        state, score = "churn_risk", 0.55
        nba = "Win-back offer; satisfaction survey"
    elif purchase_count == 1:
        state, score = "bought_once", 0.65
        nba = "Post-purchase nurture; cross-sell"
    elif cta_clicks > 3 and objection_signals == 0:
        state, score = "ready_to_buy", 0.72
        nba = "Direct conversion CTA; scarcity trigger"
    elif objection_signals > 2:
        state, score = "objection_heavy", 0.42
        nba = "Address objections; case studies; social proof"
    elif content_views > 10 and cta_clicks > 0:
        state, score = "evaluating", 0.50
        nba = "Comparison content; benefits deep-dive"
    elif content_views > 3:
        state, score = "curious", 0.35
        nba = "Hook with strong value proposition"
    else:
        state, score = "unaware", 0.10
        nba = "Top-of-funnel awareness content"

    transition_probs = _audience_transitions(state, churn_risk)
    conf = min(1.0, 0.4 + score * 0.4)

    return {
        "current_state": state,
        "state_score": round(score, 3),
        "transition_likelihoods": transition_probs,
        "next_best_action": nba,
        "estimated_ltv": round(ltv, 2),
        "confidence": round(conf, 3),
        "explanation": f"Audience segment in '{state}' state (score {score:.2f}). Action: {nba}",
    }


def _audience_transitions(state: str, churn_risk: float) -> dict[str, float]:
    base = {
        "unaware": {"curious": 0.25, "stay": 0.75},
        "curious": {"evaluating": 0.30, "unaware": 0.15, "stay": 0.55},
        "evaluating": {"ready_to_buy": 0.20, "objection_heavy": 0.15, "curious": 0.10, "stay": 0.55},
        "objection_heavy": {"evaluating": 0.25, "ready_to_buy": 0.10, "stay": 0.65},
        "ready_to_buy": {"bought_once": 0.40, "evaluating": 0.10, "stay": 0.50},
        "bought_once": {"repeat_buyer": 0.25, "churn_risk": round(churn_risk, 2), "stay": round(0.75 - churn_risk, 2)},
        "repeat_buyer": {"high_ltv": 0.20, "churn_risk": 0.08, "stay": 0.72},
        "high_ltv": {"advocate": 0.15, "churn_risk": 0.05, "stay": 0.80},
        "churn_risk": {"bought_once": 0.15, "unaware": 0.20, "stay": 0.65},
        "advocate": {"sponsor_friendly": 0.10, "stay": 0.90},
        "sponsor_friendly": {"advocate": 0.05, "stay": 0.95},
    }
    return base.get(state, {"stay": 1.0})


# ── Brain Memory Consolidation ────────────────────────────────────────

def consolidate_brain_memory(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    accounts = ctx.get("accounts", [])
    offers = ctx.get("offers", [])
    suppression_history = ctx.get("suppression_history", [])
    top_content = ctx.get("top_content", [])
    recovery_incidents = ctx.get("recovery_incidents", [])

    for a in accounts:
        ppp = a.get("profit_per_post", 0)
        eng = a.get("avg_engagement", 0)
        plat = a.get("platform", "unknown")
        if ppp > 12 and eng > 0.03:
            entries.append({
                "entry_type": "winner",
                "scope_type": "account",
                "scope_id": a.get("id"),
                "platform": plat,
                "niche": a.get("niche", ""),
                "summary": f"High-performing account: ${ppp:.2f}/post, {eng:.1%} engagement on {plat}",
                "confidence": min(1.0, 0.5 + eng * 5),
                "reuse_recommendation": f"Replicate {plat} strategy in new account launches",
                "suppression_caution": None,
                "detail_json": {"profit_per_post": ppp, "avg_engagement": eng},
                "explanation": f"Account exceeds profit and engagement thresholds on {plat}",
            })
        elif ppp < 2 and eng < 0.01 and a.get("age_days", 0) > 60:
            entries.append({
                "entry_type": "loser",
                "scope_type": "account",
                "scope_id": a.get("id"),
                "platform": plat,
                "niche": a.get("niche", ""),
                "summary": f"Underperforming account: ${ppp:.2f}/post, {eng:.1%} eng on {plat}",
                "confidence": 0.65,
                "reuse_recommendation": None,
                "suppression_caution": "Consider kill-ledger review",
                "detail_json": {"profit_per_post": ppp, "avg_engagement": eng},
                "explanation": f"Below threshold after 60+ days on {plat}",
            })

    for o in offers:
        cvr = o.get("conversion_rate", 0)
        epc = o.get("epc", 0)
        if epc > 2.0 and cvr > 0.03:
            entries.append({
                "entry_type": "best_monetization_route",
                "scope_type": "offer",
                "scope_id": o.get("id"),
                "platform": None,
                "niche": o.get("niche", ""),
                "summary": f"Strong offer: EPC ${epc:.2f}, CVR {cvr:.1%}",
                "confidence": min(1.0, 0.5 + cvr * 10),
                "reuse_recommendation": "Use as primary offer in scaling accounts",
                "suppression_caution": None,
                "detail_json": {"epc": epc, "conversion_rate": cvr},
                "explanation": f"Offer exceeds EPC and CVR thresholds",
            })

    for s in suppression_history:
        entries.append({
            "entry_type": "saturated_pattern",
            "scope_type": s.get("scope_type", "content"),
            "scope_id": s.get("scope_id"),
            "platform": s.get("platform"),
            "niche": s.get("niche", ""),
            "summary": f"Suppressed: {s.get('reason', 'unknown reason')}",
            "confidence": s.get("confidence", 0.6),
            "reuse_recommendation": None,
            "suppression_caution": "Avoid replicating this pattern",
            "detail_json": s.get("detail", {}),
            "explanation": s.get("reason", ""),
        })

    for inc in recovery_incidents:
        entries.append({
            "entry_type": "common_blocker",
            "scope_type": inc.get("scope_type", "system"),
            "scope_id": inc.get("scope_id"),
            "platform": inc.get("platform"),
            "niche": None,
            "summary": f"Blocker: {inc.get('incident_type', 'unknown')}",
            "confidence": inc.get("confidence", 0.55),
            "reuse_recommendation": inc.get("fix", None),
            "suppression_caution": None,
            "detail_json": inc.get("detail", {}),
            "explanation": inc.get("explanation", ""),
        })

    if not entries:
        entries.append({
            "entry_type": "confidence_adjustment",
            "scope_type": "brand",
            "scope_id": None,
            "platform": None,
            "niche": None,
            "summary": "No strong signals for memory consolidation yet",
            "confidence": 0.30,
            "reuse_recommendation": "Accumulate more data before acting on memory",
            "suppression_caution": None,
            "detail_json": {"accounts_analyzed": len(accounts), "offers_analyzed": len(offers)},
            "explanation": "Insufficient signal for strong memory entries",
        })

    return entries
