"""ProofHook AI Buyer Trust Test — deterministic scoring engine.

Pure function: scan signal dict → AiBuyerTrustReport dict. No randomness,
no LLMs, no time-based inputs, no DB access. Same input always produces
the same output (locked by ``test_ai_buyer_trust_engine.py`` determinism
tests).

Score range: 0–100. Eight buyer-language dimensions weighted into a
composite, plus three technical signals that surface as evidence and
applies bounded penalties when catastrophic. When a page or signal is
absent we record ``not_assessed`` rather than penalize — a missing FAQ
page is "not assessed", not "scored 0".

Package recommendation is threshold-based exactly as specified by the
operator:
    < 40                    → proof_infrastructure_buildout
    40–59                   → ai_search_authority_sprint
    60–74                   → ai_search_authority_sprint + authority_monitoring_retainer
    75–89                   → authority_monitoring_retainer
    90+                     → ai_search_authority_system

Copy rules: never claim guaranteed rankings, citations, or AI placement.
"""

from __future__ import annotations

import re
from typing import Any

FORMULA_VERSION = "v1"
REPORT_VERSION = "v1"
SCAN_VERSION = "v1"

# ─────────────────────────────────────────────────────────────────────
# Dimension weights (sum to 1.0)
# ─────────────────────────────────────────────────────────────────────

DIMENSION_WEIGHTS: dict[str, float] = {
    "entity_clarity": 0.15,
    "audience_clarity": 0.10,
    "offer_clarity": 0.15,
    "proof_strength": 0.15,
    "comparison_readiness": 0.10,
    "answer_engine_readiness": 0.10,
    "trust_signal_density": 0.10,
    "ai_search_eligibility": 0.15,
}

PUBLIC_DIMENSION_LABEL: dict[str, str] = {
    "entity_clarity": "Can AI understand what you do?",
    "audience_clarity": "Can AI understand who you serve?",
    "offer_clarity": "Can AI identify your offers?",
    "proof_strength": "Can AI see proof you are credible?",
    "comparison_readiness": "Can AI compare you clearly?",
    "answer_engine_readiness": "Can AI answer buyer questions from your site?",
    "trust_signal_density": "Can AI find trust signals?",
    "ai_search_eligibility": "Can AI understand why someone should choose you?",
}

# AI Authority lane slugs (mirror apps/web/src/lib/proofhook-packages.ts).
PACKAGE_BUILDOUT = "proof_infrastructure_buildout"
PACKAGE_SPRINT = "ai_search_authority_sprint"
PACKAGE_RETAINER = "authority_monitoring_retainer"
PACKAGE_SYSTEM = "ai_search_authority_system"

# Creative Proof lane companion slugs — recommended alongside the AI
# Authority pick when a dimension gap reads as a creative-side fix
# (proof videos, hook variants, founder clips, paid creative, etc.).
CREATIVE_SIGNAL_ENTRY = "signal_entry"  # 4-asset pack
CREATIVE_MOMENTUM_ENGINE = "momentum_engine"  # 8–12/mo recurring
CREATIVE_CONVERSION_ARCH = "conversion_architecture"  # audit + hook rebuild
CREATIVE_PAID_MEDIA = "paid_media_engine"  # 12–20/mo + paid optim
CREATIVE_LAUNCH_SEQUENCE = "launch_sequence"
CREATIVE_COMMAND = "creative_command"  # high-throughput recurring


def score_label_for(total: int) -> str:
    if total >= 90:
        return "authority_ready"
    if total >= 75:
        return "strong"
    if total >= 60:
        return "developing"
    if total >= 40:
        return "weak"
    return "not_ready"


def confidence_label_for(value: float) -> str:
    if value >= 0.75:
        return "high"
    if value >= 0.5:
        return "medium"
    return "low"


# ─────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────


def score_ai_buyer_trust(signals: dict[str, Any]) -> dict[str, Any]:
    """Score a fetched-website signal dict and return a full report.

    Input shape (produced by website_scanner._make_signals_dict):
        {
          "homepage": {url, status_code, title, h1[], h2[], meta_description,
                       jsonld_blocks[], body_text_snippet, fetch_error,
                       content_type},
          "homepage_failed": bool,
          "robots_txt_present": bool,
          "robots_txt_blocks_ai": bool,
          "sitemap_present": bool,
          "sitemap_url_count": int,
          "subpages": [ {same shape as homepage}, ... ],
          "all_jsonld_types": [str],
          "all_jsonld_blocks": [dict],
        }

    Output shape:
        {
          "total_score": int 0-100,
          "score_label": str,
          "confidence": float 0.0-1.0,
          "confidence_label": str ("low"|"medium"|"high"),
          "dimension_scores": {dim: int},
          "technical_scores": {entry: int},
          "evidence": {dim: {detected, missing, why_it_matters,
                              recommended_fix, confidence, public_label,
                              status (assessed|not_assessed)}},
          "top_gaps": [{dimension, public_label, score, detected, missing,
                        why_it_matters, recommended_fix}, ...],
          "quick_wins": [str],
          "recommended_package": {primary_slug, secondary_slug?, rationale},
          "formula_version": str,
        }
    """
    homepage_failed = bool(signals.get("homepage_failed"))
    if homepage_failed:
        return _failed_homepage_report(signals)

    dim_results: dict[str, dict[str, Any]] = {}
    dim_results["entity_clarity"] = _score_entity_clarity(signals)
    dim_results["audience_clarity"] = _score_audience_clarity(signals)
    dim_results["offer_clarity"] = _score_offer_clarity(signals)
    dim_results["proof_strength"] = _score_proof_strength(signals)
    dim_results["comparison_readiness"] = _score_comparison_readiness(signals)
    dim_results["answer_engine_readiness"] = _score_answer_engine_readiness(signals)
    dim_results["trust_signal_density"] = _score_trust_signal_density(signals)
    dim_results["ai_search_eligibility"] = _score_ai_search_eligibility(signals, dim_results)

    technical = _score_technical(signals)

    # Composite — weighted sum of assessed dimensions only. Unassessed
    # dimensions are excluded from both numerator and denominator so a
    # site that hides one page doesn't get artificially low.
    weighted_sum = 0.0
    weight_total = 0.0
    for dim, weight in DIMENSION_WEIGHTS.items():
        d = dim_results[dim]
        if d["status"] == "not_assessed":
            continue
        weighted_sum += d["score"] * weight
        weight_total += weight
    composite = weighted_sum / weight_total if weight_total > 0 else 0.0

    # Technical penalty / bonus
    composite = _apply_technical_adjustments(composite, technical)
    total_score = int(round(_clamp(composite, 0, 100)))

    # Confidence — proportion of assessed dimensions × proportion of pages
    # that returned 200, with a 0.4 floor. Displayed as low/medium/high.
    assessed = sum(1 for d in dim_results.values() if d["status"] != "not_assessed")
    pages_assessed = signals.get("subpages", []) + ([signals["homepage"]] if signals.get("homepage") else [])
    pages_ok = sum(1 for p in pages_assessed if p and (p.get("status_code") or 0) < 400 and not p.get("fetch_error"))
    pages_attempted = max(len(pages_assessed), 1)
    confidence = _clamp(
        0.4 + 0.4 * (pages_ok / pages_attempted) + 0.2 * (assessed / len(DIMENSION_WEIGHTS)),
        0.0,
        1.0,
    )

    # Top 2 gaps — assessed dimensions sorted by lowest score
    sorted_gaps = sorted(
        ((dim, d) for dim, d in dim_results.items() if d["status"] != "not_assessed"),
        key=lambda kv: kv[1]["score"],
    )
    top_gaps = [
        {
            "dimension": dim,
            "public_label": PUBLIC_DIMENSION_LABEL[dim],
            "score": d["score"],
            "detected": d["detected"],
            "missing": d["missing"],
            "why_it_matters": d["why_it_matters"],
            "recommended_fix": d["recommended_fix"],
            "confidence_label": confidence_label_for(d["confidence"]),
        }
        for dim, d in sorted_gaps[:2]
    ]

    # Quick wins — concrete actions derived from the lowest-scoring dim and
    # any technical penalty. Always at least one item, always concrete.
    quick_wins = _build_quick_wins(dim_results, technical, signals)

    recommended = _recommend_package(total_score, dim_results)

    # Public-facing evidence slice — same shape as internal but stripped of
    # the raw signal arrays we consider operator-only.
    public_evidence = {
        dim: {
            "public_label": PUBLIC_DIMENSION_LABEL[dim],
            "status": d["status"],
            "score": d["score"],
            "confidence_label": confidence_label_for(d["confidence"]),
        }
        for dim, d in dim_results.items()
    }

    # ── Platform-ready outputs (consumed by Authority Snapshot, monitoring,
    # proposal builder) ──
    buyer_questions = _build_buyer_questions(signals, dim_results)
    authority_graph = _build_authority_graph(signals, dim_results, technical, buyer_questions)
    recommended_pages = _build_recommended_pages(signals, dim_results)
    recommended_schema = _build_recommended_schema(signals, technical)
    recommended_proof_assets = _build_recommended_proof_assets(signals, dim_results)
    recommended_comparison_surfaces = _build_recommended_comparison_surfaces(signals, dim_results)
    monitoring_recommendation = _build_monitoring_recommendation(total_score)

    report = {
        "total_score": total_score,
        "authority_score": total_score,
        "score_label": score_label_for(total_score),
        "confidence": round(confidence, 3),
        "confidence_label": confidence_label_for(confidence),
        "dimension_scores": {dim: d["score"] for dim, d in dim_results.items()},
        "technical_scores": technical,
        "evidence": dim_results,
        "public_evidence": public_evidence,
        "top_gaps": top_gaps,
        "quick_wins": quick_wins,
        "recommended_package": recommended,
        "authority_graph": authority_graph,
        "buyer_questions": buyer_questions,
        "recommended_pages": recommended_pages,
        "recommended_schema": recommended_schema,
        "recommended_proof_assets": recommended_proof_assets,
        "recommended_comparison_surfaces": recommended_comparison_surfaces,
        "monitoring_recommendation": monitoring_recommendation,
        "formula_version": FORMULA_VERSION,
        "report_version": REPORT_VERSION,
        "scan_version": SCAN_VERSION,
    }
    return report


