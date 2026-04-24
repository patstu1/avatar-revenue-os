"""Revenue Growth Commander engine: exact portfolio-expansion commands.

Composes from existing persisted data (scale recs, launch candidates, blockers,
readiness). Produces commands, not advice. Pure functions — no DB access.
"""
from __future__ import annotations

from packages.scoring.scale import RK_ADD_NICHE_SPINOFF, RK_ADD_PLATFORM_SPECIFIC, niche_jaccard

COMMANDER_SOURCE = "growth_commander"

COMMAND_TYPES = [
    "launch_account", "increase_output", "suppress_account", "pause_account",
    "shift_platform", "shift_niche", "add_offer_first", "fix_funnel_first",
    "merge_accounts", "do_nothing",
]

ALL_PLATFORMS = {"youtube", "tiktok", "instagram", "twitter", "reddit", "linkedin", "facebook"}


def map_content_role(candidate_type: str, content_style: str | None) -> str:
    ct = (candidate_type or "").lower()
    if "experimental" in ct:
        return "experimental_satellite"
    if "evergreen" in ct or "authority" in ct:
        return "evergreen_authority"
    if "trend" in ct:
        return "trend_capture"
    if "localized" in ct or "language" in ct:
        return "localized_expansion"
    if "offer" in ct:
        return "offer_aligned_conversion"
    if "niche" in ct and "spin" in ct:
        return "niche_spinoff"
    if "platform" in ct:
        return "platform_expansion"
    if content_style and str(content_style).strip():
        return f"content_style:{str(content_style).strip()[:48]}"
    return "portfolio_growth"


def _required_resources(expected_cost: float, urgency: float, command_type: str) -> dict:
    hours = 2.0
    if command_type in ("launch_account", "shift_platform", "shift_niche"):
        hours = 10.0
    elif command_type in ("fix_funnel_first", "add_offer_first"):
        hours = 6.0
    elif command_type == "merge_accounts":
        hours = 5.0
    return {
        "estimated_cash_outlay_usd": round(float(expected_cost), 2),
        "estimated_ops_hours_week_one": hours,
        "creative_dependency": (
            "flagship_hook_library" if command_type in ("launch_account", "shift_platform", "shift_niche") else "minimal"
        ),
        "urgency_score": round(float(urgency), 1),
    }


def _build_execution_spec(command_type: str, cmd: dict, accounts: list[dict], brand_niche: str | None) -> dict:
    ev = cmd.get("evidence") or {}
    nf = cmd.get("niche_fit") or {}
    pf = cmd.get("platform_fit") or {}
    mp = cmd.get("monetization_path") or {}
    if command_type == "launch_account":
        return {
            "platform": pf.get("platform"),
            "niche": nf.get("niche") or brand_niche,
            "sub_niche": nf.get("sub_niche") or "",
            "avatar_persona_strategy": ev.get("avatar_persona_strategy") or "",
            "content_role": map_content_role(ev.get("candidate_type", ""), ev.get("content_style")),
            "monetization_path": (mp.get("primary_method") or "affiliate"),
            "language": ev.get("language", "en"),
            "geography": ev.get("geography", "US"),
            "posting_strategy": ev.get("posting_strategy", ""),
        }
    if command_type in ("shift_platform", "shift_niche"):
        return {
            "platform": pf.get("platform"),
            "niche": nf.get("niche") or brand_niche,
            "sub_niche": nf.get("sub_niche") or "",
            "avatar_persona_strategy": ev.get("avatar_persona_strategy") or "Differentiate from flagship; clear sub-audience.",
            "content_role": map_content_role(command_type, None),
            "monetization_path": mp.get("primary_method") or "mirror_flagship",
            "language": ev.get("language", "en"),
            "geography": ev.get("geography", "US"),
        }
    if command_type == "increase_output":
        un = ev.get("best_account") or "?"
        plat = pf.get("platform")
        return {
            "platform": plat,
            "content_role": "exploit_winner_volume",
            "target_account": un,
            "monetization_path": mp.get("primary_method") or "existing",
        }
    if command_type in ("suppress_account", "pause_account"):
        return {
            "platform": pf.get("platform"),
            "content_role": "reduce_or_pause_underperformer",
            "target_account": ev.get("target_username") or "",
        }
    if command_type == "merge_accounts":
        return {
            "platform": ev.get("platform"),
            "content_role": "consolidate_overlap",
            "accounts": ev.get("accounts") or [],
        }
    if command_type == "fix_funnel_first":
        return {"content_role": "funnel_remediation", "blocked_expansion": True}
    if command_type == "add_offer_first":
        return {"content_role": "offer_catalog_expansion", "blocked_scale": True}
    if command_type == "do_nothing":
        return {"content_role": "hold_scan_next_cycle", "comfort_mode": False}
    return {"content_role": "portfolio_action", "command_type": command_type}


