"""Content Scheduling Engine — optimal posting times, slot management, anti-collision.

Determines the best time to publish content per platform and prevents multiple
accounts from posting at the same minute.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Any

OPTIMAL_POSTING_WINDOWS: dict[str, list[tuple[int, int]]] = {
    "youtube": [(8, 10), (12, 14), (17, 19)],
    "tiktok": [(7, 9), (11, 13), (19, 22)],
    "instagram": [(8, 10), (11, 13), (17, 19)],
    "x": [(8, 10), (12, 14), (17, 19)],
    "linkedin": [(7, 9), (12, 13), (17, 18)],
    "reddit": [(6, 8), (12, 14), (20, 22)],
    "pinterest": [(14, 16), (20, 22)],
}

TIMEZONE_OFFSETS: dict[str, int] = {
    "US_EAST": -5,
    "US_CENTRAL": -6,
    "US_MOUNTAIN": -7,
    "US_PACIFIC": -8,
    "UK": 0,
    "EU_CENTRAL": 1,
    "AUSTRALIA": 10,
    "INDIA": 5,
}


def get_optimal_publish_time(
    platform: str,
    account_id: str,
    target_timezone: str = "US_EAST",
    now: datetime | None = None,
) -> datetime:
    """Calculate the next optimal publish time for an account on a platform.

    Uses account_id hash to jitter times so no two accounts post at the same minute.
    """
    now = now or datetime.now(timezone.utc)
    tz_offset = TIMEZONE_OFFSETS.get(target_timezone, -5)
    local_hour = (now.hour + tz_offset) % 24

    windows = OPTIMAL_POSTING_WINDOWS.get(platform.lower(), [(9, 11), (17, 19)])

    best_window = None
    for start, end in windows:
        if local_hour < start:
            best_window = (start, end)
            break
    if not best_window:
        best_window = windows[0]
        now = now + timedelta(days=1)

    seed = int(hashlib.sha256(account_id.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    target_hour = rng.randint(best_window[0], best_window[1] - 1)
    target_minute = rng.randint(0, 59)

    target_local = now.replace(hour=0, minute=0, second=0, microsecond=0)
    target_local = target_local.replace(hour=(target_hour - tz_offset) % 24, minute=target_minute)

    if target_local <= now:
        target_local += timedelta(days=1)

    return target_local


def check_slot_collision(
    proposed_time: datetime,
    existing_schedule: list[datetime],
    min_gap_minutes: int = 5,
) -> dict[str, Any]:
    """Check if a proposed publish time collides with existing schedule."""
    for existing in existing_schedule:
        gap = abs((proposed_time - existing).total_seconds()) / 60
        if gap < min_gap_minutes:
            return {"collision": True, "conflicting_time": existing.isoformat(), "gap_minutes": gap}
    return {"collision": False}


def resolve_collision(
    proposed_time: datetime,
    existing_schedule: list[datetime],
    min_gap_minutes: int = 5,
) -> datetime:
    """Shift a proposed time forward until it doesn't collide."""
    adjusted = proposed_time
    max_shifts = 20
    for _ in range(max_shifts):
        collision = check_slot_collision(adjusted, existing_schedule, min_gap_minutes)
        if not collision["collision"]:
            return adjusted
        adjusted += timedelta(minutes=min_gap_minutes)
    return adjusted


def build_daily_schedule(
    accounts: list[dict[str, str]],
    platform: str,
    posts_per_account: int = 1,
    target_timezone: str = "US_EAST",
) -> list[dict[str, Any]]:
    """Build a collision-free daily schedule for multiple accounts on one platform."""
    schedule: list[dict[str, Any]] = []
    booked_times: list[datetime] = []

    for acct in accounts:
        for post_num in range(posts_per_account):
            seed_id = f"{acct['account_id']}_{post_num}"
            proposed = get_optimal_publish_time(platform, seed_id, target_timezone)
            final_time = resolve_collision(proposed, booked_times)
            booked_times.append(final_time)
            schedule.append(
                {
                    "account_id": acct["account_id"],
                    "account_username": acct.get("username", ""),
                    "platform": platform,
                    "scheduled_at": final_time.isoformat(),
                    "post_number": post_num + 1,
                }
            )

    schedule.sort(key=lambda s: s["scheduled_at"])
    return schedule
