"""Kill ledger engine — underperformer identification and hindsight review
(pure functions, no I/O, no SQLAlchemy)."""
from __future__ import annotations

from typing import Any

KILL_LEDGER = "kill_ledger_engine"

# ---------------------------------------------------------------------------
# Kill scopes and default thresholds
# ---------------------------------------------------------------------------

KILL_SCOPES: list[str] = [
    "topic_cluster",
    "offer",
    "content_family",
    "account",
    "platform_mix",
    "audience_segment",
    "funnel",
    "paid_campaign",
    "sponsor_strategy",
]

_DEFAULT_THRESHOLDS: dict[str, dict[str, float]] = {
    "topic_cluster": {"min_engagement_rate": 0.02, "min_revenue": 50.0, "min_impressions": 1000},
    "offer": {"min_conversion_rate": 0.01, "min_revenue": 100.0, "min_aov": 10.0},
    "content_family": {"min_engagement_rate": 0.015, "min_revenue": 25.0, "min_impressions": 500},
    "account": {"min_follower_growth_rate": 0.005, "min_engagement_rate": 0.01, "min_revenue": 50.0},
    "platform_mix": {"min_revenue_share": 0.05, "min_engagement_rate": 0.01},
    "audience_segment": {"min_conversion_rate": 0.005, "min_ltv": 5.0},
    "funnel": {"min_conversion_rate": 0.01, "min_revenue": 50.0, "min_throughput": 10},
    "paid_campaign": {"min_roas": 1.0, "min_conversions": 5, "min_ctr": 0.005},
    "sponsor_strategy": {"min_revenue": 200.0, "min_renewal_rate": 0.30},
}

# ---------------------------------------------------------------------------
# Replacement recommendation templates
# ---------------------------------------------------------------------------