def _finalize_command_metadata(commands: list[dict], accounts: list[dict], brand_niche: str | None) -> None:
    for c in commands:
        ct = c["command_type"]
        c.setdefault("required_resources", _required_resources(
            float(c.get("expected_cost", 0)), float(c.get("urgency", 0)), ct,
        ))
        c.setdefault("execution_spec", _build_execution_spec(ct, c, accounts, brand_niche))


def compute_portfolio_directive(
    current_count: int,
    scale_rec: dict,
    balance: dict,
    ranked_commands: list[dict],
    leak_count: int,
) -> dict:
    """Top-level portfolio control: target account count, lanes, hold vs expand (evidence-driven)."""
    rec_n = max(0, int(scale_rec.get("recommended_account_count") or current_count))
    exp_conf = float(scale_rec.get("expansion_confidence") or 0.0)
    top = ranked_commands[0] if ranked_commands else None
    top_type = top["command_type"] if top else "do_nothing"
    comp = top.get("comparison") if top else {}
    winner = comp.get("winner", "tie") if comp else "tie"

    if top_type in ("do_nothing",):
        hold_vs_expand = "hold"
    elif top_type in ("fix_funnel_first", "add_offer_first"):
        hold_vs_expand = "remediate_before_expand"
    elif top_type in ("launch_account", "shift_platform", "shift_niche", "increase_output"):
        hold_vs_expand = "expand"
    elif top_type in ("suppress_account", "pause_account", "merge_accounts"):
        hold_vs_expand = "cut_or_consolidate"
    else:
        hold_vs_expand = "hold"

    explanation = (
        f"Active creator accounts: {current_count}. Scale engine structural target: {rec_n}. "
        f"Profit comparison (new vs existing push) favors: {winner}. "
        f"Open revenue leaks: {leak_count}. "
    )
    if balance.get("overbuilt"):
        explanation += f"Overbuilt platforms: {[x.get('platform') for x in balance['overbuilt']]}. "
    if balance.get("absent_platforms"):
        explanation += f"Absent platforms (opportunity): {balance['absent_platforms'][:4]}. "

    downstream = (
        f"Execute highest-priority command ({top_type}); re-run scale + growth recompute after execution."
        if top else "Recompute when new performance data is available."
    )

    evidence = {
        "recommended_account_count_source": "scale_recommendation.recommended_account_count",
        "scale_recommendation_key": scale_rec.get("recommendation_key"),
        "incremental_profit_new_account": scale_rec.get("incremental_profit_new_account"),
        "incremental_profit_existing_push": scale_rec.get("incremental_profit_existing_push"),
        "comparison_winner": winner,
        "open_leak_count": leak_count,
        "absent_platforms": balance.get("absent_platforms", []),
        "overbuilt_platforms": [x.get("platform") for x in balance.get("overbuilt", [])],
        "underbuilt_platforms": [x.get("platform") for x in balance.get("underbuilt", [])],
    }
    urg = max((float(c.get("urgency", 0)) for c in ranked_commands), default=40.0)
    conf = min(1.0, max(0.15, exp_conf if exp_conf else 0.55))
    return {
        "current_account_count": current_count,
        "recommended_account_count": rec_n,
        "account_count_delta": rec_n - current_count,
        "explanation": explanation.strip(),
        "confidence": round(conf, 3),
        "evidence": evidence,
        "downstream_action": downstream,
        "urgency": round(urg, 1),
        "hold_vs_expand": hold_vs_expand,
        "next_best_command_type": top_type,
        "comfort_mode": False,
        "source": COMMANDER_SOURCE,
    }


def _comparison(inc_new: float, inc_existing: float) -> dict:
    ratio = inc_new / inc_existing if inc_existing > 1e-6 else (99.0 if inc_new > 0 else 0.0)
    return {
        "incremental_new": round(inc_new, 2),
        "incremental_existing": round(inc_existing, 2),
        "ratio": round(ratio, 3),
        "winner": "new_account" if ratio > 1.15 else ("more_output" if inc_existing > inc_new * 0.85 else "tie"),
    }


def _success_threshold(command_type: str, expected_upside: float) -> dict:
    if command_type == "launch_account":
        return {"metric": "weekly_profit", "target_value": round(max(10, expected_upside * 0.3), 2), "timeframe_days": 60}
    if command_type == "increase_output":
        return {"metric": "incremental_rpm", "target_value": 2.0, "timeframe_days": 30}
    return {"metric": "no_regression", "target_value": 0.0, "timeframe_days": 30}


def _failure_threshold(command_type: str) -> dict:
    if command_type == "launch_account":
        return {"metric": "weekly_profit", "floor_value": -20.0, "timeframe_days": 90, "action_on_failure": "pause_account"}
    if command_type == "increase_output":
        return {"metric": "rpm_decline_pct", "floor_value": -15.0, "timeframe_days": 45, "action_on_failure": "revert_output_volume"}
    if command_type == "suppress_account":
        return {"metric": "n/a", "floor_value": 0, "timeframe_days": 0, "action_on_failure": "n/a"}
    return {"metric": "no_metric", "floor_value": 0, "timeframe_days": 30, "action_on_failure": "re-evaluate"}


