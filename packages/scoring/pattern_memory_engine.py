"""Winning-Pattern Memory Engine — extract, score, cluster, decay, reuse patterns.

Pure functions. No I/O.
"""

from __future__ import annotations

import hashlib
from typing import Any

PATTERN_TYPES = [
    "hook",
    "creative_structure",
    "content_form",
    "offer_angle",
    "cta",
    "monetization",
    "audience_response",
]

OFFER_ANGLE_PATTERNS = {
    "budget": "Budget/affordability angle",
    "premium": "Premium/luxury positioning",
    "convenience": "Convenience or time-saving angle",
    "comparison": "Side-by-side comparison angle",
    "problem_relief": "Problem-relief or pain-solution angle",
    "identity": "Identity or status angle",
    "productivity": "Productivity or efficiency angle",
    "health": "Health or longevity angle",
}

AUDIENCE_RESPONSE_PATTERNS = {
    "objection_heavy_high_conversion": "High objection volume but strong downstream conversion",
    "high_engagement_low_monetization": "Lots of engagement, weak monetization",
    "low_engagement_high_purchase": "Low vanity metrics but strong purchase intent",
    "trust_building_winner": "Builds trust — high saves, shares, follows",
    "reach_winner": "Exceptional reach — viral signals",
    "conversion_winner": "Strong conversion metrics across the board",
}

HOOK_PATTERNS = {
    "direct_pain": "Leads with a pain point the audience feels right now",
    "curiosity": "Opens with an unanswered question or surprising claim",
    "comparison": "Compares two options to create decision tension",
    "things_i_wish": "Personal regret framing — 'things I wish I knew'",
    "dont_buy_until": "Purchase-gating urgency — 'don't buy X until you see this'",
    "authority_led": "Credential or expertise-first opening",
    "testimonial_led": "Social proof or customer result opening",
}

CREATIVE_STRUCTURES = {
    "problem_solution_cta": "Problem → solution → CTA",
    "listicle": "Numbered list of tips/items",
    "before_after": "Before/after transformation",
    "talking_head_broll": "Talking head with B-roll inserts",
    "text_carousel": "Text-led carousel slides",
    "fast_cut_comparison": "Fast-cut side-by-side comparison",
    "demo_voiceover": "Product demo with voiceover narration",
    "objection_answer": "Address objection then resolve",
}

CTA_PATTERNS = {
    "soft": "Gentle suggestion — 'check it out if interested'",
    "direct": "Strong imperative — 'click the link now'",
    "link_in_bio": "Platform-specific bio link redirect",
    "comment_to_get": "Engagement-gated — 'comment X to get the link'",
    "save_share": "Soft viral — 'save this for later'",
    "urgency": "Time/quantity pressure — 'only 3 left'",
    "newsletter_signup": "Owned-audience capture — 'subscribe to the newsletter'",
    "product_click": "Direct product link with tracking",
}

WIN_THRESHOLD = 0.6
LOSE_THRESHOLD = 0.25
DECAY_THRESHOLD = 0.15
MIN_EVIDENCE_COUNT = 3