_REPLACEMENT_TEMPLATES: dict[str, str] = {
    "topic_cluster": "Reallocate content effort to the next highest-engagement topic cluster",
    "offer": "Replace with a higher-converting offer or repackage at a different price point",
    "content_family": "Retire this content family and redirect resources to proven formats",
    "account": "Consolidate audience into remaining accounts or pivot niche positioning",
    "platform_mix": "Shift posting cadence and budget away from this platform toward higher-ROI channels",
    "audience_segment": "Merge low-value segment into a broader cohort or stop targeting entirely",
    "funnel": "Redesign the funnel with a different entry point or simplify the conversion path",
    "paid_campaign": "Pause spend immediately; reallocate budget to organic winners or better-performing campaigns",
    "sponsor_strategy": "Renegotiate terms or replace sponsor with a better-fit brand partnership",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _merge_thresholds(user_thresholds: dict, scope_type: str) -> dict[str, float]:
    """Merge user-provided thresholds with defaults for a given scope."""
    base = dict(_DEFAULT_THRESHOLDS.get(scope_type, {}))
    scope_overrides = user_thresholds.get(scope_type, {})
    if isinstance(scope_overrides, dict):
        base.update(scope_overrides)
    for k in list(user_thresholds.keys()):
        if k.startswith("min_") or k.startswith("max_"):
            base.setdefault(k, user_thresholds[k])
    return base


def _failure_count(candidate: dict, thresholds: dict[str, float]) -> tuple[int, int, list[str]]:
    """Count how many threshold checks the candidate fails.

    Returns (failed, total_checked, list of failure descriptions).
    """
    failed = 0
    total = 0
    failures: list[str] = []
    for key, threshold_val in thresholds.items():
        metric_key = key.replace("min_", "").replace("max_", "")
        actual = candidate.get(metric_key)
        if actual is None:
            continue
        actual = float(actual)
        total += 1
        if key.startswith("min_") and actual < float(threshold_val):
            failed += 1
            failures.append(f"{metric_key} {actual:.4f} < threshold {float(threshold_val):.4f}")
        elif key.startswith("max_") and actual > float(threshold_val):
            failed += 1
            failures.append(f"{metric_key} {actual:.4f} > threshold {float(threshold_val):.4f}")
    return failed, total, failures


# ---------------------------------------------------------------------------
# Engine 1 — Kill candidate evaluator
# ---------------------------------------------------------------------------

def evaluate_kill_candidates(
    underperformers: list[dict],
    thresholds: dict,
) -> list[dict[str, Any]]:
    """Evaluate a list of underperforming items and recommend kills.

    Parameters
    ----------
    underperformers:
        List of dicts, each with at minimum: scope_type (str from KILL_SCOPES),
        scope_id (str/uuid), plus metric fields matching threshold keys
        (e.g. engagement_rate, revenue, conversion_rate, impressions, roas, etc.).
        Optional: name (str), notes (str).
    thresholds:
        Dict of overrides. Can be keyed by scope_type for scope-specific overrides
        (e.g. {"offer": {"min_revenue": 200}}) or flat min_/max_ keys applied globally.

    Returns
    -------
    list[dict] — one entry per kill candidate: scope_type, scope_id, kill_reason,
    performance_snapshot, replacement_recommendation, confidence, explanation,
    KILL_LEDGER marker.
    """
    results: list[dict[str, Any]] = []

    for candidate in underperformers:
        scope_type = str(candidate.get("scope_type", "")).strip()
        scope_id = str(candidate.get("scope_id", ""))
        name = str(candidate.get("name", scope_id))

        if scope_type not in KILL_SCOPES:
            continue

        merged = _merge_thresholds(thresholds, scope_type)
        failed, total_checked, failures = _failure_count(candidate, merged)

        if failed == 0 or total_checked == 0:
            continue

        fail_ratio = failed / total_checked

        # ------------------------------------------------------------------ performance snapshot
        snapshot_keys = [
            "engagement_rate", "revenue", "impressions", "conversion_rate",
            "aov", "follower_growth_rate", "revenue_share", "ltv",
            "throughput", "roas", "conversions", "ctr", "renewal_rate",
        ]
        performance_snapshot: dict[str, Any] = {}
        for k in snapshot_keys:
            if k in candidate:
                performance_snapshot[k] = candidate[k]
        if candidate.get("name"):
            performance_snapshot["name"] = str(candidate["name"])
        performance_snapshot["thresholds_applied"] = merged
        performance_snapshot["failures"] = failures

        # ------------------------------------------------------------------ kill reason
        kill_reason = (
            f"{scope_type.replace('_', ' ').title()} '{name}' failed {failed}/{total_checked} "
            f"threshold checks: {'; '.join(failures[:3])}"
            + (f" (and {len(failures) - 3} more)" if len(failures) > 3 else "")
        )

        # ------------------------------------------------------------------ replacement
        base_rec = _REPLACEMENT_TEMPLATES.get(scope_type, f"Replace or retire this {scope_type}")
        replacement_recommendation: dict[str, Any] = {
            "action": base_rec,
            "scope_type": scope_type,
            "urgency": "high" if fail_ratio >= 0.75 else ("medium" if fail_ratio >= 0.50 else "low"),
        }

        # ------------------------------------------------------------------ confidence
        confidence = round(_clamp(
            0.30
            + fail_ratio * 0.40
            + _clamp(total_checked / 5.0) * 0.20
            + 0.10
        ), 3)

        # ------------------------------------------------------------------ explanation
        explanation = (
            f"Kill candidate: {scope_type} '{name}' (id={scope_id}). "
            f"Failed {failed} of {total_checked} checks (ratio {fail_ratio:.2f}). "
            f"Key failures: {'; '.join(failures[:2])}. "
            f"Recommendation: {base_rec}. Confidence {confidence:.2f}."
        )

        results.append({
            "scope_type": scope_type,
            "scope_id": scope_id,
            "kill_reason": kill_reason,
            "performance_snapshot": performance_snapshot,
            "replacement_recommendation": replacement_recommendation,
            "confidence": confidence,
            "explanation": explanation,
            KILL_LEDGER: True,
        })

    results.sort(key=lambda r: r["confidence"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Engine 2 — Kill hindsight review
# ---------------------------------------------------------------------------

def review_kill_hindsight(
    kill_entry: dict,
    post_kill_data: dict,
) -> dict[str, Any]:
    """Compare pre-kill performance with post-kill trajectory to assess correctness.

    Parameters
    ----------
    kill_entry:
        Dict with: scope_type, scope_id, kill_reason, performance_snapshot (dict
        containing pre-kill metric values), killed_at (str/datetime).
    post_kill_data:
        Dict with post-kill metrics matching snapshot keys, plus optional:
        replacement_performance (dict with same metric keys as the killed item),
        overall_brand_revenue_delta (float, positive = improved),
        time_since_kill_days (int).

    Returns
    -------
    dict with hindsight_outcome, was_correct_kill, explanation, confidence,
    KILL_LEDGER marker.
    """
    snapshot = kill_entry.get("performance_snapshot", {})
    scope_type = str(kill_entry.get("scope_type", "unknown"))
    scope_id = str(kill_entry.get("scope_id", ""))

    replacement = post_kill_data.get("replacement_performance", {})
    revenue_delta = float(post_kill_data.get("overall_brand_revenue_delta", 0))
    days_since = int(post_kill_data.get("time_since_kill_days", 0))

    # ------------------------------------------------------------------ compare metrics
    improved_metrics: list[str] = []
    worsened_metrics: list[str] = []
    neutral_metrics: list[str] = []

    comparison_keys = [
        "revenue", "engagement_rate", "conversion_rate", "roas",
        "impressions", "ltv", "throughput", "ctr",
    ]

    for key in comparison_keys:
        pre_val = snapshot.get(key)
        post_val = post_kill_data.get(key)
        if pre_val is None or post_val is None:
            continue

        pre_val = float(pre_val)
        post_val = float(post_val)

        if pre_val == 0 and post_val == 0:
            neutral_metrics.append(key)
        elif post_val > pre_val * 1.05:
            improved_metrics.append(key)
        elif post_val < pre_val * 0.95:
            worsened_metrics.append(key)
        else:
            neutral_metrics.append(key)

    # Replacement outperformance check
    replacement_wins = 0
    replacement_total = 0
    for key in comparison_keys:
        pre_val = snapshot.get(key)
        rep_val = replacement.get(key)
        if pre_val is None or rep_val is None:
            continue
        replacement_total += 1
        if float(rep_val) > float(pre_val):
            replacement_wins += 1

    # ------------------------------------------------------------------ determine correctness
    total_compared = len(improved_metrics) + len(worsened_metrics) + len(neutral_metrics)

    if total_compared == 0 and replacement_total == 0:
        was_correct_kill = None
        hindsight_outcome = (
            f"Insufficient data to evaluate kill of {scope_type} '{scope_id}'. "
            f"No comparable metrics available after {days_since} days."
        )
        confidence = 0.20
    else:
        positive_signals = len(improved_metrics)
        negative_signals = len(worsened_metrics)

        if replacement_total > 0:
            replacement_ratio = replacement_wins / replacement_total
            if replacement_ratio >= 0.50:
                positive_signals += 2
            else:
                negative_signals += 1

        if revenue_delta > 0:
            positive_signals += 1
        elif revenue_delta < 0:
            negative_signals += 1

        if positive_signals > negative_signals:
            was_correct_kill = True
            hindsight_outcome = (
                f"Kill of {scope_type} '{scope_id}' was CORRECT. "
                f"{len(improved_metrics)} metric(s) improved, {len(worsened_metrics)} worsened. "
                f"Revenue delta: ${revenue_delta:+,.2f}."
            )
        elif negative_signals > positive_signals:
            was_correct_kill = False
            hindsight_outcome = (
                f"Kill of {scope_type} '{scope_id}' was INCORRECT. "
                f"{len(worsened_metrics)} metric(s) worsened, only {len(improved_metrics)} improved. "
                f"Revenue delta: ${revenue_delta:+,.2f}."
            )
        else:
            was_correct_kill = True
            hindsight_outcome = (
                f"Kill of {scope_type} '{scope_id}' was NEUTRAL-TO-CORRECT. "
                f"Metrics split evenly ({len(improved_metrics)} improved, {len(worsened_metrics)} worsened). "
                f"Revenue delta: ${revenue_delta:+,.2f}. No negative impact detected."
            )

        # ------------------------------------------------------------------ confidence
        data_depth = _clamp(total_compared / 5.0) * 0.25
        time_signal = _clamp(days_since / 60.0) * 0.20
        clarity = _clamp(abs(positive_signals - negative_signals) / max(1, total_compared)) * 0.25
        confidence = round(_clamp(0.30 + data_depth + time_signal + clarity), 3)

    # ------------------------------------------------------------------ explanation
    explanation = (
        f"Hindsight review for {scope_type} '{scope_id}' "
        f"({days_since} days post-kill). "
        f"Improved: {improved_metrics or ['none']}. "
        f"Worsened: {worsened_metrics or ['none']}. "
        f"Neutral: {neutral_metrics or ['none']}. "
        f"Replacement outperformed on {replacement_wins}/{replacement_total} metrics. "
        f"Overall brand revenue delta: ${revenue_delta:+,.2f}. "
        f"Verdict: {'correct' if was_correct_kill is True else ('incorrect' if was_correct_kill is False else 'insufficient data')}."
    )

    return {
        "hindsight_outcome": hindsight_outcome,
        "was_correct_kill": was_correct_kill,
        "explanation": explanation,
        "confidence": confidence,
        KILL_LEDGER: True,
    }