def _find_merge_account_pair(accounts: list[dict]) -> tuple[dict, dict] | None:
    """Same platform + high niche overlap → merge consideration."""
    for i, ai in enumerate(accounts):
        for j in range(i + 1, len(accounts)):
            aj = accounts[j]
            if (ai.get("platform") or "").lower() != (aj.get("platform") or "").lower():
                continue
            jac = niche_jaccard(ai.get("niche_focus"), aj.get("niche_focus"))
            if jac >= 0.55:
                return (ai, aj)
    return None


def _first_week_plan(candidate: dict) -> list[dict]:
    platform = candidate.get("primary_platform", "youtube")
    niche = candidate.get("niche", "general")
    return [
        {"day": "Day 1", "action": f"Create {platform} account with niche-aligned branding for '{niche}'."},
        {"day": "Day 2", "action": "Set up avatar/persona. Configure bio, links, and monetization integrations."},
        {"day": "Day 3", "action": "Publish first content piece — adapt top-performing hook from flagship."},
        {"day": "Day 4", "action": "Publish second piece. Monitor initial engagement signals."},
        {"day": "Day 5", "action": "Review Day 3-4 metrics. Adjust hook/CTA if CTR < 2%."},
        {"day": "Day 6", "action": "Publish third piece with offer integration. Track attribution."},
        {"day": "Day 7", "action": "Week 1 review: impressions, CTR, first conversions. Decide ramp or pivot."},
    ]


def assess_portfolio_balance(accounts: list[dict]) -> dict:
    """Which platforms are overbuilt, underbuilt, or absent."""
    platform_counts: dict[str, int] = {}
    for a in accounts:
        p = (a.get("platform") or "youtube").lower()
        platform_counts[p] = platform_counts.get(p, 0) + 1

    total = max(1, len(accounts))
    overbuilt: list[dict] = []
    underbuilt: list[dict] = []
    absent: list[str] = []

    for p in ALL_PLATFORMS:
        count = platform_counts.get(p, 0)
        share = count / total
        if count == 0:
            absent.append(p)
        elif share > 0.5 and count >= 2:
            overbuilt.append({"platform": p, "count": count, "share": round(share, 2), "reason": "Over-concentrated — diversification reduces risk."})
        elif count == 1 and total >= 3:
            underbuilt.append({"platform": p, "count": count, "reason": "Single account on active platform — opportunity to expand."})

    return {
        "total_accounts": len(accounts),
        "platform_distribution": platform_counts,
        "overbuilt": overbuilt,
        "underbuilt": underbuilt,
        "absent_platforms": absent,
        COMMANDER_SOURCE: True,
    }


def find_whitespace(
    accounts: list[dict],
    brand_niche: str | None,
    geo_recs: list[dict],
) -> list[dict]:
    """Find untapped platform/niche/geo combinations."""
    used = {(a.get("platform", "").lower(), (a.get("niche_focus") or "").lower(), (a.get("geography") or "US").upper()) for a in accounts}
    opportunities: list[dict] = []

    niche = (brand_niche or "general").lower()
    for p in ALL_PLATFORMS:
        if not any(u[0] == p for u in used):
            opportunities.append({
                "platform": p, "niche": niche, "geography": "US",
                "reason": f"No presence on {p} — untapped audience.",
                "estimated_opportunity_score": 60.0,
            })

    for gr in geo_recs:
        geo = gr.get("target_geography", "")
        lang = gr.get("target_language", "en")
        for p in ALL_PLATFORMS:
            key = (p, niche, geo.upper())
            if key not in used:
                opportunities.append({
                    "platform": p, "niche": niche, "geography": geo, "language": lang,
                    "reason": f"Geo expansion: {geo}/{lang} on {p}.",
                    "estimated_opportunity_score": round(float(gr.get("estimated_revenue_potential", 0)) / 100, 1),
                })

    return sorted(opportunities, key=lambda x: -x.get("estimated_opportunity_score", 0))[:10]


