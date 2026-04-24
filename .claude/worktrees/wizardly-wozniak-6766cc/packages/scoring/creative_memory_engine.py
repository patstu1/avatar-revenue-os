"""Creative Memory Engine — index reusable content atoms and query them."""
from __future__ import annotations

from typing import Any

CREATIVE_MEMORY = "creative_memory_engine"

ATOM_TYPES = [
    "hook", "opening", "cta", "thumbnail_pattern", "trust_block",
    "objection_response", "close_angle", "sponsor_safe_pattern",
    "visual_pacing", "scene_sequence",
]

MAX_ATOMS_PER_RUN = 20


def _extract_atom_type(item: dict[str, Any]) -> str:
    """Heuristic atom-type classification from content metadata."""
    title = (item.get("title") or "").lower()
    body = (item.get("body") or item.get("text") or "").lower()
    combined = f"{title} {body}"

    if any(kw in combined for kw in ("hook", "attention", "opener")):
        return "hook"
    if any(kw in combined for kw in ("cta", "call to action", "click", "buy now")):
        return "cta"
    if any(kw in combined for kw in ("thumbnail", "cover", "thumb")):
        return "thumbnail_pattern"
    if any(kw in combined for kw in ("trust", "testimonial", "proof", "credibility")):
        return "trust_block"
    if any(kw in combined for kw in ("objection", "but what if", "concern", "hesitat")):
        return "objection_response"
    if any(kw in combined for kw in ("close", "final", "seal the deal")):
        return "close_angle"
    if any(kw in combined for kw in ("sponsor", "ad read", "brand partner")):
        return "sponsor_safe_pattern"
    if any(kw in combined for kw in ("pacing", "rhythm", "visual flow")):
        return "visual_pacing"
    if any(kw in combined for kw in ("sequence", "scene", "storyboard")):
        return "scene_sequence"
    return "opening"


def _performance_summary(
    item_id: str, performance_data: list[dict[str, Any]]
) -> dict[str, Any]:
    """Aggregate engagement and conversion metrics for a content item."""
    matching = [p for p in performance_data if str(p.get("content_item_id")) == str(item_id)]
    if not matching:
        return {"avg_engagement": 0.0, "avg_conversion": 0.0, "sample_size": 0}

    eng = sum(p.get("engagement_rate", 0.0) for p in matching) / len(matching)
    cvr = sum(p.get("conversion_rate", 0.0) for p in matching) / len(matching)
    return {
        "avg_engagement": round(eng, 4),
        "avg_conversion": round(cvr, 4),
        "sample_size": len(matching),
    }


def _originality_caution(atom_type: str, reuse_count: int) -> float:
    """Higher score when a pattern has been reused too often (audience fatigue risk)."""
    base = min(1.0, reuse_count / 20.0)
    if atom_type in ("hook", "cta", "close_angle"):
        return round(min(1.0, base * 1.4), 3)
    return round(base, 3)


def _reuse_recommendations(
    atom_type: str, niche: str, platform: str, funnel_stage: str
) -> list[str]:
    """Suggest contexts where this atom could be redeployed."""
    recs: list[str] = []
    if atom_type == "hook":
        recs.append(f"Reuse as opener for {platform} short-form in {niche}")
        recs.append(f"Adapt for email subject line targeting {funnel_stage} stage")
    elif atom_type == "cta":
        recs.append(f"Test as primary CTA on {platform}")
        recs.append(f"Embed in {funnel_stage} email sequence")
    elif atom_type == "trust_block":
        recs.append(f"Use as social proof on landing pages ({niche})")
        recs.append(f"Repurpose for sponsor pitch deck")
    elif atom_type == "objection_response":
        recs.append(f"Insert in FAQ section for {niche} offers")
        recs.append(f"Use in objection-handling email sequence")
    else:
        recs.append(f"Reuse in {niche} content on {platform}")
        recs.append(f"Adapt for {funnel_stage} funnel stage")
    return recs