def _sig(pattern_type: str, pattern_name: str, platform: str = "", niche: str = "") -> str:
    raw = f"{pattern_type}:{pattern_name}:{platform}:{niche}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def extract_patterns_from_content(
    content_items: list[dict[str, Any]],
    performance: dict[str, dict[str, float]],
    niche: str = "general",
    comment_data: dict[str, dict[str, float]] | None = None,
) -> list[dict[str, Any]]:
    """Derive patterns from content + performance data.

    Reads structured metadata fields (hook_type, cta_type, offer_angle,
    creative_structure, audience_response_profile) when present, falling
    back to title/form inference when absent.
    """
    patterns: list[dict[str, Any]] = []
    cdata = comment_data or {}

    for ci in content_items:
        ci_id = str(ci.get("id", ""))
        perf = performance.get(ci_id, {})
        platform = ci.get("platform", "unknown")
        form = ci.get("content_form") or ci.get("content_type", "unknown")
        title = ci.get("title", "")
        tags = ci.get("tags", {})
        monetization = ci.get("monetization_method", "")

        imp = float(perf.get("impressions", 0))
        clicks = float(perf.get("clicks", 0))
        eng = float(perf.get("engagement_rate", 0))
        rev = float(perf.get("revenue", 0))
        cvr = float(perf.get("conversion_rate", 0))
        profit = float(perf.get("profit", 0))

        hook_type = ci.get("hook_type") or _infer_hook(title, tags)
        if hook_type:
            patterns.append(
                _build_pattern(
                    "hook", hook_type, platform, niche, form, monetization, imp, clicks, eng, rev, cvr, profit, ci_id
                )
            )

        structure = ci.get("creative_structure") or _infer_structure(form, tags)
        if structure:
            patterns.append(
                _build_pattern(
                    "creative_structure",
                    structure,
                    platform,
                    niche,
                    form,
                    monetization,
                    imp,
                    clicks,
                    eng,
                    rev,
                    cvr,
                    profit,
                    ci_id,
                )
            )

        patterns.append(
            _build_pattern(
                "content_form", form, platform, niche, form, monetization, imp, clicks, eng, rev, cvr, profit, ci_id
            )
        )

        if monetization:
            patterns.append(
                _build_pattern(
                    "monetization",
                    monetization,
                    platform,
                    niche,
                    form,
                    monetization,
                    imp,
                    clicks,
                    eng,
                    rev,
                    cvr,
                    profit,
                    ci_id,
                )
            )

        cta = ci.get("cta_type")
        if cta:
            patterns.append(
                _build_pattern(
                    "cta", cta, platform, niche, form, monetization, imp, clicks, eng, rev, cvr, profit, ci_id
                )
            )

        angle = ci.get("offer_angle")
        if angle:
            patterns.append(
                _build_pattern(
                    "offer_angle", angle, platform, niche, form, monetization, imp, clicks, eng, rev, cvr, profit, ci_id
                )
            )

        ar = _classify_audience_response(perf, ci.get("audience_response_profile") or {}, cdata.get(ci_id, {}))
        if ar:
            patterns.append(
                _build_pattern(
                    "audience_response",
                    ar,
                    platform,
                    niche,
                    form,
                    monetization,
                    imp,
                    clicks,
                    eng,
                    rev,
                    cvr,
                    profit,
                    ci_id,
                )
            )

    return patterns


def _classify_audience_response(
    perf: dict[str, float],
    ar_profile: dict[str, Any],
    comment_agg: dict[str, float],
) -> str | None:
    """Classify audience response pattern from perf + comment data."""
    eng = float(perf.get("engagement_rate", 0) or 0)
    cvr = float(perf.get("conversion_rate", 0) or 0)
    imp = float(perf.get("impressions", 0) or 0)
    profit = float(perf.get("profit", 0) or 0)
    sentiment = float(ar_profile.get("avg_sentiment", 0) or comment_agg.get("avg_sentiment", 0))
    purchase_pct = float(ar_profile.get("purchase_intent_pct", 0) or comment_agg.get("purchase_intent_pct", 0))
    objection_pct = float(ar_profile.get("objection_pct", 0) or comment_agg.get("objection_pct", 0))

    if objection_pct > 0.3 and cvr > 0.03:
        return "objection_heavy_high_conversion"
    if eng > 0.08 and profit < 5:
        return "high_engagement_low_monetization"
    if eng < 0.03 and purchase_pct > 0.2:
        return "low_engagement_high_purchase"
    if imp > 30000:
        return "reach_winner"
    if cvr > 0.05 and profit > 20:
        return "conversion_winner"
    if sentiment > 0.6 and eng > 0.05:
        return "trust_building_winner"
    return None


def _infer_hook(title: str, tags: Any) -> str | None:
    t = title.lower()
    if any(w in t for w in ("don't buy", "stop buying", "before you buy")):
        return "dont_buy_until"
    if any(w in t for w in ("wish i knew", "things i wish", "mistakes")):
        return "things_i_wish"
    if any(w in t for w in ("vs", "versus", "compared", "which is better")):
        return "comparison"
    if any(w in t for w in ("pain", "struggle", "problem", "frustrated")):
        return "direct_pain"
    if "?" in title or any(w in t for w in ("secret", "nobody tells", "hidden")):
        return "curiosity"
    return "curiosity"


def _infer_structure(form: str, tags: Any) -> str | None:
    f = (form or "").lower()
    if "carousel" in f:
        return "text_carousel"
    if "demo" in f or "product" in f:
        return "demo_voiceover"
    if "avatar" in f or "talking" in f:
        return "talking_head_broll"
    if "list" in f:
        return "listicle"
    return "problem_solution_cta"


def _build_pattern(
    ptype: str,
    pname: str,
    platform: str,
    niche: str,
    form: str,
    monetization: str,
    imp: float,
    clicks: float,
    eng: float,
    rev: float,
    cvr: float,
    profit: float,
    ci_id: str,
) -> dict[str, Any]:
    return {
        "pattern_type": ptype,
        "pattern_name": pname,
        "pattern_signature": _sig(ptype, pname, platform, niche),
        "platform": platform,
        "niche": niche,
        "content_form": form,
        "monetization_method": monetization,
        "evidence": {
            "content_item_id": ci_id,
            "impressions": imp,
            "clicks": clicks,
            "engagement_rate": eng,
            "revenue": rev,
            "conversion_rate": cvr,
            "profit": profit,
        },
    }