def generate_growth_commands(
    scale_rec: dict,
    candidates: list[dict],
    blockers: list[dict],
    readiness: dict | None,
    accounts: list[dict],
    offers: list[dict],
    brand_niche: str | None,
    trust_avg: float,
    leak_count: int,
    geo_recs: list[dict],
) -> list[dict]:
    """Generate exact growth commands from all available intelligence.

    Every command includes comparison, cannibalization analysis, success/failure
    thresholds, and first-week plan where applicable.
    """
    commands: list[dict] = []
    inc_new = float(scale_rec.get("incremental_profit_new_account", 0))
    inc_vol = float(scale_rec.get("incremental_profit_existing_push", 0))
    readiness_score = float((readiness or {}).get("launch_readiness_score", 0))
    rec_key = scale_rec.get("recommendation_key", "monitor")
    comparison = _comparison(inc_new, inc_vol)

    high_severity_blockers = [b for b in blockers if b.get("severity") in ("high", "critical")]
    blocking_factors = [b.get("title", b.get("blocker_type", "unknown")) for b in high_severity_blockers]

    if leak_count > 5 and high_severity_blockers:
        commands.append({
            "command_type": "fix_funnel_first",
            "priority": 95,
            "title": "FIX FUNNEL BEFORE ANY EXPANSION",
            "exact_instruction": f"Resolve {leak_count} open revenue leaks and {len(high_severity_blockers)} high-severity blockers before launching new accounts.",
            "rationale": "Scaling with a leaking funnel amplifies losses. Fix first, then expand.",
            "comparison": comparison,
            "platform_fit": {"platform": "all", "fit_score": 0, "reason": "Blocked by funnel issues."},
            "niche_fit": {"niche": brand_niche or "", "sub_niche": "", "fit_score": 0, "reason": "N/A — funnel fix required."},
            "monetization_path": {"primary_method": "fix_existing", "secondary_method": "", "expected_rpm": 0},
            "cannibalization_analysis": {"risk": 0, "overlap_accounts": [], "mitigation": "N/A"},
            "success_threshold": {"metric": "leak_count", "target_value": max(0, leak_count - 3), "timeframe_days": 14},
            "failure_threshold": {"metric": "leak_count", "floor_value": leak_count + 2, "timeframe_days": 30, "action_on_failure": "escalate_funnel_audit"},
            "expected_upside": 0, "expected_cost": 0,
            "expected_time_to_signal_days": 7, "expected_time_to_profit_days": 0,
            "confidence": 0.9, "urgency": 90.0,
            "blocking_factors": blocking_factors,
            "first_week_plan": [],
            "linked_launch_candidate_id": None,
            "linked_scale_recommendation_id": scale_rec.get("id"),
            "evidence": {"leak_count": leak_count, "high_blockers": len(high_severity_blockers)},
            COMMANDER_SOURCE: True,
        })

    # Persisted launch readiness: blocks expansion when funnel components are weak (no leak prerequisite).
    if (readiness or {}) and readiness_score > 0 and readiness_score < 50 and not (leak_count > 5 and high_severity_blockers):
        commands.append({
            "command_type": "fix_funnel_first",
            "priority": 88,
            "title": "IMPROVE FUNNEL READINESS BEFORE EXPANSION",
            "exact_instruction": (
                f"Launch readiness score is {readiness_score:.0f}/100 — fix funnel instrumentation, "
                "landing paths, and conversion before funding new accounts."
            ),
            "rationale": "Cold expansion with weak funnel readiness amplifies waste; remediate funnel first.",
            "comparison": comparison,
            "platform_fit": {"platform": "all", "fit_score": 0, "reason": "Blocked by readiness gate."},
            "niche_fit": {"niche": brand_niche or "", "sub_niche": "", "fit_score": 0, "reason": "N/A — funnel readiness."},
            "monetization_path": {"primary_method": "fix_existing", "secondary_method": "", "expected_rpm": 0},
            "cannibalization_analysis": {"risk": 0, "overlap_accounts": [], "mitigation": "N/A"},
            "success_threshold": {"metric": "launch_readiness_score", "target_value": 55, "timeframe_days": 21},
            "failure_threshold": {"metric": "launch_readiness_score", "floor_value": 40, "timeframe_days": 30, "action_on_failure": "deep_funnel_audit"},
            "expected_upside": 0, "expected_cost": 0,
            "expected_time_to_signal_days": 14, "expected_time_to_profit_days": 0,
            "confidence": 0.82, "urgency": 85.0,
            "blocking_factors": ["launch_readiness_below_50"],
            "first_week_plan": [],
            "linked_launch_candidate_id": None,
            "linked_scale_recommendation_id": scale_rec.get("id"),
            "evidence": {"launch_readiness_score": readiness_score, "gate": "funnel_readiness", "recommended_action": (readiness or {}).get("recommended_action")},
            COMMANDER_SOURCE: True,
        })

    if len(offers) < 2 and "offer" in rec_key:
        commands.append({
            "command_type": "add_offer_first",
            "priority": 90,
            "title": "ADD OFFER BEFORE SCALING",
            "exact_instruction": f"Add at least 1 complementary offer to the catalog (currently {len(offers)} offer(s)). Target: different monetization method from existing.",
            "rationale": "Thin offer catalog limits revenue per visitor. Diversify before adding accounts.",
            "comparison": comparison,
            "platform_fit": {"platform": "all", "fit_score": 0.5, "reason": "Offer gap affects all platforms."},
            "niche_fit": {"niche": brand_niche or "", "sub_niche": "", "fit_score": 0.5, "reason": "Niche supports multiple offer types."},
            "monetization_path": {"primary_method": "add_complementary", "secondary_method": "", "expected_rpm": 0},
            "cannibalization_analysis": {"risk": 0, "overlap_accounts": [], "mitigation": "N/A"},
            "success_threshold": {"metric": "active_offers", "target_value": 2, "timeframe_days": 14},
            "failure_threshold": {"metric": "active_offers", "floor_value": 1, "timeframe_days": 30, "action_on_failure": "prioritize_offer_sourcing"},
            "expected_upside": inc_vol * 0.5, "expected_cost": 50,
            "expected_time_to_signal_days": 14, "expected_time_to_profit_days": 30,
            "confidence": 0.75, "urgency": 80.0,
            "blocking_factors": ["Insufficient offer diversity"],
            "first_week_plan": [],
            "linked_launch_candidate_id": None,
            "linked_scale_recommendation_id": scale_rec.get("id"),
            "evidence": {"offer_count": len(offers)},
            COMMANDER_SOURCE: True,
        })

    expansion_blocked = any(c["command_type"] in ("fix_funnel_first", "add_offer_first") for c in commands)

    bna = scale_rec.get("best_next_account") or {}
    tgt_plat = (bna.get("platform_suggestion") or "").lower()
    has_launch_on_tgt = any((c.get("primary_platform") or "").lower() == tgt_plat for c in candidates)
    if (not expansion_blocked and rec_key == RK_ADD_PLATFORM_SPECIFIC and tgt_plat and not has_launch_on_tgt
            and inc_new >= inc_vol * 0.85):
        existing_on_tgt = [a for a in accounts if (a.get("platform") or "").lower() == tgt_plat]
        pfit = 0.9 if not existing_on_tgt else (0.7 if len(existing_on_tgt) == 1 else 0.4)
        commands.append({
            "command_type": "shift_platform",
            "priority": 72,
            "title": f"SHIFT EXPANSION TO {tgt_plat.upper()}",
            "exact_instruction": (
                f"Stand up the next account on {tgt_plat} (scale engine: platform-specific expansion). "
                f"Reuse proven hooks from the flagship; differentiate posting times and lead magnets to limit overlap."
            ),
            "rationale": bna.get("rationale") or "Diversify platform exposure while reusing proven creative patterns.",
            "comparison": comparison,
            "platform_fit": {"platform": tgt_plat, "fit_score": round(pfit, 2),
                             "reason": "Scale recommendation: add_platform_specific_account."},
            "niche_fit": {"niche": brand_niche or "", "sub_niche": "", "fit_score": 0.75,
                          "reason": "Adjacent angle on core niche."},
            "monetization_path": {"primary_method": "mirror_flagship", "secondary_method": "", "expected_rpm": round(inc_new / 4, 2) if inc_new > 0 else 5.0},
            "cannibalization_analysis": {"risk": 0.35, "overlap_accounts": [a.get("username", "?") for a in existing_on_tgt][:3],
                                          "mitigation": "Separate schedule, creatives, and lead magnet to limit audience overlap."},
            "success_threshold": _success_threshold("launch_account", inc_new),
            "failure_threshold": _failure_threshold("launch_account"),
            "expected_upside": round(inc_new, 2),
            "expected_cost": 150.0,
            "expected_time_to_signal_days": 21,
            "expected_time_to_profit_days": 60,
            "confidence": 0.72,
            "urgency": 62.0,
            "blocking_factors": blocking_factors,
            "first_week_plan": _first_week_plan({
                "primary_platform": tgt_plat, "niche": brand_niche or "core",
                "sub_niche": bna.get("niche_suggestion", ""),
            }),
            "linked_launch_candidate_id": None,
            "linked_scale_recommendation_id": scale_rec.get("id"),
            "evidence": {
                "recommendation_key": rec_key, "best_next_account": bna,
                "language": "en", "geography": "US",
                "avatar_persona_strategy": bna.get("niche_suggestion") or "Distinct sub-brand voice from flagship.",
            },
            COMMANDER_SOURCE: True,
        })

    if (not expansion_blocked and rec_key == RK_ADD_NICHE_SPINOFF and not candidates
            and len(accounts) >= 1 and inc_new >= inc_vol * 0.85):
        spin = (bna.get("niche_suggestion") or f"Sub-niche of {brand_niche or 'core'}").strip()
        plat0 = (bna.get("platform_suggestion") or accounts[0].get("platform") or "youtube").lower()
        commands.append({
            "command_type": "shift_niche",
            "priority": 71,
            "title": "OPEN NICHE SPINOFF (SUB-AUDIENCE SPLIT)",
            "exact_instruction": (
                f"Create a dedicated spinoff on {plat0} for sub-audience: {spin}. "
                f"Position distinctly from existing accounts; cross-promote only after validation."
            ),
            "rationale": bna.get("rationale") or "Separate sub-audience to reduce cannibalization.",
            "comparison": comparison,
            "platform_fit": {"platform": plat0, "fit_score": 0.75, "reason": "Same platform family — faster creative reuse."},
            "niche_fit": {"niche": brand_niche or "", "sub_niche": spin, "fit_score": 0.8, "reason": "Explicit spinoff path from scale engine."},
            "monetization_path": {"primary_method": "affiliate", "secondary_method": "", "expected_rpm": round(inc_new / 4, 2) if inc_new > 0 else 5.0},
            "cannibalization_analysis": {"risk": 0.4, "overlap_accounts": [accounts[0].get("username", "?")],
                                          "mitigation": "Separated sub-niche and content style."},
            "success_threshold": _success_threshold("launch_account", inc_new),
            "failure_threshold": _failure_threshold("launch_account"),
            "expected_upside": round(inc_new, 2),
            "expected_cost": 150.0,
            "expected_time_to_signal_days": 21,
            "expected_time_to_profit_days": 60,
            "confidence": 0.7,
            "urgency": 58.0,
            "blocking_factors": blocking_factors,
            "first_week_plan": _first_week_plan({"primary_platform": plat0, "niche": spin, "sub_niche": spin}),
            "linked_launch_candidate_id": None,
            "linked_scale_recommendation_id": scale_rec.get("id"),
            "evidence": {
                "recommendation_key": rec_key, "best_next_account": bna,
                "language": "en",
                "geography": accounts[0].get("geography") or "US",
                "avatar_persona_strategy": f"Spinoff persona for: {spin}",
            },
            COMMANDER_SOURCE: True,
        })

    for candidate in candidates:
        cann_risk = float(candidate.get("cannibalization_risk", 0))
        aud_sep = float(candidate.get("audience_separation_score", 0))
        cand_blockers = candidate.get("launch_blockers") or []
        platform = candidate.get("primary_platform", "youtube")
        niche = candidate.get("niche", brand_niche or "general")

        if cann_risk > 0.6:
            mitigation = "High overlap — launch requires niche-differentiated angle or different platform."
        elif cann_risk > 0.4:
            mitigation = "Moderate overlap — separate sub-niche and content style."
        else:
            mitigation = "Low overlap — safe to launch."

        overlap_accounts = [a.get("username", a.get("id", "?")) for a in accounts
                          if (a.get("platform", "").lower() == platform.lower() and
                              (a.get("niche_focus") or "").lower() == niche.lower())]

        existing_on_platform = [a for a in accounts if (a.get("platform") or "").lower() == platform.lower()]
        platform_fit_score = 0.9 if len(existing_on_platform) == 0 else (0.7 if len(existing_on_platform) == 1 else 0.4)

        rev_min = float(candidate.get("expected_monthly_revenue_min", 0))
        rev_max = float(candidate.get("expected_monthly_revenue_max", 0))
        launch_cost = float(candidate.get("expected_launch_cost", 150))

        priority = 70
        if readiness_score >= 70 and not cand_blockers:
            priority = 85
        elif readiness_score < 50 or cann_risk > 0.5:
            priority = 45

        if blocking_factors and not commands:
            priority = min(priority, 40)

        commands.append({
            "command_type": "launch_account",
            "priority": priority,
            "title": f"LAUNCH: {candidate.get('candidate_type', 'account').replace('_', ' ').upper()} on {platform.upper()}",
            "exact_instruction": (
                f"Create {candidate.get('candidate_type', 'new')} account on {platform}. "
                f"Niche: {niche}. Sub-niche: {candidate.get('sub_niche', 'core')}. "
                f"Language: {candidate.get('language', 'en')}. Geography: {candidate.get('geography', 'US')}. "
                f"Monetization: {candidate.get('monetization_path', 'affiliate')}. "
                f"Post {candidate.get('posting_strategy', '2/day, ramp over 2 weeks')}."
            ),
            "rationale": "; ".join(candidate.get("supporting_reasons") or [rec_key.replace("_", " ")]),
            "comparison": comparison,
            "platform_fit": {"platform": platform, "fit_score": round(platform_fit_score, 2),
                           "reason": f"{'New platform — max opportunity.' if len(existing_on_platform) == 0 else f'{len(existing_on_platform)} existing on {platform}.'}"},
            "niche_fit": {"niche": niche, "sub_niche": candidate.get("sub_niche", ""),
                        "fit_score": round(min(1.0, aud_sep + 0.2), 2),
                        "reason": f"Audience separation {aud_sep:.2f}."},
            "monetization_path": {"primary_method": (candidate.get("monetization_path") or "affiliate").split("|")[0].strip(),
                                "secondary_method": "", "expected_rpm": round(inc_new / 4, 2) if inc_new > 0 else 5.0},
            "cannibalization_analysis": {"risk": round(cann_risk, 3), "overlap_accounts": overlap_accounts[:3], "mitigation": mitigation},
            "success_threshold": _success_threshold("launch_account", rev_max),
            "failure_threshold": _failure_threshold("launch_account"),
            "expected_upside": round(rev_max, 2),
            "expected_cost": round(launch_cost, 2),
            "expected_time_to_signal_days": int(candidate.get("expected_time_to_signal_days", 21)),
            "expected_time_to_profit_days": int(candidate.get("expected_time_to_profit_days", 60)),
            "confidence": round(float(candidate.get("confidence", 0.5)), 2),
            "urgency": round(float(candidate.get("urgency", 50)), 1),
            "blocking_factors": cand_blockers + blocking_factors,
            "first_week_plan": _first_week_plan(candidate),
            "linked_launch_candidate_id": candidate.get("id"),
            "linked_scale_recommendation_id": scale_rec.get("id"),
            "evidence": {
                "readiness": readiness_score, "cannibalization": cann_risk, "separation": aud_sep,
                "rev_range": [rev_min, rev_max], "candidate_type": candidate.get("candidate_type"),
                "avatar_persona_strategy": candidate.get("avatar_persona_strategy") or "",
                "content_style": candidate.get("content_style") or "",
                "language": candidate.get("language", "en"),
                "geography": candidate.get("geography", "US"),
                "posting_strategy": candidate.get("posting_strategy", ""),
            },
            COMMANDER_SOURCE: True,
        })

    if comparison["winner"] == "more_output" and accounts:
        best = max(accounts, key=lambda a: float(a.get("profit_per_post", 0)))
        commands.append({
            "command_type": "increase_output",
            "priority": 75 if not blocking_factors else 50,
            "title": f"INCREASE OUTPUT on {best.get('username', best.get('platform', '?'))}",
            "exact_instruction": (
                f"Increase posting frequency on {best.get('username', '?')} by +1 post/day. "
                f"Current profit/post: ${float(best.get('profit_per_post', 0)):.2f}. "
                f"Expected incremental weekly profit: ${inc_vol:.2f}."
            ),
            "rationale": "Exploitation beats expansion at current margins. More output on winners is more profitable than a new account.",
            "comparison": comparison,
            "platform_fit": {"platform": best.get("platform", "youtube"), "fit_score": 0.9, "reason": "Already performing on this platform."},
            "niche_fit": {"niche": best.get("niche_focus", ""), "sub_niche": "", "fit_score": 0.9, "reason": "Proven niche performance."},
            "monetization_path": {"primary_method": "existing", "secondary_method": "", "expected_rpm": float(best.get("revenue_per_mille", 0))},
            "cannibalization_analysis": {"risk": 0, "overlap_accounts": [], "mitigation": "Same account — no cannibalization."},
            "success_threshold": _success_threshold("increase_output", inc_vol),
            "failure_threshold": _failure_threshold("increase_output"),
            "expected_upside": round(inc_vol * 4, 2),
            "expected_cost": 0, "expected_time_to_signal_days": 14, "expected_time_to_profit_days": 14,
            "confidence": 0.8, "urgency": 65.0,
            "blocking_factors": blocking_factors,
            "first_week_plan": [],
            "linked_launch_candidate_id": None,
            "linked_scale_recommendation_id": scale_rec.get("id"),
            "evidence": {
                "best_account": best.get("username"),
                "profit_per_post": float(best.get("profit_per_post", 0)),
                "scale_role": best.get("scale_role") or "",
            },
            COMMANDER_SOURCE: True,
        })

    for a in accounts:
        health = (a.get("account_health") or "healthy").lower()
        ppp = float(a.get("profit_per_post", 0))
        if health in ("critical", "suspended") or (ppp < 1.0 and float(a.get("fatigue_score", 0)) > 0.6):
            commands.append({
                "command_type": "suppress_account" if health in ("critical", "suspended") else "pause_account",
                "priority": 60,
                "title": f"{'SUPPRESS' if health in ('critical', 'suspended') else 'PAUSE'}: {a.get('username', '?')}",
                "exact_instruction": f"{'Suppress' if health in ('critical', 'suspended') else 'Pause'} account {a.get('username', '?')} — {health} health, ${ppp:.2f}/post profit.",
                "rationale": f"Account is {'unhealthy' if health in ('critical', 'suspended') else 'underperforming with high fatigue'}. Redirecting resources to stronger accounts.",
                "comparison": comparison,
                "platform_fit": {"platform": a.get("platform", ""), "fit_score": 0, "reason": "Account underperforming."},
                "niche_fit": {"niche": a.get("niche_focus", ""), "sub_niche": "", "fit_score": 0, "reason": "N/A"},
                "monetization_path": {"primary_method": "none", "secondary_method": "", "expected_rpm": 0},
                "cannibalization_analysis": {"risk": 0, "overlap_accounts": [], "mitigation": "Removal reduces overlap."},
                "success_threshold": _success_threshold("suppress_account", 0),
                "failure_threshold": _failure_threshold("suppress_account"),
                "expected_upside": 0, "expected_cost": 0,
                "expected_time_to_signal_days": 0, "expected_time_to_profit_days": 0,
                "confidence": 0.85, "urgency": 55.0,
                "blocking_factors": [],
                "first_week_plan": [],
                "linked_launch_candidate_id": None,
                "linked_scale_recommendation_id": None,
                "evidence": {
                    "health": health, "profit_per_post": ppp, "fatigue": float(a.get("fatigue_score", 0)),
                    "target_username": a.get("username"),
                },
                COMMANDER_SOURCE: True,
            })

    merge_pair = None if expansion_blocked else _find_merge_account_pair(accounts)
    if merge_pair:
        ai, aj = merge_pair
        u1, u2 = ai.get("username", "?"), aj.get("username", "?")
        plat = (ai.get("platform") or "?").lower()
        commands.append({
            "command_type": "merge_accounts",
            "priority": 55,
            "title": f"MERGE OVERLAPPING ACCOUNTS ON {plat.upper()}",
            "exact_instruction": (
                f"Consolidate {u1} and {u2} into one primary account on {plat}: keep the higher profit/post line, "
                f"redirect handle, and merge content calendars to remove cannibalization."
            ),
            "rationale": "High niche overlap on the same platform — merging reduces audience split and ops overhead.",
            "comparison": comparison,
            "platform_fit": {"platform": plat, "fit_score": 0.5, "reason": "Overlap consolidation."},
            "niche_fit": {"niche": ai.get("niche_focus", ""), "sub_niche": "", "fit_score": 0.5,
                          "reason": "Jaccard overlap above threshold."},
            "monetization_path": {"primary_method": "consolidate", "secondary_method": "", "expected_rpm": 0},
            "cannibalization_analysis": {
                "risk": round(niche_jaccard(ai.get("niche_focus"), aj.get("niche_focus")), 3),
                "overlap_accounts": [u1, u2],
                "mitigation": "Single account — eliminates cross-account overlap.",
            },
            "success_threshold": {"metric": "combined_weekly_profit", "target_value": 0, "timeframe_days": 30},
            "failure_threshold": {"metric": "audience_churn_pct", "floor_value": 15, "timeframe_days": 30, "action_on_failure": "re-evaluate_merge"},
            "expected_upside": round(float(ai.get("profit_per_post", 0)) + float(aj.get("profit_per_post", 0)), 2),
            "expected_cost": 0,
            "expected_time_to_signal_days": 14,
            "expected_time_to_profit_days": 30,
            "confidence": 0.65,
            "urgency": 45.0,
            "blocking_factors": blocking_factors,
            "first_week_plan": [],
            "linked_launch_candidate_id": None,
            "linked_scale_recommendation_id": scale_rec.get("id"),
            "evidence": {"accounts": [u1, u2], "platform": plat},
            COMMANDER_SOURCE: True,
        })

    if not commands:
        commands.append({
            "command_type": "do_nothing",
            "priority": 10,
            "title": "HOLD — NO EXPANSION JUSTIFIED",
            "exact_instruction": "No action required. Current portfolio is optimally sized for available data. Re-evaluate after next performance cycle.",
            "rationale": f"Readiness {readiness_score:.0f}/100, no candidates generated, no blockers flagged.",
            "comparison": comparison,
            "platform_fit": {"platform": "all", "fit_score": 0.5, "reason": "Stable."},
            "niche_fit": {"niche": brand_niche or "", "sub_niche": "", "fit_score": 0.5, "reason": "Stable."},
            "monetization_path": {"primary_method": "existing", "secondary_method": "", "expected_rpm": 0},
            "cannibalization_analysis": {"risk": 0, "overlap_accounts": [], "mitigation": "N/A"},
            "success_threshold": {"metric": "maintain_profit", "target_value": 0, "timeframe_days": 30},
            "failure_threshold": {"metric": "profit_decline_pct", "floor_value": -10, "timeframe_days": 30, "action_on_failure": "re-evaluate"},
            "expected_upside": 0, "expected_cost": 0,
            "expected_time_to_signal_days": 30, "expected_time_to_profit_days": 0,
            "confidence": 0.6, "urgency": 10.0,
            "blocking_factors": [],
            "first_week_plan": [],
            "linked_launch_candidate_id": None,
            "linked_scale_recommendation_id": scale_rec.get("id"),
            "evidence": {"readiness": readiness_score, "candidates": 0, "blockers": len(blockers)},
            COMMANDER_SOURCE: True,
        })

    _finalize_command_metadata(commands, accounts, brand_niche)
    return rank_commands(commands)


def rank_commands(commands: list[dict]) -> list[dict]:
    """Sort commands: fixes first, then launches, then increases, then suppressions, then hold.
    Within each group, sort by priority descending."""
    type_order = {"fix_funnel_first": 0, "add_offer_first": 1, "launch_account": 2,
                  "increase_output": 3, "shift_platform": 4, "shift_niche": 4,
                  "suppress_account": 5, "pause_account": 5, "merge_accounts": 5, "do_nothing": 9}
    return sorted(commands, key=lambda c: (type_order.get(c["command_type"], 6), -c["priority"]))