# ─────────────────────────────────────────────────────────────────────
# Failed-homepage path
# ─────────────────────────────────────────────────────────────────────


def _failed_homepage_report(signals: dict[str, Any]) -> dict[str, Any]:
    error = (signals.get("homepage") or {}).get("fetch_error") or "homepage_unreachable"
    not_assessed = {
        dim: {
            "score": 0,
            "status": "not_assessed",
            "detected": [],
            "missing": [f"Could not fetch the homepage ({error})"],
            "why_it_matters": "Without a fetchable homepage we can't assess this dimension.",
            "recommended_fix": "Confirm the URL is correct and publicly reachable, then re-run the test.",
            "confidence": 0.0,
            "public_label": PUBLIC_DIMENSION_LABEL[dim],
        }
        for dim in DIMENSION_WEIGHTS
    }
    return {
        "total_score": 0,
        "authority_score": 0,
        "score_label": "not_assessed",
        "confidence": 0.0,
        "confidence_label": "low",
        "dimension_scores": {dim: 0 for dim in DIMENSION_WEIGHTS},
        "technical_scores": {
            "schema_coverage": 0,
            "crawl_sitemap_readiness": 0,
            "faq_depth": 0,
        },
        "evidence": not_assessed,
        "public_evidence": {
            dim: {
                "public_label": PUBLIC_DIMENSION_LABEL[dim],
                "status": "not_assessed",
                "score": 0,
                "confidence_label": "low",
            }
            for dim in DIMENSION_WEIGHTS
        },
        "top_gaps": [],
        "quick_wins": ["Make sure the URL you submitted is publicly reachable, then re-run the test."],
        "recommended_package": {
            "primary_slug": None,
            "secondary_slug": None,
            "rationale": "We couldn't reach your site to score it. Re-run the test once the URL is reachable.",
        },
        "authority_graph": {},
        "buyer_questions": [],
        "recommended_pages": [],
        "recommended_schema": [],
        "recommended_proof_assets": [],
        "recommended_comparison_surfaces": [],
        "monitoring_recommendation": None,
        "formula_version": FORMULA_VERSION,
        "report_version": REPORT_VERSION,
        "scan_version": SCAN_VERSION,
    }


# ─────────────────────────────────────────────────────────────────────
# Per-dimension scorers — each returns a dict, no globals, no randomness
# ─────────────────────────────────────────────────────────────────────


def _score_entity_clarity(signals: dict[str, Any]) -> dict[str, Any]:
    homepage = signals.get("homepage") or {}
    detected: list[str] = []
    missing: list[str] = []
    score = 0

    title = (homepage.get("title") or "").strip()
    if len(title) >= 10:
        score += 20
        detected.append(f"Page title: “{title[:120]}”")
    else:
        missing.append("Homepage <title> is missing or too short")

    h1s = homepage.get("h1") or []
    if h1s:
        score += 15
        detected.append(f"Primary headline: “{h1s[0][:120]}”")
    else:
        missing.append("No <h1> on the homepage")

    meta = (homepage.get("meta_description") or "").strip()
    if len(meta) >= 50:
        score += 10
        detected.append("Meta description present")
    else:
        missing.append("No or weak meta description")

    types = set(signals.get("all_jsonld_types") or [])
    if "Organization" in types or "LocalBusiness" in types:
        score += 20
        detected.append("Organization JSON-LD found")
    else:
        missing.append("No Organization JSON-LD")

    if "LocalBusiness" in types:
        score += 5
        detected.append("LocalBusiness JSON-LD (location-aware)")

    # Location language — city / state / country / "serving X" patterns —
    # signals to local-aware AI assistants and Google Local that the entity
    # is geo-anchored. Soft bonus, not a hard requirement.
    body = (homepage.get("body_text_snippet") or "").lower()
    if re.search(
        r"\b(based in|headquartered in|serving|located in|offices in)\s+[A-Z][a-z]+",
        homepage.get("body_text_snippet") or "",
    ) or re.search(
        r"\b\d{5}(-\d{4})?\b",
        body,  # US ZIP
    ):
        score += 10
        detected.append("Location language detected")
    else:
        missing.append("No 'based in / serving / located in' language")

    about = _find_subpage(signals, ("/about",))
    if about and (about.get("status_code") or 0) < 400:
        score += 15
        detected.append("About page reachable")
    else:
        missing.append("No About page found at common paths")

    # Differentiators block — explicit "what makes us different / unlike /
    # purpose-built" framing on the homepage moves entity clarity for AI
    # summarizers separately from differentiation in ai_search_eligibility.
    diff_words = ("unlike", "different from", "purpose-built", "what makes us different")
    if any(w in body for w in diff_words):
        score += 5
        detected.append("Differentiator language on homepage")

    return _dim_result(
        score,
        detected,
        missing,
        why_it_matters=(
            "When AI assistants summarize a business they read the title, the H1, "
            "Organization schema, and the About page first. Without these, your "
            "category and what you do are guessed."
        ),
        recommended_fix=(
            "Set a clear <title> ('{Service} for {audience}'), an H1 that names "
            "the category you compete in, a 50–160 character meta description, "
            "Organization JSON-LD, and a reachable /about page."
        ),
    )


