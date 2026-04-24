"""Experiment decision engine — prioritise A/B tests, evaluate outcomes, promote or suppress."""

from __future__ import annotations

from typing import Any

EXP_DEC = "experiment_decision"

_PROMOTION_UPLIFT_THRESHOLD = 0.05
_PROMOTION_CONFIDENCE_THRESHOLD = 0.80
_SUPPRESSION_UPLIFT_THRESHOLD = -0.03
_SUPPRESSION_STALE_DAYS = 30
_MIN_ALLOCATION = 0.05
_MAX_ALLOCATION = 0.30
_REDUNDANCY_WINDOW_DAYS = 30


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _confidence_gap_weight(gap: float) -> float:
    """Higher gap = more value in running the test."""
    return _clamp(gap * 1.4, 0.0, 1.0)


def _is_redundant(exp: dict, others: list[dict]) -> bool:
    """Same scope+type within the redundancy window is considered redundant."""
    scope_type = exp.get("target_scope_type", "")
    scope_id = exp.get("target_scope_id")
    exp_type = exp.get("experiment_type", "")
    age_days = exp.get("age_days", 0)

    for o in others:
        if o is exp:
            continue
        if (
            o.get("target_scope_type") == scope_type
            and o.get("target_scope_id") == scope_id
            and o.get("experiment_type") == exp_type
            and o.get("age_days", 999) < _REDUNDANCY_WINDOW_DAYS
            and age_days >= o.get("age_days", 999)
        ):
            return True
    return False


