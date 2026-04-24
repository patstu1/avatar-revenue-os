"""Execution guardrails — cost caps, failure thresholds, confidence gates.

These guardrails prevent runaway spend and wasteful execution.
All state is stored in Redis for cross-worker visibility.
All caps are configurable via environment variables.

Usage:
    from packages.guardrails.execution_guardrails import GuardrailEngine

    engine = GuardrailEngine()

    # Before making an expensive API call:
    allowed, reason = await engine.check_provider_spend("openai", estimated_cost=0.15)
    if not allowed:
        raise GuardrailBlocked(reason)

    # After a successful call:
    await engine.record_spend("openai", actual_cost=0.12)

    # Check failure threshold before retrying:
    allowed, reason = await engine.check_failure_threshold("generation", "heygen")
    if not allowed:
        # Circuit breaker tripped
        ...
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional

import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Configuration from environment (with sane defaults)
# ---------------------------------------------------------------------------

# Per-provider daily spend caps (USD). 0 = unlimited.
_DEFAULT_PROVIDER_CAPS = {
    "openai": 50.0,
    "anthropic": 100.0,
    "google_ai": 30.0,
    "heygen": 75.0,
    "did": 50.0,
    "runway": 50.0,
    "elevenlabs": 30.0,
    "fal": 25.0,
    "replicate": 25.0,
    "suno": 10.0,
}

# Lane-level daily spend caps (USD)
_DEFAULT_LANE_CAPS = {
    "generation": 100.0,
    "publishing": 20.0,
    "analytics": 30.0,
    "outreach": 15.0,
    "brain": 50.0,
    "mxp": 25.0,
}

# Failure thresholds — circuit breaker trips after N failures in window
_FAILURE_WINDOW_SECONDS = 3600  # 1 hour
_FAILURE_THRESHOLD = 10  # failures per provider per window

# Confidence threshold for expensive actions (0-1)
_CONFIDENCE_THRESHOLD = float(os.environ.get("GUARDRAIL_CONFIDENCE_THRESHOLD", "0.3"))


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str = ""
    spend_today: float = 0.0
    cap: float = 0.0
    failures_in_window: int = 0


class GuardrailBlocked(Exception):
    """Raised when a guardrail blocks execution."""
    def __init__(self, reason: str, category: str = "guardrail"):
        self.reason = reason
        self.category = category
        super().__init__(reason)


class GuardrailEngine:
    """Stateful guardrail engine backed by Redis for cross-worker visibility."""

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._provider_caps = self._load_provider_caps()
        self._lane_caps = self._load_lane_caps()

    def _load_provider_caps(self) -> dict[str, float]:
        caps = dict(_DEFAULT_PROVIDER_CAPS)
        # Override from env: GUARDRAIL_CAP_OPENAI=100
        for provider in list(caps.keys()):
            env_key = f"GUARDRAIL_CAP_{provider.upper()}"
            env_val = os.environ.get(env_key)
            if env_val is not None:
                try:
                    caps[provider] = float(env_val)
                except ValueError:
                    pass
        # Global override
        global_cap = os.environ.get("GUARDRAIL_GLOBAL_DAILY_CAP")
        if global_cap:
            try:
                g = float(global_cap)
                caps = {k: min(v, g) for k, v in caps.items()}
            except ValueError:
                pass
        return caps

    def _load_lane_caps(self) -> dict[str, float]:
        caps = dict(_DEFAULT_LANE_CAPS)
        for lane in list(caps.keys()):
            env_key = f"GUARDRAIL_LANE_CAP_{lane.upper()}"
            env_val = os.environ.get(env_key)
            if env_val is not None:
                try:
                    caps[lane] = float(env_val)
                except ValueError:
                    pass
        return caps

    def _get_redis(self):
        """Lazy Redis connection."""
        if self._redis is not None:
            return self._redis
        try:
            import redis
            url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            self._redis = redis.Redis.from_url(url, decode_responses=True)
            return self._redis
        except Exception:
            return None

    def _today_key(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ── Provider spend caps ───────────────────────────────────────────

    def check_provider_spend(self, provider: str, estimated_cost: float = 0.0) -> GuardrailResult:
        """Check if a provider spend is within daily cap."""
        cap = self._provider_caps.get(provider, 0.0)
        if cap <= 0:
            return GuardrailResult(allowed=True, reason="no cap configured")

        r = self._get_redis()
        if r is None:
            # If Redis is down, allow but log warning
            logger.warning("guardrail.redis_unavailable", provider=provider)
            return GuardrailResult(allowed=True, reason="redis unavailable, allowing")

        key = f"guardrail:spend:{provider}:{self._today_key()}"
        try:
            current = float(r.get(key) or 0)
        except Exception:
            return GuardrailResult(allowed=True, reason="redis read failed")

        projected = current + estimated_cost
        if projected > cap:
            reason = f"Provider {provider} daily spend cap exceeded: ${current:.2f} + ${estimated_cost:.2f} > ${cap:.2f} cap"
            logger.warning("guardrail.spend_cap_exceeded",
                           provider=provider, current=current,
                           estimated=estimated_cost, cap=cap)
            return GuardrailResult(
                allowed=False, reason=reason,
                spend_today=current, cap=cap,
            )

        return GuardrailResult(
            allowed=True, spend_today=current, cap=cap,
            reason=f"${projected:.2f} / ${cap:.2f}",
        )

    def record_spend(self, provider: str, actual_cost: float) -> None:
        """Record actual spend for a provider."""
        if actual_cost <= 0:
            return

        r = self._get_redis()
        if r is None:
            return

        key = f"guardrail:spend:{provider}:{self._today_key()}"
        try:
            pipe = r.pipeline()
            pipe.incrbyfloat(key, actual_cost)
            pipe.expire(key, 86400 * 2)  # expire after 2 days
            pipe.execute()
        except Exception:
            logger.exception("guardrail.record_spend.failed", provider=provider)

    # ── Lane spend caps ──────────────────────────────────────────────

    def check_lane_spend(self, lane: str, estimated_cost: float = 0.0) -> GuardrailResult:
        """Check if a lane (queue) spend is within daily cap."""
        cap = self._lane_caps.get(lane, 0.0)
        if cap <= 0:
            return GuardrailResult(allowed=True, reason="no lane cap configured")

        r = self._get_redis()
        if r is None:
            return GuardrailResult(allowed=True, reason="redis unavailable")

        key = f"guardrail:lane:{lane}:{self._today_key()}"
        try:
            current = float(r.get(key) or 0)
        except Exception:
            return GuardrailResult(allowed=True, reason="redis read failed")

        projected = current + estimated_cost
        if projected > cap:
            reason = f"Lane {lane} daily spend cap exceeded: ${current:.2f} + ${estimated_cost:.2f} > ${cap:.2f} cap"
            logger.warning("guardrail.lane_cap_exceeded",
                           lane=lane, current=current,
                           estimated=estimated_cost, cap=cap)
            return GuardrailResult(
                allowed=False, reason=reason,
                spend_today=current, cap=cap,
            )

        return GuardrailResult(allowed=True, spend_today=current, cap=cap)

    def record_lane_spend(self, lane: str, actual_cost: float) -> None:
        """Record actual spend for a lane."""
        if actual_cost <= 0:
            return

        r = self._get_redis()
        if r is None:
            return

        key = f"guardrail:lane:{lane}:{self._today_key()}"
        try:
            pipe = r.pipeline()
            pipe.incrbyfloat(key, actual_cost)
            pipe.expire(key, 86400 * 2)
            pipe.execute()
        except Exception:
            logger.exception("guardrail.record_lane_spend.failed", lane=lane)

    # ── Failure circuit breaker ──────────────────────────────────────

    def check_failure_threshold(self, lane: str, provider: str) -> GuardrailResult:
        """Check if failure count is below circuit breaker threshold."""
        r = self._get_redis()
        if r is None:
            return GuardrailResult(allowed=True, reason="redis unavailable")

        key = f"guardrail:failures:{lane}:{provider}"
        try:
            count = int(r.get(key) or 0)
        except Exception:
            return GuardrailResult(allowed=True, reason="redis read failed")

        threshold = int(os.environ.get("GUARDRAIL_FAILURE_THRESHOLD", str(_FAILURE_THRESHOLD)))
        if count >= threshold:
            reason = (
                f"Circuit breaker tripped: {lane}/{provider} has "
                f"{count} failures in the last hour (threshold={threshold})"
            )
            logger.error("guardrail.circuit_breaker_tripped",
                         lane=lane, provider=provider,
                         failures=count, threshold=threshold)
            return GuardrailResult(
                allowed=False, reason=reason,
                failures_in_window=count,
            )

        return GuardrailResult(allowed=True, failures_in_window=count)

    def record_failure(self, lane: str, provider: str) -> None:
        """Increment failure counter for circuit breaker."""
        r = self._get_redis()
        if r is None:
            return

        key = f"guardrail:failures:{lane}:{provider}"
        try:
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, _FAILURE_WINDOW_SECONDS)
            pipe.execute()
        except Exception:
            logger.exception("guardrail.record_failure.failed",
                             lane=lane, provider=provider)

    def clear_failures(self, lane: str, provider: str) -> None:
        """Reset failure counter (called on success)."""
        r = self._get_redis()
        if r is None:
            return

        key = f"guardrail:failures:{lane}:{provider}"
        try:
            r.delete(key)
        except Exception:
            pass

    # ── Confidence gate ──────────────────────────────────────────────

    def check_confidence(self, confidence: float, action: str = "") -> GuardrailResult:
        """Block expensive actions below confidence threshold."""
        threshold = _CONFIDENCE_THRESHOLD
        if confidence < threshold:
            reason = (
                f"Confidence {confidence:.2f} below threshold {threshold:.2f} "
                f"for action '{action}'. Blocking expensive execution."
            )
            logger.info("guardrail.confidence_gate",
                        confidence=confidence, threshold=threshold, action=action)
            return GuardrailResult(allowed=False, reason=reason)
        return GuardrailResult(allowed=True)

    # ── Spend summary (for ops endpoint) ─────────────────────────────

    def get_spend_summary(self) -> dict:
        """Return current spend vs caps for all providers and lanes."""
        r = self._get_redis()
        today = self._today_key()
        summary = {"date": today, "providers": {}, "lanes": {}}

        if r is None:
            return summary

        for provider, cap in self._provider_caps.items():
            key = f"guardrail:spend:{provider}:{today}"
            try:
                current = float(r.get(key) or 0)
            except Exception:
                current = 0.0
            pct = (current / cap * 100) if cap > 0 else 0.0
            summary["providers"][provider] = {
                "spent": round(current, 2),
                "cap": cap,
                "pct": round(pct, 1),
                "blocked": current >= cap,
            }

        for lane, cap in self._lane_caps.items():
            key = f"guardrail:lane:{lane}:{today}"
            try:
                current = float(r.get(key) or 0)
            except Exception:
                current = 0.0
            pct = (current / cap * 100) if cap > 0 else 0.0
            summary["lanes"][lane] = {
                "spent": round(current, 2),
                "cap": cap,
                "pct": round(pct, 1),
                "blocked": current >= cap,
            }

        return summary
