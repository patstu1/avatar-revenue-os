"""Expansion gatekeeper: deterministic primary gate + deferred expansion commands.

Business inputs mix first-class DB counts with proxies where list/email telemetry
is not modeled — see docs/16-growth-pack-architecture.md."""
from __future__ import annotations
from typing import Any, Optional

from packages.scoring.growth_commander import COMMANDER_SOURCE, rank_commands

EXPANSION_TYPES = frozenset({
    "launch_account", "shift_platform", "shift_niche", "increase_output",
})


def compute_gatekeeper_inputs(
    *,
    accounts: list[dict],
    offer_count: int,
    sponsor_profile_count: int,
    sponsor_open_deal_count: int,
    audience_segment_total_estimated_size: int,
    readiness: Optional[dict],
    trust_avg: float,
    leak_count: int,
    scale_rec: dict,
) -> dict[str, Any]:
    """Derive gatekeeper signals. Scores are 0–100 unless noted."""
    readiness_score = float((readiness or {}).get("launch_readiness_score") or 0)
    inc_new = float(scale_rec.get("incremental_profit_new_account") or 0)
    inc_vol = float(scale_rec.get("incremental_profit_existing_push") or 0)
    expansion_favored = inc_new >= inc_vol * 0.85 and inc_new > 0

    # Owned-audience readiness: trust + audience_segments estimated_size (first-class count proxy);
    # no dedicated email/SMS subscriber table — segment rollups are the system signal when present.
    seg = int(audience_segment_total_estimated_size or 0)
    segment_boost = min(35.0, (seg ** 0.5) * 1.8) if seg > 0 else 0.0
    owned_audience_readiness_score = min(
        100.0,
        trust_avg * 0.5 + segment_boost + min(15.0, offer_count * 4.0),
    )

    # Sponsor inventory: first-class counts from sponsor_profiles + sponsor_opportunities.
    sponsor_inventory_readiness_score = min(
        100.0,
        sponsor_profile_count * 16.0 + sponsor_open_deal_count * 20.0,
    )

    # Operator bandwidth: proxy from posting_capacity * (1+fatigue) load per account.
    n = max(1, len(accounts))
    load = 0.0
    for a in accounts:
        cap = float(a.get("posting_capacity_per_day") or 2)
        fat = float(a.get("fatigue_score") or 0)
        load += cap * (1.0 + min(1.0, fat))
    operator_bandwidth_score = max(0.0, 100.0 - min(100.0, (load / n) * 5.5))

    # Comfort / underused upside pressure: margin opportunity vs pushing existing.
    if inc_vol > 1e-6:
        ratio = inc_new / inc_vol
        upside_pressure_score = min(100.0, max(0.0, (ratio - 0.75) * 45.0 + 48.0))
    else:
        upside_pressure_score = min(100.0, 35.0 + inc_new * 1.5)

    return {
        "owned_audience_readiness_score": round(owned_audience_readiness_score, 1),
        "sponsor_inventory_readiness_score": round(sponsor_inventory_readiness_score, 1),
        "operator_bandwidth_score": round(operator_bandwidth_score, 1),
        "upside_pressure_score": round(upside_pressure_score, 1),
        "readiness_score": readiness_score,
        "leak_count": leak_count,
        "offer_count": offer_count,
        "sponsor_profile_count": sponsor_profile_count,
        "sponsor_open_deal_count": sponsor_open_deal_count,
        "audience_segment_total_estimated_size": seg,
        "expansion_favored": expansion_favored,
        "incremental_profit_new_account": inc_new,
        "incremental_profit_existing_push": inc_vol,
        "input_class": {
            "owned_audience_readiness": "proxy_plus_segments",
            "sponsor_inventory": "first_class_counts",
            "operator_bandwidth": "proxy_posting_load",
            "upside_pressure": "derived_from_incremental_profits",
        },
    }


