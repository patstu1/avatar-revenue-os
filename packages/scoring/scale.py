"""Phase 5 scale intelligence: readiness, incremental profit, cannibalization, expansion."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Canonical recommendation keys (persisted + API)
RK_DO_NOT_SCALE_YET = "do_not_scale_yet"
RK_SCALE_WINNERS_HARDER = "scale_current_winners_harder"
RK_ADD_EXPERIMENTAL = "add_experimental_account"
RK_ADD_NICHE_SPINOFF = "add_niche_spinoff_account"
RK_ADD_OFFER_SPECIFIC = "add_offer_specific_account"
RK_ADD_PLATFORM_SPECIFIC = "add_platform_specific_account"
RK_ADD_LOCALIZED = "add_localized_language_account"
RK_ADD_EVERGREEN_AUTHORITY = "add_evergreen_authority_account"
RK_ADD_TREND_CAPTURE = "add_trend_capture_account"
RK_REDUCE_WEAK = "reduce_or_suppress_weak_account"
RK_IMPROVE_FUNNEL = "improve_funnel_before_scaling"
RK_ADD_OFFER_FIRST = "add_new_offer_before_adding_account"
RK_MONITOR = "monitor"

NEW_ACCOUNT_OVERHEAD_USD = 150.0
VOLUME_LIFT_FACTOR = 0.35
EXPANSION_BEATS_EXISTING_RATIO = 1.15


def _tokens(s: str | None) -> set[str]:
    if not s:
        return set()
    return {t for t in s.lower().replace("/", " ").replace(",", " ").split() if len(t) > 1}


def niche_jaccard(a: str | None, b: str | None) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def health_to_score(health: str) -> float:
    h = (health or "healthy").lower()
    return {
        "healthy": 1.0,
        "warning": 0.75,
        "degraded": 0.5,
        "critical": 0.25,
        "suspended": 0.0,
    }.get(h, 0.7)


@dataclass
class AccountScaleSnapshot:
    """Per-account inputs for scale math (mapped from CreatorAccount + live rollup)."""

    account_id: str
    platform: str
    username: str
    niche_focus: str | None
    sub_niche_focus: str | None
    revenue: float
    profit: float
    profit_per_post: float
    revenue_per_mille: float
    ctr: float
    conversion_rate: float
    follower_growth_rate: float
    fatigue_score: float
    saturation_score: float
    originality_drift_score: float
    diminishing_returns_score: float
    posting_capacity_per_day: int
    account_health: str
    offer_performance_score: float  # 0–1 from brand offers
    scale_role: str | None = None
    impressions_rollup: int = 0


@dataclass
class ScaleEngineResult:
    scale_readiness_score: float
    incremental_profit_new_account: float
    incremental_profit_more_volume: float
    cannibalization_risk: float
    audience_segment_separation: float
    expansion_confidence: float
    recommendation_key: str
    coarse_action: str  # RecommendedAction value
    recommended_account_count: int
    explanation: str
    best_next_account: dict[str, Any]
    weekly_action_plan: list[dict[str, Any]]
    score_components: dict[str, float]
    penalties: dict[str, float]
    secondary_keys: list[str] = field(default_factory=list)


def compute_offer_performance_score(offers: list[dict]) -> float:
    """0–1 from active offers: blend EPC and conversion."""
    if not offers:
        return 0.35
    best = 0.0
    for o in offers:
        epc = float(o.get("epc") or 0) / 5.0
        cr = float(o.get("conversion_rate") or 0) / 0.1
        best = max(best, min(1.0, (epc + cr) / 2))
    return round(min(1.0, max(0.15, best)), 4)


def compute_cannibalization_risk(accounts: list[AccountScaleSnapshot]) -> float:
    """0–1: high when many same-platform accounts share niche wording."""
    if len(accounts) < 2:
        return 0.12
    pairs: list[float] = []
    [a.platform for a in accounts]
    for i, ai in enumerate(accounts):
        for j in range(i + 1, len(accounts)):
            aj = accounts[j]
            niche_sim = niche_jaccard(
                " ".join(filter(None, [ai.niche_focus, ai.sub_niche_focus])),
                " ".join(filter(None, [aj.niche_focus, aj.sub_niche_focus])),
            )
            platform_hit = 1.0 if ai.platform == aj.platform else 0.35
            pairs.append(niche_sim * platform_hit)
    avg = sum(pairs) / len(pairs) if pairs else 0.0
    return round(min(1.0, avg * 1.25), 4)


def compute_audience_segment_separation(accounts: list[AccountScaleSnapshot]) -> float:
    """1 = well separated; 0 = overlapping."""
    if len(accounts) < 2:
        return 0.85
    cr = compute_cannibalization_risk(accounts)
    return round(max(0.0, min(1.0, 1.0 - cr)), 4)


def compute_expansion_confidence(
    accounts: list[AccountScaleSnapshot],
    total_impressions: int,
    profitable_account_count: int,
) -> float:
    vol = min(1.0, total_impressions / 150_000) if total_impressions else 0.2
    profit_signal = min(1.0, profitable_account_count / max(1, len(accounts)))
    base = 0.25 + 0.45 * vol + 0.3 * profit_signal
    return round(min(1.0, max(0.1, base)), 4)


def compute_scale_readiness_score(
    accounts: list[AccountScaleSnapshot],
    offer_performance_score: float,
) -> tuple[float, dict[str, float]]:
    if not accounts:
        return 0.0, {}

    parts: dict[str, float] = {}
    agg = 0.0
    n = len(accounts)
    for a in accounts:
        h = health_to_score(a.account_health)
        fat = max(0.0, 1.0 - min(1.0, a.fatigue_score))
        sat = max(0.0, 1.0 - min(1.0, a.saturation_score))
        dr = max(0.0, 1.0 - min(1.0, a.diminishing_returns_score))
        ctr_n = min(1.0, a.ctr / 0.06)
        cvr_n = min(1.0, a.conversion_rate / 0.08)
        fg = min(1.0, max(0.0, a.follower_growth_rate) / 0.05)
        orig = max(0.0, 1.0 - min(1.0, a.originality_drift_score))
        acc_score = (
            0.18 * h
            + 0.14 * fat
            + 0.14 * sat
            + 0.1 * ctr_n
            + 0.1 * cvr_n
            + 0.12 * dr
            + 0.1 * fg
            + 0.08 * orig
            + 0.04 * offer_performance_score
        )
        agg += acc_score

    avg = agg / n
    portfolio_0_1 = min(1.0, max(0.0, avg))
    parts["per_account_readiness_avg"] = round(portfolio_0_1, 4)
    parts["offer_performance"] = round(offer_performance_score, 4)
    return round(portfolio_0_1 * 100, 2), parts


def compute_incremental_profit_more_volume(accounts: list[AccountScaleSnapshot]) -> float:
    total = 0.0
    for a in accounts:
        lift = a.posting_capacity_per_day * VOLUME_LIFT_FACTOR
        marginal_units = lift * max(0.0, 1.0 - min(1.0, a.diminishing_returns_score))
        total += max(0.0, a.profit_per_post) * marginal_units
    return round(total, 2)


def compute_incremental_profit_new_account(
    accounts: list[AccountScaleSnapshot],
    expansion_confidence: float,
    cannibalization_risk: float,
) -> float:
    if not accounts:
        return 0.0
    best_ppp = max(a.profit_per_post for a in accounts)
    cap = max(a.posting_capacity_per_day for a in accounts)
    baseline_week = best_ppp * min(cap, 3) * 7
    raw = baseline_week * expansion_confidence * max(0.2, 1.0 - cannibalization_risk)
    return round(max(0.0, raw - NEW_ACCOUNT_OVERHEAD_USD), 2)


def _pick_best_next_account(
    recommendation_key: str,
    accounts: list[AccountScaleSnapshot],
    brand_niche: str | None,
) -> dict[str, Any]:
    platforms_seen = {a.platform for a in accounts}
    _all_plats = [
        "youtube",
        "tiktok",
        "instagram",
        "twitter",
        "reddit",
        "linkedin",
        "facebook",
        "pinterest",
        "threads",
        "snapchat",
    ]
    alt = next((p for p in _all_plats if p not in platforms_seen), "tiktok")
    if recommendation_key == RK_ADD_PLATFORM_SPECIFIC:
        return {
            "account_type_key": recommendation_key,
            "platform_suggestion": alt,
            "niche_suggestion": brand_niche or "Adjacent angle on core niche",
            "rationale": "Diversify platform exposure while reusing proven creative patterns.",
        }
    if recommendation_key == RK_ADD_NICHE_SPINOFF:
        return {
            "account_type_key": recommendation_key,
            "platform_suggestion": list(platforms_seen)[0] if platforms_seen else "youtube",
            "niche_suggestion": f"Sub-niche spinoff of: {brand_niche or 'core topic'}",
            "rationale": "Separate sub-audience to reduce cannibalization and test new angles.",
        }
    if recommendation_key == RK_ADD_LOCALIZED:
        return {
            "account_type_key": recommendation_key,
            "language_suggestion": "es",
            "platform_suggestion": "youtube",
            "rationale": "Language/geo split increases audience segment separation.",
        }
    if recommendation_key == RK_ADD_TREND_CAPTURE:
        return {
            "account_type_key": recommendation_key,
            "posting_capacity_suggestion": 4,
            "rationale": "Short-cycle account to harvest trends without risking flagship quality.",
        }
    if recommendation_key == RK_ADD_EVERGREEN_AUTHORITY:
        return {
            "account_type_key": recommendation_key,
            "content_style": "longer-format authority / explainers",
            "rationale": "Balances volatile short-form performance with compounding evergreen.",
        }
    if recommendation_key == RK_ADD_OFFER_SPECIFIC:
        return {
            "account_type_key": recommendation_key,
            "rationale": "Dedicated CTA alignment when multiple offers split conversion intent.",
        }
    if recommendation_key == RK_ADD_EXPERIMENTAL:
        return {
            "account_type_key": recommendation_key,
            "rationale": "Maintain default 1 flagship + 1 experimental structure for learning.",
        }
    return {
        "account_type_key": recommendation_key or RK_SCALE_WINNERS_HARDER,
        "rationale": "Derived from scale engine comparison of expansion vs exploitation.",
    }


def build_weekly_action_plan(
    primary_key: str,
    accounts: list[AccountScaleSnapshot],
    weak_usernames: list[str],
) -> list[dict[str, Any]]:
    flagship = next((a for a in accounts if (a.scale_role or "").lower() == "flagship"), None)
    exp = next((a for a in accounts if (a.scale_role or "").lower() == "experimental"), None)
    win_user = flagship.username if flagship else (accounts[0].username if accounts else "@account")

    plans = [
        {
            "day": "Monday",
            "theme": "Exploit winners",
            "actions": [
                f"Increase {win_user} output by +1 post if QA pass rate > 80%.",
                "Review top 3 hooks from last 14 days for reuse as variants.",
            ],
        },
        {
            "day": "Tuesday",
            "theme": "Funnel integrity",
            "actions": [
                "Audit CTAs and landing paths on flagship posts with traffic but low conversion.",
                "Confirm UTM + attribution on net-new experiments only.",
            ],
        },
        {
            "day": "Wednesday",
            "theme": "Capacity & fatigue",
            "actions": [
                "Check fatigue and saturation scores before adding volume.",
                "Trim weakest 10% of posting backlog if originality drift is rising.",
            ],
        },
        {
            "day": "Thursday",
            "theme": "Portfolio structure",
            "actions": [
                "Align experimental learnings back to flagship only after validation.",
                "Document cannibalization guardrails (niche wording + platform split).",
            ],
        },
        {
            "day": "Friday",
            "theme": "Expansion decision",
            "actions": [
                "Re-run scale recompute before opening a new account.",
                "Only add accounts if incremental expansion profit clears exploitation baseline.",
            ],
        },
    ]

    if primary_key == RK_SCALE_WINNERS_HARDER:
        plans[0]["actions"].insert(0, "Prioritize posting capacity on highest profit_per_post accounts.")
    elif primary_key == RK_IMPROVE_FUNNEL:
        plans[1]["theme"] = "Funnel fix sprint"
        plans[1]["actions"] = ["Fix primary bottleneck before volume.", "Delay new account creation."]
    elif primary_key in (RK_ADD_EXPERIMENTAL, RK_ADD_PLATFORM_SPECIFIC, RK_ADD_NICHE_SPINOFF):
        plans[4]["actions"][0] = "Prepare brief templates for the new account angle before launch."

    if weak_usernames:
        plans[2]["actions"].append(f"Review or reduce posting on weak accounts: {', '.join(weak_usernames[:3])}")

    if exp:
        plans[3]["actions"].insert(
            0, f"Ship 2 controlled tests on experimental {exp.username}; promote winners only to flagship."
        )

    return plans


def _default_roles_if_missing(accounts: list[AccountScaleSnapshot]) -> None:
    """Mutates snapshots: assign flagship / experimental by profit when missing."""
    if len(accounts) < 2:
        if accounts and not accounts[0].scale_role:
            accounts[0].scale_role = "flagship"
        return
    sorted_accs = sorted(accounts, key=lambda x: x.profit, reverse=True)
    id_to_role: dict[str, str] = {}
    for a in accounts:
        if a.scale_role:
            id_to_role[a.account_id] = a.scale_role
    if len([x for x in accounts if x.scale_role]) < 2:
        id_to_role[sorted_accs[0].account_id] = "flagship"
        for a in sorted_accs[1:]:
            if a.account_id not in id_to_role:
                id_to_role[a.account_id] = "experimental"
                break
    for a in accounts:
        if a.account_id in id_to_role:
            a.scale_role = id_to_role[a.account_id]


def run_scale_engine(
    accounts: list[AccountScaleSnapshot],
    offers: list[dict],
    total_impressions: int,
    brand_niche: str | None,
    funnel_weak: bool,
    weak_offer_diversity: bool,
) -> ScaleEngineResult:
    """Main entry: recommendations + persisted-friendly payload fragments."""
    _default_roles_if_missing(accounts)

    offer_pf = compute_offer_performance_score(offers)
    cann = compute_cannibalization_risk(accounts)
    seg_sep = compute_audience_segment_separation(accounts)
    prof_count = sum(1 for a in accounts if a.profit > 0)
    exp_conf = compute_expansion_confidence(accounts, total_impressions, prof_count)
    readiness, comp_parts = compute_scale_readiness_score(accounts, offer_pf)
    inc_existing = compute_incremental_profit_more_volume(accounts)
    inc_new = compute_incremental_profit_new_account(accounts, exp_conf, cann)
    ratio = inc_new / inc_existing if inc_existing > 1e-6 else (1.0 if inc_new > 0 else 0.0)

    penalties: dict[str, float] = {}
    if cann > 0.55:
        penalties["high_cannibalization"] = round(cann, 4)
    if readiness < 35:
        penalties["low_readiness"] = round(readiness, 2)

    secondary: list[str] = []
    weak_accounts = [a for a in accounts if a.profit_per_post < 2 and a.impressions_rollup > 300]
    weak_names = [a.username for a in weak_accounts]

    for _ in weak_accounts[:2]:
        secondary.append(RK_REDUCE_WEAK)

    rec_key = RK_MONITOR
    coarse = "monitor"
    explanation = ""
    comparison_ratio = round(ratio, 4)

    if weak_offer_diversity:
        rec_key = RK_ADD_OFFER_FIRST
        coarse = "experiment"
        explanation = "Offer catalog is thin or weak; diversify monetization before scaling surface area."
    elif funnel_weak:
        rec_key = RK_IMPROVE_FUNNEL
        coarse = "maintain"
        explanation = "CTR or conversion bottleneck detected; improve funnel before scaling spend or new accounts."
    elif readiness < 28:
        rec_key = RK_DO_NOT_SCALE_YET
        coarse = "maintain"
        explanation = f"Scale readiness {readiness:.1f}/100 is below safe threshold."
    elif inc_new > inc_existing * EXPANSION_BEATS_EXISTING_RATIO and exp_conf >= 0.45 and cann < 0.62:
        if cann > 0.45:
            rec_key = RK_ADD_NICHE_SPINOFF
            coarse = "scale"
            explanation = "Expansion beats exploitation; high cannibalization risk favors a niche-separated account."
        elif len({a.platform for a in accounts}) < 2:
            rec_key = RK_ADD_PLATFORM_SPECIFIC
            coarse = "scale"
            explanation = "Expansion beats exploitation; add platform diversification."
        elif seg_sep < 0.45:
            rec_key = RK_ADD_LOCALIZED
            coarse = "experiment"
            explanation = "Audience overlap high; language/geo split improves separation."
        else:
            rec_key = RK_ADD_EXPERIMENTAL
            coarse = "experiment"
            explanation = "Incremental profit from a controlled new account exceeds marginal volume on incumbents."
    elif readiness >= 55 and inc_existing >= inc_new * 0.85:
        rec_key = RK_SCALE_WINNERS_HARDER
        coarse = "scale"
        explanation = "Portfolio is readiness-strong; push volume on current winners before expanding footprint."
    elif offer_pf < 0.45:
        rec_key = RK_ADD_OFFER_SPECIFIC
        coarse = "experiment"
        explanation = "Offer performance signal weak relative to traffic; tighten offer-to-audience fit."
    elif seg_sep >= 0.65 and exp_conf >= 0.55:
        rec_key = RK_ADD_TREND_CAPTURE
        coarse = "experiment"
        explanation = "Segments are separated enough to run a trend-harvest lane without eroding flagship."
    else:
        rec_key = RK_ADD_EVERGREEN_AUTHORITY
        coarse = "maintain"
        explanation = "Default to authority/evergreen lane until trend bandwidth is justified."

    if len(accounts) == 1:
        if rec_key not in (RK_DO_NOT_SCALE_YET, RK_IMPROVE_FUNNEL, RK_ADD_OFFER_FIRST):
            rec_key = RK_ADD_EXPERIMENTAL
            coarse = "experiment"
            explanation = (
                "Single-account brand: add experimental lane per default portfolio (1 flagship + 1 experimental)."
            )

    best_next = _pick_best_next_account(rec_key, accounts, brand_niche)
    weekly = build_weekly_action_plan(rec_key, accounts, weak_names)

    rec_count = 2
    if exp_conf >= 0.65 and cann < 0.4 and readiness > 60:
        rec_count = min(6, 2 + int(readiness // 25))
    elif rec_key == RK_DO_NOT_SCALE_YET:
        rec_count = max(1, len([a for a in accounts if (a.scale_role or "").lower() == "flagship"]))

    comp_parts["incremental_profit_new_account"] = inc_new
    comp_parts["incremental_profit_existing_push"] = inc_existing
    comp_parts["comparison_ratio"] = comparison_ratio
    comp_parts["cannibalization_risk"] = cann
    comp_parts["audience_segment_separation"] = seg_sep
    comp_parts["expansion_confidence"] = exp_conf

    return ScaleEngineResult(
        scale_readiness_score=readiness,
        incremental_profit_new_account=inc_new,
        incremental_profit_more_volume=inc_existing,
        cannibalization_risk=cann,
        audience_segment_separation=seg_sep,
        expansion_confidence=exp_conf,
        recommendation_key=rec_key,
        coarse_action=coarse,
        recommended_account_count=rec_count,
        explanation=explanation,
        best_next_account=best_next,
        weekly_action_plan=weekly,
        score_components=comp_parts,
        penalties=penalties,
        secondary_keys=list(dict.fromkeys(secondary)),
    )