def score_pattern(
    evidence_list: list[dict[str, float]],
) -> dict[str, Any]:
    """Score a pattern from its accumulated evidence."""
    n = len(evidence_list)
    if n == 0:
        return {"win_score": 0, "confidence": 0, "performance_band": "unknown", "is_winner": False, "is_loser": False}

    avg_eng = sum(e.get("engagement_rate", 0) for e in evidence_list) / n
    avg_cvr = sum(e.get("conversion_rate", 0) for e in evidence_list) / n
    avg_profit = sum(e.get("profit", 0) for e in evidence_list) / n
    total_imp = sum(e.get("impressions", 0) for e in evidence_list)

    engagement_score = min(1.0, avg_eng * 10)
    conversion_score = min(1.0, avg_cvr * 20)
    profit_score = min(1.0, avg_profit / 100) if avg_profit > 0 else 0
    reach_score = min(1.0, total_imp / max(total_imp + 1, 1))  # Self-relative: any impressions = some reach

    win_score = round(0.25 * engagement_score + 0.30 * conversion_score + 0.30 * profit_score + 0.15 * reach_score, 3)
    sample_penalty = max(0.3, min(1.0, n / 10))
    confidence = round(win_score * sample_penalty, 3)

    band = "hero" if win_score > 0.7 else "strong" if win_score > 0.5 else "standard" if win_score > 0.3 else "weak"

    return {
        "win_score": win_score,
        "confidence": confidence,
        "performance_band": band,
        "is_winner": win_score >= WIN_THRESHOLD and n >= MIN_EVIDENCE_COUNT,
        "is_loser": win_score < LOSE_THRESHOLD and n >= MIN_EVIDENCE_COUNT,
        "sample_size": n,
    }


def detect_decay(
    previous_win_score: float,
    current_win_score: float,
    usage_count: int,
) -> dict[str, Any]:
    """Detect pattern decay."""
    if previous_win_score <= 0:
        return {"decaying": False, "decay_rate": 0, "decay_reason": "no_history"}

    drop = previous_win_score - current_win_score
    decay_rate = round(drop / max(previous_win_score, 0.01), 3)
    overuse = usage_count > 20

    reasons = []
    if decay_rate > DECAY_THRESHOLD:
        reasons.append("score_decline")
    if overuse:
        reasons.append("overuse_saturation")

    decaying = len(reasons) > 0
    recommendation = "Retire or refresh this pattern" if decaying else "Pattern still performing"
    if overuse and not (decay_rate > DECAY_THRESHOLD):
        recommendation = "High usage — monitor for fatigue"

    return {
        "decaying": decaying,
        "decay_rate": decay_rate,
        "decay_reason": ", ".join(reasons) if reasons else "none",
        "recommendation": recommendation,
    }


