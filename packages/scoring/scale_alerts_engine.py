"""Scale alerts, launch candidates, blocker diagnostics, launch readiness engines.

Pure functions — no DB access. Service layer handles persistence.
"""

from __future__ import annotations

SCALE_ALERT_SOURCE = "scale_alerts_engine"

ALERT_TYPES = [
    "scale_now",
    "scale_soon",
    "hold_and_monitor",
    "do_not_scale_yet",
    "reduce_existing_account",
    "suppress_account",
    "improve_funnel_before_scaling",
    "improve_offer_before_scaling",
    "improve_retention_before_scaling",
    "improve_originality_before_scaling",
    "expansion_opportunity_detected",
    "cannibalization_warning",
    "saturation_warning",
    "platform_shift_recommendation",
    "niche_shift_recommendation",
]

CANDIDATE_TYPES = [
    "flagship_expansion",
    "experimental_account",
    "niche_spinoff",
    "offer_specific_account",
    "platform_specialist_account",
    "language_expansion_account",
    "geo_localized_account",
    "evergreen_authority_account",
    "trend_capture_account",
    "high_ticket_conversion_account",
    "feeder_account",
]

BLOCKER_TYPES = [
    "low_scale_readiness",
    "weak_funnel_economics",
    "weak_offer_fit",
    "weak_retention",
    "weak_ctr",
    "weak_conversion_rate",
    "poor_account_health",
    "high_content_fatigue",
    "high_niche_saturation",
    "high_cannibalization_risk",
    "poor_audience_separation",
    "weak_originality",
    "weak_trust",
    "insufficient_monetization_depth",
    "insufficient_posting_capacity",
    "insufficient_repeatability",
    "insufficient_confidence",
]

# Maps scale.py recommendation_key -> launch candidate type (None = no new account candidate)
REC_KEY_TO_CANDIDATE = {
    "scale_current_winners_harder": "flagship_expansion",
    "add_experimental_account": "experimental_account",
    "add_niche_spinoff_account": "niche_spinoff",
    "add_offer_specific_account": "offer_specific_account",
    "add_platform_specific_account": "platform_specialist_account",
    "add_localized_language_account": "language_expansion_account",
    "add_evergreen_authority_account": "evergreen_authority_account",
    "add_trend_capture_account": "trend_capture_account",
    "add_new_offer_before_adding_account": "offer_specific_account",
    "do_not_scale_yet": None,
    "monitor": None,
    "improve_funnel_before_scaling": None,
    "reduce_or_suppress_weak_account": None,
}

REC_KEY_TO_ALERT = {
    "do_not_scale_yet": "do_not_scale_yet",
    "scale_current_winners_harder": "scale_now",
    "add_experimental_account": "scale_soon",
    "add_niche_spinoff_account": "expansion_opportunity_detected",
    "add_offer_specific_account": "expansion_opportunity_detected",
    "add_platform_specific_account": "platform_shift_recommendation",
    "add_localized_language_account": "expansion_opportunity_detected",
    "add_evergreen_authority_account": "scale_soon",
    "add_trend_capture_account": "scale_soon",
    "reduce_or_suppress_weak_account": "reduce_existing_account",
    "improve_funnel_before_scaling": "improve_funnel_before_scaling",
    "add_new_offer_before_adding_account": "improve_offer_before_scaling",
    "monitor": "hold_and_monitor",
}

EXPANSION_ALERT_TYPES = frozenset(
    {
        "expansion_opportunity_detected",
        "scale_soon",
        "scale_now",
        "platform_shift_recommendation",
        "niche_shift_recommendation",
    }
)

CANNIBALIZATION_SUPPRESS_THRESHOLD = 0.75


def _severity_for(alert_type: str, urgency: float) -> str:
    if urgency >= 80 or alert_type in ("scale_now", "cannibalization_warning", "suppress_account"):
        return "critical"
    if urgency >= 55:
        return "high"
    if urgency >= 35:
        return "medium"
    return "low"


