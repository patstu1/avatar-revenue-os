"""Phase 7 engines: sponsor sales, comment-to-cash, knowledge graph, roadmap, capital allocation.

All functions are pure/deterministic — no DB access. Service layer handles persistence.
"""

from __future__ import annotations

PHASE7_SOURCE = "phase7_engine"

SPONSOR_SAFE_CATEGORIES = {
    "personal finance",
    "finance",
    "investing",
    "business",
    "saas",
    "health",
    "wellness",
    "fitness",
    "education",
    "technology",
    "productivity",
    "marketing",
    "real estate",
    "career",
    "parenting",
    "travel",
    "food",
    "lifestyle",
    "gaming",
    "entertainment",
}

SPONSOR_UNSAFE_KEYWORDS = {
    "gambling",
    "adult",
    "weapons",
    "tobacco",
    "drugs",
    "crypto scam",
    "mlm",
    "pyramid",
    "hate",
    "violence",
    "extremism",
}


# ---------------------------------------------------------------------------
# 1. Sponsor Sales Engine
# ---------------------------------------------------------------------------


def is_sponsor_safe(niche: str | None, content_tags: list | None = None) -> tuple[bool, str]:
    """Check if brand niche is sponsor-safe."""
    n = (niche or "").lower().strip()
    if not n:
        return True, "No niche set — default safe."
    for kw in SPONSOR_UNSAFE_KEYWORDS:
        if kw in n:
            return False, f"Unsafe keyword detected: {kw}"
    if any(kw in n for cat in SPONSOR_SAFE_CATEGORIES for kw in [cat]):
        return True, f"Niche '{n}' is in safe category."
    return True, f"Niche '{n}' not flagged — default safe."


def recommend_sponsor_packages(
    brand_niche: str | None,
    accounts: list[dict],
    total_revenue: float,
    total_impressions: int,
) -> list[dict]:
    """Generate sponsor package recommendations based on brand metrics."""
    safe, reason = is_sponsor_safe(brand_niche)
    if not safe:
        return [{"package": "blocked", "reason": reason}]

    packages = []
    follower_total = sum(a.get("follower_count", 0) for a in accounts)
    platforms = list({a.get("platform", "youtube") for a in accounts})

    if follower_total >= 10000:
        packages.append(
            {
                "package": "sponsored_integration",
                "title": "Sponsored Content Integration",
                "suggested_rate": round(max(500.0, follower_total * 0.02), 2),
                "rationale": f"Audience of {follower_total:,} supports integration deals.",
                "platforms": platforms,
                "priority_score": min(100.0, follower_total / 1000),
            }
        )

    if total_impressions >= 50000:
        cpm = round(total_revenue / max(1, total_impressions) * 1000, 2) if total_revenue > 0 else 5.0
        packages.append(
            {
                "package": "brand_awareness",
                "title": "Brand Awareness Campaign",
                "suggested_rate": round(max(300.0, cpm * total_impressions / 1000 * 0.1), 2),
                "rationale": f"CPM track record of ${cpm} over {total_impressions:,} impressions.",
                "platforms": platforms,
                "priority_score": 80.0 if total_impressions > 0 else 30.0,  # Any impressions = high priority
            }
        )

    if len(accounts) >= 2:
        packages.append(
            {
                "package": "multi_platform_bundle",
                "title": "Multi-Platform Sponsor Bundle",
                "suggested_rate": round(max(800.0, follower_total * 0.03), 2),
                "rationale": f"Cross-platform presence ({', '.join(platforms)}) enables bundle pricing.",
                "platforms": platforms,
                "priority_score": 70.0 + len(accounts) * 5,
            }
        )

    if not packages:
        packages.append(
            {
                "package": "growth_milestone",
                "title": "Growth Milestone Package",
                "suggested_rate": 250.0,
                "rationale": "Pre-threshold — build audience proof before sponsor outreach.",
                "platforms": platforms,
                "priority_score": 30.0,
            }
        )

    return sorted(packages, key=lambda p: -p["priority_score"])


# ---------------------------------------------------------------------------
# 2. Comment-to-Cash Engine
# ---------------------------------------------------------------------------

PURCHASE_INTENT_PHRASES = [
    "where can i buy",
    "how do i get",
    "link please",
    "drop the link",
    "what's the price",
    "how much",
    "is it worth",
    "should i buy",
    "take my money",
    "shut up and take",
    "need this",
    "want this",
    "sign me up",
    "how to sign up",
    "where to sign up",
    "can i get",
    "do you have a code",
    "discount code",
    "promo code",
    "coupon",
]

