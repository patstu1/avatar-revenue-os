"""Failure-Family Suppression Engine — cluster, detect, suppress, decay.

Pure functions. No I/O.
"""
from __future__ import annotations
from typing import Any, Optional
from collections import defaultdict
from datetime import datetime, timedelta, timezone

FAMILY_TYPES = [
    "hook_type", "content_form", "offer_angle", "cta_style",
    "platform_mismatch", "publish_timing", "avatar_mode",
    "creative_structure", "monetization_path",
]

SUPPRESSION_THRESHOLD = 3
PERSISTENT_THRESHOLD = 6
TEMPORARY_DAYS = 30
PERSISTENT_DAYS = 90

ALTERNATIVE_MAP = {
    "hook_type": "Try a different hook family — curiosity, comparison, or authority-led",
    "content_form": "Switch to a different content form — carousel, long-form, or demo",
    "offer_angle": "Pivot to a different offer angle — budget, proof-led, or convenience",
    "cta_style": "Test a softer or harder CTA — save/share vs direct-link",
    "platform_mismatch": "Move this content type to a better-fit platform",
    "publish_timing": "Shift posting window to a tested high-engagement slot",
    "avatar_mode": "Try the opposite — avatar if faceless failed, faceless if avatar failed",
    "creative_structure": "Switch structure — listicle, before/after, or problem-solution",
    "monetization_path": "Test a different monetization path — affiliate vs lead-gen vs premium",
}


def cluster_failures(
    failing_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group failing content into families by shared attributes."""
    groups: dict[str, list[dict]] = defaultdict(list)

    for item in failing_items:
        for ftype in FAMILY_TYPES:
            val = item.get(ftype)
            if val:
                key = f"{ftype}:{val}"
                groups[key].append(item)

    families = []
    for key, members in groups.items():
        ftype, fkey = key.split(":", 1)
        avg_fail = sum(float(m.get("fail_score", 0) or 0) for m in members) / max(1, len(members))
        families.append({
            "family_type": ftype,
            "family_key": fkey,
            "failure_count": len(members),
            "avg_fail_score": round(avg_fail, 3),
            "members": members,
            "first_seen_at": min((m.get("created_at") for m in members if m.get("created_at")), default=None),
            "last_seen_at": max((m.get("created_at") for m in members if m.get("created_at")), default=None),
        })

    return sorted(families, key=lambda f: (-f["failure_count"], -f["avg_fail_score"]))


def detect_repeat_failures(
    families: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Identify families that have hit the suppression threshold."""
    repeats = []
    for f in families:
        if f["failure_count"] >= SUPPRESSION_THRESHOLD:
            repeats.append({
                **f,
                "should_suppress": True,
                "mode": "persistent" if f["failure_count"] >= PERSISTENT_THRESHOLD else "temporary",
            })
    return repeats


def build_suppression_rules(
    repeat_families: list[dict[str, Any]],
    now: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    """Generate suppression rules for repeat-failure families."""
    now = now or datetime.now(timezone.utc)
    rules = []

    for f in repeat_families:
        if not f.get("should_suppress"):
            continue
        mode = f.get("mode", "temporary")
        days = PERSISTENT_DAYS if mode == "persistent" else TEMPORARY_DAYS
        expires = now + timedelta(days=days)

        rules.append({
            "family_type": f["family_type"],
            "family_key": f["family_key"],
            "suppression_mode": mode,
            "retest_after_days": days,
            "expires_at": expires,
            "reason": f"{f['family_type']}:{f['family_key']} failed {f['failure_count']} times (avg score {f['avg_fail_score']:.2f})",
            "recommended_alternative": ALTERNATIVE_MAP.get(f["family_type"], "Try a different approach"),
        })

    return rules


def check_suppression_decay(
    rules: list[dict[str, Any]],
    now: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    """Check which suppression rules have expired and can be retested."""
    now = now or datetime.now(timezone.utc)
    expired = []
    for r in rules:
        exp = r.get("expires_at")
        if exp and exp <= now:
            expired.append({
                "family_type": r["family_type"],
                "family_key": r["family_key"],
                "reason": "suppression_expired",
                "recommendation": f"Retest {r['family_type']}:{r['family_key']} — suppression period ended",
            })
    return expired


def is_suppressed(
    family_type: str,
    family_key: str,
    active_rules: list[dict[str, Any]],
) -> bool:
    """Check if a specific family is currently suppressed."""
    for r in active_rules:
        if r.get("family_type") == family_type and r.get("family_key") == family_key and r.get("is_active", True):
            return True
    return False


def get_active_suppressions(
    active_rules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return all active suppressions with reasons and retest dates."""
    return [
        {
            "family_type": r["family_type"],
            "family_key": r["family_key"],
            "mode": r.get("suppression_mode", "temporary"),
            "reason": r.get("reason", ""),
            "retest_after": str(r.get("expires_at", "")),
            "alternative": ALTERNATIVE_MAP.get(r["family_type"], ""),
        }
        for r in active_rules if r.get("is_active", True)
    ]