def _dashboard_section(alert_type: str) -> str:
    return {
        "scale_now": "scale_command_center",
        "scale_soon": "scale_command_center",
        "hold_and_monitor": "scale_command_center",
        "do_not_scale_yet": "why_not_yet",
        "reduce_existing_account": "portfolio_overview",
        "suppress_account": "why_not_yet",
        "improve_funnel_before_scaling": "revenue_leaks",
        "improve_offer_before_scaling": "offers",
        "improve_retention_before_scaling": "growth_blockers",
        "improve_originality_before_scaling": "content",
        "expansion_opportunity_detected": "launch_candidates",
        "cannibalization_warning": "saturation",
        "saturation_warning": "saturation",
        "platform_shift_recommendation": "launch_candidates",
        "niche_shift_recommendation": "niche_expansion",
    }.get(alert_type, "scale_command_center")


def _strip_engine_meta(d: dict) -> dict:
    out = {k: v for k, v in d.items() if k != SCALE_ALERT_SOURCE}
    sm = out.get("supporting_metrics") or {}
    if isinstance(sm, dict):
        sm = {k: v for k, v in sm.items() if k != SCALE_ALERT_SOURCE}
        out["supporting_metrics"] = sm
    return out


def dedupe_alerts_by_type(alerts: list[dict]) -> list[dict]:
    """Keep the highest-urgency alert per alert_type (recompute idempotency)."""
    best: dict[str, dict] = {}
    for a in alerts:
        t = a.get("alert_type", "")
        u = float(a.get("urgency", 0))
        if t not in best or u > float(best[t].get("urgency", 0)):
            best[t] = a
    return list(best.values())


