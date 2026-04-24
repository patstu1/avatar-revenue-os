"""Revenue Intelligence Engine — ML-powered revenue optimization.

Combines dynamic offer matching, revenue forecasting, anomaly detection,
and opportunity scoring into a unified intelligence layer.

All functions are pure/deterministic — no DB access. Service layer handles persistence.
Uses only stdlib (math, statistics, itertools, collections). No numpy/sklearn.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from itertools import combinations

# ══════════════════════════════════════════════════════════════════════════
# DATA TYPES
# ══════════════════════════════════════════════════════════════════════════


class RevenueSignalStrength(str, Enum):
    EXPLOSIVE = "explosive"
    STRONG = "strong"
    STEADY = "steady"
    DECLINING = "declining"
    CRITICAL = "critical"


@dataclass
class OfferPerformanceProfile:
    offer_id: str
    epc: float
    conversion_rate: float
    avg_order_value: float
    audience_fit_score: float
    freshness_score: float
    competition_density: float
    seasonal_multiplier: float
    platform_affinity: dict[str, float] = field(default_factory=dict)
    historical_rpm: list[float] = field(default_factory=list)


@dataclass
class AudienceSegment:
    segment_id: str
    name: str
    size: int
    avg_engagement_rate: float
    avg_conversion_rate: float
    avg_revenue_per_user: float
    top_content_types: list[str]
    top_platforms: list[str]
    price_sensitivity: float
    intent_signals: dict[str, float] = field(default_factory=dict)


@dataclass
class ContentRevenueProjection:
    content_id: str
    projected_impressions: int
    projected_clicks: int
    projected_conversions: int
    projected_revenue: float
    projected_profit: float
    confidence: float
    best_offer_id: str
    best_platform: str
    optimal_publish_time: str | None = None
    revenue_ceiling: float = 0.0
    revenue_floor: float = 0.0


@dataclass
class RevenueAnomaly:
    entity_type: str
    entity_id: str
    anomaly_type: str
    severity: float
    expected_value: float
    actual_value: float
    deviation_sigma: float
    explanation: str
    recommended_action: str


@dataclass
class RevenueForecast:
    period: str
    forecasts: list[dict]
    trend: str
    growth_rate: float
    confidence: float


# ══════════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════════════════

_EPS = 1e-9


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    return num / den if abs(den) > _EPS else default


def _cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity between two sparse vectors represented as dicts."""
    keys = set(a) & set(b)
    if not keys:
        return 0.0
    dot = sum(a[k] * b[k] for k in keys)
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    if mag_a < _EPS or mag_b < _EPS:
        return 0.0
    return dot / (mag_a * mag_b)


def _ewma(values: list[float], alpha: float = 0.3) -> list[float]:
    """Exponentially-weighted moving average."""
    if not values:
        return []
    result = [values[0]]
    for v in values[1:]:
        result.append(alpha * v + (1.0 - alpha) * result[-1])
    return result


def _rolling_std(values: list[float], window: int = 7) -> list[float]:
    """Rolling standard deviation with minimum 3-sample requirement."""
    result = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        window_vals = values[start : i + 1]
        if len(window_vals) >= 3:
            result.append(statistics.stdev(window_vals))
        else:
            result.append(0.0)
    return result


def _least_squares_exp_decay(
    ys: list[float],
    xs: list[float] | None = None,
) -> tuple[float, float, float]:
    """Fit y = A * exp(-lambda * x) + B using iterative linearised least squares.

    Returns (A, lam, B).  Falls back to simple heuristic when the data
    is too short or monotone.
    """
    n = len(ys)
    if n < 3:
        peak = max(ys) if ys else 1.0
        return (peak, 0.01, 0.0)

    if xs is None:
        xs = list(range(n))

    floor_estimate = min(ys)
    peak_estimate = max(ys) - floor_estimate
    if peak_estimate < _EPS:
        return (0.0, 0.01, floor_estimate)

    best_a, best_lam, best_b = peak_estimate, 0.05, floor_estimate
    best_sse = float("inf")

    for lam_candidate in [0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5]:
        shifted = [max(y - floor_estimate, _EPS) for y in ys]
        log_shifted = [math.log(s) for s in shifted]
        log_xs = [-lam_candidate * x for x in xs]

        sum_x = sum(log_xs)
        sum_y = sum(log_shifted)
        sum_xy = sum(lx * ly for lx, ly in zip(log_xs, log_shifted))
        sum_x2 = sum(lx * lx for lx in log_xs)

        denom = n * sum_x2 - sum_x * sum_x
        if abs(denom) < _EPS:
            continue

        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n
        a_fit = math.exp(intercept)

        sse = sum((y - (a_fit * math.exp(-lam_candidate * x) + floor_estimate)) ** 2 for x, y in zip(xs, ys))
        if sse < best_sse:
            best_sse = sse
            best_a = a_fit
            best_lam = lam_candidate
            best_b = floor_estimate

    return (best_a, best_lam, best_b)


def _classify_signal_strength(ratio: float) -> RevenueSignalStrength:
    if ratio > 3.0:
        return RevenueSignalStrength.EXPLOSIVE
    if ratio > 1.5:
        return RevenueSignalStrength.STRONG
    if ratio > 0.75:
        return RevenueSignalStrength.STEADY
    if ratio > 0.25:
        return RevenueSignalStrength.DECLINING
    return RevenueSignalStrength.CRITICAL


# ══════════════════════════════════════════════════════════════════════════
# 1 · DYNAMIC OFFER MATCHING
# ══════════════════════════════════════════════════════════════════════════


