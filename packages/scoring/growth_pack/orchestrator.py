"""Orchestrates deterministic growth pack outputs from shared context."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from packages.scoring.growth_pack.platform_os import normalize_platform, platform_spec
from packages.scoring.scale import niche_jaccard


def _rev_range(cmd: dict) -> tuple[float, float]:
    ev = cmd.get("evidence") or {}
    if isinstance(ev.get("rev_range"), (list, tuple)) and len(ev["rev_range"]) >= 2:
        return float(ev["rev_range"][0]), float(ev["rev_range"][1])
    up = float(cmd.get("expected_upside") or 0)
    return max(0.0, up * 0.5), max(0.0, up)


def _consequence(command_type: str) -> dict[str, Any]:
    return {
        "launch_account": {
            "revenue": "Delayed channel learning; competitor capture on platform.",
            "ops": "Team assumes portfolio is complete; misallocated creative capacity.",
        },
        "increase_output": {
            "revenue": "Leaves incremental profit from winners on the table.",
            "ops": "Underutilized posting capacity on proven account.",
        },
        "fix_funnel_first": {
            "revenue": "Scaling amplifies leak — net profit may decline.",
            "ops": "Wasted ad/creative spend driving to broken paths.",
        },
        "do_nothing": {
            "revenue": "Opportunity cost if market moves; monitor cycle risk.",
            "ops": "None if data truly supports hold.",
        },
    }.get(command_type, {"revenue": "Missed upside or unresolved drag.", "ops": "Portfolio drift."})


def canonical_fields_from_command(
    cmd: dict,
    *,
    deadline_days: int = 7,
) -> dict[str, Any]:
    """Map engine command dict to growth_commands canonical columns."""
    es = cmd.get("execution_spec") or {}
    pf = cmd.get("platform_fit") or {}
    nf = cmd.get("niche_fit") or {}
    mp = cmd.get("monetization_path") or {}
    can = cmd.get("cannibalization_analysis") or {}
    blockers = cmd.get("blocking_factors")
    if not isinstance(blockers, list):
        blockers = []
    rev_min, rev_max = _rev_range(cmd)
    plat = es.get("platform") or pf.get("platform") or ""
    if not plat or plat == "all":
        plat = None
    deadline = datetime.now(timezone.utc) + timedelta(days=deadline_days)
    return {
        "command_priority": int(cmd.get("priority", 50)),
        "action_deadline": deadline,
        "platform": plat,
        "account_type": es.get("content_role") or cmd.get("command_type", ""),
        "niche": (nf.get("niche") or "")[:255] or None,
        "sub_niche": (nf.get("sub_niche") or "")[:255] or None,
        "persona_strategy_json": {"avatar_persona": es.get("avatar_persona_strategy"), "execution_spec": es},
        "monetization_strategy_json": {
            "primary": mp.get("primary_method"),
            "secondary": mp.get("secondary_method"),
            "expected_rpm": mp.get("expected_rpm"),
        },
        "output_requirements_json": {
            "first_week_plan": cmd.get("first_week_plan") or [],
            "posting_strategy": es.get("posting_strategy") or es.get("posting_plan"),
        },
        "success_threshold_json": cmd.get("success_threshold") or {},
        "failure_threshold_json": cmd.get("failure_threshold") or {},
        "expected_revenue_min": rev_min,
        "expected_revenue_max": rev_max,
        "risk_score": float(can.get("risk") or 0),
        "blockers_json": blockers,
        "explanation_json": {
            "title": cmd.get("title"),
            "rationale": cmd.get("rationale"),
            "comparison": cmd.get("comparison"),
            "exact_instruction": cmd.get("exact_instruction"),
        },
        "consequence_if_ignored_json": _consequence(cmd.get("command_type", "")),
        "lifecycle_status": "active",
    }


def build_portfolio_launch_plan(
    *,
    recommended_total: int,
    platform_mix: dict[str, int],
    launch_order: list[dict[str, Any]],
    role_mix: dict[str, int],
    cost_90: float,
    rev_min_90: float,
    rev_max_90: float,
    confidence: float,
    explanation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "recommended_total_account_count": recommended_total,
        "recommended_platform_mix_json": platform_mix,
        "recommended_launch_order_json": launch_order,
        "recommended_role_mix_json": role_mix,
        "estimated_first_90_day_cost": round(cost_90, 2),
        "expected_first_90_day_revenue_min": round(rev_min_90, 2),
        "expected_first_90_day_revenue_max": round(rev_max_90, 2),
        "confidence_score": round(confidence, 4),
        "explanation_json": explanation,
    }


def build_launch_blueprints_from_commands(
    launch_cmds: list[dict],
    brand_niche: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for cmd in launch_cmds[:5]:
        es = cmd.get("execution_spec") or {}
        nf = cmd.get("niche_fit") or {}
        plat = normalize_platform(es.get("platform") or cmd.get("platform_fit", {}).get("platform"))
        spec = platform_spec(plat)
        out.append(
            {
                "platform": plat,
                "account_type": cmd.get("command_type", "launch_account"),
                "niche": nf.get("niche") or brand_niche or "general",
                "sub_niche": nf.get("sub_niche"),
                "persona_strategy_json": {"strategy": es.get("avatar_persona_strategy"), "platform_os": spec},
                "monetization_strategy_json": {
                    "path": cmd.get("monetization_path"),
                    "styles": spec.get("monetization_styles"),
                },
                "content_role": es.get("content_role"),
                "first_30_content_plan_json": [{"week": 1, "beats": ["hook_tests", "offer_bridge", "cta_variant"]}],
                "first_offer_stack_json": [{"tier": "lead_magnet"}, {"tier": "core_offer"}],
                "first_cta_strategy_json": {"primary": "bio_link", "secondary": "pinned_comment"},
                "first_owned_audience_strategy_json": {
                    "capture": "newsletter_or_sms",
                    "reason": "reduce_rented_audience_risk",
                },
                "success_criteria_json": cmd.get("success_threshold") or {},
                "failure_criteria_json": cmd.get("failure_threshold") or {},
                "expected_cost": float(cmd.get("expected_cost") or 0),
                "expected_time_to_signal_days": int(cmd.get("expected_time_to_signal_days") or 21),
                "confidence_score": float(cmd.get("confidence") or 0),
                "explanation_json": {"command": cmd.get("title"), "evidence": cmd.get("evidence")},
            }
        )
    return out


def build_platform_allocation_rows(
    accounts_by_platform: dict[str, int],
    scale_rec: dict[str, Any],
    brand_niche: str,
) -> list[dict[str, Any]]:
    rec_n = int(scale_rec.get("recommended_account_count") or 1)
    max(1, sum(accounts_by_platform.values()))
    rows: list[dict[str, Any]] = []
    for plat, spec in [
        ("tiktok", None),
        ("instagram", None),
        ("youtube", None),
        ("twitter", None),
        ("reddit", None),
        ("linkedin", None),
        ("facebook", None),
    ]:
        cur = accounts_by_platform.get(plat, 0)
        gap = max(0, min(3, rec_n - cur)) if rec_n > cur else 0
        upside = float(scale_rec.get("incremental_profit_new_account") or 0) * (0.15 if cur == 0 else 0.08)
        priority = 90 - cur * 10 + (20 if cur == 0 else 0)
        rows.append(
            {
                "platform": plat,
                "recommended_account_count": min(rec_n, cur + max(1, gap)) if gap else cur,
                "current_account_count": cur,
                "expansion_priority": min(100, max(0, priority)),
                "rationale_json": {
                    "platform_os": platform_spec(plat),
                    "brand_niche": brand_niche,
                    "gap_signal": gap,
                },
                "expected_upside": round(upside, 2),
                "confidence_score": float(scale_rec.get("expansion_confidence") or 0.5),
            }
        )
    return rows


def build_niche_rows(
    whitespace: list[dict],
    candidates: list[dict],
    brand_niche: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for c in candidates[:5]:
        key = (c.get("niche", ""), c.get("sub_niche") or "")
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "niche": c.get("niche") or brand_niche,
                "sub_niche": c.get("sub_niche"),
                "recommended_account_role": c.get("candidate_type", "growth")[:120],
                "recommended_platform": normalize_platform(c.get("primary_platform")),
                "expected_upside": float(c.get("expected_monthly_revenue_max") or 0),
                "saturation_risk": 0.25,
                "cannibalization_risk": float(c.get("cannibalization_risk") or 0),
                "confidence_score": float(c.get("confidence") or 0.5),
                "explanation_json": {"source": "launch_candidate", "reasons": c.get("supporting_reasons")},
            }
        )
    for w in whitespace[:5]:
        key = (w.get("niche", ""), w.get("geography") or "")
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "niche": w.get("niche") or brand_niche,
                "sub_niche": None,
                "recommended_account_role": "whitespace_satellite",
                "recommended_platform": normalize_platform(w.get("platform")),
                "expected_upside": float(w.get("estimated_opportunity_score") or 40),
                "saturation_risk": 0.2,
                "cannibalization_risk": 0.15,
                "confidence_score": 0.45,
                "explanation_json": {"source": "whitespace", "reason": w.get("reason")},
            }
        )
    return rows


def build_growth_blockers(
    leak_count: int,
    blocker_dicts: list[dict],
    funnel_weak: bool,
    extra_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if leak_count > 3:
        rows.append(
            {
                "blocker_type": "revenue_leak",
                "severity": "high" if leak_count > 8 else "medium",
                "affected_scope_type": "funnel",
                "affected_scope_id": None,
                "reason": f"{leak_count} unresolved revenue leaks detected.",
                "recommended_fix": "Patch top leaks before funding new accounts.",
                "expected_impact_json": {"profit_recovery_pct_estimate": min(25, leak_count * 2)},
                "confidence_score": 0.85,
                "urgency_score": min(100.0, 60.0 + leak_count),
            }
        )
    for b in blocker_dicts[:8]:
        rows.append(
            {
                "blocker_type": b.get("blocker_type", "unknown"),
                "severity": b.get("severity", "medium"),
                "affected_scope_type": "scale",
                "affected_scope_id": None,
                "reason": b.get("title", "blocker"),
                "recommended_fix": "Resolve blocker per scale diagnostics.",
                "expected_impact_json": {"severity": b.get("severity")},
                "confidence_score": 0.7,
                "urgency_score": 70.0 if b.get("severity") in ("high", "critical") else 45.0,
            }
        )
    if funnel_weak:
        rows.append(
            {
                "blocker_type": "funnel_readiness",
                "severity": "high",
                "affected_scope_type": "funnel",
                "affected_scope_id": None,
                "reason": "Funnel not ready for cold scale.",
                "recommended_fix": "Improve funnel before scaling.",
                "expected_impact_json": {"conversion_lift_pct": 15},
                "confidence_score": 0.65,
                "urgency_score": 75.0,
            }
        )
    if extra_rows:
        rows.extend(extra_rows)
    return rows


def build_capital_plan(
    total_budget: float,
    platform_mix: dict[str, float],
    capital_constrained: bool,
) -> dict[str, Any]:
    holdback = round(total_budget * (0.2 if capital_constrained else 0.1), 2)
    return {
        "total_budget": round(total_budget, 2),
        "platform_budget_mix_json": platform_mix,
        "account_budget_mix_json": {
            "launch": round(total_budget * 0.35, 2),
            "exploit_winners": round(total_budget * 0.25, 2),
        },
        "content_budget_mix_json": {"production": round(total_budget * 0.2, 2)},
        "funnel_budget_mix_json": {"landing_qa": round(total_budget * 0.1, 2)},
        "paid_budget_mix_json": {"amplification": round(total_budget * 0.1, 2)},
        "holdback_budget": holdback,
        "explanation_json": {
            "rule": "60/20/10 style split with holdback for optionality",
            "capital_constrained": capital_constrained,
        },
        "confidence_score": 0.55 if capital_constrained else 0.7,
    }


def build_cannibalization_pairs(accounts: list[dict]) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for i, ai in enumerate(accounts):
        for j in range(i + 1, len(accounts)):
            aj = accounts[j]
            if (ai.get("platform") or "").lower() != (aj.get("platform") or "").lower():
                continue
            topic = niche_jaccard(ai.get("niche_focus"), aj.get("niche_focus"))
            if topic < 0.35:
                continue
            ov = round((topic + 0.2) / 1.2, 3)
            risk = "high" if ov > 0.75 else ("medium" if ov > 0.5 else "low")
            pairs.append(
                {
                    "account_a_id": ai["id"],
                    "account_b_id": aj["id"],
                    "overlap_score": ov,
                    "audience_overlap_score": round(min(1.0, topic + 0.1), 3),
                    "topic_overlap_score": topic,
                    "monetization_overlap_score": round(topic * 0.9, 3),
                    "risk_level": risk,
                    "recommendation_json": {
                        "action": "merge_or_differentiate" if risk != "low" else "monitor",
                        "mitigation": "Separate sub-niche or schedule windows",
                    },
                }
            )
    return pairs


def build_portfolio_output(
    accounts: list[dict],
    accounts_by_platform: dict[str, int],
) -> dict[str, Any]:
    per_platform: dict[str, Any] = {}
    per_account: dict[str, Any] = {}
    total_rec = 0
    sat_risk = 0.0
    for plat, cnt in accounts_by_platform.items():
        spec = platform_spec(plat)
        cadence = spec["posting_cadence_posts_per_week"]
        mid = (cadence["min"] + cadence["max"]) / 2
        per_platform[plat] = {"target_posts_per_week": mid, "accounts": cnt, "saturation_hint": min(1.0, cnt * 0.15)}
        sat_risk += min(1.0, cnt * 0.12)
        total_rec += int(mid * cnt)
    for a in accounts:
        cap = int(a.get("posting_capacity_per_day") or 2) * 7
        per_account[str(a["id"])] = {
            "max_posts_per_week": cap,
            "recommended_posts_per_week": min(cap, 10),
            "fatigue": float(a.get("fatigue_score") or 0),
        }
    throttle = {}
    for plat, cnt in accounts_by_platform.items():
        if cnt >= 3:
            throttle[plat] = {"action": "throttle_new_posts_10pct", "reason": "platform_saturation_cluster"}
    return {
        "total_output_recommendation": total_rec,
        "per_platform_output_json": per_platform,
        "per_account_output_json": per_account,
        "duplication_risk_score": round(min(1.0, sat_risk * 0.4), 3),
        "saturation_risk_score": round(min(1.0, sat_risk / max(1, len(accounts_by_platform))), 3),
        "throttle_recommendation_json": throttle,
    }