def generate_scale_alerts(
    scale_rec: dict,
    accounts: list[dict],
    trust_avg: float,
    leak_count: int,
    cannibalization_risk: float,
    saturation_scores: list[float],
    fatigue_scores: list[float],
    originality_scores: list[float],
) -> list[dict]:
    """Generate alerts from scale recommendation + brand health signals."""
    alerts: list[dict] = []
    rec_key = scale_rec.get("recommendation_key", "monitor")
    readiness = float(scale_rec.get("scale_readiness_score", 0))
    inc_new = float(scale_rec.get("incremental_profit_new_account", 0))
    inc_vol = float(scale_rec.get("incremental_profit_existing_push", 0))

    alert_type = REC_KEY_TO_ALERT.get(rec_key, "hold_and_monitor")
    urgency = min(100.0, readiness * 0.8 + (inc_new - inc_vol) * 0.1)
    if alert_type in ("scale_now", "scale_soon"):
        urgency = max(urgency, 60.0)

    sm_base = {
        "readiness": readiness,
        "inc_new": inc_new,
        "inc_vol": inc_vol,
        "rec_key": rec_key,
        "severity": _severity_for(alert_type, urgency),
        "dashboard_section": _dashboard_section(alert_type),
    }
    alerts.append(
        _strip_engine_meta(
            {
                "alert_type": alert_type,
                "title": f"Scale signal: {rec_key.replace('_', ' ')}",
                "summary": scale_rec.get("explanation", ""),
                "explanation": f"Readiness {readiness:.0f}/100. New account ΔP ${inc_new:.0f} vs volume ΔP ${inc_vol:.0f}.",
                "recommended_action": scale_rec.get("explanation", ""),
                "confidence": min(1.0, readiness / 100),
                "urgency": round(urgency, 1),
                "expected_upside": round(max(inc_new, inc_vol), 2),
                "expected_cost": 150.0 if "add_" in rec_key else 0.0,
                "expected_time_to_signal_days": 14 if readiness > 60 else 30,
                "supporting_metrics": sm_base,
                "blocking_factors": [],
                SCALE_ALERT_SOURCE: True,
            }
        )
    )

    if cannibalization_risk > 0.5:
        u = round(cannibalization_risk * 70, 1)
        alerts.append(
            _strip_engine_meta(
                {
                    "alert_type": "cannibalization_warning",
                    "title": "High cannibalization risk across portfolio",
                    "summary": f"Risk score {cannibalization_risk:.2f} — accounts may be competing for same audience.",
                    "explanation": "Niche overlap between existing accounts is elevated.",
                    "recommended_action": "Diversify niche angles or platforms before adding accounts.",
                    "confidence": 0.7,
                    "urgency": u,
                    "expected_upside": 0,
                    "expected_cost": 0,
                    "expected_time_to_signal_days": 7,
                    "supporting_metrics": {
                        "cannibalization_risk": cannibalization_risk,
                        "severity": _severity_for("cannibalization_warning", u),
                        "dashboard_section": _dashboard_section("cannibalization_warning"),
                    },
                    "blocking_factors": [],
                    SCALE_ALERT_SOURCE: True,
                }
            )
        )

    avg_sat = sum(saturation_scores) / max(1, len(saturation_scores)) if saturation_scores else 0
    if avg_sat > 0.6:
        u = round(avg_sat * 60, 1)
        alerts.append(
            _strip_engine_meta(
                {
                    "alert_type": "saturation_warning",
                    "title": "Niche saturation elevated",
                    "summary": f"Average saturation {avg_sat:.2f} across accounts.",
                    "explanation": "Content angles are becoming repetitive in this niche.",
                    "recommended_action": "Rotate hooks, enter adjacent sub-niches, or reduce posting frequency.",
                    "confidence": 0.65,
                    "urgency": u,
                    "expected_upside": 0,
                    "expected_cost": 0,
                    "expected_time_to_signal_days": 7,
                    "supporting_metrics": {
                        "avg_saturation": avg_sat,
                        "severity": _severity_for("saturation_warning", u),
                        "dashboard_section": _dashboard_section("saturation_warning"),
                    },
                    "blocking_factors": [],
                    SCALE_ALERT_SOURCE: True,
                }
            )
        )
    if avg_sat > 0.72:
        u = round(avg_sat * 65, 1)
        alerts.append(
            _strip_engine_meta(
                {
                    "alert_type": "niche_shift_recommendation",
                    "title": "Consider adjacent niche or sub-niche shift",
                    "summary": f"Saturation {avg_sat:.2f} — whitespace may be outside current niche core.",
                    "explanation": "Opportunity density may be higher with a differentiated angle or adjacent niche.",
                    "recommended_action": "Model adjacent sub-niches and test hooks before scaling volume.",
                    "confidence": 0.62,
                    "urgency": u,
                    "expected_upside": round(inc_new * 0.3, 2),
                    "expected_cost": 120.0,
                    "expected_time_to_signal_days": 21,
                    "supporting_metrics": {
                        "avg_saturation": avg_sat,
                        "severity": _severity_for("niche_shift_recommendation", u),
                        "dashboard_section": _dashboard_section("niche_shift_recommendation"),
                    },
                    "blocking_factors": [],
                    SCALE_ALERT_SOURCE: True,
                }
            )
        )

    avg_fatigue = sum(fatigue_scores) / max(1, len(fatigue_scores)) if fatigue_scores else 0
    if avg_fatigue > 0.55:
        u = round(avg_fatigue * 55, 1)
        alerts.append(
            _strip_engine_meta(
                {
                    "alert_type": "improve_retention_before_scaling",
                    "title": "Content fatigue rising",
                    "summary": f"Average fatigue {avg_fatigue:.2f}.",
                    "explanation": "Audience engagement declining due to repetitive content.",
                    "recommended_action": "Refresh templates and creative formats before scaling volume.",
                    "confidence": 0.6,
                    "urgency": u,
                    "expected_upside": 0,
                    "expected_cost": 0,
                    "expected_time_to_signal_days": 14,
                    "supporting_metrics": {
                        "avg_fatigue": avg_fatigue,
                        "severity": _severity_for("improve_retention_before_scaling", u),
                        "dashboard_section": _dashboard_section("improve_retention_before_scaling"),
                    },
                    "blocking_factors": [],
                    SCALE_ALERT_SOURCE: True,
                }
            )
        )

    avg_orig = sum(originality_scores) / max(1, len(originality_scores)) if originality_scores else 0
    if avg_orig > 0.45:
        u = round(avg_orig * 50, 1)
        alerts.append(
            _strip_engine_meta(
                {
                    "alert_type": "improve_originality_before_scaling",
                    "title": "Originality drift detected",
                    "summary": f"Average drift score {avg_orig:.2f}.",
                    "explanation": "Content similarity to existing library is increasing.",
                    "recommended_action": "Introduce new angles, formats, or hooks before adding volume.",
                    "confidence": 0.55,
                    "urgency": u,
                    "expected_upside": 0,
                    "expected_cost": 0,
                    "expected_time_to_signal_days": 14,
                    "supporting_metrics": {
                        "avg_originality_drift": avg_orig,
                        "severity": _severity_for("improve_originality_before_scaling", u),
                        "dashboard_section": _dashboard_section("improve_originality_before_scaling"),
                    },
                    "blocking_factors": [],
                    SCALE_ALERT_SOURCE: True,
                }
            )
        )

    if trust_avg < 50:
        u = round((100 - trust_avg) * 0.5, 1)
        alerts.append(
            _strip_engine_meta(
                {
                    "alert_type": "suppress_account",
                    "title": "Low trust average — stabilize before scaling",
                    "summary": f"Trust avg {trust_avg:.0f}/100.",
                    "explanation": "Account health or engagement quality is below threshold.",
                    "recommended_action": "Address account health issues and engagement quality.",
                    "confidence": 0.6,
                    "urgency": u,
                    "expected_upside": 0,
                    "expected_cost": 0,
                    "expected_time_to_signal_days": 21,
                    "supporting_metrics": {
                        "trust_avg": trust_avg,
                        "severity": _severity_for("suppress_account", u),
                        "dashboard_section": _dashboard_section("suppress_account"),
                    },
                    "blocking_factors": [],
                    SCALE_ALERT_SOURCE: True,
                }
            )
        )

    if leak_count > 5:
        u = min(80.0, leak_count * 8.0)
        alerts.append(
            _strip_engine_meta(
                {
                    "alert_type": "improve_funnel_before_scaling",
                    "title": f"{leak_count} open revenue leaks",
                    "summary": "Fix conversion leaks before adding scale.",
                    "explanation": f"{leak_count} leak reports open — scaling will amplify losses.",
                    "recommended_action": "Prioritize leak fixes from revenue leak dashboard.",
                    "confidence": 0.7,
                    "urgency": u,
                    "expected_upside": 0,
                    "expected_cost": 0,
                    "expected_time_to_signal_days": 7,
                    "supporting_metrics": {
                        "leak_count": leak_count,
                        "severity": _severity_for("improve_funnel_before_scaling", u),
                        "dashboard_section": _dashboard_section("improve_funnel_before_scaling"),
                    },
                    "blocking_factors": [],
                    SCALE_ALERT_SOURCE: True,
                }
            )
        )

    return dedupe_alerts_by_type(alerts)