def _score_audience_clarity(signals: dict[str, Any]) -> dict[str, Any]:
    detected: list[str] = []
    missing: list[str] = []
    score = 0

    homepage = signals.get("homepage") or {}
    text = " ".join(
        [homepage.get("title") or "", homepage.get("meta_description") or ""]
        + (homepage.get("h1") or [])
        + (homepage.get("h2") or [])
        + [homepage.get("body_text_snippet") or ""]
    ).lower()

    audience_phrases = re.findall(
        r"\bfor\s+(small\s+businesses|founders|startups|saas|agencies|clinics|"
        r"med\s*spas|law\s+firms|real\s+estate|ecommerce|b2b|enterprise|coaches|"
        r"consultants|marketers|teams|operators|creators|brands)\b",
        text,
    )
    if audience_phrases:
        score += 35
        detected.append("Audience language detected: " + ", ".join(sorted(set(audience_phrases))[:5]))
    else:
        missing.append("No 'for {audience}' language on the homepage")

    about = _find_subpage(signals, ("/about",))
    if about and (about.get("body_text_snippet") or ""):
        score += 25
        detected.append("About page describes the audience")
    else:
        missing.append("About page either missing or thin on audience description")

    services = _find_subpage(signals, ("/services", "/products", "/pricing"))
    if services and (services.get("body_text_snippet") or ""):
        score += 25
        detected.append("Services/products page describes who it's for")
    else:
        missing.append("No services/products page that names the buyer")

    types = set(signals.get("all_jsonld_types") or [])
    if "Service" in types:
        score += 15
        detected.append("Service JSON-LD found")
    else:
        missing.append("No Service JSON-LD")

    return _dim_result(
        score,
        detected,
        missing,
        why_it_matters=(
            "AI assistants need to map your business to a buyer profile to "
            "recommend you in the right comparison set. If your site doesn't "
            "name the audience, you get bucketed generically."
        ),
        recommended_fix=(
            "Add explicit 'for {audience}' language on the homepage, the About "
            "page, and at least one Services or Pricing page. Add Service "
            "JSON-LD with audience.name."
        ),
    )


def _score_offer_clarity(signals: dict[str, Any]) -> dict[str, Any]:
    detected: list[str] = []
    missing: list[str] = []
    score = 0

    services = _find_subpage(signals, ("/services", "/products", "/pricing"))
    if services and (services.get("status_code") or 0) < 400:
        score += 30
        detected.append(f"Offer page reachable: {services.get('url')}")
        h2s = services.get("h2") or []
        if h2s:
            score += 15
            detected.append(f"Offer page lists {len(h2s)} sub-heading(s)")
    else:
        missing.append("No /services, /products, or /pricing page reachable")

    pricing = _find_subpage(signals, ("/pricing",))
    if pricing and (pricing.get("status_code") or 0) < 400:
        score += 15
        detected.append("Pricing page reachable")
    else:
        missing.append("No public pricing page")

    types = set(signals.get("all_jsonld_types") or [])
    schema_score = 0
    for t in ("Service", "Product", "Offer"):
        if t in types:
            schema_score += 13
            detected.append(f"{t} JSON-LD found")
    if schema_score == 0:
        missing.append("No Service / Product / Offer JSON-LD")
    score += min(schema_score, 40)

    return _dim_result(
        score,
        detected,
        missing,
        why_it_matters=(
            "Buyers ask AI 'what does {company} sell?' and 'how much does it cost?' "
            "Without service/product/offer schema and a public pricing surface, "
            "the assistant can't give a concrete answer about you."
        ),
        recommended_fix=(
            "Publish a /services or /products page with one heading per offer, "
            "a /pricing page (even a 'starts at' range), and Service or Product "
            "JSON-LD on each offer page."
        ),
    )


def _score_proof_strength(signals: dict[str, Any]) -> dict[str, Any]:
    detected: list[str] = []
    missing: list[str] = []
    score = 0

    proof_pages = []
    for sub in ("/case", "/testimonial", "/proof", "/reviews"):
        page = _find_subpage(signals, (sub,))
        if page and (page.get("status_code") or 0) < 400:
            proof_pages.append(page.get("url"))
    if proof_pages:
        score += min(40, 15 * len(proof_pages))
        detected.append(f"Proof page(s) reachable: {len(proof_pages)}")
    else:
        missing.append("No case-study / testimonial / proof / reviews page")

    homepage = signals.get("homepage") or {}
    body = (homepage.get("body_text_snippet") or "").lower()
    proof_words = ("testimonial", "case study", "client", "review", "trusted by", "before and after")
    hits = [w for w in proof_words if w in body]
    if hits:
        score += min(15, 4 * len(hits))
        detected.append("Proof language on homepage: " + ", ".join(hits))
    else:
        missing.append("No testimonial/case-study language on the homepage")

    # Before/after / outcome language is a strong AI-summary signal because
    # assistants prefer outcome-anchored citations over testimonial walls.
    if re.search(r"\bbefore\s*(/|and)\s*after\b", body) or re.search(r"\bresults?:\b", body):
        score += 10
        detected.append("Before/after or results: language detected")

    # Credentials / awards / certifications — these are explicit AI-trust
    # scaffolding even when proof pages don't exist.
    cred_pages = []
    for sub in ("/credentials", "/awards", "/certifications", "/team", "/press"):
        page = _find_subpage(signals, (sub,))
        if page and (page.get("status_code") or 0) < 400:
            cred_pages.append(page.get("url"))
    if cred_pages:
        score += min(15, 6 * len(cred_pages))
        detected.append(f"Credential / award / press page(s): {len(cred_pages)}")
    if any(w in body for w in ("certified", "accredited", "award", "press", "featured in")):
        score += 5
        detected.append("Credential / press language on homepage")

    types = set(signals.get("all_jsonld_types") or [])
    if "Review" in types or "AggregateRating" in types:
        score += 20
        detected.append("Review / AggregateRating JSON-LD found")
    else:
        missing.append("No Review or AggregateRating JSON-LD")

    if "Article" in types:
        score += 10
        detected.append("Article schema present (proof-supporting content)")

    return _dim_result(
        score,
        detected,
        missing,
        why_it_matters=(
            "AI systems weigh credibility before recommending a business. "
            "Without case studies, named clients, reviews, or AggregateRating "
            "schema, you read as 'unproven' to the assistant."
        ),
        recommended_fix=(
            "Publish a /case-studies or /proof page with at least 3 named "
            "engagements (or anonymized but specific) and add Review JSON-LD "
            "where you have public reviews."
        ),
    )