OBJECTION_PHRASES = [
    "too expensive",
    "not worth it",
    "scam",
    "doesn't work",
    "waste of money",
    "better alternative",
    "overpriced",
    "rip off",
    "already tried",
    "didn't work for me",
    "snake oil",
    "clickbait",
]


def classify_comment_intent(text: str) -> dict:
    """Classify a comment for purchase intent, objections, and questions."""
    lower = text.lower().strip()
    is_purchase = any(p in lower for p in PURCHASE_INTENT_PHRASES)
    is_objection = any(p in lower for p in OBJECTION_PHRASES)
    is_question = "?" in text
    intent = (
        "purchase_intent"
        if is_purchase
        else ("objection" if is_objection else ("question" if is_question else "neutral"))
    )
    return {
        "intent": intent,
        "is_purchase_intent": is_purchase,
        "is_objection": is_objection,
        "is_question": is_question,
        "confidence": 0.8 if is_purchase or is_objection else 0.5,
    }


def extract_comment_cash_signals(
    comments: list[dict],
    offers: list[dict],
) -> list[dict]:
    """Extract actionable cash signals from classified comments."""
    signals: list[dict] = []
    purchase_comments = [c for c in comments if c.get("is_purchase_intent")]
    objection_comments = [c for c in comments if classify_comment_intent(c.get("comment_text", ""))["is_objection"]]

    if purchase_comments:
        best_offer = max(offers, key=lambda o: float(o.get("epc", 0))) if offers else None
        signals.append(
            {
                "signal_type": "purchase_intent_cluster",
                "signal_strength": min(1.0, len(purchase_comments) / 10.0),
                "estimated_revenue_potential": round(
                    len(purchase_comments) * float(best_offer.get("payout_amount", 10)) * 0.15
                    if best_offer
                    else len(purchase_comments) * 1.5,
                    2,
                ),
                "suggested_offer_id": best_offer.get("id") if best_offer else None,
                "suggested_content_angle": "Create dedicated conversion content addressing the buying questions from comments.",
                "explanation": f"{len(purchase_comments)} comments with purchase intent detected.",
                PHASE7_SOURCE: True,
            }
        )

    if objection_comments:
        signals.append(
            {
                "signal_type": "objection_pattern",
                "signal_strength": min(1.0, len(objection_comments) / 8.0),
                "estimated_revenue_potential": round(len(objection_comments) * 5.0, 2),
                "suggested_offer_id": None,
                "suggested_content_angle": "Create objection-handling content or FAQ video addressing repeated concerns.",
                "explanation": f"{len(objection_comments)} objection-pattern comments detected.",
                PHASE7_SOURCE: True,
            }
        )

    question_comments = [c for c in comments if c.get("is_question")]
    if len(question_comments) >= 3:
        signals.append(
            {
                "signal_type": "question_cluster",
                "signal_strength": min(1.0, len(question_comments) / 15.0),
                "estimated_revenue_potential": round(len(question_comments) * 2.0, 2),
                "suggested_offer_id": None,
                "suggested_content_angle": "Address top questions in a dedicated Q&A or explainer piece.",
                "explanation": f"{len(question_comments)} question comments — potential content gap.",
                PHASE7_SOURCE: True,
            }
        )

    return signals


# ---------------------------------------------------------------------------
# 3. Knowledge Graph Builder
# ---------------------------------------------------------------------------


