"""Real-time Execution Engine — Live revenue optimization and smart scheduling.

Handles real-time decision making, optimal posting schedules,
circuit breaker patterns, and live performance monitoring.
"""
from __future__ import annotations

import math
import statistics
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# 1. Circuit Breaker for External Services
# ---------------------------------------------------------------------------

class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout_s: float = 60
    half_open_max_calls: int = 3
    success_threshold: int = 2
    monitoring_window_s: float = 120


class CircuitBreaker:
    """Production circuit breaker with sliding window failure detection."""

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._failure_timestamps: deque[float] = deque()
        self._success_count_half_open = 0
        self._half_open_call_count = 0
        self._opened_at: float = 0.0
        self._total_calls = 0
        self._total_failures = 0
        self._total_successes = 0
        self._latencies: deque[float] = deque(maxlen=200)
        self._state_changes: list[dict[str, Any]] = []

    # -- public API ----------------------------------------------------------

    def call(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute *func* through the circuit breaker."""
        with self._lock:
            self._maybe_transition()
            if self._state == CircuitState.OPEN:
                raise RuntimeError(
                    f"CircuitBreaker '{self.name}' is OPEN — calls rejected"
                )
            if (
                self._state == CircuitState.HALF_OPEN
                and self._half_open_call_count >= self.config.half_open_max_calls
            ):
                raise RuntimeError(
                    f"CircuitBreaker '{self.name}' HALF_OPEN limit reached"
                )
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_call_count += 1
            self._total_calls += 1

        start = time.monotonic()
        try:
            result = func(*args, **kwargs)
            latency_ms = (time.monotonic() - start) * 1000
            self.record_success(latency_ms)
            return result
        except Exception as exc:
            latency_ms = (time.monotonic() - start) * 1000
            self.record_failure(exc, latency_ms)
            raise

    def record_success(self, latency_ms: float) -> None:
        with self._lock:
            self._total_successes += 1
            self._latencies.append(latency_ms)
            if self._state == CircuitState.HALF_OPEN:
                self._success_count_half_open += 1
                if self._success_count_half_open >= self.config.success_threshold:
                    self._transition(CircuitState.CLOSED)

    def record_failure(self, error: Exception, latency_ms: float) -> None:
        now = time.monotonic()
        with self._lock:
            self._total_failures += 1
            self._latencies.append(latency_ms)
            self._failure_timestamps.append(now)
            self._prune_old_failures(now)

            if self._state == CircuitState.HALF_OPEN:
                self._transition(CircuitState.OPEN)
            elif self._state == CircuitState.CLOSED:
                if len(self._failure_timestamps) >= self.config.failure_threshold:
                    self._transition(CircuitState.OPEN)

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._maybe_transition()
            return self._state

    @property
    def metrics(self) -> dict[str, Any]:
        with self._lock:
            lats = list(self._latencies)
        avg_lat = statistics.mean(lats) if lats else 0.0
        p95 = (
            sorted(lats)[int(len(lats) * 0.95)] if len(lats) >= 2 else avg_lat
        )
        return {
            "name": self.name,
            "state": self.state.value,
            "total_calls": self._total_calls,
            "total_successes": self._total_successes,
            "total_failures": self._total_failures,
            "failure_rate": (
                round(self._total_failures / self._total_calls, 4)
                if self._total_calls
                else 0.0
            ),
            "avg_latency_ms": round(avg_lat, 2),
            "p95_latency_ms": round(p95, 2),
            "state_changes": len(self._state_changes),
            "state_history": self._state_changes[-10:],
        }

    # -- internals -----------------------------------------------------------

    def _prune_old_failures(self, now: float) -> None:
        cutoff = now - self.config.monitoring_window_s
        while self._failure_timestamps and self._failure_timestamps[0] < cutoff:
            self._failure_timestamps.popleft()

    def _maybe_transition(self) -> None:
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self.config.recovery_timeout_s:
                self._transition(CircuitState.HALF_OPEN)

    def _transition(self, new_state: CircuitState) -> None:
        old = self._state
        self._state = new_state
        self._state_changes.append(
            {"from": old.value, "to": new_state.value, "at": time.time()}
        )
        if new_state == CircuitState.OPEN:
            self._opened_at = time.monotonic()
        elif new_state == CircuitState.HALF_OPEN:
            self._success_count_half_open = 0
            self._half_open_call_count = 0
        elif new_state == CircuitState.CLOSED:
            self._failure_timestamps.clear()
            self._success_count_half_open = 0
            self._half_open_call_count = 0


class CircuitBreakerRegistry:
    """Global registry of circuit breakers for all external services."""

    _breakers: dict[str, CircuitBreaker] = {}
    _lock = threading.Lock()

    @classmethod
    def get_or_create(
        cls, service_name: str, config: CircuitBreakerConfig | None = None
    ) -> CircuitBreaker:
        with cls._lock:
            if service_name not in cls._breakers:
                cls._breakers[service_name] = CircuitBreaker(service_name, config)
            return cls._breakers[service_name]

    @classmethod
    def health_report(cls) -> dict[str, Any]:
        with cls._lock:
            breakers = dict(cls._breakers)
        services = {}
        for name, cb in breakers.items():
            services[name] = cb.metrics
        open_count = sum(
            1 for m in services.values() if m["state"] == CircuitState.OPEN.value
        )
        return {
            "total_services": len(services),
            "open_circuits": open_count,
            "healthy": open_count == 0,
            "services": services,
        }

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._breakers.clear()


# ---------------------------------------------------------------------------
# 2. ML-Optimized Posting Scheduler
# ---------------------------------------------------------------------------

@dataclass
class PlatformTimeSlot:
    hour: int
    day_of_week: int
    engagement_multiplier: float
    competition_density: float
    audience_online_pct: float


@dataclass
class ScheduleRecommendation:
    recommended_times: list[dict[str, Any]]
    avoid_times: list[dict[str, Any]]
    reasoning: str
    expected_engagement_lift_pct: float


# 24-hour engagement multipliers per platform (weekday average).
# Index = hour (0-23). Values represent relative engagement vs daily mean (1.0).
_YOUTUBE_HOURLY = [
    0.30, 0.20, 0.15, 0.12, 0.15, 0.25, 0.45, 0.65,
    0.85, 1.10, 1.20, 1.25, 1.30, 1.20, 1.15, 1.25,
    1.35, 1.50, 1.55, 1.45, 1.30, 1.10, 0.80, 0.50,
]
_TIKTOK_HOURLY = [
    0.25, 0.18, 0.12, 0.10, 0.12, 0.20, 0.55, 0.80,
    0.95, 1.05, 1.10, 1.20, 1.25, 1.15, 1.05, 1.10,
    1.20, 1.35, 1.45, 1.55, 1.50, 1.35, 1.00, 0.55,
]
_INSTAGRAM_HOURLY = [
    0.30, 0.22, 0.15, 0.12, 0.15, 0.25, 0.50, 0.75,
    1.00, 1.15, 1.20, 1.30, 1.25, 1.15, 1.05, 1.10,
    1.20, 1.35, 1.40, 1.30, 1.15, 0.95, 0.70, 0.45,
]
_X_HOURLY = [
    0.35, 0.25, 0.18, 0.15, 0.18, 0.30, 0.55, 0.80,
    1.10, 1.25, 1.30, 1.25, 1.35, 1.25, 1.10, 1.05,
    1.15, 1.25, 1.20, 1.10, 0.95, 0.80, 0.60, 0.40,
]
_LINKEDIN_HOURLY = [
    0.15, 0.10, 0.08, 0.07, 0.10, 0.20, 0.50, 0.90,
    1.40, 1.55, 1.50, 1.35, 1.40, 1.30, 1.15, 1.05,
    1.10, 1.15, 0.90, 0.65, 0.45, 0.30, 0.20, 0.15,
]

_WEEKEND_DAMPING = {
    "youtube": 0.90,
    "tiktok": 1.10,
    "instagram": 1.05,
    "x": 0.85,
    "linkedin": 0.40,
}

PLATFORM_ENGAGEMENT_CURVES: dict[str, list[float]] = {
    "youtube": _YOUTUBE_HOURLY,
    "tiktok": _TIKTOK_HOURLY,
    "instagram": _INSTAGRAM_HOURLY,
    "x": _X_HOURLY,
    "linkedin": _LINKEDIN_HOURLY,
}

_TIMEZONE_UTC_OFFSETS: dict[str, int] = {
    "America/New_York": -5,
    "America/Chicago": -6,
    "America/Denver": -7,
    "America/Los_Angeles": -8,
    "Europe/London": 0,
    "Europe/Berlin": 1,
    "Asia/Kolkata": 5,
    "Asia/Tokyo": 9,
    "Australia/Sydney": 10,
    "UTC": 0,
}


def _get_tz_offset(timezone: str) -> int:
    return _TIMEZONE_UTC_OFFSETS.get(timezone, 0)


def _engagement_for_slot(
    platform: str, hour: int, day_of_week: int
) -> float:
    curve = PLATFORM_ENGAGEMENT_CURVES.get(platform.lower(), _INSTAGRAM_HOURLY)
    base = curve[hour % 24]
    if day_of_week >= 5:
        base *= _WEEKEND_DAMPING.get(platform.lower(), 0.9)
    return base


def _bayesian_update(
    prior_mean: float,
    prior_var: float,
    observed_values: list[float],
    obs_var: float = 0.5,
) -> tuple[float, float]:
    """Conjugate Gaussian Bayesian update: returns (posterior_mean, posterior_var)."""
    if not observed_values:
        return prior_mean, prior_var
    n = len(observed_values)
    obs_mean = statistics.mean(observed_values)
    posterior_var = 1.0 / (1.0 / prior_var + n / obs_var)
    posterior_mean = posterior_var * (prior_mean / prior_var + n * obs_mean / obs_var)
    return posterior_mean, posterior_var


def _thompson_sample(mean: float, var: float) -> float:
    """Draw from a Gaussian posterior (Box-Muller since we only use stdlib)."""
    import random
    std = max(math.sqrt(var), 1e-6)
    u1 = random.random() or 1e-12
    u2 = random.random()
    z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    return mean + std * z


def compute_optimal_schedule(
    platform: str,
    timezone: str,
    historical_performance: list[dict[str, Any]],
    posts_per_day: int = 1,
    competitor_schedule: list[dict[str, Any]] | None = None,
) -> ScheduleRecommendation:
    """Compute optimal posting times using Bayesian optimization of engagement.

    Combines:
    1. Platform-specific baseline engagement curves
    2. Historical performance data (actual results)
    3. Audience activity patterns
    4. Competition avoidance (post when competitors don't)

    Uses Thompson sampling to balance exploration vs exploitation.
    """
    tz_offset = _get_tz_offset(timezone)
    now = datetime.utcnow()
    today_dow = now.weekday()

    # Build per-hour prior from platform curve
    hour_priors: dict[int, tuple[float, float]] = {}
    for h in range(24):
        base = _engagement_for_slot(platform, h, today_dow)
        hour_priors[h] = (base, 0.25)

    # Bucket historical data by local hour
    hour_observations: dict[int, list[float]] = {h: [] for h in range(24)}
    for entry in historical_performance:
        posted_at = entry.get("posted_at")
        if isinstance(posted_at, str):
            try:
                dt = datetime.fromisoformat(posted_at.replace("Z", "+00:00").split("+")[0])
            except ValueError:
                continue
        elif isinstance(posted_at, datetime):
            dt = posted_at
        else:
            continue
        local_hour = (dt.hour + tz_offset) % 24
        eng = entry.get("engagement_rate", 0.0)
        imps = entry.get("impressions", 0)
        score = eng * math.log1p(imps) if imps else eng
        if score > 0:
            hour_observations[local_hour].append(score)

    # Bayesian update per hour
    hour_posteriors: dict[int, tuple[float, float]] = {}
    for h in range(24):
        pm, pv = hour_priors[h]
        obs = hour_observations[h]
        hour_posteriors[h] = _bayesian_update(pm, pv, obs)

    # Competition density adjustment
    comp_density: dict[int, float] = {h: 0.0 for h in range(24)}
    if competitor_schedule:
        for entry in competitor_schedule:
            ch = entry.get("hour")
            if ch is not None and 0 <= ch < 24:
                comp_density[ch] = min(1.0, comp_density[ch] + 0.15)

    # Thompson sampling: score each hour
    hour_scores: list[tuple[int, float]] = []
    for h in range(24):
        pm, pv = hour_posteriors[h]
        sample = _thompson_sample(pm, pv)
        sample *= (1.0 - 0.4 * comp_density[h])
        hour_scores.append((h, sample))

    hour_scores.sort(key=lambda x: x[1], reverse=True)

    # Select top slots with minimum 2-hour spacing
    selected: list[int] = []
    for h, _ in hour_scores:
        if all(abs(h - s) >= 2 and abs(h - s) != 22 for s in selected):
            selected.append(h)
            if len(selected) >= posts_per_day:
                break

    if not selected:
        selected = [hour_scores[0][0]] if hour_scores else [9]

    selected.sort()

    # Build recommendations
    recommended: list[dict[str, Any]] = []
    base_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if now.hour > max(selected):
        base_date += timedelta(days=1)

    dict(hour_scores)
    best_prior = max(v[0] for v in hour_posteriors.values()) or 1.0

    for h in selected:
        utc_hour = (h - tz_offset) % 24
        rec_time = base_date.replace(hour=utc_hour, minute=15)
        if rec_time < now:
            rec_time += timedelta(days=1)
        pm, pv = hour_posteriors[h]
        confidence = max(0.0, min(1.0, 1.0 - math.sqrt(pv)))
        boost = ((pm / best_prior) - 1.0) * 100 if best_prior else 0.0
        recommended.append({
            "datetime": rec_time.isoformat() + "Z",
            "local_hour": h,
            "platform": platform,
            "confidence": round(confidence, 3),
            "expected_engagement_boost": round(max(boost, 0.0), 1),
            "competition_density": round(comp_density[h], 2),
        })

    # Identify avoid times (bottom 25% of scores)
    avoid_cutoff = len(hour_scores) * 3 // 4
    avoid: list[dict[str, Any]] = []
    for h, sc in hour_scores[avoid_cutoff:]:
        avoid.append({
            "hour": h,
            "platform": platform,
            "reason": "low_engagement" if comp_density[h] < 0.3 else "high_competition",
            "score": round(sc, 3),
        })

    avg_boost = (
        statistics.mean(r["expected_engagement_boost"] for r in recommended)
        if recommended
        else 0.0
    )

    obs_count = sum(len(v) for v in hour_observations.values())
    data_note = (
        f"Based on {obs_count} historical data points"
        if obs_count > 10
        else "Primarily using platform baseline curves (limited historical data)"
    )
    reasoning = (
        f"{data_note}. Bayesian posteriors updated per hour with Thompson sampling "
        f"for exploration. Competition density applied for {sum(1 for v in comp_density.values() if v > 0)} "
        f"contested hours. Timezone: {timezone}."
    )

    return ScheduleRecommendation(
        recommended_times=recommended,
        avoid_times=avoid,
        reasoning=reasoning,
        expected_engagement_lift_pct=round(avg_boost, 1),
    )


def optimize_cross_platform_schedule(
    platforms: list[str],
    posts_per_day_per_platform: dict[str, int],
    historical_data: dict[str, list[dict[str, Any]]],
    timezone: str = "America/New_York",
) -> dict[str, ScheduleRecommendation]:
    """Optimize posting schedule across multiple platforms simultaneously.

    Ensures cross-platform synergy (stagger posts for maximum reach)
    and avoids self-competition.
    """
    per_platform: dict[str, ScheduleRecommendation] = {}
    booked_hours: list[int] = []

    platform_order = sorted(
        platforms,
        key=lambda p: posts_per_day_per_platform.get(p, 1),
        reverse=True,
    )

    for plat in platform_order:
        ppd = posts_per_day_per_platform.get(plat, 1)
        hist = historical_data.get(plat, [])

        cross_comp = [{"hour": h} for h in booked_hours]

        rec = compute_optimal_schedule(
            platform=plat,
            timezone=timezone,
            historical_performance=hist,
            posts_per_day=ppd,
            competitor_schedule=cross_comp,
        )
        per_platform[plat] = rec

        for slot in rec.recommended_times:
            booked_hours.append(slot.get("local_hour", 0))

    return per_platform


# ---------------------------------------------------------------------------
# 3. Live Performance Monitor
# ---------------------------------------------------------------------------

@dataclass
class LiveMetricWindow:
    """Sliding window of live performance metrics."""

    window_size_minutes: int = 60
    data_points: deque = field(default_factory=lambda: deque(maxlen=1000))
    _alpha: float = field(default=0.1, repr=False)

    def add(self, value: float, timestamp: float | None = None) -> None:
        ts = timestamp if timestamp is not None else time.time()
        self.data_points.append((ts, value))

    def _window_points(self) -> list[tuple[float, float]]:
        cutoff = time.time() - self.window_size_minutes * 60
        return [(ts, v) for ts, v in self.data_points if ts >= cutoff]

    @property
    def current_rate(self) -> float:
        """Events per minute in the window."""
        pts = self._window_points()
        if len(pts) < 2:
            return float(len(pts))
        span_min = (pts[-1][0] - pts[0][0]) / 60.0
        if span_min <= 0:
            return float(len(pts))
        return len(pts) / span_min

    @property
    def trend(self) -> str:
        """Detect trend: accelerating, steady, decelerating."""
        pts = self._window_points()
        if len(pts) < 6:
            return "steady"
        mid = len(pts) // 2
        first_half = [v for _, v in pts[:mid]]
        second_half = [v for _, v in pts[mid:]]
        avg_first = statistics.mean(first_half)
        avg_second = statistics.mean(second_half)
        if avg_first == 0:
            return "accelerating" if avg_second > 0 else "steady"
        ratio = avg_second / avg_first
        if ratio > 1.10:
            return "accelerating"
        if ratio < 0.90:
            return "decelerating"
        return "steady"

    @property
    def ewma(self) -> float:
        """Exponentially weighted moving average."""
        pts = self._window_points()
        if not pts:
            return 0.0
        ema = pts[0][1]
        for _, v in pts[1:]:
            ema = self._alpha * v + (1.0 - self._alpha) * ema
        return ema

    @property
    def stats(self) -> dict[str, float]:
        pts = self._window_points()
        vals = [v for _, v in pts]
        if not vals:
            return {"count": 0, "mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
        return {
            "count": len(vals),
            "mean": round(statistics.mean(vals), 4),
            "std": round(statistics.pstdev(vals), 4),
            "min": round(min(vals), 4),
            "max": round(max(vals), 4),
        }


class LivePerformanceMonitor:
    """Tracks live performance metrics with anomaly detection."""

    def __init__(self) -> None:
        self.metrics: dict[str, LiveMetricWindow] = {}
        self.alerts: deque = deque(maxlen=100)
        self._alert_configs: dict[str, dict[str, float]] = {}
        self._lock = threading.Lock()

    def configure_alert(
        self,
        metric_name: str,
        upper_threshold: float | None = None,
        lower_threshold: float | None = None,
        anomaly_std_devs: float = 3.0,
    ) -> None:
        cfg: dict[str, float] = {"anomaly_std_devs": anomaly_std_devs}
        if upper_threshold is not None:
            cfg["upper"] = upper_threshold
        if lower_threshold is not None:
            cfg["lower"] = lower_threshold
        self._alert_configs[metric_name] = cfg

    def record_event(self, metric_name: str, value: float) -> None:
        with self._lock:
            if metric_name not in self.metrics:
                self.metrics[metric_name] = LiveMetricWindow()
            self.metrics[metric_name].add(value)

        triggered = self._check_metric_alert(metric_name, value)
        if triggered:
            with self._lock:
                self.alerts.append(triggered)

    def get_dashboard_snapshot(self) -> dict[str, Any]:
        with self._lock:
            names = list(self.metrics.keys())
            windows = {n: self.metrics[n] for n in names}
            recent_alerts = list(self.alerts)

        dashboard: dict[str, Any] = {"metrics": {}, "alerts": recent_alerts[-20:]}
        for name, win in windows.items():
            dashboard["metrics"][name] = {
                "rate_per_min": round(win.current_rate, 3),
                "trend": win.trend,
                "ewma": round(win.ewma, 4),
                **win.stats,
            }
        dashboard["overall_health"] = (
            "degraded" if any(a.get("severity") == "critical" for a in recent_alerts[-10:]) else "healthy"
        )
        return dashboard

    def check_alerts(self) -> list[dict[str, Any]]:
        fired: list[dict[str, Any]] = []
        with self._lock:
            names = list(self.metrics.keys())
        for name in names:
            with self._lock:
                win = self.metrics.get(name)
            if not win:
                continue
            st = win.stats
            if st["count"] < 5:
                continue
            cfg = self._alert_configs.get(name, {})
            std_devs = cfg.get("anomaly_std_devs", 3.0)
            if st["std"] > 0:
                latest = win.data_points[-1][1] if win.data_points else 0.0
                z = abs(latest - st["mean"]) / st["std"]
                if z >= std_devs:
                    alert = {
                        "metric": name,
                        "type": "anomaly",
                        "z_score": round(z, 2),
                        "value": latest,
                        "mean": st["mean"],
                        "std": st["std"],
                        "severity": "critical" if z >= std_devs + 1 else "warning",
                        "timestamp": time.time(),
                    }
                    fired.append(alert)
            upper = cfg.get("upper")
            if upper is not None and st["max"] > upper:
                fired.append({
                    "metric": name,
                    "type": "threshold_upper",
                    "value": st["max"],
                    "threshold": upper,
                    "severity": "warning",
                    "timestamp": time.time(),
                })
            lower = cfg.get("lower")
            if lower is not None and st["min"] < lower:
                fired.append({
                    "metric": name,
                    "type": "threshold_lower",
                    "value": st["min"],
                    "threshold": lower,
                    "severity": "warning",
                    "timestamp": time.time(),
                })
        return fired

    def _check_metric_alert(self, metric_name: str, value: float) -> dict[str, Any] | None:
        cfg = self._alert_configs.get(metric_name)
        if not cfg:
            return None
        with self._lock:
            win = self.metrics.get(metric_name)
        if not win:
            return None
        st = win.stats
        if st["count"] < 10 or st["std"] == 0:
            return None
        z = abs(value - st["mean"]) / st["std"]
        threshold = cfg.get("anomaly_std_devs", 3.0)
        if z >= threshold:
            return {
                "metric": metric_name,
                "type": "anomaly",
                "z_score": round(z, 2),
                "value": value,
                "mean": st["mean"],
                "std": st["std"],
                "severity": "critical" if z >= threshold + 1 else "warning",
                "timestamp": time.time(),
            }
        upper = cfg.get("upper")
        if upper is not None and value > upper:
            return {
                "metric": metric_name,
                "type": "threshold_upper",
                "value": value,
                "threshold": upper,
                "severity": "warning",
                "timestamp": time.time(),
            }
        lower = cfg.get("lower")
        if lower is not None and value < lower:
            return {
                "metric": metric_name,
                "type": "threshold_lower",
                "value": value,
                "threshold": lower,
                "severity": "warning",
                "timestamp": time.time(),
            }
        return None


# ---------------------------------------------------------------------------
# 4. Revenue Velocity Tracker
# ---------------------------------------------------------------------------

@dataclass
class RevenueVelocity:
    current_rpm: float
    rpm_trend: str
    hourly_revenue_rate: float
    daily_projection: float
    monthly_projection: float
    velocity_score: float
    momentum_index: float
    time_to_next_milestone: float | None


def compute_revenue_velocity(
    hourly_revenues: list[tuple[str, float]],
    impressions_per_hour: list[float],
    target_monthly: float = 10000,
) -> RevenueVelocity:
    """Compute real-time revenue velocity with momentum analysis.

    Uses exponentially weighted metrics to give more weight to recent data
    while maintaining stability from historical patterns.
    """
    if not hourly_revenues:
        return RevenueVelocity(
            current_rpm=0.0,
            rpm_trend="steady",
            hourly_revenue_rate=0.0,
            daily_projection=0.0,
            monthly_projection=0.0,
            velocity_score=0.0,
            momentum_index=0.0,
            time_to_next_milestone=None,
        )

    revenues = [r for _, r in hourly_revenues]

    # EWMA of hourly revenue (alpha = 0.15 → recent-biased)
    alpha = 0.15
    ema_rev = revenues[0]
    for r in revenues[1:]:
        ema_rev = alpha * r + (1.0 - alpha) * ema_rev

    # RPM calculation
    total_rev = sum(revenues)
    total_imps = sum(impressions_per_hour[: len(revenues)]) if impressions_per_hour else 0.0
    current_rpm = (total_rev / total_imps * 1000) if total_imps > 0 else 0.0

    # RPM trend via recent vs older half
    n = len(revenues)
    if n >= 6:
        mid = n // 2
        first_half = statistics.mean(revenues[:mid])
        second_half = statistics.mean(revenues[mid:])
        if first_half > 0:
            ratio = second_half / first_half
            if ratio > 1.10:
                rpm_trend = "accelerating"
            elif ratio < 0.90:
                rpm_trend = "decelerating"
            else:
                rpm_trend = "steady"
        else:
            rpm_trend = "accelerating" if second_half > 0 else "steady"
    else:
        rpm_trend = "steady"

    hourly_revenue_rate = ema_rev

    # Projections using EWMA rate
    daily_projection = ema_rev * 24
    monthly_projection = daily_projection * 30

    # Momentum index: ratio of last-12h EWMA to prior-12h EWMA
    if n >= 24:
        recent_12 = revenues[-12:]
        prior_12 = revenues[-24:-12]
        ema_recent = recent_12[0]
        for r in recent_12[1:]:
            ema_recent = alpha * r + (1.0 - alpha) * ema_recent
        ema_prior = prior_12[0]
        for r in prior_12[1:]:
            ema_prior = alpha * r + (1.0 - alpha) * ema_prior
        momentum_index = ema_recent / ema_prior if ema_prior > 0 else 1.0
    elif n >= 4:
        mid = n // 2
        avg_recent = statistics.mean(revenues[mid:])
        avg_prior = statistics.mean(revenues[:mid])
        momentum_index = avg_recent / avg_prior if avg_prior > 0 else 1.0
    else:
        momentum_index = 1.0

    # Velocity score (0-100 composite)
    rate_score = min(40.0, (hourly_revenue_rate / max(target_monthly / 720, 0.01)) * 40)
    momentum_score = min(30.0, momentum_index * 15)
    consistency_score = 0.0
    if n >= 4:
        cv = statistics.pstdev(revenues) / statistics.mean(revenues) if statistics.mean(revenues) > 0 else 1.0
        consistency_score = max(0.0, 30.0 * (1.0 - min(cv, 1.0)))
    velocity_score = min(100.0, rate_score + momentum_score + consistency_score)

    # Time to next milestone (hours)
    if hourly_revenue_rate > 0 and target_monthly > 0:
        # Estimate monthly revenue already accumulated (assume first entry is ~72h ago)
        hours_of_data = min(n, 72)
        accumulated_this_month = total_rev * (720 / hours_of_data) if hours_of_data > 0 else 0.0
        remaining = max(0.0, target_monthly - accumulated_this_month)
        time_to_next_milestone = remaining / hourly_revenue_rate if hourly_revenue_rate > 0 else None
    else:
        time_to_next_milestone = None

    return RevenueVelocity(
        current_rpm=round(current_rpm, 4),
        rpm_trend=rpm_trend,
        hourly_revenue_rate=round(hourly_revenue_rate, 4),
        daily_projection=round(daily_projection, 2),
        monthly_projection=round(monthly_projection, 2),
        velocity_score=round(velocity_score, 1),
        momentum_index=round(momentum_index, 4),
        time_to_next_milestone=round(time_to_next_milestone, 1) if time_to_next_milestone is not None else None,
    )