def _score_comparison_readiness(signals: dict[str, Any]) -> dict[str, Any]:
    detected: list[str] = []
    missing: list[str] = []
    score = 0

    found = []
    for sub in ("/vs", "/compare", "/comparison", "/alternative"):
        page = _find_subpage(signals, (sub,))
        if page and (page.get("status_code") or 0) < 400:
            found.append(page.get("url"))
    if found:
        score += min(50, 20 * len(found))
        detected.append(f"Comparison/alternatives page(s): {len(found)}")
    else:
        missing.append("No comparison, /vs, or /alternatives page")

    # "Best {category}" / "top {category} for {audience}" surfaces — the
    # category-level decision-support page that AI assistants pull from
    # when buyers ask "what's the best X for Y".
    best_page = None
    for sub in ("/best-", "/top-", "/leading-", "/category"):
        page = _find_subpage(signals, (sub,))
        if page and (page.get("status_code") or 0) < 400:
            best_page = page
            break
    if best_page is not None:
        score += 15
        detected.append(f"Best-of / category page reachable: {best_page.get('url')}")
    else:
        missing.append("No 'best {category}' or category decision-support page")

    # Explicit "how to choose" decision-support page.
    how_choose = None
    for sub in ("/how-to-choose", "/choosing", "/buyers-guide", "/buyer-guide"):
        page = _find_subpage(signals, (sub,))
        if page and (page.get("status_code") or 0) < 400:
            how_choose = page
            break
    if how_choose is not None:
        score += 15
        detected.append(f"Decision-support page reachable: {how_choose.get('url')}")
    else:
        missing.append("No /how-to-choose or buyer's-guide page")

    homepage = signals.get("homepage") or {}
    body = (homepage.get("body_text_snippet") or "").lower()
    if any(p in body for p in (" vs ", " versus ", "alternatives to", "how to choose", "best ")):
        score += 10
        detected.append("Comparison language on homepage")
    else:
        missing.append("No comparison language on the homepage")

    pricing = _find_subpage(signals, ("/pricing",))
    if pricing and any(
        t in (pricing.get("body_text_snippet") or "").lower() for t in ("compared to", "vs ", "alternative")
    ):
        score += 10
        detected.append("Pricing page references comparisons")

    return _dim_result(
        score,
        detected,
        missing,
        why_it_matters=(
            "Buyers asking 'A vs B' get answers built from the comparison "
            "pages each side publishes. If you don't publish one, the "
            "comparison comes from your competitor's framing."
        ),
        recommended_fix=(
            "Publish at least one /compare/{competitor} or /alternatives-to-{x} "
            "page that names the trade-offs honestly. One page beats none."
        ),
    )


def _score_answer_engine_readiness(signals: dict[str, Any]) -> dict[str, Any]:
    detected: list[str] = []
    missing: list[str] = []
    score = 0

    faq = _find_subpage(signals, ("/faq",))
    types = set(signals.get("all_jsonld_types") or [])
    if faq and (faq.get("status_code") or 0) < 400:
        score += 30
        detected.append(f"FAQ page reachable: {faq.get('url')}")
        h2_count = len(faq.get("h2") or [])
        if h2_count >= 6:
            score += 25
            detected.append(f"FAQ has {h2_count} sub-questions")
        elif h2_count > 0:
            score += 10
            detected.append(f"FAQ has {h2_count} sub-questions")
        else:
            missing.append("FAQ page is too thin (under 6 questions)")
    else:
        missing.append("No /faq page reachable")

    if "FAQPage" in types:
        score += 30
        detected.append("FAQPage JSON-LD found")
    else:
        missing.append("No FAQPage JSON-LD")

    # Question-format headings anywhere
    all_h2 = []
    for p in [signals.get("homepage")] + (signals.get("subpages") or []):
        if p:
            all_h2.extend(p.get("h2") or [])
    question_headings = [h for h in all_h2 if h.endswith("?")]
    if question_headings:
        score += min(10, 3 * len(question_headings))
        detected.append(f"{len(question_headings)} question-format heading(s) across the site")
    else:
        missing.append("No question-format headings (“What is...?”)")

    # Direct buyer-question / category-education surfaces — answer-engine
    # pages keyed off "how-to-choose", buyer's guide, what-is, "guide-to",
    # "explained" URLs.
    education_pages: list[str] = []
    for sub in ("/how-to-choose", "/buyers-guide", "/buyer-guide", "/guide-to", "/what-is", "/explained"):
        page = _find_subpage(signals, (sub,))
        if page and (page.get("status_code") or 0) < 400:
            education_pages.append(page.get("url"))
    if education_pages:
        score += min(15, 8 * len(education_pages))
        detected.append(f"Direct-answer / education page(s): {len(education_pages)}")
    else:
        missing.append("No direct-answer or category education page")

    return _dim_result(
        score,
        detected,
        missing,
        why_it_matters=(
            "AI search systems pull direct answers from FAQ pages and "
            "question-format headings. Without these, they paraphrase your "
            "competitors' answers instead of yours."
        ),
        recommended_fix=(
            "Publish a /faq page with the top 8 buyer questions, mark it up "
            "with FAQPage JSON-LD, and use question-format headings on at "
            "least one services page."
        ),
    )


def _score_trust_signal_density(signals: dict[str, Any]) -> dict[str, Any]:
    detected: list[str] = []
    missing: list[str] = []
    score = 0

    homepage = signals.get("homepage") or {}
    body = (homepage.get("body_text_snippet") or "").lower()
    contact_page = _find_subpage(signals, ("/contact",))
    if contact_page and (contact_page.get("status_code") or 0) < 400:
        score += 20
        detected.append("Contact page reachable")
    else:
        missing.append("No /contact page reachable")

    if re.search(
        r"\b\d{1,4}\s+\w+(\s+\w+){0,4}\s+(street|st\.?|avenue|ave\.?|road|rd\.?|suite|ste\.?|drive|dr\.?)", body
    ):
        score += 15
        detected.append("Physical address detected on homepage")
    else:
        missing.append("No physical address on the homepage")

    if re.search(r"[\w.+\-]+@[\w.\-]+\.[a-z]{2,}", body):
        score += 10
        detected.append("Contact email visible on homepage")
    if re.search(r"\b(\+?1[\s\-.])?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b", body):
        score += 10
        detected.append("Phone number visible on homepage")

    types = set(signals.get("all_jsonld_types") or [])
    if "LocalBusiness" in types:
        score += 20
        detected.append("LocalBusiness JSON-LD found")
    if "Organization" in types:
        # Already counted in entity_clarity, but having sameAs / address in Org schema is a trust signal too.
        for block in signals.get("all_jsonld_blocks") or []:
            if isinstance(block, dict) and block.get("@type") == "Organization":
                if "sameAs" in block:
                    score += 10
                    detected.append("Organization schema has sameAs links")
                    break

    if any("privacy" in (l or "").lower() for l in (homepage.get("internal_links") or [])):
        score += 10
        detected.append("Privacy policy linked from homepage")
    if any("terms" in (l or "").lower() for l in (homepage.get("internal_links") or [])):
        score += 5
        detected.append("Terms linked from homepage")

    return _dim_result(
        score,
        detected,
        missing,
        why_it_matters=(
            "Trust signals (address, phone, contact page, privacy/terms, "
            "sameAs) are how AI assistants tell a real business from a "
            "thin landing page."
        ),
        recommended_fix=(
            "Publish a /contact page with email + phone + physical address. "
            "Link your social profiles via Organization.sameAs. Link a "
            "/privacy and /terms page from the footer."
        ),
    )