def build_knowledge_graph_entries(
    brand_niche: str | None,
    accounts: list[dict],
    offers: list[dict],
    winners: list[dict],
    segments: list[dict],
    leaks: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Build nodes and edges for the brand knowledge graph."""
    nodes: list[dict] = []
    edges: list[dict] = []
    node_ids: dict[str, int] = {}

    def _add_node(ntype: str, label: str, props: dict | None = None) -> int:
        key = f"{ntype}:{label}"
        if key in node_ids:
            return node_ids[key]
        idx = len(nodes)
        node_ids[key] = idx
        nodes.append({"node_type": ntype, "label": label, "properties": props or {}, PHASE7_SOURCE: True})
        return idx

    def _add_edge(src: int, tgt: int, etype: str, weight: float = 1.0, props: dict | None = None):
        edges.append(
            {
                "source_idx": src,
                "target_idx": tgt,
                "edge_type": etype,
                "weight": weight,
                "properties": props or {},
                PHASE7_SOURCE: True,
            }
        )

    niche_label = (brand_niche or "general")[:120]
    niche_idx = _add_node("niche", niche_label)

    for a in accounts:
        plat = a.get("platform", "unknown")
        plat_idx = _add_node("platform", plat)
        _add_edge(niche_idx, plat_idx, "niche_uses_platform", 1.0)

        geo = a.get("geography") or "US"
        geo_idx = _add_node("geography", geo)
        _add_edge(plat_idx, geo_idx, "platform_in_geography", 1.0)

    for o in offers:
        offer_idx = _add_node("offer", o.get("name", str(o.get("id", "?")))[:200])
        _add_edge(niche_idx, offer_idx, "niche_best_offer", float(o.get("epc", 1.0)))

    for w in winners:
        hook_idx = _add_node("hook", (w.get("title") or "untitled")[:200])
        _add_edge(niche_idx, hook_idx, "niche_best_hook", float(w.get("win_score", 0.5)))
        plat = w.get("platform", "youtube")
        plat_idx = _add_node("platform", plat)
        _add_edge(hook_idx, plat_idx, "hook_performs_on_platform", float(w.get("rpm", 1.0)))

    for s in segments:
        seg_idx = _add_node("segment", s.get("name", "unnamed")[:200])
        _add_edge(seg_idx, niche_idx, "segment_in_niche", 1.0)

    return nodes, edges


# ---------------------------------------------------------------------------
# 4. Roadmap Engine
# ---------------------------------------------------------------------------


def generate_roadmap(
    brand_niche: str | None,
    accounts: list[dict],
    offers: list[dict],
    winners: list[dict],
    leaks: list[dict],
    segments: list[dict],
    geo_recs: list[dict],
    scale_rec_key: str | None,
    trust_avg: float,
) -> list[dict]:
    """Generate prioritized roadmap recommendations across 6 categories."""
    items: list[dict] = []

    if winners:
        top = winners[:3]
        for w in top:
            items.append(
                {
                    "category": "content",
                    "title": f"Clone winner: {(w.get('title') or 'top post')[:80]}",
                    "description": "Repurpose winning format/hook with fresh angle.",
                    "priority_score": min(100.0, 60.0 + float(w.get("win_score", 0.5)) * 40),
                    "estimated_impact_revenue": round(float(w.get("revenue", 0)) * 0.3, 2),
                    "estimated_effort": "low",
                    "rationale": f"Win score {w.get('win_score', '?')} — proven format.",
                    PHASE7_SOURCE: True,
                }
            )

    if len(accounts) < 3 and scale_rec_key and "add_" in (scale_rec_key or ""):
        items.append(
            {
                "category": "account_launch",
                "title": f"Launch account per scale engine: {scale_rec_key}",
                "description": "Scale engine recommends adding a new account.",
                "priority_score": 75.0,
                "estimated_impact_revenue": 500.0,
                "estimated_effort": "high",
                "rationale": "Phase 5 scale engine recommends expansion.",
                PHASE7_SOURCE: True,
            }
        )

    if len(offers) < 3:
        items.append(
            {
                "category": "offer",
                "title": "Add offer to diversify monetization",
                "description": "Offer catalog is thin — test a new payout model.",
                "priority_score": 65.0,
                "estimated_impact_revenue": 300.0,
                "estimated_effort": "medium",
                "rationale": f"Only {len(offers)} active offer(s).",
                PHASE7_SOURCE: True,
            }
        )

    if geo_recs:
        best = geo_recs[0]
        items.append(
            {
                "category": "niche_expansion",
                "title": f"Expand to {best.get('target_geography', '?')}/{best.get('target_language', '?')}",
                "description": "Geo/language expansion opportunity from Phase 6.",
                "priority_score": 60.0,
                "estimated_impact_revenue": float(best.get("estimated_revenue_potential", 0)),
                "estimated_effort": "high",
                "rationale": best.get("rationale", ""),
                PHASE7_SOURCE: True,
            }
        )

    if leaks:
        worst = sorted(leaks, key=lambda l: -float(l.get("estimated_leaked_revenue", 0)))[:2]
        for lk in worst:
            items.append(
                {
                    "category": "experiment",
                    "title": f"Fix leak: {lk.get('leak_type', 'unknown')}",
                    "description": lk.get("recommended_fix", "Address revenue leak."),
                    "priority_score": min(90.0, 50.0 + float(lk.get("estimated_leaked_revenue", 0)) * 0.05),
                    "estimated_impact_revenue": float(lk.get("estimated_recoverable", 0)),
                    "estimated_effort": "medium",
                    "rationale": lk.get("root_cause", ""),
                    PHASE7_SOURCE: True,
                }
            )

    if trust_avg < 50:
        items.append(
            {
                "category": "suppression",
                "title": "Audit low-trust accounts before scaling",
                "description": "Trust scores are low — stabilize before adding volume.",
                "priority_score": 55.0,
                "estimated_impact_revenue": 0.0,
                "estimated_effort": "low",
                "rationale": f"Average trust score {trust_avg:.0f}/100.",
                PHASE7_SOURCE: True,
            }
        )

    return sorted(items, key=lambda x: -x["priority_score"])[:10]


# ---------------------------------------------------------------------------
# 5. Capital Allocation Engine
# ---------------------------------------------------------------------------


def compute_capital_allocation(
    total_budget: float,
    total_revenue: float,
    total_profit: float,
    accounts: list[dict],
    offers: list[dict],
    leak_count: int,
    paid_candidate_count: int,
    geo_rec_count: int,
    trust_avg: float,
    scale_rec_key: str | None,
    productization_rec_count: int = 0,
    owned_audience_size: int = 0,
) -> list[dict]:
    """Recommend where the next dollar should go across 9 allocation targets."""
    allocations: list[dict] = []
    budget = max(total_budget, total_profit * 0.3, 100.0)

    weights = {
        "content_volume": 25.0,
        "new_accounts": 8.0,
        "paid_amplification": 12.0,
        "funnel_optimization": 12.0,
        "sponsor_outreach": 8.0,
        "geo_language_expansion": 8.0,
        "productization": 10.0,
        "owned_audience_nurture": 10.0,
        "reserve": 7.0,
    }

    if leak_count > 3:
        weights["funnel_optimization"] += 8.0
        weights["content_volume"] -= 4.0
        weights["reserve"] -= 4.0

    if paid_candidate_count > 0:
        weights["paid_amplification"] += 5.0
        weights["content_volume"] -= 5.0

    if scale_rec_key and "add_" in (scale_rec_key or ""):
        weights["new_accounts"] += 8.0
        weights["reserve"] -= 4.0
        weights["content_volume"] -= 4.0

    if geo_rec_count > 0:
        weights["geo_language_expansion"] += 4.0
        weights["content_volume"] -= 4.0

    if trust_avg < 50:
        weights["content_volume"] -= 3.0
        weights["funnel_optimization"] += 3.0

    if productization_rec_count > 0:
        weights["productization"] += 5.0
        weights["reserve"] -= 3.0
        weights["content_volume"] -= 2.0

    if owned_audience_size > 0:
        weights["owned_audience_nurture"] += 5.0
        weights["content_volume"] -= 3.0
        weights["reserve"] -= 2.0

    total_w = sum(max(0, w) for w in weights.values())
    for target, w in weights.items():
        w = max(0, w)
        pct = round(w / total_w * 100, 1) if total_w > 0 else 0.0
        dollar = round(budget * w / total_w, 2) if total_w > 0 else 0.0
        roi_mult = {
            "content_volume": 2.5,
            "new_accounts": 1.8,
            "paid_amplification": 3.0,
            "funnel_optimization": 4.0,
            "sponsor_outreach": 2.0,
            "geo_language_expansion": 1.5,
            "productization": 5.0,
            "owned_audience_nurture": 3.5,
            "reserve": 0.0,
        }.get(target, 1.0)
        allocations.append(
            {
                "allocation_target_type": target,
                "recommended_allocation_pct": pct,
                "dollar_amount": dollar,
                "expected_marginal_roi": round(roi_mult, 2),
                "rationale": _alloc_rationale(
                    target, pct, leak_count, paid_candidate_count, geo_rec_count, scale_rec_key
                ),
                PHASE7_SOURCE: True,
            }
        )

    return sorted(allocations, key=lambda a: -a["recommended_allocation_pct"])


def _alloc_rationale(target: str, pct: float, leaks: int, paid: int, geo: int, scale_key: str | None) -> str:
    base = {
        "content_volume": "Primary revenue driver — winner cloning and volume scaling.",
        "new_accounts": "Portfolio expansion per scale engine recommendation.",
        "paid_amplification": "Boost proven winners with paid spend.",
        "funnel_optimization": "Fix revenue leaks and conversion bottlenecks.",
        "sponsor_outreach": "Monetize audience through sponsor deals.",
        "geo_language_expansion": "Diversify into new markets.",
        "productization": "Build high-margin products (courses, memberships) from proven content.",
        "owned_audience_nurture": "Grow and monetize owned channels (email, community, subscribers).",
        "reserve": "Buffer for opportunistic or emergency allocation.",
    }.get(target, "")
    modifiers = []
    if target == "funnel_optimization" and leaks > 3:
        modifiers.append(f"Elevated: {leaks} open leaks.")
    if target == "paid_amplification" and paid > 0:
        modifiers.append(f"{paid} paid candidates ready.")
    if target == "new_accounts" and scale_key and "add_" in scale_key:
        modifiers.append(f"Scale engine: {scale_key}.")
    if target == "geo_language_expansion" and geo > 0:
        modifiers.append(f"{geo} expansion recs.")
    return f"{base} {' '.join(modifiers)}".strip()