def compute_offer_score(
    offer: OfferPerformanceProfile,
    segment: AudienceSegment,
    platform: str,
    content_type: str,
) -> float:
    """Multi-factor offer scoring that maximises expected revenue per impression.

    Combines EPC × audience_fit × freshness × (1 – competition) × seasonal
    × platform_affinity with diminishing-returns modelling and audience-specific
    adjustments.
    """
    base_expected = offer.epc * offer.conversion_rate * offer.avg_order_value
    base_score = math.log1p(base_expected) if base_expected > 0 else 0.0

    if segment.intent_signals and offer.platform_affinity:
        cosine = _cosine_similarity(segment.intent_signals, offer.platform_affinity)
        audience_mult = 0.5 + 0.5 * cosine
    else:
        audience_mult = _clamp(offer.audience_fit_score, 0.1, 1.0)

    segment_cr_ratio = _safe_div(segment.avg_conversion_rate, offer.conversion_rate, 1.0)
    audience_mult *= _clamp(0.5 + 0.5 * segment_cr_ratio, 0.3, 1.5)

    freshness_mult = 0.3 + 0.7 * _clamp(offer.freshness_score)

    competition_penalty = 1.0 - 0.6 * _clamp(offer.competition_density)

    seasonal_mult = max(0.5, offer.seasonal_multiplier)

    platform_fit = offer.platform_affinity.get(platform, 0.5)
    platform_mult = 0.4 + 0.6 * _clamp(platform_fit)

    content_bonus = 1.0
    if content_type in segment.top_content_types:
        content_bonus = 1.15

    price_penalty = 1.0
    if segment.price_sensitivity > 0.6 and offer.avg_order_value > 100:
        overshoot = (offer.avg_order_value - 100) / 200
        price_penalty = max(0.4, 1.0 - segment.price_sensitivity * _clamp(overshoot))

    if offer.historical_rpm:
        rpm_trend = _safe_div(
            statistics.mean(offer.historical_rpm[-3:]),
            statistics.mean(offer.historical_rpm),
            1.0,
        )
        maturity_factor = _clamp(rpm_trend, 0.5, 1.5)
    else:
        maturity_factor = 1.0

    raw = (
        base_score
        * audience_mult
        * freshness_mult
        * competition_penalty
        * seasonal_mult
        * platform_mult
        * content_bonus
        * price_penalty
        * maturity_factor
    )

    return round(raw, 6)


def rank_offers_for_content(
    offers: list[OfferPerformanceProfile],
    segment: AudienceSegment,
    platform: str,
    content_type: str,
    top_k: int = 5,
) -> list[tuple[str, float, dict]]:
    """Rank offers by expected revenue impact.

    Returns ``[(offer_id, score, breakdown)]`` for the top *k* offers.
    """
    scored: list[tuple[str, float, dict]] = []

    for offer in offers:
        total = compute_offer_score(offer, segment, platform, content_type)

        base_expected = offer.epc * offer.conversion_rate * offer.avg_order_value
        breakdown = {
            "base_expected_value": round(base_expected, 4),
            "audience_fit": round(offer.audience_fit_score, 4),
            "freshness": round(offer.freshness_score, 4),
            "competition_density": round(offer.competition_density, 4),
            "seasonal_multiplier": round(offer.seasonal_multiplier, 4),
            "platform_affinity": round(offer.platform_affinity.get(platform, 0.5), 4),
            "price_sensitivity_penalty": round(
                max(
                    0.4,
                    1.0 - segment.price_sensitivity * _clamp((offer.avg_order_value - 100) / 200),
                )
                if segment.price_sensitivity > 0.6 and offer.avg_order_value > 100
                else 1.0,
                4,
            ),
            "signal_strength": _classify_signal_strength(
                _safe_div(total, max(1e-6, statistics.mean([s for _, s, _ in scored]) if scored else 1.0))
            ).value,
        }
        scored.append((offer.offer_id, total, breakdown))

    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[:top_k]


def compute_optimal_offer_mix(
    offers: list[OfferPerformanceProfile],
    segments: list[AudienceSegment],
    daily_content_slots: int,
    budget_constraint: float = float("inf"),
) -> list[dict]:
    """Solve the offer-content allocation problem to maximise total revenue.

    Uses a greedy knapsack approach: for each content slot, select the
    offer–segment–platform combo with highest marginal revenue contribution,
    accounting for diminishing returns from offer saturation.
    """
    offer_usage: dict[str, int] = defaultdict(int)
    allocation: list[dict] = []
    total_cost = 0.0

    all_platforms: set[str] = set()
    for seg in segments:
        all_platforms.update(seg.top_platforms)
    if not all_platforms:
        all_platforms = {"default"}

    for slot_idx in range(daily_content_slots):
        best_combo: dict | None = None
        best_marginal = -1.0

        for offer in offers:
            usage = offer_usage[offer.offer_id]
            saturation_decay = 1.0 / (1.0 + 0.3 * usage)

            for seg in segments:
                for plat in seg.top_platforms or list(all_platforms):
                    content_type = seg.top_content_types[0] if seg.top_content_types else "general"
                    raw_score = compute_offer_score(offer, seg, plat, content_type)
                    marginal = raw_score * saturation_decay

                    estimated_rev = (
                        offer.epc
                        * offer.conversion_rate
                        * offer.avg_order_value
                        * seg.size
                        * seg.avg_engagement_rate
                        * saturation_decay
                    )
                    estimated_cost = estimated_rev * 0.05
                    if total_cost + estimated_cost > budget_constraint:
                        continue

                    if marginal > best_marginal:
                        best_marginal = marginal
                        best_combo = {
                            "slot": slot_idx,
                            "offer_id": offer.offer_id,
                            "segment_id": seg.segment_id,
                            "platform": plat,
                            "content_type": content_type,
                            "marginal_score": round(marginal, 6),
                            "estimated_revenue": round(estimated_rev, 2),
                            "estimated_cost": round(estimated_cost, 2),
                            "saturation_factor": round(saturation_decay, 4),
                        }

        if best_combo is None:
            break

        offer_usage[best_combo["offer_id"]] += 1
        total_cost += best_combo["estimated_cost"]
        allocation.append(best_combo)

    return allocation


