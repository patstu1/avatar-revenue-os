"""Contribution engine — multi-touch attribution models and cross-model comparison."""
from __future__ import annotations

import math
from typing import Any

CONTRIB = "contribution"

SUPPORTED_MODELS = ["first_touch", "last_touch", "linear", "time_decay", "position_based"]

_TIME_DECAY_HALF_LIFE_DAYS = 7.0
_POSITION_FIRST_WEIGHT = 0.40
_POSITION_LAST_WEIGHT = 0.40
_POSITION_MID_WEIGHT_SHARE = 0.20
_DIVERGENCE_ALERT_THRESHOLD = 0.30


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _time_decay_weight(days_before_conversion: float) -> float:
    if days_before_conversion <= 0:
        return 1.0
    return math.pow(0.5, days_before_conversion / _TIME_DECAY_HALF_LIFE_DAYS)


def _score_touchpoints_first_touch(
    touchpoints: list[dict[str, Any]],
    total_value: float,
) -> list[dict[str, Any]]:
    if not touchpoints:
        return []
    first = touchpoints[0]
    results = []
    for tp in touchpoints:
        is_first = tp is first
        val = total_value if is_first else 0.0
        score = 1.0 if is_first else 0.0
        results.append({
            "scope_type": tp.get("scope_type", "unknown"),
            "scope_id": tp.get("scope_id"),
            "estimated_contribution_value": round(val, 2),
            "contribution_score": round(score, 4),
        })
    return results


def _score_touchpoints_last_touch(
    touchpoints: list[dict[str, Any]],
    total_value: float,
) -> list[dict[str, Any]]:
    if not touchpoints:
        return []
    last = touchpoints[-1]
    results = []
    for tp in touchpoints:
        is_last = tp is last
        val = total_value if is_last else 0.0
        score = 1.0 if is_last else 0.0
        results.append({
            "scope_type": tp.get("scope_type", "unknown"),
            "scope_id": tp.get("scope_id"),
            "estimated_contribution_value": round(val, 2),
            "contribution_score": round(score, 4),
        })
    return results


def _score_touchpoints_linear(
    touchpoints: list[dict[str, Any]],
    total_value: float,
) -> list[dict[str, Any]]:
    n = len(touchpoints)
    if n == 0:
        return []
    equal_val = total_value / n
    equal_score = 1.0 / n
    return [
        {
            "scope_type": tp.get("scope_type", "unknown"),
            "scope_id": tp.get("scope_id"),
            "estimated_contribution_value": round(equal_val, 2),
            "contribution_score": round(equal_score, 4),
        }
        for tp in touchpoints
    ]


def _score_touchpoints_time_decay(
    touchpoints: list[dict[str, Any]],
    total_value: float,
) -> list[dict[str, Any]]:
    if not touchpoints:
        return []
    weights = []
    for tp in touchpoints:
        days = float(tp.get("days_before_conversion", 0))
        weights.append(_time_decay_weight(days))
    w_sum = sum(weights) or 1.0
    results = []
    for tp, w in zip(touchpoints, weights):
        normed = w / w_sum
        results.append({
            "scope_type": tp.get("scope_type", "unknown"),
            "scope_id": tp.get("scope_id"),
            "estimated_contribution_value": round(total_value * normed, 2),
            "contribution_score": round(normed, 4),
        })
    return results


def _score_touchpoints_position_based(
    touchpoints: list[dict[str, Any]],
    total_value: float,
) -> list[dict[str, Any]]:
    n = len(touchpoints)
    if n == 0:
        return []
    if n == 1:
        return [{
            "scope_type": touchpoints[0].get("scope_type", "unknown"),
            "scope_id": touchpoints[0].get("scope_id"),
            "estimated_contribution_value": round(total_value, 2),
            "contribution_score": 1.0,
        }]
    mid_count = max(n - 2, 1)
    mid_each = _POSITION_MID_WEIGHT_SHARE / mid_count
    results = []
    for i, tp in enumerate(touchpoints):
        if i == 0:
            w = _POSITION_FIRST_WEIGHT
        elif i == n - 1:
            w = _POSITION_LAST_WEIGHT
        else:
            w = mid_each
        results.append({
            "scope_type": tp.get("scope_type", "unknown"),
            "scope_id": tp.get("scope_id"),
            "estimated_contribution_value": round(total_value * w, 2),
            "contribution_score": round(w, 4),
        })
    return results


_MODEL_FNS = {
    "first_touch": _score_touchpoints_first_touch,
    "last_touch": _score_touchpoints_last_touch,
    "linear": _score_touchpoints_linear,
    "time_decay": _score_touchpoints_time_decay,
    "position_based": _score_touchpoints_position_based,
}


