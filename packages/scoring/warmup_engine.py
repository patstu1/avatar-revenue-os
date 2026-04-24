"""Account Warmup Engine — safe, gradual account scaling to avoid platform bans.

Phases: seed → trickle → build → accelerate → scale
Each phase has strict posting limits and engagement requirements.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

WARMUP_PHASES = {
    "seed": {"day_range": (0, 3), "max_posts_per_day": 0, "engagement_required": True, "monetization_allowed": False, "description": "Profile setup, follow accounts, engage with niche content"},
    "trickle": {"day_range": (4, 14), "max_posts_per_day": 1, "engagement_required": True, "monetization_allowed": False, "description": "1 post/day, short-form only, no links"},
    "build": {"day_range": (15, 30), "max_posts_per_day": 2, "engagement_required": True, "monetization_allowed": True, "description": "2 posts/day, introduce links gradually"},
    "accelerate": {"day_range": (31, 60), "max_posts_per_day": 4, "engagement_required": False, "monetization_allowed": True, "description": "3-4 posts/day, full monetization"},
    "scale": {"day_range": (61, 9999), "max_posts_per_day": 10, "engagement_required": False, "monetization_allowed": True, "description": "System-determined cadence based on performance"},
}

PLATFORM_WARMUP_OVERRIDES = {
    "tiktok": {"trickle": {"max_posts_per_day": 1}, "build": {"max_posts_per_day": 2}, "accelerate": {"max_posts_per_day": 3}},
    "instagram": {"trickle": {"max_posts_per_day": 1}, "build": {"max_posts_per_day": 2}, "accelerate": {"max_posts_per_day": 3}},
    "youtube": {"trickle": {"max_posts_per_day": 1}, "build": {"max_posts_per_day": 1}, "accelerate": {"max_posts_per_day": 2}},
    "x": {"trickle": {"max_posts_per_day": 2}, "build": {"max_posts_per_day": 4}, "accelerate": {"max_posts_per_day": 6}},
    "linkedin": {"trickle": {"max_posts_per_day": 1}, "build": {"max_posts_per_day": 1}, "accelerate": {"max_posts_per_day": 2}},
}


def determine_warmup_phase(account_created_at: datetime, now: datetime | None = None) -> dict[str, Any]:
    """Determine the current warmup phase for an account based on its age."""
    now = now or datetime.now(timezone.utc)
    if account_created_at.tzinfo is None:
        account_created_at = account_created_at.replace(tzinfo=timezone.utc)
    age_days = (now - account_created_at).days

    current_phase = "seed"
    for phase_name, config in WARMUP_PHASES.items():
        low, high = config["day_range"]
        if low <= age_days <= high:
            current_phase = phase_name
            break

    config = WARMUP_PHASES[current_phase]
    return {
        "phase": current_phase,
        "age_days": age_days,
        "max_posts_per_day": config["max_posts_per_day"],
        "engagement_required": config["engagement_required"],
        "monetization_allowed": config["monetization_allowed"],
        "description": config["description"],
    }


def get_daily_post_limit(account_created_at: datetime, platform: str, now: datetime | None = None) -> int:
    """Get the maximum posts allowed today for an account."""
    phase_info = determine_warmup_phase(account_created_at, now)
    phase = phase_info["phase"]
    base_limit = phase_info["max_posts_per_day"]

    overrides = PLATFORM_WARMUP_OVERRIDES.get(platform.lower(), {})
    phase_override = overrides.get(phase, {})
    return phase_override.get("max_posts_per_day", base_limit)


def can_post_now(account_created_at: datetime, platform: str, posts_today: int, now: datetime | None = None) -> dict[str, Any]:
    """Check if an account can post right now given warmup constraints."""
    limit = get_daily_post_limit(account_created_at, platform, now)
    phase = determine_warmup_phase(account_created_at, now)

    if posts_today >= limit:
        return {"allowed": False, "reason": f"Daily limit reached ({posts_today}/{limit})", "phase": phase["phase"], "limit": limit}
    return {"allowed": True, "remaining": limit - posts_today, "phase": phase["phase"], "limit": limit}


def can_monetize(account_created_at: datetime, now: datetime | None = None) -> bool:
    """Check if an account is allowed to include monetization links."""
    phase = determine_warmup_phase(account_created_at, now)
    return phase["monetization_allowed"]


def detect_shadow_ban(recent_metrics: list[dict[str, Any]], baseline_impressions: float = 100) -> dict[str, Any]:
    """Detect potential shadow-ban from engagement metrics."""
    if not recent_metrics or len(recent_metrics) < 3:
        return {"detected": False, "reason": "insufficient data"}

    recent_impressions = [m.get("impressions", 0) for m in recent_metrics[-5:]]
    avg_recent = sum(recent_impressions) / len(recent_impressions) if recent_impressions else 0

    older_impressions = [m.get("impressions", 0) for m in recent_metrics[:-5]] if len(recent_metrics) > 5 else []
    avg_older = sum(older_impressions) / len(older_impressions) if older_impressions else baseline_impressions

    if avg_older > 0 and avg_recent / max(avg_older, 1) < 0.3:
        return {"detected": True, "severity": "high", "reason": f"Impressions dropped {((1 - avg_recent/max(avg_older,1)) * 100):.0f}%", "recommendation": "throttle_and_cooldown"}

    zero_reach = sum(1 for m in recent_metrics[-3:] if m.get("impressions", 0) == 0)
    if zero_reach >= 2:
        return {"detected": True, "severity": "critical", "reason": f"{zero_reach}/3 recent posts have zero impressions", "recommendation": "pause_7_days"}

    return {"detected": False, "reason": "metrics within normal range"}


def generate_cooldown_plan(severity: str) -> dict[str, Any]:
    """Generate a recovery plan after shadow-ban detection."""
    if severity == "critical":
        return {"pause_days": 7, "resume_phase": "trickle", "monetization_pause": True, "engagement_boost": True}
    return {"pause_days": 3, "resume_phase": "build", "monetization_pause": True, "engagement_boost": True}