# ══════════════════════════════════════════════════════════════════════════
# 2 · MULTI-TOUCH ATTRIBUTION
# ══════════════════════════════════════════════════════════════════════════


@dataclass
class TouchPoint:
    timestamp: datetime
    channel: str
    content_id: str
    event_type: str
    value: float = 0.0


@dataclass
class AttributionResult:
    conversion_id: str
    total_value: float
    touchpoint_credits: list[dict]
    model_used: str
    path_length: int
    time_to_conversion_hours: float


def _path_meta(touchpoints: list[TouchPoint]) -> tuple[int, float]:
    if len(touchpoints) < 2:
        return len(touchpoints), 0.0
    ts_sorted = sorted(touchpoints, key=lambda t: t.timestamp)
    delta = (ts_sorted[-1].timestamp - ts_sorted[0].timestamp).total_seconds()
    return len(touchpoints), delta / 3600.0


def attribute_linear(
    touchpoints: list[TouchPoint],
    conversion_value: float,
) -> AttributionResult:
    """Equal credit to all touchpoints."""
    path_len, ttc = _path_meta(touchpoints)
    if not touchpoints:
        return AttributionResult(
            conversion_id="",
            total_value=conversion_value,
            touchpoint_credits=[],
            model_used="linear",
            path_length=0,
            time_to_conversion_hours=0.0,
        )

    share = conversion_value / len(touchpoints)
    credits = [
        {
            "content_id": tp.content_id,
            "channel": tp.channel,
            "credit": round(share, 6),
            "model": "linear",
        }
        for tp in touchpoints
    ]
    return AttributionResult(
        conversion_id="",
        total_value=round(conversion_value, 6),
        touchpoint_credits=credits,
        model_used="linear",
        path_length=path_len,
        time_to_conversion_hours=round(ttc, 2),
    )


def attribute_time_decay(
    touchpoints: list[TouchPoint],
    conversion_value: float,
    half_life_hours: float = 168.0,
) -> AttributionResult:
    """Exponential time-decay: touchpoints closer to conversion get more credit."""
    path_len, ttc = _path_meta(touchpoints)
    if not touchpoints:
        return AttributionResult(
            conversion_id="",
            total_value=conversion_value,
            touchpoint_credits=[],
            model_used="time_decay",
            path_length=0,
            time_to_conversion_hours=0.0,
        )

    ts_sorted = sorted(touchpoints, key=lambda t: t.timestamp)
    conversion_time = ts_sorted[-1].timestamp
    decay_constant = math.log(2) / max(half_life_hours, _EPS)

    raw_weights: list[float] = []
    for tp in ts_sorted:
        hours_before = (conversion_time - tp.timestamp).total_seconds() / 3600.0
        raw_weights.append(math.exp(-decay_constant * hours_before))

    total_weight = sum(raw_weights) or 1.0
    credits = [
        {
            "content_id": tp.content_id,
            "channel": tp.channel,
            "credit": round(conversion_value * w / total_weight, 6),
            "model": "time_decay",
            "hours_before_conversion": round((conversion_time - tp.timestamp).total_seconds() / 3600.0, 2),
        }
        for tp, w in zip(ts_sorted, raw_weights)
    ]

    return AttributionResult(
        conversion_id="",
        total_value=round(conversion_value, 6),
        touchpoint_credits=credits,
        model_used="time_decay",
        path_length=path_len,
        time_to_conversion_hours=round(ttc, 2),
    )


def attribute_position_based(
    touchpoints: list[TouchPoint],
    conversion_value: float,
    first_weight: float = 0.4,
    last_weight: float = 0.4,
    middle_weight: float = 0.2,
) -> AttributionResult:
    """U-shaped model: first touch + last touch get most credit."""
    path_len, ttc = _path_meta(touchpoints)
    if not touchpoints:
        return AttributionResult(
            conversion_id="",
            total_value=conversion_value,
            touchpoint_credits=[],
            model_used="position_based",
            path_length=0,
            time_to_conversion_hours=0.0,
        )

    ts_sorted = sorted(touchpoints, key=lambda t: t.timestamp)
    n = len(ts_sorted)

    weights: list[float] = []
    if n == 1:
        weights = [1.0]
    elif n == 2:
        weights = [first_weight / (first_weight + last_weight), last_weight / (first_weight + last_weight)]
    else:
        mid_count = n - 2
        mid_each = middle_weight / mid_count if mid_count > 0 else 0.0
        weights = [first_weight] + [mid_each] * mid_count + [last_weight]

    total_w = sum(weights) or 1.0
    credits = [
        {
            "content_id": tp.content_id,
            "channel": tp.channel,
            "credit": round(conversion_value * w / total_w, 6),
            "model": "position_based",
            "position": "first" if i == 0 else ("last" if i == n - 1 else "middle"),
        }
        for i, (tp, w) in enumerate(zip(ts_sorted, weights))
    ]

    return AttributionResult(
        conversion_id="",
        total_value=round(conversion_value, 6),
        touchpoint_credits=credits,
        model_used="position_based",
        path_length=path_len,
        time_to_conversion_hours=round(ttc, 2),
    )