def _one_candidate(
    candidate_type: str,
    scale_rec: dict,
    accounts: list[dict],
    brand_niche: str | None,
    cannibalization_risk: float,
    audience_separation: float,
    offers: list[dict],
    platform_override: str | None = None,
    geo_override: str | None = None,
    lang_override: str | None = None,
) -> dict:
    readiness = float(scale_rec.get("scale_readiness_score", 0))
    inc_new = float(scale_rec.get("incremental_profit_new_account", 0))
    best_next = scale_rec.get("best_next_account", {})
    platforms_used = {a.get("platform", "youtube") for a in accounts}
    _all_plats = ["youtube", "tiktok", "instagram", "twitter", "reddit", "linkedin", "facebook"]
    alt_platform = next((p for p in _all_plats if p not in platforms_used), "tiktok")
    niche = brand_niche or "general"
    geo = geo_override or ((accounts[0].get("geography") or "US") if accounts else "US")
    lang = lang_override or ((accounts[0].get("language") or "en") if accounts else "en")

    rev_min = max(0, inc_new * 0.6)
    rev_max = max(rev_min + 1, inc_new * 1.4)
    launch_cost = 150.0 + (80.0 if candidate_type in ("flagship_expansion", "high_ticket_conversion_account") else 0)
    if candidate_type == "feeder_account":
        launch_cost = 75.0

    platform = platform_override or best_next.get("platform_suggestion", alt_platform)
    if candidate_type == "language_expansion_account":
        lang = lang_override or "es"
        geo = geo_override or "LATAM"
    elif candidate_type == "geo_localized_account":
        geo = geo_override or "EU-5"
    elif candidate_type == "platform_specialist_account":
        platform = alt_platform
    elif candidate_type == "high_ticket_conversion_account":
        rev_min = max(rev_min, 2000)
        rev_max = max(rev_max, 8000)
        launch_cost += 200.0

    reasons = [best_next.get("rationale", f"Scale engine suggests {candidate_type}.")]
    if readiness > 60:
        reasons.append(f"Scale readiness {readiness:.0f}/100 supports expansion.")
    if inc_new > 100:
        reasons.append(f"Incremental profit estimate ${inc_new:.0f}/week from new account.")

    blockers: list[str] = []
    if cannibalization_risk > 0.5:
        blockers.append(f"Cannibalization risk {cannibalization_risk:.2f} — separate niche angle needed.")
    if readiness < 40:
        blockers.append(f"Scale readiness {readiness:.0f}/100 is below launch threshold.")

    return {
        "candidate_type": candidate_type,
        "primary_platform": platform,
        "secondary_platform": next(
            (
                p
                for p in ["instagram", "tiktok", "youtube", "twitter", "reddit", "linkedin", "facebook"]
                if p != platform and p not in platforms_used
            ),
            None,
        ),
        "niche": niche,
        "sub_niche": best_next.get("niche_suggestion", f"Sub-angle of {niche}"),
        "language": lang,
        "geography": geo,
        "avatar_persona_strategy": f"New {candidate_type.replace('_', ' ')} persona for {niche}",
        "monetization_path": f"Primary: {offers[0].get('name', 'affiliate') if offers else 'affiliate'} | Method: content → CTA → offer",
        "content_style": best_next.get("content_style", "Match winning formats from flagship"),
        "posting_strategy": f"{best_next.get('posting_capacity_suggestion', 2)} posts/day, ramp over 2 weeks",
        "expected_monthly_revenue_min": round(rev_min, 2),
        "expected_monthly_revenue_max": round(rev_max, 2),
        "expected_launch_cost": round(launch_cost, 2),
        "expected_time_to_signal_days": 21 if readiness > 60 else 45,
        "expected_time_to_profit_days": 60 if readiness > 60 else 120,
        "cannibalization_risk": round(cannibalization_risk, 3),
        "audience_separation_score": round(audience_separation, 3),
        "confidence": min(0.9, readiness / 100),
        "urgency": min(100.0, readiness * 0.8 + inc_new * 0.05),
        "supporting_reasons": reasons,
        "required_resources": ["avatar setup", "content templates", f"platform account ({platform})"],
        "launch_blockers": blockers,
        SCALE_ALERT_SOURCE: True,
    }


