"""Opportunity-Cost Ranking Engine — score actions by what is lost by waiting.

Pure functions. No I/O.
"""

from __future__ import annotations

from typing import Any

ACTION_TYPES = [
    "push_volume",
    "launch_account",
    "switch_content_form",
    "promote_winner",
    "kill_weak_lane",
    "activate_monetization",
    "fix_blocker",
    "run_experiment",
    "upgrade_provider",
    "publish_asset",
]

SAFE_WAIT_THRESHOLD = 0.25
URGENT_THRESHOLD = 0.70

DELAY_PROFILES = {
    "push_volume": {"base_daily": 5.0, "decay": 0.02, "sensitivity": "normal"},
    "launch_account": {"base_daily": 2.0, "decay": 0.01, "sensitivity": "low"},
    "switch_content_form": {"base_daily": 3.0, "decay": 0.03, "sensitivity": "normal"},
    "promote_winner": {"base_daily": 8.0, "decay": 0.05, "sensitivity": "high"},
    "kill_weak_lane": {"base_daily": 6.0, "decay": 0.04, "sensitivity": "high"},
    "activate_monetization": {"base_daily": 10.0, "decay": 0.06, "sensitivity": "critical"},
    "fix_blocker": {"base_daily": 12.0, "decay": 0.08, "sensitivity": "critical"},
    "run_experiment": {"base_daily": 1.0, "decay": 0.01, "sensitivity": "low"},
    "upgrade_provider": {"base_daily": 2.0, "decay": 0.02, "sensitivity": "normal"},
    "publish_asset": {"base_daily": 4.0, "decay": 0.03, "sensitivity": "normal"},
}


def generate_candidates(system_state: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate action candidates from current system state."""
    candidates: list[dict[str, Any]] = []

    for acct in system_state.get("accounts", []):
        state = acct.get("state", "warming")
        name = acct.get("name", "unknown")
        aid = acct.get("id")

        if state == "scaling":
            candidates.append(
                {
                    "action_type": "push_volume",
                    "action_key": f"volume:{name}",
                    "target_id": aid,
                    "expected_upside": 30,
                    "confidence": 0.7,
                }
            )
        if state == "weak":
            candidates.append(
                {
                    "action_type": "kill_weak_lane",
                    "action_key": f"kill:{name}",
                    "target_id": aid,
                    "expected_upside": 15,
                    "confidence": 0.8,
                }
            )
        if state in ("monetizing", "scaling"):
            candidates.append(
                {
                    "action_type": "activate_monetization",
                    "action_key": f"monetize:{name}",
                    "target_id": aid,
                    "expected_upside": 50,
                    "confidence": 0.6,
                }
            )

    for winner in system_state.get("experiment_winners", []):
        candidates.append(
            {
                "action_type": "promote_winner",
                "action_key": f"promote:{winner.get('name', 'exp')}",
                "target_id": winner.get("id"),
                "expected_upside": 40,
                "confidence": float(winner.get("confidence", 0.8)),
            }
        )

    for blocker in system_state.get("blockers", []):
        candidates.append(
            {
                "action_type": "fix_blocker",
                "action_key": f"fix:{blocker.get('name', 'blocker')}",
                "target_id": blocker.get("id"),
                "expected_upside": 25,
                "confidence": 0.9,
            }
        )

    for exp in system_state.get("pending_experiments", []):
        candidates.append(
            {
                "action_type": "run_experiment",
                "action_key": f"exp:{exp.get('name', 'test')}",
                "target_id": exp.get("id"),
                "expected_upside": 15,
                "confidence": 0.4,
            }
        )

    for asset in system_state.get("ready_assets", []):
        candidates.append(
            {
                "action_type": "publish_asset",
                "action_key": f"publish:{asset.get('title', 'asset')[:30]}",
                "target_id": asset.get("id"),
                "expected_upside": 20,
                "confidence": 0.7,
            }
        )

    return candidates


def score_upside(candidate: dict[str, Any]) -> float:
    """Score expected upside on 0-1 scale."""
    raw = float(candidate.get("expected_upside", 0) or 0)
    return round(min(1.0, raw / 50), 3)


def score_cost_of_delay(candidate: dict[str, Any]) -> dict[str, Any]:
    """Score what is lost per day by not doing this action."""
    atype = candidate.get("action_type", "")
    profile = DELAY_PROFILES.get(atype, {"base_daily": 3.0, "decay": 0.02, "sensitivity": "normal"})

    upside = float(candidate.get("expected_upside", 0) or 0)
    daily = round(profile["base_daily"] * (1 + upside / 100), 2)
    weekly = round(daily * 7, 2)

    return {
        "daily_cost": daily,
        "weekly_cost": weekly,
        "decay_rate": profile["decay"],
        "time_sensitivity": profile["sensitivity"],
    }


def score_urgency(candidate: dict[str, Any], delay_info: dict[str, Any]) -> float:
    """Score urgency on 0-1 scale based on delay cost and sensitivity."""
    sensitivity_map = {"critical": 1.0, "high": 0.75, "normal": 0.5, "low": 0.25}
    sens = sensitivity_map.get(delay_info.get("time_sensitivity", "normal"), 0.5)
    daily = float(delay_info.get("daily_cost", 0) or 0)
    confidence = float(candidate.get("confidence", 0.5) or 0.5)

    raw = 0.40 * sens + 0.35 * min(1.0, daily / 15) + 0.25 * confidence
    return round(min(1.0, raw), 3)


def rank_actions(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank all candidates by composite score. Returns sorted list with positions."""
    scored = []
    for c in candidates:
        upside = score_upside(c)
        delay = score_cost_of_delay(c)
        urgency = score_urgency(c, delay)
        confidence = float(c.get("confidence", 0.5) or 0.5)

        composite = round(
            0.30 * upside + 0.30 * min(1.0, delay["daily_cost"] / 15) + 0.25 * urgency + 0.15 * confidence,
            4,
        )

        safe = composite < SAFE_WAIT_THRESHOLD
        atype = c.get("action_type", "")
        akey = c.get("action_key", "")

        explanation_parts = [
            f"{atype}:{akey}",
            f"upside={upside:.2f}",
            f"delay=${delay['daily_cost']:.0f}/day",
            f"urgency={urgency:.2f}",
            f"confidence={confidence:.2f}",
        ]
        if safe:
            explanation_parts.append("SAFE TO WAIT")

        scored.append(
            {
                **c,
                "expected_upside": upside,
                "cost_of_delay": delay["daily_cost"],
                "urgency": urgency,
                "confidence": confidence,
                "composite_rank": composite,
                "safe_to_wait": safe,
                "delay_info": delay,
                "explanation": " | ".join(explanation_parts),
            }
        )

    scored.sort(key=lambda x: -x["composite_rank"])
    for i, s in enumerate(scored):
        s["rank_position"] = i + 1

    return scored


def build_report(ranked: list[dict[str, Any]]) -> dict[str, Any]:
    """Build summary report from ranked actions."""
    total_cost = sum(r.get("cost_of_delay", 0) for r in ranked)
    safe_count = sum(1 for r in ranked if r.get("safe_to_wait"))
    top_type = ranked[0]["action_type"] if ranked else None

    return {
        "total_actions": len(ranked),
        "top_action_type": top_type,
        "total_opportunity_cost": round(total_cost, 2),
        "safe_to_wait_count": safe_count,
        "summary": f"{len(ranked)} actions ranked. ${total_cost:.0f}/day total opportunity cost. {safe_count} can safely wait. Top priority: {top_type or 'none'}",
    }