def apply_prior_scope_signals(
    experiments: list[dict[str, Any]],
    prior_scope_signals: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Adjust expected_upside on experiment dicts using last-run outcome signals (same scope).

    Returns (mutated experiments list, influence summary dict).
    """
    if not prior_scope_signals:
        return experiments, {"signals_applied": 0, "by_scope": []}

    def _key(e: dict[str, Any]) -> tuple[str, str | None]:
        return (
            str(e.get("target_scope_type", "")),
            str(e.get("target_scope_id")) if e.get("target_scope_id") else None,
        )

    applied: list[dict[str, Any]] = []
    count = 0
    for exp in experiments:
        for sig in prior_scope_signals:
            st = str(sig.get("target_scope_type", ""))
            sid = str(sig.get("target_scope_id")) if sig.get("target_scope_id") else None
            if _key(exp) != (st, sid):
                continue
            ot = str(sig.get("outcome_type", ""))
            uplift = float(sig.get("observed_uplift", 0.0))
            base = float(exp.get("expected_upside", 0.0))
            if ot == "promote":
                exp["expected_upside"] = round(_clamp(base + 0.06 + max(0.0, uplift) * 0.15), 4)
            elif ot == "suppress":
                exp["expected_upside"] = round(_clamp(base - 0.12 + min(0.0, uplift) * 0.1), 4)
            elif ot in ("continue", "inconclusive"):
                exp["expected_upside"] = round(_clamp(base + 0.02), 4)
            applied.append(
                {"scope": f"{st}:{sid}", "outcome_type": ot, "delta_expected_upside": exp["expected_upside"] - base}
            )
            count += 1
            break

    return experiments, {"signals_applied": count, "by_scope": applied}


def prioritize_experiment_candidates(
    experiments: list[dict[str, Any]],
    brand_context: dict[str, Any],
) -> list[dict[str, Any]]:
    """Score and rank experiment candidates.

    Parameters
    ----------
    experiments:
        Each dict should have: experiment_type, target_scope_type,
        target_scope_id (optional), hypothesis, expected_upside (0-1),
        confidence_gap (0-1), age_days (int, 0 = new).
    brand_context:
        Keys: brand_id, total_traffic (int), risk_tolerance (0-1, default 0.5).

    Returns
    -------
    list[dict] sorted descending by priority_score, redundant entries removed.
    """
    total_traffic = max(1, brand_context.get("total_traffic", 1000))
    risk_tolerance = _clamp(brand_context.get("risk_tolerance", 0.5))

    scored: list[dict[str, Any]] = []
    for exp in experiments:
        if _is_redundant(exp, experiments):
            continue

        expected_upside = _clamp(float(exp.get("expected_upside", 0.0)))
        confidence_gap = _clamp(float(exp.get("confidence_gap", 0.0)))
        gap_w = _confidence_gap_weight(confidence_gap)

        priority = _clamp(expected_upside * 0.55 + gap_w * 0.35 + risk_tolerance * 0.10)

        raw_alloc = _MIN_ALLOCATION + priority * (_MAX_ALLOCATION - _MIN_ALLOCATION)
        allocation = round(_clamp(raw_alloc, _MIN_ALLOCATION, _MAX_ALLOCATION), 3)

        promotion_rule = {
            "min_uplift": _PROMOTION_UPLIFT_THRESHOLD,
            "min_confidence": _PROMOTION_CONFIDENCE_THRESHOLD,
            "auto_promote": priority > 0.7,
        }
        suppression_rule = {
            "max_negative_uplift": _SUPPRESSION_UPLIFT_THRESHOLD,
            "stale_days": _SUPPRESSION_STALE_DAYS,
        }

        conf = _clamp(0.50 + expected_upside * 0.25 + (1 - confidence_gap) * 0.20)

        scored.append(
            {
                "experiment_type": exp.get("experiment_type", "unknown"),
                "target_scope_type": exp.get("target_scope_type", "unknown"),
                "target_scope_id": exp.get("target_scope_id"),
                "hypothesis": exp.get("hypothesis", ""),
                "expected_upside": round(expected_upside, 4),
                "confidence_gap": round(confidence_gap, 4),
                "priority_score": round(priority, 4),
                "recommended_allocation": allocation,
                "promotion_rule": promotion_rule,
                "suppression_rule": suppression_rule,
                "explanation": (
                    f"Priority {priority:.3f} from upside {expected_upside:.2f} "
                    f"(wt 0.55) + gap weight {gap_w:.2f} (wt 0.35) + "
                    f"risk tolerance {risk_tolerance:.2f} (wt 0.10). "
                    f"Allocating {allocation:.1%} of {total_traffic} traffic."
                ),
                "confidence": round(conf, 4),
                EXP_DEC: True,
            }
        )

    scored.sort(key=lambda r: r["priority_score"], reverse=True)
    return scored


def evaluate_experiment_outcome(
    experiment: dict[str, Any],
    observed_data: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate results of a running experiment and recommend action.

    Parameters
    ----------
    experiment:
        The original experiment dict (must include experiment_type).
    observed_data:
        Keys: variants (list[dict] with variant_id, conversion_rate, sample_size),
        days_running (int), baseline_conversion_rate (float).

    Returns
    -------
    dict with outcome_type, winner, losers, confidence, uplift, action, explanation.
    """
    variants = observed_data.get("variants", [])
    days_running = int(observed_data.get("days_running", 0))
    baseline_cr = float(observed_data.get("baseline_conversion_rate", 0.0))

    if not variants:
        return {
            "outcome_type": "inconclusive",
            "winner_variant_id": None,
            "loser_variant_ids": [],
            "confidence": 0.0,
            "observed_uplift": 0.0,
            "recommended_next_action": "collect_more_data",
            "explanation": "No variant data provided.",
            EXP_DEC: True,
        }

    best = max(variants, key=lambda v: float(v.get("conversion_rate", 0)))
    worst = min(variants, key=lambda v: float(v.get("conversion_rate", 0)))

    best_cr = float(best.get("conversion_rate", 0))
    worst_cr = float(worst.get("conversion_rate", 0))
    best_n = int(best.get("sample_size", 0))

    if baseline_cr > 0:
        uplift = (best_cr - baseline_cr) / baseline_cr
    elif worst_cr > 0:
        uplift = (best_cr - worst_cr) / worst_cr
    else:
        uplift = 0.0

    sample_factor = _clamp(best_n / 500, 0.3, 1.0)
    spread = abs(best_cr - worst_cr) / max(best_cr, 0.001)
    raw_conf = _clamp(0.50 + spread * 0.35 + sample_factor * 0.15)

    losers = [v.get("variant_id") for v in variants if v.get("variant_id") != best.get("variant_id")]

    if uplift >= _PROMOTION_UPLIFT_THRESHOLD and raw_conf >= _PROMOTION_CONFIDENCE_THRESHOLD:
        outcome = "promote"
        action = f"Roll out variant {best.get('variant_id')} to 100% traffic."
    elif uplift <= _SUPPRESSION_UPLIFT_THRESHOLD:
        outcome = "suppress"
        action = f"Kill test — negative uplift {uplift:.2%}. Revert to control."
    elif days_running > _SUPPRESSION_STALE_DAYS and raw_conf < _PROMOTION_CONFIDENCE_THRESHOLD:
        outcome = "suppress"
        action = f"Stale after {days_running}d with no clear signal. Shut down."
    elif raw_conf >= 0.6:
        outcome = "continue"
        action = "Continue collecting data toward promotion threshold."
    else:
        outcome = "inconclusive"
        action = "Increase sample size or extend run."

    explanation = (
        f"Best variant {best.get('variant_id')} at CR {best_cr:.4f} vs "
        f"baseline {baseline_cr:.4f} = {uplift:+.2%} uplift. "
        f"Confidence {raw_conf:.3f} after {days_running}d, "
        f"{best_n} samples. Decision: {outcome}."
    )

    return {
        "outcome_type": outcome,
        "winner_variant_id": best.get("variant_id"),
        "loser_variant_ids": losers,
        "confidence": round(_clamp(raw_conf), 4),
        "observed_uplift": round(uplift, 6),
        "recommended_next_action": action,
        "explanation": explanation,
        EXP_DEC: True,
    }