def index_creative_atoms(
    content_items: list[dict[str, Any]],
    performance_data: list[dict[str, Any]],
    brand_context: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract reusable creative atoms from content items.

    Parameters
    ----------
    content_items:
        List of dicts with content metadata.
        Expected keys: id, title, body/text, platform, niche, monetization_type,
        funnel_stage, reuse_count (optional).
    performance_data:
        List of dicts with performance metrics per content item.
        Expected keys: content_item_id, engagement_rate, conversion_rate.
    brand_context:
        Dict with brand-level context.
        Expected keys: niche, default_platform, default_monetization_type.

    Returns
    -------
    list[dict] — up to MAX_ATOMS_PER_RUN atoms, each with atom_type, content_json,
    niche, platform, monetization_type, funnel_stage, performance_summary,
    reuse_recommendations, originality_caution_score, confidence.
    """
    default_niche = brand_context.get("niche", "general")
    default_platform = brand_context.get("default_platform", "youtube")
    default_monetization = brand_context.get("default_monetization_type", "affiliate")

    atoms: list[dict[str, Any]] = []

    for item in content_items:
        if len(atoms) >= MAX_ATOMS_PER_RUN:
            break

        item_id = str(item.get("id", ""))
        atom_type = _extract_atom_type(item)
        niche = item.get("niche") or default_niche
        platform = item.get("platform") or default_platform
        monetization_type = item.get("monetization_type") or default_monetization
        funnel_stage = item.get("funnel_stage") or "awareness"
        reuse_count = int(item.get("reuse_count", 0))

        perf = _performance_summary(item_id, performance_data)
        caution = _originality_caution(atom_type, reuse_count)
        recs = _reuse_recommendations(atom_type, niche, platform, funnel_stage)

        combined_perf = perf["avg_engagement"] + perf["avg_conversion"]
        exp_boost = float(brand_context.get("experiment_outcome_confidence_boost", 0.0))
        confidence = round(
            min(0.95, 0.35 + combined_perf * 5 + min(0.25, perf["sample_size"] / 40) + exp_boost),
            3,
        )

        atoms.append({
            "content_item_id": item_id,
            "atom_type": atom_type,
            "content_json": {
                "title": item.get("title", ""),
                "excerpt": (item.get("body") or item.get("text") or "")[:300],
            },
            "niche": niche,
            "platform": platform,
            "monetization_type": monetization_type,
            "funnel_stage": funnel_stage,
            "performance_summary": perf,
            "reuse_recommendations": recs,
            "originality_caution_score": caution,
            "confidence": confidence,
            "explanation": (
                f"Extracted {atom_type} atom from '{item.get('title', 'untitled')}'. "
                f"Avg engagement {perf['avg_engagement']:.4f}, "
                f"caution {caution:.3f}."
            ),
            CREATIVE_MEMORY: True,
        })

    return atoms


def query_atoms(
    atoms: list[dict[str, Any]],
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    """Filter and sort atoms by criteria.

    Parameters
    ----------
    atoms:
        List of atom dicts (output of index_creative_atoms or DB records).
    filters:
        Dict with optional keys: niche, platform, monetization_type,
        funnel_stage, atom_type. Only atoms matching all provided filters
        are returned.

    Returns
    -------
    list[dict] — filtered atoms sorted by performance score descending.
    """
    f_niche = filters.get("niche")
    f_platform = filters.get("platform")
    f_monetization = filters.get("monetization_type")
    f_funnel = filters.get("funnel_stage")
    f_atom_type = filters.get("atom_type")

    filtered: list[dict[str, Any]] = []
    for atom in atoms:
        if f_niche and atom.get("niche") != f_niche:
            continue
        if f_platform and atom.get("platform") != f_platform:
            continue
        if f_monetization and atom.get("monetization_type") != f_monetization:
            continue
        if f_funnel and atom.get("funnel_stage") != f_funnel:
            continue
        if f_atom_type and atom.get("atom_type") != f_atom_type:
            continue
        filtered.append(atom)

    def _perf_score(a: dict[str, Any]) -> float:
        ps = a.get("performance_summary", {})
        return ps.get("avg_engagement", 0.0) + ps.get("avg_conversion", 0.0)

    filtered.sort(key=_perf_score, reverse=True)
    return filtered