def cluster_patterns(
    patterns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group patterns by type + platform into clusters."""
    groups: dict[str, list[dict]] = {}
    for p in patterns:
        key = f"{p.get('pattern_type', '')}:{p.get('platform', 'all')}"
        groups.setdefault(key, []).append(p)

    clusters = []
    for key, members in groups.items():
        ptype, platform = key.split(":", 1)
        avg_score = sum(m.get("win_score", 0) for m in members) / max(1, len(members))
        clusters.append(
            {
                "cluster_name": f"{ptype} winners on {platform}",
                "cluster_type": ptype,
                "platform": platform if platform != "all" else None,
                "pattern_ids": [str(m.get("id", "")) for m in members],
                "avg_win_score": round(avg_score, 3),
                "pattern_count": len(members),
                "explanation": f"{len(members)} {ptype} patterns on {platform}, avg score {avg_score:.2f}",
            }
        )

    return sorted(clusters, key=lambda c: -c["avg_win_score"])


def recommend_reuse(
    winning_patterns: list[dict[str, Any]],
    target_platforms: list[str],
) -> list[dict[str, Any]]:
    """Recommend which winning patterns to reuse on which platforms."""
    recs = []
    for p in winning_patterns:
        if not p.get("is_winner", p.get("win_score", 0) >= WIN_THRESHOLD):
            continue
        src_platform = p.get("platform", "")
        for tp in target_platforms:
            if tp == src_platform:
                continue
            uplift = round(p.get("win_score", 0) * 0.7, 3)
            recs.append(
                {
                    "pattern_id": str(p.get("id", "")),
                    "pattern_name": p.get("pattern_name", ""),
                    "pattern_type": p.get("pattern_type", ""),
                    "source_platform": src_platform,
                    "target_platform": tp,
                    "target_content_form": p.get("content_form"),
                    "expected_uplift": uplift,
                    "confidence": round(p.get("confidence", 0) * 0.8, 3),
                    "explanation": f"Reuse {p.get('pattern_name', '')} ({p.get('pattern_type', '')}) from {src_platform} on {tp} — expected {uplift:.0%} uplift",
                }
            )

    return sorted(recs, key=lambda r: -r["expected_uplift"])[:20]


# ── Experiment integration ──────────────────────────────────────────────


def suggest_experiments_from_patterns(
    winning_patterns: list[dict[str, Any]],
    losing_patterns: list[dict[str, Any]],
    existing_experiment_variables: list[str],
) -> list[dict[str, Any]]:
    """Suggest experiments based on pattern memory gaps and strengths."""
    suggestions: list[dict[str, Any]] = []

    win_types = {p.get("pattern_type") for p in winning_patterns}
    lose_types = {p.get("pattern_type") for p in losing_patterns}
    all_types = set(PATTERN_TYPES)
    untested = all_types - win_types - lose_types - set(existing_experiment_variables)

    for ptype in untested:
        suggestions.append(
            {
                "tested_variable": ptype,
                "hypothesis": f"No winning or losing data for {ptype} — needs deliberate testing",
                "priority": "high",
                "source": "pattern_gap",
            }
        )

    for p in winning_patterns:
        if p.get("win_score", 0) >= 0.7 and p.get("usage_count", 0) < 5:
            suggestions.append(
                {
                    "tested_variable": p.get("pattern_type", ""),
                    "hypothesis": f"Strong winner '{p.get('pattern_name', '')}' with low usage — validate with controlled test",
                    "priority": "medium",
                    "source": "underexploited_winner",
                    "pattern_name": p.get("pattern_name"),
                }
            )

    for p in losing_patterns:
        if p.get("fail_score", 0) > 0.8:
            suggestions.append(
                {
                    "tested_variable": p.get("pattern_type", ""),
                    "hypothesis": f"Strong loser '{p.get('pattern_name', '')}' — test alternative in same category",
                    "priority": "medium",
                    "source": "loser_replacement",
                    "pattern_name": p.get("pattern_name"),
                }
            )

    return suggestions


def ingest_experiment_outcome(
    experiment_type: str,
    winning_variant_config: dict[str, Any],
    losing_variant_configs: list[dict[str, Any]],
    performance_data: dict[str, float],
) -> dict[str, Any]:
    """Convert an experiment outcome into pattern memory entries."""
    result: dict[str, Any] = {"winners": [], "losers": []}

    w_name = winning_variant_config.get("pattern_name") or winning_variant_config.get("variant_label", "unknown")
    result["winners"].append(
        {
            "pattern_type": experiment_type,
            "pattern_name": w_name,
            "evidence": performance_data,
            "source": "experiment_winner",
        }
    )

    for lc in losing_variant_configs:
        l_name = lc.get("pattern_name") or lc.get("variant_label", "unknown")
        result["losers"].append(
            {
                "pattern_type": experiment_type,
                "pattern_name": l_name,
                "source": "experiment_loser",
            }
        )

    return result


# ── Portfolio allocation integration ────────────────────────────────────


def compute_pattern_allocation_weights(
    clusters: list[dict[str, Any]],
    total_budget: float,
) -> list[dict[str, Any]]:
    """Compute budget allocation weights from pattern cluster strength."""
    if not clusters:
        return []

    total_score = sum(max(0.01, c.get("avg_win_score", 0)) * c.get("pattern_count", 1) for c in clusters)
    if total_score <= 0:
        total_score = 1.0

    allocations = []
    for c in clusters:
        weighted = max(0.01, c.get("avg_win_score", 0)) * c.get("pattern_count", 1)
        share = weighted / total_score
        hero_eligible = c.get("avg_win_score", 0) >= 0.6
        allocations.append(
            {
                "cluster_type": c.get("cluster_type", ""),
                "platform": c.get("platform"),
                "cluster_name": c.get("cluster_name", ""),
                "allocation_pct": round(share * 100, 1),
                "allocated_budget": round(share * total_budget, 2),
                "hero_eligible": hero_eligible,
                "provider_tier": "hero" if hero_eligible else "bulk",
                "explanation": f"{c.get('cluster_name', '')}: {share * 100:.1f}% ({'hero' if hero_eligible else 'bulk'} tier)",
            }
        )

    return sorted(allocations, key=lambda a: -a["allocation_pct"])