def generate_launch_candidates(
    scale_rec: dict,
    accounts: list[dict],
    brand_niche: str | None,
    cannibalization_risk: float,
    audience_separation: float,
    offers: list[dict],
) -> list[dict]:
    """Generate typed launch candidates from scale recommendation."""
    if cannibalization_risk >= CANNIBALIZATION_SUPPRESS_THRESHOLD:
        return []

    rec_key = scale_rec.get("recommendation_key", "monitor")
    candidate_type = REC_KEY_TO_CANDIDATE.get(rec_key)
    out: list[dict] = []

    if candidate_type:
        raw = _one_candidate(
            candidate_type,
            scale_rec,
            accounts,
            brand_niche,
            cannibalization_risk,
            audience_separation,
            offers,
        )
        out.append(_strip_engine_meta(raw))

    # Secondary opportunity: platform shift specialist when multi-platform portfolio underutilized
    readiness = float(scale_rec.get("scale_readiness_score", 0))
    if len(accounts) >= 2 and readiness > 55 and cannibalization_risk < 0.45:
        plat_set = {a.get("platform", "youtube") for a in accounts}
        if len(plat_set) == 1 and not out:
            raw = _one_candidate(
                "platform_specialist_account",
                scale_rec,
                accounts,
                brand_niche,
                cannibalization_risk,
                audience_separation,
                offers,
            )
            raw["supporting_reasons"] = list(raw.get("supporting_reasons", [])) + [
                "Portfolio concentrated on one platform — diversification candidate.",
            ]
            out.append(_strip_engine_meta(raw))

    # Feeder / experimental when monitoring but healthy
    if rec_key == "monitor" and readiness >= 50 and cannibalization_risk < 0.4:
        raw = _one_candidate(
            "feeder_account",
            scale_rec,
            accounts,
            brand_niche,
            cannibalization_risk,
            audience_separation,
            offers,
        )
        raw["urgency"] = min(55.0, float(raw["urgency"]))
        out.append(_strip_engine_meta(raw))

    # High-ticket path when incremental profit very high
    inc_new = float(scale_rec.get("incremental_profit_new_account", 0))
    if inc_new > 2000 and cannibalization_risk < 0.5:
        raw = _one_candidate(
            "high_ticket_conversion_account",
            scale_rec,
            accounts,
            brand_niche,
            cannibalization_risk,
            audience_separation,
            offers,
        )
        raw["supporting_reasons"] = list(raw.get("supporting_reasons", [])) + [
            "High incremental profit supports a conversion-focused account.",
        ]
        out.append(_strip_engine_meta(raw))

    # Dedupe by candidate_type — keep highest urgency
    by_type: dict[str, dict] = {}
    for c in out:
        t = c["candidate_type"]
        if t not in by_type or float(c["urgency"]) > float(by_type[t]["urgency"]):
            by_type[t] = c
    return list(by_type.values())


