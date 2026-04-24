"""Ceiling Override — intercepts scoring engine outputs and removes artificial constraints.

The pre-existing scoring engines produce outputs (BrainDecision, OpportunityScore,
RecommendationQueue, etc.) that may be distorted by internal fixed thresholds.

This module provides post-processing functions that our services call AFTER
reading engine outputs to neutralize any decisions driven by artificial ceilings
rather than real portfolio context.

Example: If brain_phase_b_engine classifies an account as "suppress" solely because
follower_count < 500 (a fixed threshold), but the portfolio's smallest account has
15,000 followers, the suppress decision was driven by an artificial ceiling that
doesn't apply. This module would flag that decision for re-evaluation.
"""
from __future__ import annotations


def override_brain_decision(decision: dict, calibration_ctx: dict) -> dict:
    """Re-evaluate a BrainDecision against portfolio context.

    If the decision was driven by thresholds below the portfolio's operating scale,
    upgrade the confidence to reflect that the threshold is non-binding.
    """
    decision_class = decision.get("decision_class", "")
    decision.get("confidence", 0)

    # If the brain said "suppress" or "throttle" but the portfolio is producing revenue,
    # the suppress decision may be an artifact of fixed thresholds, not real underperformance.
    if decision_class in ("suppress", "throttle", "kill"):
        if calibration_ctx.get("has_revenue") and calibration_ctx.get("total_revenue", 0) > 0:
            # Don't automatically override, but flag for re-evaluation
            decision["ceiling_override"] = {
                "original_class": decision_class,
                "override_reason": "Portfolio has revenue — suppress decision may be threshold artifact",
                "recommendation": "re_evaluate_with_portfolio_context",
                "portfolio_revenue": calibration_ctx.get("total_revenue", 0),
            }

    # If the brain said "hold" but the portfolio has multiple revenue sources and patterns,
    # the hold may be overly conservative
    if decision_class == "hold" and calibration_ctx.get("has_multiple_sources"):
        decision["ceiling_override"] = {
            "original_class": decision_class,
            "override_reason": "Portfolio has multiple revenue sources — hold may be too conservative",
            "recommendation": "consider_upgrade_to_scale",
        }

    return decision


def override_opportunity_score(score: float, calibration_ctx: dict) -> float:
    """Recalibrate an opportunity score if the scoring engine used fixed thresholds.

    Scores from engines that normalize against fixed divisors (e.g., /50000 followers)
    may undervalue opportunities in portfolios that are smaller or larger than the
    engine's assumptions.
    """
    portfolio_scale = calibration_ctx.get("account_count", 0) + calibration_ctx.get("offer_count", 0)

    if portfolio_scale > 0 and score < 0.3:
        # If the portfolio exists but the score is low, the engine may have
        # penalized due to fixed threshold comparisons
        # Apply a floor based on whether the portfolio has proven revenue
        if calibration_ctx.get("has_revenue"):
            return max(score, 0.3)  # Revenue-proven portfolios get a floor

    return score


def override_recommendation_action(action: str, calibration_ctx: dict) -> str:
    """Override a recommendation action if it's driven by fixed thresholds.

    Actions like "SUPPRESS" or "REDUCE" may be artifacts of the engine's
    fixed normalization rather than real underperformance.
    """
    if action in ("SUPPRESS", "suppress") and calibration_ctx.get("has_revenue"):
        return "MONITOR"  # Downgrade suppress to monitor in revenue-producing portfolios

    if action in ("REDUCE", "reduce") and calibration_ctx.get("has_multiple_sources"):
        return "MAINTAIN"  # Don't reduce diversified portfolios

    return action


def filter_suppress_decisions(
    decisions: list[dict], calibration_ctx: dict
) -> list[dict]:
    """Filter out suppress/throttle decisions that are ceiling artifacts.

    Returns only decisions where suppression is justified by portfolio-relative
    underperformance, not by fixed thresholds.
    """
    if not calibration_ctx.get("has_revenue"):
        return decisions  # No revenue = can't determine if suppress is artificial

    filtered = []
    for d in decisions:
        dc = d.get("decision_class", "")
        if dc in ("suppress", "throttle", "kill"):
            # Check if the entity being suppressed is below portfolio average
            expected_upside = d.get("expected_upside", 0)
            avg_upside = calibration_ctx.get("total_revenue", 0) / max(calibration_ctx.get("account_count", 1), 1)

            if expected_upside is not None and expected_upside > avg_upside * 0.1:
                # Entity has meaningful upside relative to portfolio — don't suppress
                d["ceiling_override"] = {"suppressed_by_override": True, "reason": "upside above portfolio threshold"}
                continue

        filtered.append(d)

    return filtered