def compute_contribution_reports(
    touchpoints: list[dict[str, Any]],
    attribution_models: list[str],
) -> list[dict[str, Any]]:
    """Compute contribution for each scope across one or more attribution models.

    Parameters
    ----------
    touchpoints:
        Ordered list (oldest first) of touchpoint dicts. Expected keys:
        scope_type (str), scope_id (str|None), value (float),
        days_before_conversion (float, 0 = conversion moment).
    attribution_models:
        Subset of SUPPORTED_MODELS.

    Returns
    -------
    list[dict] with one entry per model x scope, including estimated_contribution_value,
    contribution_score, confidence, caveats, explanation.
    """
    models_to_run = [m for m in attribution_models if m in _MODEL_FNS]
    if not models_to_run:
        models_to_run = SUPPORTED_MODELS

    total_value = sum(float(tp.get("value", 0)) for tp in touchpoints)
    n = len(touchpoints)

    reports: list[dict[str, Any]] = []
    for model_name in models_to_run:
        fn = _MODEL_FNS[model_name]
        scored = fn(touchpoints, total_value)

        caveats: list[str] = []
        if n < 3:
            caveats.append("Fewer than 3 touchpoints — attribution unreliable.")
        if model_name in ("first_touch", "last_touch") and n > 5:
            caveats.append(
                f"{model_name} ignores {n - 1} of {n} touchpoints. "
                "Consider multi-touch models."
            )

        base_conf = 0.55 + min(0.30, n * 0.03)
        if caveats:
            base_conf -= 0.10

        for row in scored:
            reports.append({
                "attribution_model": model_name,
                "scope_type": row["scope_type"],
                "scope_id": row["scope_id"],
                "estimated_contribution_value": row["estimated_contribution_value"],
                "contribution_score": row["contribution_score"],
                "confidence": round(_clamp(base_conf), 4),
                "caveats": caveats,
                "explanation": (
                    f"Model {model_name}: scope {row['scope_type']}:{row['scope_id']} "
                    f"attributed {row['contribution_score']:.2%} of ${total_value:.2f} "
                    f"({n} touchpoints)."
                ),
                CONTRIB: True,
            })

    return reports


def compare_attribution_models(
    reports: list[dict[str, Any]],
) -> dict[str, Any]:
    """Cross-model comparison to detect where last-click misleads.

    Parameters
    ----------
    reports:
        Output of compute_contribution_reports.

    Returns
    -------
    dict with divergences list, misleading_last_click_scopes, recommendations,
    confidence, explanation.
    """
    by_scope: dict[str, dict[str, float]] = {}
    for r in reports:
        key = f"{r.get('scope_type', '')}:{r.get('scope_id', '')}"
        model = r.get("attribution_model", "")
        by_scope.setdefault(key, {})[model] = r.get("contribution_score", 0)

    divergences: list[dict[str, Any]] = []
    misleading_scopes: list[str] = []

    for scope_key, model_scores in by_scope.items():
        last_touch_score = model_scores.get("last_touch", 0)
        time_decay_score = model_scores.get("time_decay", 0)

        if time_decay_score > 0:
            divergence = abs(last_touch_score - time_decay_score) / max(time_decay_score, 0.001)
        elif last_touch_score > 0:
            divergence = 1.0
        else:
            divergence = 0.0

        is_misleading = divergence > _DIVERGENCE_ALERT_THRESHOLD

        divergences.append({
            "scope": scope_key,
            "last_touch_score": round(last_touch_score, 4),
            "time_decay_score": round(time_decay_score, 4),
            "divergence_pct": round(divergence, 4),
            "misleading_last_click": is_misleading,
        })

        if is_misleading:
            misleading_scopes.append(scope_key)

    recommendations: list[str] = []
    if misleading_scopes:
        recommendations.append(
            f"Last-click significantly diverges from time-decay for "
            f"{len(misleading_scopes)} scope(s): {', '.join(misleading_scopes[:5])}. "
            "Use time_decay or position_based for budget decisions."
        )
    else:
        recommendations.append(
            "Attribution models are broadly aligned. Last-click is acceptable "
            "for operational use, though time_decay is recommended for strategic decisions."
        )

    total_scopes = len(by_scope)
    misleading_ratio = len(misleading_scopes) / max(total_scopes, 1)
    conf = _clamp(0.70 - misleading_ratio * 0.3)

    return {
        "divergences": divergences,
        "misleading_last_click_scopes": misleading_scopes,
        "recommendations": recommendations,
        "confidence": round(conf, 4),
        "explanation": (
            f"Compared {len(by_scope)} scopes across models. "
            f"{len(misleading_scopes)} scope(s) show >30% last-click divergence."
        ),
        CONTRIB: True,
    }