def diagnose_scale_blockers(
    readiness: float,
    accounts: list[dict],
    trust_avg: float,
    leak_count: int,
    cannibalization_risk: float,
    audience_separation: float,
    offer_count: int,
    expansion_confidence: float = 0.5,
    avg_ctr: float = 0.02,
    avg_cvr: float = 0.02,
    total_posting_cap: int = 6,
    monetization_depth: int = 0,
) -> list[dict]:
    """Detect and return all active scale blockers."""
    blockers: list[dict] = []

    def _add(btype, title, explanation, fix, current, threshold, severity="medium"):
        blockers.append(
            {
                "blocker_type": btype,
                "title": title,
                "explanation": explanation,
                "recommended_fix": fix,
                "current_value": round(float(current), 4),
                "threshold_value": round(float(threshold), 4),
                "severity": severity,
                "evidence": {SCALE_ALERT_SOURCE: True},
            }
        )

    if readiness < 35:
        _add(
            "low_scale_readiness",
            "Scale readiness too low",
            f"Score {readiness:.0f}/100 is below safe launch threshold.",
            "Improve account health, reduce fatigue, increase CTR/CVR.",
            readiness,
            35,
            "high",
        )

    n = max(1, len(accounts))
    for a in accounts:
        if float(a.get("fatigue_score", 0)) > 0.6:
            _add(
                "high_content_fatigue",
                f"Fatigue on {a.get('username', '?')}",
                "Content fatigue elevated.",
                "Rotate hooks and creative templates.",
                float(a.get("fatigue_score", 0)),
                0.6,
            )
        if float(a.get("saturation_score", 0)) > 0.6:
            _add(
                "high_niche_saturation",
                f"Saturation on {a.get('username', '?')}",
                "Niche saturation high.",
                "Enter adjacent sub-niche or reduce posting frequency.",
                float(a.get("saturation_score", 0)),
                0.6,
            )
        if float(a.get("originality_drift_score", 0)) > 0.45:
            _add(
                "weak_originality",
                f"Originality drift on {a.get('username', '?')}",
                "Content too similar to existing library.",
                "Introduce new content formats.",
                float(a.get("originality_drift_score", 0)),
                0.45,
            )
        if float(a.get("ctr", 0)) < 0.012:
            _add(
                "weak_ctr",
                f"Low CTR on {a.get('username', '?')}",
                "Click-through rate is below viable scaling threshold.",
                "Test hooks, thumbnails, and first-frame retention.",
                float(a.get("ctr", 0)),
                0.012,
            )
        if float(a.get("conversion_rate", 0)) < 0.008:
            _add(
                "weak_conversion_rate",
                f"Low CVR on {a.get('username', '?')}",
                "Conversion rate underperforms vs threshold.",
                "Tighten offer alignment and funnel steps.",
                float(a.get("conversion_rate", 0)),
                0.008,
            )
        health = (a.get("account_health") or "healthy").lower()
        if health in ("degraded", "critical", "suspended"):
            _add(
                "poor_account_health",
                f"Account health: {health}",
                "Account health is degraded.",
                "Stabilize account before scaling.",
                {"healthy": 1, "warning": 0.75, "degraded": 0.5, "critical": 0.25, "suspended": 0}.get(health, 0.5),
                0.75,
                "high",
            )

    if trust_avg < 50:
        _add(
            "weak_trust",
            "Low trust average",
            f"Trust {trust_avg:.0f}/100.",
            "Fix engagement quality and account health.",
            trust_avg,
            50,
        )
    if cannibalization_risk > 0.5:
        _add(
            "high_cannibalization_risk",
            "Cannibalization risk elevated",
            f"Risk {cannibalization_risk:.2f}.",
            "Separate niche angles or platforms.",
            cannibalization_risk,
            0.5,
        )
    if audience_separation < 0.4:
        _add(
            "poor_audience_separation",
            "Audience overlap too high",
            f"Separation {audience_separation:.2f}.",
            "Diversify niche or platform.",
            audience_separation,
            0.4,
        )
    if leak_count > 5:
        _add(
            "weak_funnel_economics",
            f"{leak_count} open leaks",
            "Revenue leaks undermining unit economics.",
            "Fix leaks before scaling.",
            leak_count,
            5,
        )
    if offer_count < 2:
        _add(
            "weak_offer_fit",
            "Offer catalog too thin",
            f"Only {offer_count} offer(s).",
            "Add complementary offers.",
            offer_count,
            2,
        )
    if monetization_depth < 2:
        _add(
            "insufficient_monetization_depth",
            "Monetization depth limited",
            f"Depth score {monetization_depth}.",
            "Add offers, bundles, or upsell paths.",
            monetization_depth,
            2,
        )
    if avg_ctr < 0.015:
        _add(
            "weak_ctr",
            "Portfolio CTR below threshold",
            f"Average CTR {avg_ctr:.4f}.",
            "Improve hooks and CTR before scaling spend.",
            avg_ctr,
            0.015,
        )
    if avg_cvr < 0.01:
        _add(
            "weak_conversion_rate",
            "Portfolio conversion below threshold",
            f"Average CVR {avg_cvr:.4f}.",
            "Fix funnel and offer-message fit.",
            avg_cvr,
            0.01,
        )
    if total_posting_cap < 3:
        _add(
            "insufficient_posting_capacity",
            "Posting capacity too low for multi-account scale",
            f"Total capacity {total_posting_cap}/day.",
            "Hire editors or reduce account count.",
            total_posting_cap,
            3,
        )
    if readiness < 45 and len(accounts) < 2:
        _add(
            "insufficient_repeatability",
            "Limited proof of repeatability",
            f"{len(accounts)} active account(s).",
            "Prove one more repeatable winner before launching.",
            len(accounts),
            2,
        )
    if expansion_confidence < 0.28:
        _add(
            "insufficient_confidence",
            "Expansion confidence low",
            f"Confidence {expansion_confidence:.2f}.",
            "Gather more signal before new launches.",
            expansion_confidence,
            0.28,
        )

    avg_fat = sum(float(a.get("fatigue_score", 0)) for a in accounts) / n
    if avg_fat > 0.55:
        _add(
            "weak_retention",
            "Retention pressure from fatigue",
            f"Average fatigue {avg_fat:.2f}.",
            "Refresh creative before scaling.",
            avg_fat,
            0.55,
        )

    # Dedupe blocker_type keeping highest severity
    sev_rank = {"high": 3, "medium": 2, "low": 1}
    merged: dict[str, dict] = {}
    for b in blockers:
        t = b["blocker_type"]
        if t not in merged or sev_rank.get(b.get("severity", "medium"), 2) > sev_rank.get(
            merged[t].get("severity", "medium"), 2
        ):
            merged[t] = b
    return list(merged.values())