def pick_primary_gate(
    gatekeeper: dict[str, Any],
    *,
    has_high_cannibalization: bool,
) -> tuple[str, str]:
    """Return (gate_key, explanation). Priority: funnel → overlap → monetization → owned_audience → capacity."""
    rs = float(gatekeeper.get("readiness_score") or 100)
    leaks = int(gatekeeper.get("leak_count") or 0)
    if rs > 0 and rs < 50:
        return ("funnel", "Launch readiness score below 50 — improve funnel before expanding account footprint.")
    if leaks > 8:
        return ("funnel", "Unresolved revenue leak volume is high — stabilize funnel before expansion.")
    if has_high_cannibalization:
        return ("overlap", "High same-platform topic overlap — consolidate or differentiate before new launches.")
    offers = int(gatekeeper.get("offer_count") or 0)
    if offers < 2 and gatekeeper.get("expansion_favored"):
        return ("monetization", "Offer catalog is thin while expansion is margin-favored — improve monetization depth first.")
    oa = float(gatekeeper.get("owned_audience_readiness_score") or 100)
    if oa < 38:
        return ("owned_audience", "Owned-audience capture readiness is below threshold — strengthen capture before new rented reach.")
    bw = float(gatekeeper.get("operator_bandwidth_score") or 100)
    if bw < 28:
        return ("capacity", "Operator bandwidth proxy indicates capacity constraints — hold net-new expansion.")
    sp = float(gatekeeper.get("sponsor_inventory_readiness_score") or 100)
    if sp < 22 and offers >= 2 and gatekeeper.get("expansion_favored"):
        return ("monetization", "Sponsor inventory is thin for brand-safe expansion — build sponsor pipeline or diversify monetization.")
    return ("none", "")


def _defer_expansion_command(cmd: dict, gate_key: str, explanation: str) -> dict:
    orig = cmd.get("command_type")
    ev = dict(cmd.get("evidence") or {})
    ev["gating_primary"] = gate_key
    ev["gating_explanation"] = explanation
    ev["deferred_from_command_type"] = orig
    ev["gatekeeper"] = True
    return {
        **cmd,
        "command_type": "do_nothing",
        "priority": min(int(cmd.get("priority") or 50), 41),
        "title": f"DEFERRED EXPANSION ({gate_key}) — was: {orig}",
        "exact_instruction": (
            f"Gating ({gate_key}): {explanation} "
            f"Do not execute expansion until the primary gate clears. "
            f"Original intent: {str(cmd.get('exact_instruction', ''))[:400]}"
        ),
        "rationale": (cmd.get("rationale") or "") + f" [Deferred: {gate_key}]",
        "evidence": ev,
        COMMANDER_SOURCE: True,
    }


def apply_gatekeeper_to_commands(
    commands: list[dict],
    gatekeeper: dict[str, Any],
    *,
    has_high_cannibalization: bool,
    brand_niche: Optional[str],
) -> list[dict]:
    """Suppress or defer expansion commands when a primary gate is active."""
    gate_key, explanation = pick_primary_gate(gatekeeper, has_high_cannibalization=has_high_cannibalization)
    if gate_key == "none":
        for c in commands:
            ev = c.get("evidence")
            if isinstance(ev, dict):
                ev.setdefault("gatekeeper_context", gatekeeper)
        return rank_commands(commands)

    out: list[dict] = []
    for c in commands:
        ct = c.get("command_type")
        if ct in EXPANSION_TYPES:
            out.append(_defer_expansion_command(c, gate_key, explanation))
        elif ct == "fix_funnel_first" and gate_key == "funnel":
            ev = dict(c.get("evidence") or {})
            ev.setdefault("gating_primary", "funnel")
            ev["gating_explanation"] = explanation
            c2 = {**c, "evidence": ev}
            out.append(c2)
        else:
            ev = c.get("evidence")
            if isinstance(ev, dict):
                ev.setdefault("gating_primary", gate_key)
                ev.setdefault("gating_explanation", explanation)
            out.append(c)

    for c in out:
        ev = c.get("evidence")
        if isinstance(ev, dict):
            ev.setdefault("gatekeeper_context", gatekeeper)

    return rank_commands(out)


def gatekeeper_blocker_rows(gate_key: str, explanation: str, gatekeeper: dict[str, Any]) -> list[dict[str, Any]]:
    """Extra pack blocker rows for active gate + signal summaries."""
    if gate_key == "none":
        return []
    severity = "critical" if gate_key in ("funnel", "capacity", "overlap") else "high"
    rows = [{
        "blocker_type": f"gatekeeper_{gate_key}",
        "severity": severity,
        "affected_scope_type": "portfolio",
        "affected_scope_id": None,
        "reason": explanation,
        "recommended_fix": "Clear primary gate before executing deferred expansion commands.",
        "expected_impact_json": {"gate_key": gate_key, "gatekeeper_scores": {
            "owned_audience": gatekeeper.get("owned_audience_readiness_score"),
            "sponsor_inventory": gatekeeper.get("sponsor_inventory_readiness_score"),
            "operator_bandwidth": gatekeeper.get("operator_bandwidth_score"),
            "upside_pressure": gatekeeper.get("upside_pressure_score"),
        }},
        "confidence_score": 0.88,
        "urgency_score": 92.0 if severity == "critical" else 78.0,
    }]
    return rows
