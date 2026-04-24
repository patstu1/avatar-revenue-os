"""Digital Twin / Simulation Engine — scenario gen, outcome/risk/confidence estimation. Pure functions."""

from __future__ import annotations

from typing import Any

SCENARIO_TYPES = [
    "push_volume_vs_launch_account",
    "switch_content_form_vs_keep",
    "push_offer_vs_switch_offer",
    "premium_vs_cheap_asset",
    "push_winner_vs_wait",
    "expand_platform_vs_deepen",
    "keep_campaign_vs_suppress",
    "page_a_vs_page_b",
]


def generate_scenarios(system_state: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate simulation scenarios from current system state."""
    scenarios = []

    for acct in system_state.get("scaling_accounts", []):
        scenarios.append(
            _pair(
                "push_volume_vs_launch_account",
                {
                    "label": f"Push volume on {acct.get('name', 'acct')}",
                    "upside": 30,
                    "cost": 5,
                    "risk": 0.2,
                    "time": 7,
                },
                {"label": "Launch new account instead", "upside": 20, "cost": 15, "risk": 0.4, "time": 30},
                acct,
            )
        )

    for winner in system_state.get("experiment_winners", []):
        conf = float(winner.get("confidence", 0.7))
        scenarios.append(
            _pair(
                "push_winner_vs_wait",
                {
                    "label": f"Promote winner now (conf={conf:.0%})",
                    "upside": 40,
                    "cost": 3,
                    "risk": 1 - conf,
                    "time": 3,
                },
                {"label": "Wait for more evidence", "upside": 45, "cost": 1, "risk": 0.1, "time": 21},
                winner,
            )
        )

    for offer in system_state.get("offers", []):
        rank = float(offer.get("rank_score", 0.5))
        if rank < 0.4:
            scenarios.append(
                _pair(
                    "push_offer_vs_switch_offer",
                    {
                        "label": f"Keep current offer (rank={rank:.2f})",
                        "upside": rank * 50,
                        "cost": 2,
                        "risk": 0.3,
                        "time": 7,
                    },
                    {"label": "Switch to higher-ranked offer", "upside": 35, "cost": 5, "risk": 0.2, "time": 7},
                    offer,
                )
            )

    for camp in system_state.get("weak_campaigns", []):
        scenarios.append(
            _pair(
                "keep_campaign_vs_suppress",
                {
                    "label": f"Keep campaign {camp.get('name', '')[:30]}",
                    "upside": 10,
                    "cost": 8,
                    "risk": 0.4,
                    "time": 14,
                },
                {"label": "Suppress and reallocate budget", "upside": 25, "cost": 2, "risk": 0.15, "time": 3},
                camp,
            )
        )

    return scenarios


def _pair(stype: str, a: dict, b: dict, context: dict) -> dict[str, Any]:
    return {"scenario_type": stype, "option_a": a, "option_b": b, "context": context}


def estimate_outcome(option: dict[str, Any]) -> dict[str, Any]:
    """Estimate the outcome of a single option."""
    upside = float(option.get("upside", 0))
    cost = float(option.get("cost", 0))
    risk = float(option.get("risk", 0.3))

    profit = upside - cost
    risk_adjusted = profit * (1 - risk)
    confidence = max(0.1, min(0.95, 0.5 + (1 - risk) * 0.3 - cost / 100))

    return {
        "expected_profit": round(profit, 2),
        "risk_adjusted_profit": round(risk_adjusted, 2),
        "confidence": round(confidence, 3),
        "time_to_signal_days": int(option.get("time", 14)),
    }


def compare_options(option_a: dict, option_b: dict) -> dict[str, Any]:
    """Compare two options and recommend the better one."""
    oa = estimate_outcome(option_a)
    ob = estimate_outcome(option_b)

    a_score = oa["risk_adjusted_profit"] * oa["confidence"]
    b_score = ob["risk_adjusted_profit"] * ob["confidence"]

    if a_score > b_score:
        winner = "a"
        delta = a_score - b_score
        explanation = f"Option A ({option_a['label']}) has higher expected risk-adjusted return"
    elif b_score > a_score:
        winner = "b"
        delta = b_score - a_score
        explanation = f"Option B ({option_b['label']}) has higher expected risk-adjusted return"
    else:
        winner = "tie"
        delta = 0
        explanation = "Options are equivalent — decide based on strategic preference"

    missing = []
    if oa["confidence"] < 0.5:
        missing.append(f"Low confidence on {option_a['label']} — need more performance data")
    if ob["confidence"] < 0.5:
        missing.append(f"Low confidence on {option_b['label']} — need more performance data")

    return {
        "winner": winner,
        "profit_delta": round(delta, 2),
        "option_a_outcome": oa,
        "option_b_outcome": ob,
        "explanation": explanation,
        "missing_evidence": missing,
        "recommendation": option_a["label"]
        if winner == "a"
        else option_b["label"]
        if winner == "b"
        else "Either — needs more data",
    }


def build_recommendation(scenario: dict[str, Any]) -> dict[str, Any]:
    """Build a full recommendation from a scenario comparison."""
    comparison = compare_options(scenario["option_a"], scenario["option_b"])
    return {
        "scenario_type": scenario["scenario_type"],
        "recommended_action": comparison["recommendation"],
        "expected_profit_delta": comparison["profit_delta"],
        "confidence": comparison["option_a_outcome"]["confidence"]
        if comparison["winner"] == "a"
        else comparison["option_b_outcome"]["confidence"],
        "missing_evidence": comparison["missing_evidence"],
        "explanation": comparison["explanation"],
    }