def _score_ai_search_eligibility(signals: dict[str, Any], dim_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Composite-of-composites: rolls up differentiation language, schema
    breadth, comparison + proof. Always assessed because it depends only on
    other dimensions and the JSON-LD types we already have."""
    detected: list[str] = []
    missing: list[str] = []
    score = 0

    types = set(signals.get("all_jsonld_types") or [])
    breadth = len(types)
    if breadth >= 5:
        score += 30
        detected.append(f"Schema breadth: {breadth} distinct @types")
    elif breadth >= 2:
        score += 15
        detected.append(f"Schema breadth: {breadth} distinct @types")
    else:
        missing.append("Very limited schema breadth")

    # "Why choose us" language anywhere
    all_text = ""
    for p in [signals.get("homepage")] + (signals.get("subpages") or []):
        if p:
            all_text += " " + (p.get("body_text_snippet") or "").lower()
    diff_words = (
        "unlike",
        "different from",
        "the only",
        "purpose-built",
        "we focus",
        "we specialise",
        "we specialize",
        "what makes us different",
        "why choose us",
    )
    diff_hits = [w for w in diff_words if w in all_text]
    if diff_hits:
        score += min(30, 8 * len(diff_hits))
        detected.append("Differentiation language: " + ", ".join(diff_hits[:3]))
    else:
        missing.append("No differentiation language ('unlike', 'we focus', etc.)")

    # Borrow strength from already-scored dimensions
    for dep in ("comparison_readiness", "proof_strength", "answer_engine_readiness"):
        d = dim_results[dep]
        if d["status"] == "assessed":
            score += int(round(d["score"] * 0.13))

    return _dim_result(
        score,
        detected,
        missing,
        why_it_matters=(
            "AI systems decide whether to recommend you by combining schema "
            "breadth, differentiation language, comparison surface, and proof "
            "depth. Weakness in any of those compounds."
        ),
        recommended_fix=(
            "Strengthen the lowest-scoring dimensions first. Rich JSON-LD + a "
            "single comparison page + clear differentiation language moves "
            "the needle the most."
        ),
    )


def _score_technical(signals: dict[str, Any]) -> dict[str, int]:
    """Three supporting technical signals — surfaced as scores 0–100 each
    and used for bounded penalties on the composite. Not part of the
    weighted dimensions."""
    types = set(signals.get("all_jsonld_types") or [])
    schema_score = 0
    if "Organization" in types or "LocalBusiness" in types:
        schema_score += 25
    if "WebSite" in types:
        schema_score += 15
    if "Service" in types or "Product" in types or "Offer" in types:
        schema_score += 25
    if "FAQPage" in types:
        schema_score += 20
    if "BreadcrumbList" in types:
        schema_score += 5
    if "Review" in types or "AggregateRating" in types:
        schema_score += 10
    schema_score = int(_clamp(schema_score, 0, 100))

    crawl_score = 0
    homepage = signals.get("homepage") or {}
    if (homepage.get("status_code") or 0) < 400 and not homepage.get("fetch_error"):
        crawl_score += 50
    if signals.get("robots_txt_present"):
        crawl_score += 25
    if signals.get("sitemap_present"):
        crawl_score += 25
    if signals.get("robots_txt_blocks_ai"):
        crawl_score = max(0, crawl_score - 30)
    crawl_score = int(_clamp(crawl_score, 0, 100))

    faq_depth = 0
    faq = _find_subpage(signals, ("/faq",))
    if faq and (faq.get("status_code") or 0) < 400:
        h2_count = len(faq.get("h2") or [])
        faq_depth = int(_clamp(h2_count * 12, 0, 100))

    return {
        "schema_coverage": schema_score,
        "crawl_sitemap_readiness": crawl_score,
        "faq_depth": faq_depth,
    }


def _apply_technical_adjustments(composite: float, technical: dict[str, int]) -> float:
    """Bounded penalty/bonus based on technical signals."""
    schema = technical["schema_coverage"]
    crawl = technical["crawl_sitemap_readiness"]
    if schema == 0:
        composite -= 8
    elif schema >= 80:
        composite += 4
    if crawl < 40:
        composite -= 6
    elif crawl >= 90:
        composite += 2
    return composite


# ─────────────────────────────────────────────────────────────────────
# Quick wins + recommendation
# ─────────────────────────────────────────────────────────────────────


def _build_quick_wins(
    dim_results: dict[str, dict[str, Any]],
    technical: dict[str, int],
    signals: dict[str, Any],
) -> list[str]:
    wins: list[str] = []
    if technical["schema_coverage"] == 0:
        wins.append(
            "Add Organization JSON-LD to the homepage. This single block lets "
            "every AI search system identify your business as a real entity."
        )
    if not signals.get("sitemap_present"):
        wins.append(
            "Publish /sitemap.xml. AI crawlers use it to find every page they "
            "should consider for buyer-question answers."
        )
    if not _find_subpage(signals, ("/faq",)):
        wins.append("Publish a /faq page answering the top 6 buyer questions. Wrap it in FAQPage JSON-LD.")

    # If none of the technical wins fired, derive a win from the lowest dim.
    if not wins:
        sorted_dims = sorted(
            ((dim, d) for dim, d in dim_results.items() if d["status"] == "assessed"),
            key=lambda kv: kv[1]["score"],
        )
        if sorted_dims:
            dim, d = sorted_dims[0]
            wins.append(d["recommended_fix"])
    return wins[:1]  # first quick win is the public one


def _recommend_package(total_score: int, dim_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Cross-lane recommendation:
      - primary_slug          — AI Authority lane (always)
      - secondary_slug        — AI Authority lane companion (sometimes)
      - creative_proof_slug   — Creative Proof lane companion (sometimes)

    Threshold-based AI Authority pick per spec; Creative Proof companion
    derived from which dimension is weakest so AI-assisted buyers see both
    structural authority AND creative proof recommended where the gap calls
    for it.
    """
    if total_score < 40:
        primary, secondary = PACKAGE_BUILDOUT, None
    elif total_score < 60:
        primary, secondary = PACKAGE_SPRINT, None
    elif total_score < 75:
        primary, secondary = PACKAGE_SPRINT, PACKAGE_RETAINER
    elif total_score < 90:
        primary, secondary = PACKAGE_RETAINER, None
    else:
        primary, secondary = PACKAGE_SYSTEM, None

    creative_companion, creative_rationale = _recommend_creative_proof_companion(total_score, dim_results)

    # One-sentence rationale referencing the lowest-scoring dimensions.
    sorted_dims = sorted(
        ((dim, d) for dim, d in dim_results.items() if d["status"] == "assessed"),
        key=lambda kv: kv[1]["score"],
    )
    if sorted_dims:
        weakest = sorted_dims[0]
        rationale = (
            f"Your weakest dimension is {PUBLIC_DIMENSION_LABEL[weakest[0]]} "
            f"at {weakest[1]['score']}/100. The recommended package rebuilds "
            f"that surface first."
        )
    else:
        rationale = (
            "Not enough dimensions assessed to pinpoint the weakest "
            "surface. The recommended package starts with the AI Search "
            "Authority audit."
        )
    if creative_companion and creative_rationale:
        rationale = f"{rationale} {creative_rationale}"
    return {
        "primary_slug": primary,
        "secondary_slug": secondary,
        "creative_proof_slug": creative_companion,
        "rationale": rationale,
    }


def _recommend_creative_proof_companion(
    total_score: int,
    dim_results: dict[str, dict[str, Any]],
) -> tuple[str | None, str | None]:
    """Pick a Creative Proof lane companion when a dimension gap maps to
    creative-side work (proof video, hook variants, founder clips, paid
    creative). Returns (slug | None, one-line rationale | None).
    """
    proof = dim_results.get("proof_strength", {})
    offer = dim_results.get("offer_clarity", {})
    audience = dim_results.get("audience_clarity", {})

    proof_score = proof.get("score", 100) if proof.get("status") == "assessed" else 100
    offer_score = offer.get("score", 100) if offer.get("status") == "assessed" else 100
    audience_score = audience.get("score", 100) if audience.get("status") == "assessed" else 100

    # Proof gap is the strongest creative-companion signal — proof videos
    # and case-study clips fill it directly.
    if proof_score < 50:
        return (
            CREATIVE_SIGNAL_ENTRY,
            "Pair with the Signal Entry creative pack to publish proof videos "
            "and case-study clips that match the new authority surfaces.",
        )

    # Offer clarity gap reads as a creative-rebuild + hook-variant problem.
    if offer_score < 50:
        return (
            CREATIVE_CONVERSION_ARCH,
            "Pair with Conversion Architecture so hooks and offer language "
            "rebuild in lockstep with the new offer pages.",
        )

    # Authority-ready businesses with thin recurring creative output benefit
    # from a sustained Momentum Engine cadence so the new pages stay alive.
    if total_score >= 75 and (proof_score < 70 or audience_score < 70):
        return (
            CREATIVE_MOMENTUM_ENGINE,
            "Pair with the Momentum Engine creative retainer so the new "
            "authority surfaces stay populated with fresh proof and hook "
            "variants each month.",
        )

    return (None, None)


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _dim_result(
    raw_score: float,
    detected: list[str],
    missing: list[str],
    *,
    why_it_matters: str,
    recommended_fix: str,
) -> dict[str, Any]:
    score = int(round(_clamp(raw_score, 0, 100)))
    confidence = _clamp(0.5 + 0.1 * len(detected) - 0.05 * len(missing), 0.2, 1.0)
    return {
        "score": score,
        "status": "assessed",
        "detected": detected,
        "missing": missing,
        "why_it_matters": why_it_matters,
        "recommended_fix": recommended_fix,
        "confidence": confidence,
        "public_label": "",  # filled in by caller via PUBLIC_DIMENSION_LABEL
    }


def _find_subpage(signals: dict[str, Any], path_substrings: tuple[str, ...]) -> dict | None:
    for page in signals.get("subpages") or []:
        if not page or not page.get("url"):
            continue
        path = page["url"].split("//", 1)[-1].split("/", 1)[-1].lower()
        path = "/" + path  # ensure leading slash for substring match
        for sub in path_substrings:
            if sub in path:
                return page
    return None


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# ─────────────────────────────────────────────────────────────────────
# Platform-ready outputs (Authority Graph, buyer questions, recommended
# pages/schema/proof, monitoring recommendation). Deterministic — derived
# from the same signals + dimension results, no randomness, no LLM.
# ─────────────────────────────────────────────────────────────────────


def _build_authority_graph(
    signals: dict[str, Any],
    dim_results: dict[str, dict[str, Any]],
    technical: dict[str, int],
    buyer_questions: list[dict[str, str]],
) -> dict[str, Any]:
    """Structured view of the authority signals grouped exactly the way
    the Decision Layer's Authority Graph view reads them:

      Company → Category → Offers → Audience → Proof → Buyer Questions
              → FAQs → Comparisons → Schema → Answer Pages → CTAs

    Each node carries the score, detected/missing evidence, and any
    structured data we can extract."""
    homepage = signals.get("homepage") or {}
    submitted = signals.get("submitted") or {}
    types = sorted(signals.get("all_jsonld_types") or [])
    body = homepage.get("body_text_snippet") or ""
    body_lower = body.lower()

    # CTA detection — links/text from the homepage that read as a primary
    # buyer action. Conservative match, so AI-summary readers can see the
    # explicit asks.
    cta_phrases = (
        "get started",
        "book a demo",
        "request a demo",
        "schedule",
        "contact us",
        "talk to",
        "buy now",
        "sign up",
        "start free",
        "request pricing",
    )
    detected_ctas = sorted({p for p in cta_phrases if p in body_lower})

    # Locations — light extraction from the visible body. Caller doesn't
    # need geocoding for the graph; the Sprint engagement does that.
    location_hits: list[str] = []
    for m in re.finditer(
        r"\b(based in|headquartered in|serving|located in|offices in)\s+([A-Z][a-zA-Z]+(?:[\s,]+[A-Z][a-zA-Z]+){0,2})",
        body,
    ):
        location_hits.append(m.group(2)[:80])
    if not location_hits:
        # ZIP-only fallback so AI readers know the entity is geo-anchored.
        zips = re.findall(r"\b\d{5}(?:-\d{4})?\b", body)
        if zips:
            location_hits = [f"ZIP {zips[0]}"]

    return {
        "version": "v1",
        "company": {
            "name": submitted.get("company_name") or homepage.get("title"),
            "website": homepage.get("url"),
            "industry": submitted.get("industry"),
        },
        "category": {
            "industry": submitted.get("industry"),
            "title": homepage.get("title"),
            "h1": (homepage.get("h1") or [None])[0],
            "meta_description": homepage.get("meta_description"),
        },
        "entity": {
            "title": homepage.get("title"),
            "h1": (homepage.get("h1") or [None])[0],
            "meta_description": homepage.get("meta_description"),
            "has_organization_schema": "Organization" in types,
            "has_local_business_schema": "LocalBusiness" in types,
            "locations": location_hits,
        },
        "audience": {
            "score": dim_results["audience_clarity"]["score"],
            "detected": dim_results["audience_clarity"]["detected"],
            "missing": dim_results["audience_clarity"]["missing"],
        },
        "offers": {
            "score": dim_results["offer_clarity"]["score"],
            "detected": dim_results["offer_clarity"]["detected"],
            "missing": dim_results["offer_clarity"]["missing"],
            "schema_coverage_score": technical["schema_coverage"],
        },
        "proof": {
            "score": dim_results["proof_strength"]["score"],
            "detected": dim_results["proof_strength"]["detected"],
            "missing": dim_results["proof_strength"]["missing"],
        },
        "buyer_questions": {
            "count": len(buyer_questions),
            "preview": [q.get("question") for q in buyer_questions[:3]],
        },
        "faqs": {
            "score": dim_results["answer_engine_readiness"]["score"],
            "depth_score": technical["faq_depth"],
            "has_faq_page_schema": "FAQPage" in types,
        },
        "comparisons": {
            "score": dim_results["comparison_readiness"]["score"],
            "detected": dim_results["comparison_readiness"]["detected"],
            "missing": dim_results["comparison_readiness"]["missing"],
        },
        "schema": {
            "score": technical["schema_coverage"],
            "types_present": types,
        },
        "answer_pages": {
            "score": dim_results["answer_engine_readiness"]["score"],
            "detected": dim_results["answer_engine_readiness"]["detected"],
            "missing": dim_results["answer_engine_readiness"]["missing"],
        },
        "ctas": {
            "detected": detected_ctas,
            "count": len(detected_ctas),
        },
        "trust_signals": {
            "score": dim_results["trust_signal_density"]["score"],
            "detected": dim_results["trust_signal_density"]["detected"],
            "missing": dim_results["trust_signal_density"]["missing"],
        },
        "crawlability": {
            "score": technical["crawl_sitemap_readiness"],
            "robots_txt_present": signals.get("robots_txt_present"),
            "robots_txt_blocks_ai": signals.get("robots_txt_blocks_ai"),
            "sitemap_present": signals.get("sitemap_present"),
            "sitemap_url_count": signals.get("sitemap_url_count", 0),
        },
    }


def _build_recommended_comparison_surfaces(
    signals: dict[str, Any],
    dim_results: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Comparison surfaces ProofHook would publish for this business.
    Distinct from `recommended_pages` because comparison work has its own
    fulfillment shape: targeted competitor pages, alternatives pages, and
    category decision-support pages.
    """
    out: list[dict[str, Any]] = []
    submitted = signals.get("submitted") or {}
    industry = (submitted.get("industry") or "category").strip().lower()
    competitor_url = submitted.get("competitor_url")

    has_compare = bool(_find_subpage(signals, ("/vs", "/compare", "/comparison", "/alternative")))
    has_best_of = bool(_find_subpage(signals, ("/best-", "/top-", "/leading-", "/category")))
    has_buyer_guide = bool(_find_subpage(signals, ("/how-to-choose", "/buyers-guide", "/buyer-guide")))

    if competitor_url:
        out.append(
            {
                "kind": "competitor_comparison",
                "slug_pattern": "/compare/{competitor}",
                "purpose": (
                    f"Direct comparison page against the named competitor "
                    f"({competitor_url}) so the assistant builds the comparison "
                    "from your framing instead of theirs."
                ),
                "priority": "high",
            }
        )
    elif not has_compare:
        out.append(
            {
                "kind": "competitor_comparison",
                "slug_pattern": "/compare/{competitor}",
                "purpose": (
                    "Pick the most-asked-about alternative in your category and "
                    "publish one comparison page. One beats none."
                ),
                "priority": "high",
            }
        )

    if not has_best_of:
        out.append(
            {
                "kind": "category_decision_support",
                "slug_pattern": f"/best-{industry.replace(' ', '-')}",
                "purpose": (
                    f"Category page targeting 'best {industry}' so AI assistants "
                    "have a destination when buyers research the category before "
                    "the brand."
                ),
                "priority": "medium",
            }
        )

    if not has_buyer_guide:
        out.append(
            {
                "kind": "buyers_guide",
                "slug_pattern": "/how-to-choose-a-{category}",
                "purpose": (
                    "Decision-support article that names the trade-offs honestly. "
                    "AI assistants pull direct answers from these pages."
                ),
                "priority": "medium",
            }
        )

    if dim_results.get("comparison_readiness", {}).get("score", 0) < 30 and not out:
        out.append(
            {
                "kind": "alternatives_page",
                "slug_pattern": "/alternatives-to-{competitor}",
                "purpose": (
                    "Alternatives surface for buyers searching 'alternatives to X'. "
                    "Owning the alternatives page wins the comparison click."
                ),
                "priority": "medium",
            }
        )

    return out


def _build_buyer_questions(
    signals: dict[str, Any],
    dim_results: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    """Buyer trust questions an AI-assisted prospect is likely to ask before
    they ever visit the website. Leads with direct-trust questions (the
    Decision-Layer framing), then adds gap-driven and operator-facing ones.

    Generated deterministically from submitted company + industry +
    detected dimension gaps. Operator sees the full list; the public
    result shows the first 3 (the trust-decision questions)."""
    submitted = signals.get("submitted") or {}
    company = submitted.get("company_name") or (signals.get("homepage") or {}).get("title") or "this business"
    company = company.split("|")[0].strip()[:80] or "this business"
    industry_raw = (submitted.get("industry") or "").strip()
    category = industry_raw or "provider"

    # ── 1. Direct-trust questions (the public-facing block) ─────────────
    trust_first: list[dict[str, str]] = [
        {
            "question": f"Is {company} trustworthy?",
            "rationale": "AI assistants weigh credibility — schema, proof, and trust signals — before including you in a recommendation.",
        },
        {
            "question": f"How does {company} compare to the alternatives?",
            "rationale": "If you don't publish your own comparison surface, the assistant builds the comparison from your competitor's framing.",
        },
        {
            "question": f"Why should someone choose {company}?",
            "rationale": "Differentiation language is how the assistant places you in a shortlist instead of a generic bucket.",
        },
        {
            "question": f"What should I know before choosing a {category} provider?",
            "rationale": "Buyers research the category before the brand. The provider that answers this clearly tends to land in the consideration set.",
        },
        {
            "question": f"Who is {company} best for?",
            "rationale": "Audience clarity decides whether the assistant surfaces you for a buyer's specific situation.",
        },
    ]

    # ── 2. Operator-facing supporting questions ─────────────────────────
    supporting: list[dict[str, str]] = [
        {
            "question": f"What does {company} actually do?",
            "rationale": "Title, H1, and Organization schema feed the one-sentence summary the assistant uses.",
        },
        {
            "question": f"What does {company} cost?",
            "rationale": "Pricing-aware comparisons need a public pricing surface — even a 'starts at' range.",
        },
        {
            "question": f"What proof does {company} have that this works?",
            "rationale": "Case studies, named clients, AggregateRating — the credibility scaffolding AI weighs.",
        },
        {
            "question": f"How fast does {company} deliver?",
            "rationale": "Time-to-value is asked early; missing answer means the assistant pulls from competitors.",
        },
        {
            "question": f"Where is {company} located, and how do I contact them?",
            "rationale": "Trust scaffolding: address, contact, sameAs. Local-business buyers read these first.",
        },
    ]

    # ── 3. Gap-driven additions ─────────────────────────────────────────
    gap_driven: list[dict[str, str]] = []
    if dim_results.get("comparison_readiness", {}).get("score", 100) < 50:
        gap_driven.append(
            {
                "question": f"Why would I choose {company} instead of [the obvious alternative]?",
                "rationale": "Comparison readiness scored low — publish at least one /compare page so this question lands on your site.",
            }
        )
    if dim_results.get("answer_engine_readiness", {}).get("score", 100) < 50:
        gap_driven.append(
            {
                "question": "What are the first questions every new buyer asks before signing up?",
                "rationale": "FAQ depth scored low — wrap the answers in FAQPage JSON-LD on a /faq page.",
            }
        )
    if dim_results.get("proof_strength", {}).get("score", 100) < 50:
        gap_driven.append(
            {
                "question": "Can you show a result you produced for a customer like me?",
                "rationale": "Proof strength scored low — one specific, named (or specifically-anonymized) case study moves the needle.",
            }
        )

    combined = trust_first + supporting + gap_driven
    return combined[:10]


def _build_recommended_pages(
    signals: dict[str, Any],
    dim_results: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Pages ProofHook would publish for this business in the Sprint /
    Buildout engagement. Deterministic — based on what's missing."""
    out: list[dict[str, Any]] = []

    if not _find_subpage(signals, ("/about",)):
        out.append(
            {
                "slug": "/about",
                "title": "About",
                "purpose": "Names the entity, the founders, the audience, and links to Organization schema.",
                "priority": "high",
            }
        )
    if not _find_subpage(signals, ("/services", "/products")):
        out.append(
            {
                "slug": "/services",
                "title": "Services / Products",
                "purpose": "One heading per offer with Service or Product JSON-LD attached.",
                "priority": "high",
            }
        )
    if not _find_subpage(signals, ("/pricing",)):
        out.append(
            {
                "slug": "/pricing",
                "title": "Pricing",
                "purpose": "At minimum a 'starts at' range so AI can answer pricing questions.",
                "priority": "high",
            }
        )
    if not _find_subpage(signals, ("/faq",)):
        out.append(
            {
                "slug": "/faq",
                "title": "FAQ",
                "purpose": "Top 8 buyer questions, FAQPage JSON-LD.",
                "priority": "high",
            }
        )
    if not _find_subpage(signals, ("/case", "/proof", "/testimonial", "/reviews")):
        out.append(
            {
                "slug": "/case-studies",
                "title": "Case Studies",
                "purpose": "At least 3 specific (anonymized OK) buyer outcomes.",
                "priority": "high",
            }
        )
    if not _find_subpage(signals, ("/vs", "/compare", "/alternative")):
        out.append(
            {
                "slug": "/compare/[competitor]",
                "title": "Comparison page",
                "purpose": "Name the trade-off honestly — one comparison page beats none.",
                "priority": "medium",
            }
        )
    if not _find_subpage(signals, ("/contact",)):
        out.append(
            {
                "slug": "/contact",
                "title": "Contact",
                "purpose": "Email + phone + physical address. Trust + local-business signal.",
                "priority": "medium",
            }
        )

    return out


def _build_recommended_schema(
    signals: dict[str, Any],
    technical: dict[str, int],
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    types = set(signals.get("all_jsonld_types") or [])
    homepage = signals.get("homepage") or {}
    homepage_url = homepage.get("url") or "/"

    if "Organization" not in types and "LocalBusiness" not in types:
        out.append(
            {
                "type": "Organization",
                "target_url": homepage_url,
                "why": "Identifies the business as a real entity with name, url, logo, sameAs.",
            }
        )
    if "WebSite" not in types:
        out.append(
            {
                "type": "WebSite",
                "target_url": homepage_url,
                "why": "Establishes the website-level identity and a SearchAction for site search.",
            }
        )
    if "Service" not in types and "Product" not in types and "Offer" not in types:
        out.append(
            {
                "type": "Service",
                "target_url": "/services/*",
                "why": "Lets AI extract the offer and price for pricing-aware comparisons.",
            }
        )
    if "FAQPage" not in types:
        out.append(
            {
                "type": "FAQPage",
                "target_url": "/faq",
                "why": "Direct-answer surface for AI assistants. Highest leverage per minute spent.",
            }
        )
    if "BreadcrumbList" not in types:
        out.append(
            {
                "type": "BreadcrumbList",
                "target_url": "every page",
                "why": "Helps AI place a page within the site hierarchy when summarizing.",
            }
        )
    if "Review" not in types and "AggregateRating" not in types:
        out.append(
            {
                "type": "Review / AggregateRating",
                "target_url": "/case-studies, /reviews",
                "why": "AI weighs credibility before recommending — public rating data is load-bearing.",
            }
        )
    return out


def _build_recommended_proof_assets(
    signals: dict[str, Any],
    dim_results: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    proof_score = dim_results.get("proof_strength", {}).get("score", 0)
    if proof_score < 60:
        out.append(
            {
                "kind": "case_studies",
                "description": "At least 3 named (or specifically-anonymized) outcome stories with the buyer's industry, problem, action, and result.",
                "priority": "high",
            }
        )
    if proof_score < 50:
        out.append(
            {
                "kind": "testimonials",
                "description": "5–8 short pull-quotes attributed to a real role + first name + company size.",
                "priority": "high",
            }
        )
        out.append(
            {
                "kind": "client_logos",
                "description": "A logo strip on the homepage with at least 6 named buyers (with permission).",
                "priority": "medium",
            }
        )
    if dim_results.get("trust_signal_density", {}).get("score", 0) < 60:
        out.append(
            {
                "kind": "credentials",
                "description": "Certifications, partnerships, awards, press mentions — the kind of trust scaffolding that makes AI cite the business.",
                "priority": "medium",
            }
        )
    if dim_results.get("comparison_readiness", {}).get("score", 0) < 50:
        out.append(
            {
                "kind": "comparison_data",
                "description": "A side-by-side table with one named alternative — pricing, scope, time-to-value, what each is best for.",
                "priority": "medium",
            }
        )
    return out


def _build_monitoring_recommendation(total_score: int) -> str:
    if total_score >= 90:
        return (
            "Authority-ready. Monitoring would track schema drift, FAQ refresh "
            "cadence, comparison-page coverage of the top competitors, and any "
            "regressions in technical signals (robots, sitemap, indexability)."
        )
    if total_score >= 75:
        return (
            "Strong baseline. Monitoring would track quarterly authority score "
            "movements, new buyer-question surface coverage, schema additions, "
            "and any new comparison/alternative pages on competitor sites."
        )
    if total_score >= 60:
        return (
            "Developing. Monitoring would track each new page added during "
            "buildout, schema coverage growth, and re-score authority every "
            "30 days to confirm the work compounds."
        )
    return (
        "Below the monitoring threshold. The Sprint or Buildout engagement "
        "needs to publish the missing pages first; monitoring becomes "
        "valuable once the buildout has shipped."
    )