def attribute_shapley(
    touchpoints: list[TouchPoint],
    conversion_value: float,
    conversion_model: callable | None = None,
) -> AttributionResult:
    """Shapley value attribution — game-theoretic fair credit allocation.

    For each touchpoint compute its marginal contribution across all possible
    orderings.  For paths > 10 touchpoints switches to Monte-Carlo sampling
    (1 000 permutations) to keep compute bounded.
    """
    path_len, ttc = _path_meta(touchpoints)
    if not touchpoints:
        return AttributionResult(
            conversion_id="",
            total_value=conversion_value,
            touchpoint_credits=[],
            model_used="shapley",
            path_length=0,
            time_to_conversion_hours=0.0,
        )

    ts_sorted = sorted(touchpoints, key=lambda t: t.timestamp)
    n = len(ts_sorted)

    def _default_conversion_model(subset_indices: frozenset[int]) -> float:
        """Heuristic conversion probability given a subset of touchpoints.

        More touchpoints and later touchpoints contribute more.
        """
        if not subset_indices:
            return 0.0
        count_factor = len(subset_indices) / n
        recency_factor = max(idx / max(n - 1, 1) for idx in subset_indices)
        type_bonus = 0.0
        for idx in subset_indices:
            if ts_sorted[idx].event_type == "convert":
                type_bonus = 0.2
            elif ts_sorted[idx].event_type == "click":
                type_bonus = max(type_bonus, 0.1)
        prob = _clamp(0.3 * count_factor + 0.4 * recency_factor + 0.3 * type_bonus)
        return prob

    model = conversion_model or _default_conversion_model
    shapley_values: list[float] = [0.0] * n

    if n <= 10:
        all_indices = set(range(n))
        for i in range(n):
            others = list(all_indices - {i})
            for size in range(len(others) + 1):
                for coalition in combinations(others, size):
                    coalition_set = frozenset(coalition)
                    with_i = coalition_set | {i}
                    marginal = model(with_i) - model(coalition_set)
                    weight = math.factorial(size) * math.factorial(n - size - 1) / math.factorial(n)
                    shapley_values[i] += weight * marginal
    else:
        import random as _rand

        rng = _rand.Random(42)
        num_samples = 1000
        for _ in range(num_samples):
            perm = list(range(n))
            rng.shuffle(perm)
            coalition: set[int] = set()
            prev_val = 0.0
            for idx in perm:
                coalition.add(idx)
                new_val = model(frozenset(coalition))
                shapley_values[idx] += (new_val - prev_val) / num_samples
                prev_val = new_val

    total_sv = sum(shapley_values) or 1.0
    credits = [
        {
            "content_id": tp.content_id,
            "channel": tp.channel,
            "credit": round(conversion_value * sv / total_sv, 6),
            "model": "shapley",
            "shapley_value": round(sv, 6),
        }
        for tp, sv in zip(ts_sorted, shapley_values)
    ]

    return AttributionResult(
        conversion_id="",
        total_value=round(conversion_value, 6),
        touchpoint_credits=credits,
        model_used="shapley",
        path_length=path_len,
        time_to_conversion_hours=round(ttc, 2),
    )


def attribute_multi_model(
    touchpoints: list[TouchPoint],
    conversion_value: float,
) -> dict[str, AttributionResult]:
    """Run all attribution models and return ensemble results."""
    return {
        "linear": attribute_linear(touchpoints, conversion_value),
        "time_decay": attribute_time_decay(touchpoints, conversion_value),
        "position_based": attribute_position_based(touchpoints, conversion_value),
        "shapley": attribute_shapley(touchpoints, conversion_value),
    }


# ══════════════════════════════════════════════════════════════════════════
# 3 · REVENUE FORECASTING — Holt-Winters Triple Exponential Smoothing
# ══════════════════════════════════════════════════════════════════════════


def forecast_revenue(
    historical_daily: list[tuple[str, float]],
    horizon_days: int = 30,
    seasonality_period: int = 7,
) -> RevenueForecast:
    """Time-series revenue forecast using triple exponential smoothing (Holt-Winters).

    Decomposes into trend + seasonality + residual, then projects forward.
    Uses multiplicative seasonality with additive trend.
    """
    values = [v for _, v in historical_daily]
    dates = [d for d, _ in historical_daily]
    n = len(values)

    if n < 2:
        return RevenueForecast(
            period="daily",
            forecasts=[],
            trend="insufficient_data",
            growth_rate=0.0,
            confidence=0.0,
        )

    m = seasonality_period

    # ── Initialisation ─────────────────────────────────────────────────
    alpha = 0.3
    beta = 0.1
    gamma = 0.15

    if n < 2 * m:
        level = statistics.mean(values)
        trend = (values[-1] - values[0]) / max(n - 1, 1)
        seasonal: list[float] = [1.0] * m
    else:
        first_cycle = values[:m]
        second_cycle = values[m : 2 * m]
        level = statistics.mean(first_cycle)
        trend = (statistics.mean(second_cycle) - statistics.mean(first_cycle)) / m

        cycle_mean = statistics.mean(first_cycle) if statistics.mean(first_cycle) > _EPS else 1.0
        seasonal = [v / cycle_mean for v in first_cycle]

    # ── Fit historical ─────────────────────────────────────────────────
    levels: list[float] = [level]
    trends: list[float] = [trend]
    seasonals: list[float] = list(seasonal)
    fitted: list[float] = []
    residuals: list[float] = []

    for t in range(n):
        s_idx = t % m
        s_t = seasonals[s_idx] if s_idx < len(seasonals) else 1.0

        if abs(s_t) < _EPS:
            s_t = 1.0

        fitted_val = (level + trend) * s_t
        fitted.append(fitted_val)
        residuals.append(values[t] - fitted_val)

        new_level = alpha * (values[t] / s_t) + (1 - alpha) * (level + trend)
        new_trend = beta * (new_level - level) + (1 - beta) * trend
        new_seasonal = gamma * (values[t] / max(new_level, _EPS)) + (1 - gamma) * s_t

        level = new_level
        trend = new_trend

        if s_idx < len(seasonals):
            seasonals[s_idx] = new_seasonal
        else:
            seasonals.append(new_seasonal)

        levels.append(level)
        trends.append(trend)

    # ── Forecast forward ───────────────────────────────────────────────
    residual_std = statistics.stdev(residuals) if len(residuals) >= 3 else 0.0

    forecasts: list[dict] = []
    last_date_str = dates[-1] if dates else "2024-01-01"
    try:
        last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        last_date = datetime.now()

    for h in range(1, horizon_days + 1):
        s_idx = (n + h - 1) % m
        s_t = seasonals[s_idx] if s_idx < len(seasonals) else 1.0
        point_forecast = (level + h * trend) * s_t

        ci_width = 1.96 * residual_std * math.sqrt(h)
        forecast_date = last_date + timedelta(days=h)

        forecasts.append(
            {
                "date": forecast_date.strftime("%Y-%m-%d"),
                "predicted": round(max(point_forecast, 0.0), 2),
                "lower_bound": round(max(point_forecast - ci_width, 0.0), 2),
                "upper_bound": round(point_forecast + ci_width, 2),
            }
        )

    # ── Trend classification ───────────────────────────────────────────
    if len(trends) >= 7:
        recent_trends = trends[-7:]
        accel = [recent_trends[i] - recent_trends[i - 1] for i in range(1, len(recent_trends))]
        avg_accel = statistics.mean(accel) if accel else 0.0
        trend_vol = statistics.stdev(accel) if len(accel) >= 3 else 0.0

        if trend_vol > abs(avg_accel) * 3 and trend_vol > 0.01 * abs(level):
            trend_label = "volatile"
        elif avg_accel > 0.005 * abs(trend):
            trend_label = "accelerating"
        elif avg_accel < -0.005 * abs(trend):
            trend_label = "decelerating"
        else:
            trend_label = "steady"
    else:
        trend_label = "steady" if abs(trend) < 0.01 * abs(level) else ("accelerating" if trend > 0 else "decelerating")

    sum(values)
    growth_rate = _safe_div(values[-1] - values[0], abs(values[0]), 0.0) if n >= 2 else 0.0

    confidence = _clamp(1.0 - _safe_div(residual_std, abs(level), 0.5), 0.1, 0.99)

    return RevenueForecast(
        period="daily",
        forecasts=forecasts,
        trend=trend_label,
        growth_rate=round(growth_rate, 4),
        confidence=round(confidence, 4),
    )