def compute_launch_readiness(
    scale_readiness: float,
    expansion_confidence: float,
    audience_separation: float,
    avg_saturation: float,
    monetization_depth: float,
    funnel_conversion_rate: float,
    trust_avg: float,
    posting_capacity_total: int,
    cannibalization_risk: float,
) -> dict:
    """Compute launch readiness score (0-100) with components and recommendation."""
    # Blend saturation with opportunity density (whitespace in niche/platform proxy)
    opportunity_density = max(0.0, 1.0 - min(1.0, avg_saturation * 0.85))
    saturation_opportunity = max(0, 1 - avg_saturation) * 0.5 + opportunity_density * 0.5
    components = {
        "scale_readiness": round(scale_readiness / 100 * 0.20, 4),
        "expansion_confidence": round(min(1, expansion_confidence) * 0.15, 4),
        "audience_separation": round(audience_separation * 0.10, 4),
        "saturation_inverse": round(saturation_opportunity * 0.10, 4),
        "monetization_depth": round(min(1, monetization_depth / 5) * 0.10, 4),
        "funnel_readiness": round(min(1, funnel_conversion_rate / 0.05) * 0.10, 4),
        "trust_readiness": round(trust_avg / 100 * 0.10, 4),
        "posting_capacity": round(min(1, posting_capacity_total / 6) * 0.05, 4),
        "cannibalization_inverse": round(max(0, 1 - cannibalization_risk) * 0.10, 4),
    }
    score = round(sum(components.values()) * 100, 1)

    gating: list[str] = []
    if scale_readiness < 35:
        gating.append("Scale readiness below threshold")
    if trust_avg < 50:
        gating.append("Trust score too low")
    if cannibalization_risk > 0.6:
        gating.append("Cannibalization risk too high")
    if funnel_conversion_rate < 0.005:
        gating.append("Funnel conversion rate near zero")

    if gating:
        action = "do_not_launch_yet"
        explanation = f"Launch blocked: {'; '.join(gating)}."
    elif score >= 70:
        action = "launch_now"
        explanation = f"Readiness {score:.0f}/100 — conditions support launch."
    elif score >= 50:
        action = "prepare_but_wait"
        explanation = f"Readiness {score:.0f}/100 — prepare assets but wait for better conditions."
    else:
        action = "monitor"
        explanation = f"Readiness {score:.0f}/100 — monitor and improve weak areas."

    return {
        "launch_readiness_score": score,
        "explanation": explanation,
        "recommended_action": action,
        "gating_factors": gating,
        "components": components,
        SCALE_ALERT_SOURCE: True,
    }
