"""Promote-Winner Engine — creation, assignment, winner detection, promotion, decay.

Pure functions. No I/O.
"""
from __future__ import annotations

import math
from typing import Any

EXPERIMENT_TYPES = [
    "hook", "content_form", "cta_type", "offer_angle",
    "avatar_vs_non_avatar", "faceless_vs_face_forward",
    "short_vs_long", "trust_vs_fast_scroll",
    "posting_window", "monetization_path", "account_role_strategy",
]

MIN_DEFAULT_SAMPLE = 30
DEFAULT_CONFIDENCE = 0.90


def create_experiment(
    tested_variable: str,
    variant_configs: list[dict[str, Any]],
    *,
    hypothesis: str = "",
    primary_metric: str = "engagement_rate",
    min_sample_size: int = MIN_DEFAULT_SAMPLE,
    confidence_threshold: float = DEFAULT_CONFIDENCE,
    platform: str | None = None,
    niche: str | None = None,
) -> dict[str, Any]:
    if tested_variable not in EXPERIMENT_TYPES:
        tested_variable = "custom"
    if len(variant_configs) < 2:
        raise ValueError("At least 2 variants required")
    variants = []
    for i, vc in enumerate(variant_configs):
        variants.append({
            "variant_name": vc.get("name", f"variant_{i}"),
            "variant_config": vc,
            "is_control": i == 0,
        })
    return {
        "tested_variable": tested_variable,
        "hypothesis": hypothesis or f"Testing {tested_variable} variants",
        "primary_metric": primary_metric,
        "min_sample_size": min_sample_size,
        "confidence_threshold": confidence_threshold,
        "platform": platform,
        "niche": niche,
        "variants": variants,
        "status": "active",
    }


def assign_variant(
    variants: list[dict[str, Any]],
    assignment_key: str,
) -> dict[str, Any]:
    """Deterministic-ish assignment based on key hash for reproducibility."""
    active = [v for v in variants if v.get("is_active", True)]
    if not active:
        return variants[0] if variants else {}
    idx = hash(assignment_key) % len(active)
    return active[idx]


def detect_winner(
    variants: list[dict[str, Any]],
    min_sample_size: int = MIN_DEFAULT_SAMPLE,
    confidence_threshold: float = DEFAULT_CONFIDENCE,
) -> dict[str, Any]:
    """Determine if there's a statistically meaningful winner."""
    if len(variants) < 2:
        return {"status": "insufficient_variants", "winner": None, "losers": []}

    sufficient = [v for v in variants if v.get("sample_count", 0) >= min_sample_size]
    if len(sufficient) < 2:
        total = sum(v.get("sample_count", 0) for v in variants)
        needed = min_sample_size * 2
        return {
            "status": "insufficient_sample",
            "winner": None,
            "losers": [],
            "total_samples": total,
            "needed": needed,
            "progress_pct": round(min(100, total / max(1, needed) * 100), 1),
        }

    sorted_v = sorted(sufficient, key=lambda v: -v.get("primary_metric_value", 0))
    best = sorted_v[0]
    second = sorted_v[1]

    best_val = best.get("primary_metric_value", 0)
    second_val = second.get("primary_metric_value", 0)
    best_n = max(1, best.get("sample_count", 1))
    second_n = max(1, second.get("sample_count", 1))

    if best_val <= 0 and second_val <= 0:
        return {"status": "no_signal", "winner": None, "losers": []}

    margin = (best_val - second_val) / max(abs(second_val), 0.001)
    se = math.sqrt((best_val * (1 - min(best_val, 1))) / best_n + (second_val * (1 - min(second_val, 1))) / second_n) if best_val < 1 and second_val < 1 else 0.01
    z = (best_val - second_val) / max(se, 0.0001)
    confidence = min(0.999, 1 - math.exp(-0.5 * z * z)) if z > 0 else 0.0

    if confidence >= confidence_threshold:
        losers = [v for v in sorted_v[1:]]
        return {
            "status": "winner_found",
            "winner": best,
            "losers": losers,
            "win_margin": round(margin, 4),
            "confidence": round(confidence, 4),
        }

    return {
        "status": "inconclusive",
        "winner": None,
        "losers": [],
        "confidence": round(confidence, 4),
        "margin": round(margin, 4),
    }


def build_promotion_rules(
    experiment: dict[str, Any],
    winner: dict[str, Any],
    win_margin: float,
    confidence: float,
) -> list[dict[str, Any]]:
    """Generate PromotedWinnerRule entries from a winner declaration."""
    rules = []
    tested_var = experiment.get("tested_variable", "")
    wconfig = winner.get("variant_config") or {}
    wname = winner.get("variant_name", "unknown")
    platform = experiment.get("platform") or experiment.get("target_platform")
    boost = round(min(0.5, win_margin * confidence), 3)

    rules.append({
        "rule_type": f"default_{tested_var}",
        "rule_key": wname,
        "rule_value": wconfig,
        "target_platform": platform,
        "weight_boost": boost,
        "explanation": f"Promoted {wname} as default {tested_var} — margin {win_margin:.1%}, confidence {confidence:.1%}",
    })

    if tested_var in ("hook", "cta_type", "offer_angle", "content_form"):
        rules.append({
            "rule_type": "brief_injection",
            "rule_key": f"preferred_{tested_var}",
            "rule_value": {"value": wname, "config": wconfig},
            "target_platform": platform,
            "weight_boost": boost,
            "explanation": f"Inject {wname} as preferred {tested_var} in content briefs",
        })

    if tested_var == "monetization_path":
        rules.append({
            "rule_type": "monetization_default",
            "rule_key": "preferred_monetization",
            "rule_value": {"value": wname, "config": wconfig},
            "target_platform": platform,
            "weight_boost": boost,
            "explanation": f"Promote {wname} as default monetization path",
        })

    return rules


def build_suppression_rules(
    experiment: dict[str, Any],
    losers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Generate suppression entries for losers."""
    rules = []
    tested_var = experiment.get("tested_variable", "")
    for loser in losers:
        lname = loser.get("variant_name", "unknown")
        rules.append({
            "rule_type": f"suppress_{tested_var}",
            "rule_key": lname,
            "target_platform": experiment.get("platform") or experiment.get("target_platform"),
            "explanation": f"Suppress {lname} — lost in {tested_var} experiment",
        })
    return rules


def check_decay_retest(
    winner_age_days: int,
    original_confidence: float,
    current_metric_value: float,
    original_metric_value: float,
) -> dict[str, Any]:
    """Check if a promoted winner needs retesting."""
    if original_metric_value <= 0:
        return {"needs_retest": False, "reason": "no_baseline"}

    performance_ratio = current_metric_value / max(original_metric_value, 0.001)
    decayed = performance_ratio < 0.7
    stale = winner_age_days > 90
    confidence_eroded = original_confidence < 0.85

    needs_retest = decayed or stale or confidence_eroded
    reasons = []
    if decayed:
        reasons.append(f"performance_dropped_to_{performance_ratio:.0%}")
    if stale:
        reasons.append(f"winner_is_{winner_age_days}_days_old")
    if confidence_eroded:
        reasons.append("confidence_below_85pct")

    return {
        "needs_retest": needs_retest,
        "reasons": reasons,
        "performance_ratio": round(performance_ratio, 3),
        "recommendation": "retest" if needs_retest else "keep_promoted",
    }