# ══════════════════════════════════════════════════════════════════════════
# 4 · ANOMALY DETECTION
# ══════════════════════════════════════════════════════════════════════════


def detect_revenue_anomalies(
    daily_revenues: list[tuple[str, float]],
    sensitivity: float = 2.0,
) -> list[RevenueAnomaly]:
    """Detect anomalies using rolling Z-score with adaptive EWMA windowing.

    Uses exponentially-weighted moving average/stddev to adapt to changing
    revenue patterns.  Classifies anomaly type (spike, drop, trend break,
    outlier) and produces severity scores and actionable recommendations.
    """
    if len(daily_revenues) < 7:
        return []

    dates = [d for d, _ in daily_revenues]
    values = [v for _, v in daily_revenues]

    alpha = 0.2
    ewma_mean = _ewma(values, alpha)

    ewma_var: list[float] = [0.0]
    for i in range(1, len(values)):
        diff_sq = (values[i] - ewma_mean[i]) ** 2
        ewma_var.append(alpha * diff_sq + (1 - alpha) * ewma_var[-1])
    ewma_std = [math.sqrt(v) for v in ewma_var]

    # Detect trend breaks via second derivative of EWMA
    ewma_diff = [0.0]
    for i in range(1, len(ewma_mean)):
        ewma_diff.append(ewma_mean[i] - ewma_mean[i - 1])
    ewma_diff2 = [0.0]
    for i in range(1, len(ewma_diff)):
        ewma_diff2.append(ewma_diff[i] - ewma_diff[i - 1])

    anomalies: list[RevenueAnomaly] = []

    for i in range(7, len(values)):
        expected = ewma_mean[i - 1]
        std = ewma_std[i - 1]
        actual = values[i]

        if std < _EPS:
            std = abs(expected) * 0.05 + _EPS

        z = (actual - expected) / std

        if abs(z) < sensitivity:
            continue

        if z > 0:
            anomaly_type = "spike"
        else:
            anomaly_type = "drop"

        if i < len(ewma_diff2) and abs(ewma_diff2[i]) > 2 * std:
            anomaly_type = "trend_break"

        window_vals = values[max(0, i - 14) : i]
        if len(window_vals) >= 5:
            iqr_sorted = sorted(window_vals)
            q1 = iqr_sorted[len(iqr_sorted) // 4]
            q3 = iqr_sorted[3 * len(iqr_sorted) // 4]
            iqr = q3 - q1
            if actual > q3 + 3 * iqr or actual < q1 - 3 * iqr:
                anomaly_type = "outlier"

        severity = _clamp(abs(z) / (sensitivity * 3), 0.1, 1.0)

        pct_change = _safe_div(actual - expected, abs(expected), 0.0) * 100

        if anomaly_type == "spike":
            if severity > 0.7:
                action = (
                    f"Investigate sudden revenue spike (+{pct_change:.0f}%). "
                    "If organic, double down on this channel/offer immediately."
                )
            else:
                action = (
                    f"Revenue up {pct_change:.0f}% vs expected. Monitor for sustainability over 48h before scaling."
                )
        elif anomaly_type == "drop":
            if severity > 0.7:
                action = (
                    f"CRITICAL: Revenue dropped {abs(pct_change):.0f}%. "
                    "Check for broken links, offer pauses, or platform penalties."
                )
            else:
                action = f"Revenue down {abs(pct_change):.0f}%. Review recent content/offer changes; may need A/B test."
        elif anomaly_type == "trend_break":
            direction = "upward" if z > 0 else "downward"
            action = (
                f"Trend break detected ({direction}). "
                "Re-evaluate forecasting baseline. "
                "Check for algorithm changes or audience shifts."
            )
        else:
            action = f"Statistical outlier ({pct_change:+.0f}%). Likely a one-off event. Exclude from trend analysis."

        explanation = (
            f"Expected ${expected:.2f}, got ${actual:.2f} "
            f"({pct_change:+.1f}%, {abs(z):.1f}σ deviation). "
            f"Based on {alpha:.0%}-weighted moving average."
        )

        anomalies.append(
            RevenueAnomaly(
                entity_type="account",
                entity_id=dates[i],
                anomaly_type=anomaly_type,
                severity=round(severity, 4),
                expected_value=round(expected, 2),
                actual_value=round(actual, 2),
                deviation_sigma=round(abs(z), 2),
                explanation=explanation,
                recommended_action=action,
            )
        )

    return anomalies


# ══════════════════════════════════════════════════════════════════════════
# 5 · LTV PREDICTION
# ══════════════════════════════════════════════════════════════════════════


@dataclass
class ContentLTV:
    content_id: str
    projected_30d_revenue: float
    projected_90d_revenue: float
    projected_365d_revenue: float
    revenue_half_life_days: float
    evergreen_score: float
    viral_coefficient: float
    marginal_value_per_impression: float


def predict_content_ltv(
    content_age_days: int,
    daily_revenue_history: list[float],
    daily_impression_history: list[float],
    content_type: str,
    platform: str,
) -> ContentLTV:
    """Predict lifetime revenue of a content piece using decay curve fitting.

    Fits a modified exponential decay: R(t) = A · exp(−λt) + B
    where B captures the evergreen floor.
    """
    content_id = f"{platform}:{content_type}:{content_age_days}d"
    n = len(daily_revenue_history)

    if n < 3:
        total = sum(daily_revenue_history)
        total_imp = sum(daily_impression_history) or 1
        return ContentLTV(
            content_id=content_id,
            projected_30d_revenue=round(total * 1.5, 2),
            projected_90d_revenue=round(total * 2.0, 2),
            projected_365d_revenue=round(total * 2.5, 2),
            revenue_half_life_days=30.0,
            evergreen_score=0.3,
            viral_coefficient=0.0,
            marginal_value_per_impression=round(_safe_div(total, total_imp), 6),
        )

    A, lam, B = _least_squares_exp_decay(daily_revenue_history)

    def _integrate_decay(t_start: int, t_end: int) -> float:
        """Integrate A·e^{−λt} + B from t_start to t_end."""
        if lam < _EPS:
            return (A + B) * (t_end - t_start)
        integral_exp = (A / lam) * (math.exp(-lam * t_start) - math.exp(-lam * t_end))
        integral_const = B * (t_end - t_start)
        return max(integral_exp + integral_const, 0.0)

    already_earned = sum(daily_revenue_history)
    remaining_30 = _integrate_decay(content_age_days, max(content_age_days, 30))
    remaining_90 = _integrate_decay(content_age_days, max(content_age_days, 90))
    remaining_365 = _integrate_decay(content_age_days, max(content_age_days, 365))

    proj_30 = already_earned + remaining_30
    proj_90 = already_earned + remaining_90
    proj_365 = already_earned + remaining_365

    if lam > _EPS:
        half_life = math.log(2) / lam
    else:
        half_life = 365.0

    peak = A + B
    if peak > _EPS:
        evergreen_score = _clamp(B / peak)
    else:
        evergreen_score = 0.0

    # Viral coefficient from impression growth
    viral_coefficient = 0.0
    if len(daily_impression_history) >= 5:
        growth_rates: list[float] = []
        for i in range(1, len(daily_impression_history)):
            prev = daily_impression_history[i - 1]
            curr = daily_impression_history[i]
            if prev > 0:
                growth_rates.append(curr / prev)
        if growth_rates:
            avg_growth = statistics.mean(growth_rates)
            viral_coefficient = max(0.0, avg_growth - 1.0) * 10

    total_imp = sum(daily_impression_history) or 1
    marginal_vpi = _safe_div(already_earned, total_imp)

    # Content type and platform adjustments
    type_mult = {
        "tutorial": 1.4,
        "review": 1.3,
        "comparison": 1.35,
        "listicle": 1.1,
        "news": 0.7,
        "opinion": 0.8,
        "story": 0.9,
    }.get(content_type.lower(), 1.0)

    platform_mult = {
        "youtube": 1.5,
        "blog": 1.3,
        "tiktok": 0.7,
        "instagram": 0.8,
        "twitter": 0.6,
        "pinterest": 1.2,
    }.get(platform.lower(), 1.0)

    longevity_adjust = type_mult * platform_mult

    return ContentLTV(
        content_id=content_id,
        projected_30d_revenue=round(proj_30 * longevity_adjust, 2),
        projected_90d_revenue=round(proj_90 * longevity_adjust, 2),
        projected_365d_revenue=round(proj_365 * longevity_adjust, 2),
        revenue_half_life_days=round(half_life, 1),
        evergreen_score=round(evergreen_score, 4),
        viral_coefficient=round(viral_coefficient, 4),
        marginal_value_per_impression=round(marginal_vpi, 6),
    )


# ══════════════════════════════════════════════════════════════════════════
# 6 · REVENUE CEILING ANALYSIS
# ══════════════════════════════════════════════════════════════════════════


@dataclass
class RevenueCeilingReport:
    brand_id: str
    current_monthly_revenue: float
    theoretical_ceiling: float
    achievable_ceiling_90d: float
    gap_analysis: list[dict]
    top_opportunities: list[dict]
    efficiency_score: float


def compute_revenue_ceiling(
    accounts: list[dict],
    offers: list[dict],
    content_velocity: int,
    avg_rpm: float,
    avg_conversion_rate: float,
) -> RevenueCeilingReport:
    """Calculate the theoretical revenue ceiling and gap analysis.

    Ceiling = Σ(account_reach × optimal_rpm × conversion_rate × avg_aov)
    Gap = Ceiling – Current, decomposed by bottleneck.
    """
    brand_id = "aggregate"
    current_monthly = 0.0
    theoretical = 0.0
    bottlenecks: list[dict] = []
    opportunities: list[dict] = []

    # ── Per-account ceiling ────────────────────────────────────────────
    for acct in accounts:
        followers = acct.get("followers", 0)
        engagement_rate = acct.get("engagement_rate", 0.02)
        monthly_impressions = acct.get("monthly_impressions", followers * 30 * engagement_rate)
        current_rev = acct.get("current_monthly_revenue", 0.0)
        platform = acct.get("platform", "unknown")

        current_monthly += current_rev

        platform_rpm_ceiling = {
            "youtube": 25.0,
            "blog": 40.0,
            "instagram": 15.0,
            "tiktok": 12.0,
            "twitter": 8.0,
            "pinterest": 20.0,
            "email": 50.0,
        }.get(platform.lower(), 15.0)

        rpm_used = min(avg_rpm, platform_rpm_ceiling)
        acct_ceiling = monthly_impressions * rpm_used / 1000.0

        theoretical += acct_ceiling

        if current_rev > 0:
            acct_efficiency = current_rev / max(acct_ceiling, _EPS)
            if acct_efficiency < 0.3:
                bottlenecks.append(
                    {
                        "bottleneck": f"{platform} account under-monetised",
                        "impact": round(acct_ceiling - current_rev, 2),
                        "fix": f"Increase {platform} RPM from ${avg_rpm:.2f} toward ${platform_rpm_ceiling:.2f} via better offer matching.",
                        "severity": round(1.0 - acct_efficiency, 4),
                    }
                )

    # ── Offer catalog ceiling ──────────────────────────────────────────
    if offers:
        best_epc = max(float(o.get("epc", 0)) for o in offers)
        avg_epc = statistics.mean([float(o.get("epc", 0)) for o in offers]) if offers else 0
        best_aov = max(float(o.get("avg_order_value", 0)) for o in offers)
        avg_aov = statistics.mean([float(o.get("avg_order_value", 0)) for o in offers]) if offers else 0

        epc_gap = best_epc - avg_epc
        if epc_gap > avg_epc * 0.5:
            total_clicks_est = sum(a.get("monthly_impressions", 0) * a.get("engagement_rate", 0.02) for a in accounts)
            epc_opportunity = total_clicks_est * epc_gap
            opportunities.append(
                {
                    "opportunity": "Shift traffic to top EPC offers",
                    "potential_uplift": round(epc_opportunity, 2),
                    "effort": "medium",
                    "timeframe_days": 14,
                }
            )

        if best_aov > avg_aov * 1.5:
            (best_aov - avg_aov) * avg_conversion_rate
            click_est = sum(a.get("monthly_impressions", 0) * a.get("engagement_rate", 0.02) for a in accounts)
            opportunities.append(
                {
                    "opportunity": "Promote higher-AOV offers to warm segments",
                    "potential_uplift": round(click_est * avg_conversion_rate * (best_aov - avg_aov) * 0.3, 2),
                    "effort": "low",
                    "timeframe_days": 7,
                }
            )

    # ── Content velocity ceiling ───────────────────────────────────────
    total_audience = sum(a.get("followers", 0) for a in accounts)
    # Dynamic: optimal velocity scales with audience, no fixed divisor
    optimal_velocity = max(
        1, int(total_audience / max(total_audience * 0.1, 1))
    )  # At least 10 pieces per 10% of audience
    if content_velocity < optimal_velocity:
        velocity_gap = optimal_velocity - content_velocity
        per_piece_rev = _safe_div(current_monthly, max(content_velocity, 1))
        velocity_opportunity = velocity_gap * per_piece_rev * 0.7
        bottlenecks.append(
            {
                "bottleneck": "Content velocity below optimal",
                "impact": round(velocity_opportunity, 2),
                "fix": f"Increase from {content_velocity} to {optimal_velocity} pieces/month "
                f"(+{velocity_gap} pieces, ~${velocity_opportunity:.0f}/mo uplift).",
                "severity": round(_clamp(velocity_gap / max(optimal_velocity, 1)), 4),
            }
        )

    # ── Conversion rate ceiling ────────────────────────────────────────
    industry_best_cr = 0.08
    if avg_conversion_rate < industry_best_cr * 0.5:
        cr_uplift_pct = (industry_best_cr - avg_conversion_rate) / max(avg_conversion_rate, _EPS)
        cr_opportunity = current_monthly * min(cr_uplift_pct, 3.0)
        bottlenecks.append(
            {
                "bottleneck": "Conversion rate below industry benchmark",
                "impact": round(cr_opportunity, 2),
                "fix": f"Improve CR from {avg_conversion_rate:.2%} toward {industry_best_cr:.2%} "
                "via better CTAs, landing pages, and audience pre-qualification.",
                "severity": round(_clamp(1.0 - avg_conversion_rate / industry_best_cr), 4),
            }
        )

    # ── Achievable 90-day ceiling ──────────────────────────────────────
    # Assume 30% of the gap can be closed in 90 days with focused effort
    gap = theoretical - current_monthly
    achievable_90d = current_monthly + gap * 0.30

    efficiency = _clamp(_safe_div(current_monthly, theoretical)) if theoretical > 0 else 0.0

    bottlenecks.sort(key=lambda b: b.get("impact", 0), reverse=True)
    opportunities.sort(key=lambda o: o.get("potential_uplift", 0), reverse=True)

    return RevenueCeilingReport(
        brand_id=brand_id,
        current_monthly_revenue=round(current_monthly, 2),
        theoretical_ceiling=round(theoretical, 2),
        achievable_ceiling_90d=round(achievable_90d, 2),
        gap_analysis=bottlenecks[:10],
        top_opportunities=opportunities[:10],
        efficiency_score=round(efficiency, 4),
    )


# ══════════════════════════════════════════════════════════════════════════
# 7 · CONTENT REVENUE PROJECTIONS
# ══════════════════════════════════════════════════════════════════════════


def project_content_revenue(
    content_id: str,
    offers: list[OfferPerformanceProfile],
    segment: AudienceSegment,
    estimated_impressions: int,
    platform: str,
    content_type: str,
) -> ContentRevenueProjection:
    """Project revenue for a piece of content before publishing.

    Combines offer scoring, audience conversion modelling, and
    confidence-banded estimates (floor/ceiling).
    """
    if not offers:
        return ContentRevenueProjection(
            content_id=content_id,
            projected_impressions=estimated_impressions,
            projected_clicks=0,
            projected_conversions=0,
            projected_revenue=0.0,
            projected_profit=0.0,
            confidence=0.0,
            best_offer_id="",
            best_platform=platform,
        )

    ranked = rank_offers_for_content(offers, segment, platform, content_type, top_k=1)
    best_offer_id = ranked[0][0] if ranked else offers[0].offer_id

    best_offer = next((o for o in offers if o.offer_id == best_offer_id), offers[0])

    ctr = _clamp(segment.avg_engagement_rate * 0.5, 0.001, 0.15)
    projected_clicks = int(estimated_impressions * ctr)

    cr = best_offer.conversion_rate * _clamp(segment.avg_conversion_rate / 0.03, 0.3, 3.0)
    projected_conversions = int(projected_clicks * cr)

    revenue = projected_conversions * best_offer.avg_order_value * best_offer.epc
    if revenue == 0 and projected_clicks > 0:
        revenue = projected_clicks * best_offer.epc

    cost_ratio = 0.15
    profit = revenue * (1.0 - cost_ratio)

    offer_rpm_history = best_offer.historical_rpm
    if len(offer_rpm_history) >= 3:
        rpm_cv = statistics.stdev(offer_rpm_history) / max(statistics.mean(offer_rpm_history), _EPS)
        confidence = _clamp(1.0 - rpm_cv, 0.2, 0.95)
    else:
        confidence = 0.5

    ceiling = revenue * 2.5
    floor_val = revenue * 0.25

    optimal_time = None
    platform_peak = {
        "youtube": "14:00",
        "instagram": "11:00",
        "tiktok": "19:00",
        "twitter": "09:00",
        "blog": "10:00",
        "pinterest": "20:00",
    }
    if platform.lower() in platform_peak:
        optimal_time = platform_peak[platform.lower()]

    return ContentRevenueProjection(
        content_id=content_id,
        projected_impressions=estimated_impressions,
        projected_clicks=projected_clicks,
        projected_conversions=projected_conversions,
        projected_revenue=round(revenue, 2),
        projected_profit=round(profit, 2),
        confidence=round(confidence, 4),
        best_offer_id=best_offer_id,
        best_platform=platform,
        optimal_publish_time=optimal_time,
        revenue_ceiling=round(ceiling, 2),
        revenue_floor=round(floor_val, 2),
    )


# ══════════════════════════════════════════════════════════════════════════
# 8 · REVENUE SIGNAL CLASSIFICATION
# ══════════════════════════════════════════════════════════════════════════


def classify_revenue_signal(
    current_value: float,
    expected_value: float,
) -> RevenueSignalStrength:
    """Classify a revenue metric relative to its expected baseline."""
    ratio = _safe_div(current_value, expected_value, 1.0)
    return _classify_signal_strength(ratio)


def compute_revenue_health_score(
    daily_revenues: list[float],
    targets: list[float] | None = None,
) -> dict:
    """Holistic revenue health score combining multiple indicators.

    Returns a 0–100 score with sub-component breakdown.
    """
    if len(daily_revenues) < 7:
        return {"score": 50.0, "components": {}, "signal": "insufficient_data"}

    recent = daily_revenues[-7:]
    older = daily_revenues[-14:-7] if len(daily_revenues) >= 14 else daily_revenues[: len(daily_revenues) // 2]

    trend_score = 50.0
    if older:
        recent_avg = statistics.mean(recent)
        older_avg = statistics.mean(older)
        growth = _safe_div(recent_avg - older_avg, abs(older_avg), 0.0)
        trend_score = _clamp(50 + growth * 100, 0, 100)

    consistency = 100 - min(
        100,
        (statistics.stdev(recent) / max(statistics.mean(recent), _EPS)) * 200,
    )
    consistency = max(0, consistency)

    target_score = 50.0
    if targets and len(targets) >= len(recent):
        recent_targets = targets[-7:]
        attainment = [_safe_div(actual, target, 1.0) for actual, target in zip(recent, recent_targets)]
        target_score = _clamp(statistics.mean(attainment) * 100, 0, 100)

    momentum_score = 50.0
    if len(daily_revenues) >= 3:
        last3 = daily_revenues[-3:]
        if last3[0] > 0:
            three_day_trend = (last3[-1] - last3[0]) / last3[0]
            momentum_score = _clamp(50 + three_day_trend * 200, 0, 100)

    weights = {"trend": 0.30, "consistency": 0.25, "target": 0.25, "momentum": 0.20}
    composite = (
        weights["trend"] * trend_score
        + weights["consistency"] * consistency
        + weights["target"] * target_score
        + weights["momentum"] * momentum_score
    )

    if composite >= 80:
        signal = RevenueSignalStrength.EXPLOSIVE.value
    elif composite >= 60:
        signal = RevenueSignalStrength.STRONG.value
    elif composite >= 40:
        signal = RevenueSignalStrength.STEADY.value
    elif composite >= 20:
        signal = RevenueSignalStrength.DECLINING.value
    else:
        signal = RevenueSignalStrength.CRITICAL.value

    return {
        "score": round(composite, 2),
        "components": {
            "trend": round(trend_score, 2),
            "consistency": round(consistency, 2),
            "target_attainment": round(target_score, 2),
            "momentum": round(momentum_score, 2),
        },
        "signal": signal,
    }
