"""Objection Mining Engine — extract, cluster, score, respond, route.

Pure functions. No I/O.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

OBJECTION_TYPES = [
    "price", "trust", "complexity", "timing", "competitor",
    "relevance", "proof", "identity", "skepticism",
]

OBJECTION_KEYWORDS = {
    "price": ["expensive", "too much", "can't afford", "cost", "cheaper", "budget", "free", "discount", "price", "not worth"],
    "trust": ["scam", "legit", "trust", "fake", "real", "honest", "sketchy", "suspicious", "reliable"],
    "complexity": ["complicated", "confusing", "hard to use", "difficult", "overwhelm", "too complex", "don't understand"],
    "timing": ["not now", "later", "busy", "not ready", "bad time", "wait", "maybe next"],
    "competitor": ["better option", "compared to", "vs", "alternative", "competitor", "switch", "already use"],
    "relevance": ["not for me", "doesn't apply", "irrelevant", "my situation", "different", "not my niche"],
    "proof": ["proof", "evidence", "results", "show me", "case study", "testimonial", "guarantee", "data"],
    "identity": ["not my thing", "not who I am", "not my style", "too basic", "too advanced", "not serious"],
    "skepticism": ["too good", "really work", "doubt", "skeptic", "believe", "bs", "hype", "overpromise"],
}

RESPONSE_ANGLES = {
    "price": {"content_angle": "Value demonstration — show ROI/savings over time", "cta_angle": "Risk-free trial or money-back guarantee CTA", "offer_angle": "budget"},
    "trust": {"content_angle": "Social proof — testimonials, case studies, transparent results", "cta_angle": "Low-commitment first step CTA", "offer_angle": "trust-first"},
    "complexity": {"content_angle": "Simplification — step-by-step walkthrough, beginner-friendly", "cta_angle": "Guided setup or demo CTA", "offer_angle": "convenience"},
    "timing": {"content_angle": "Urgency + patience balance — show cost of waiting", "cta_angle": "Save-for-later / reminder CTA", "offer_angle": "timing-sensitive"},
    "competitor": {"content_angle": "Honest comparison — show unique differentiators", "cta_angle": "Side-by-side comparison CTA", "offer_angle": "comparison"},
    "relevance": {"content_angle": "Segment-specific content — address exact use case", "cta_angle": "Quiz or segment-finder CTA", "offer_angle": "relevance-targeted"},
    "proof": {"content_angle": "Data-heavy proof — numbers, screenshots, verifiable results", "cta_angle": "Case study or results-first CTA", "offer_angle": "proof-led"},
    "identity": {"content_angle": "Identity matching — show aspirational users like them", "cta_angle": "Community or identity-aligned CTA", "offer_angle": "identity"},
    "skepticism": {"content_angle": "Transparency content — show behind-the-scenes, limitations", "cta_angle": "No-hype honest assessment CTA", "offer_angle": "transparency"},
}

CHANNEL_MAP = {
    "price": ["content_brief", "offer_angle", "email_followup", "landing_page"],
    "trust": ["content_brief", "cta_generation", "landing_page", "email_followup"],
    "complexity": ["content_brief", "landing_page", "email_followup"],
    "timing": ["email_followup", "cta_generation"],
    "competitor": ["content_brief", "landing_page"],
    "relevance": ["content_brief", "offer_angle"],
    "proof": ["content_brief", "landing_page", "cta_generation"],
    "identity": ["content_brief", "offer_angle"],
    "skepticism": ["content_brief", "cta_generation", "email_followup"],
}


def extract_objections(texts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract objection signals from raw text entries."""
    signals = []
    for entry in texts:
        raw = str(entry.get("text", "")).lower()
        source_type = entry.get("source_type", "comment")
        if len(raw) < 5:
            continue

        detected = _classify_objection(raw)
        if detected:
            severity = _score_severity(raw, detected)
            impact = _score_monetization_impact(detected, entry)
            signals.append({
                "source_type": source_type,
                "source_id": entry.get("source_id"),
                "content_item_id": entry.get("content_item_id"),
                "offer_id": entry.get("offer_id"),
                "objection_type": detected,
                "raw_text": entry.get("text", ""),
                "extracted_objection": _extract_core(raw, detected),
                "severity": severity,
                "monetization_impact": impact,
                "platform": entry.get("platform"),
            })
    return signals


def _classify_objection(text: str) -> str | None:
    scores: dict[str, int] = {}
    for otype, keywords in OBJECTION_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in text)
        if count > 0:
            scores[otype] = count
    if not scores:
        return None
    return max(scores, key=scores.get)


def _extract_core(text: str, otype: str) -> str:
    keywords = OBJECTION_KEYWORDS.get(otype, [])
    for kw in keywords:
        idx = text.find(kw)
        if idx >= 0:
            start = max(0, idx - 30)
            end = min(len(text), idx + len(kw) + 50)
            return text[start:end].strip()
    return text[:100]


def _score_severity(text: str, otype: str) -> float:
    base = 0.5
    strong_markers = ["never", "worst", "terrible", "garbage", "hate", "awful", "scam", "waste"]
    for m in strong_markers:
        if m in text:
            base += 0.15
    if "?" in text:
        base -= 0.1
    return round(max(0.1, min(1.0, base)), 3)


def _score_monetization_impact(otype: str, entry: dict) -> float:
    impact_map = {"price": 0.9, "trust": 0.85, "proof": 0.8, "competitor": 0.75, "skepticism": 0.7, "relevance": 0.6, "complexity": 0.55, "timing": 0.5, "identity": 0.4}
    base = impact_map.get(otype, 0.5)
    if entry.get("offer_id"):
        base = min(1.0, base + 0.1)
    return round(base, 3)


def cluster_objections(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group signals by objection type into clusters."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for s in signals:
        groups[s["objection_type"]].append(s)

    clusters = []
    for otype, members in groups.items():
        avg_sev = sum(m["severity"] for m in members) / max(1, len(members))
        avg_impact = sum(m["monetization_impact"] for m in members) / max(1, len(members))
        reps = [m["extracted_objection"] for m in members[:5]]
        angle = RESPONSE_ANGLES.get(otype, {})

        clusters.append({
            "objection_type": otype,
            "cluster_label": f"{otype} objections ({len(members)} signals)",
            "signal_count": len(members),
            "avg_severity": round(avg_sev, 3),
            "avg_monetization_impact": round(avg_impact, 3),
            "representative_texts": reps,
            "recommended_response_angle": angle.get("content_angle", ""),
        })

    return sorted(clusters, key=lambda c: -c["avg_monetization_impact"])


def generate_responses(clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate response recommendations for each cluster."""
    responses = []
    for c in clusters:
        otype = c["objection_type"]
        angles = RESPONSE_ANGLES.get(otype, {})
        channels = CHANNEL_MAP.get(otype, ["content_brief"])
        priority = "critical" if c["avg_monetization_impact"] > 0.8 else "high" if c["avg_monetization_impact"] > 0.6 else "medium"

        for channel in channels:
            angle_key = "content_angle" if channel == "content_brief" else "cta_angle" if channel == "cta_generation" else "content_angle"
            responses.append({
                "cluster_id": c.get("id"),
                "objection_type": otype,
                "response_type": f"address_{otype}",
                "response_angle": angles.get(angle_key, angles.get("content_angle", "")),
                "target_channel": channel,
                "priority": priority,
                "offer_angle": angles.get("offer_angle", ""),
            })

    return sorted(responses, key=lambda r: {"critical": 0, "high": 1, "medium": 2}.get(r["priority"], 3))


def build_priority_report(clusters: list[dict[str, Any]], total_signals: int) -> dict[str, Any]:
    """Build a priority report from clusters."""
    top = []
    highest_type = None
    highest_impact = 0
    for c in clusters[:5]:
        top.append({"type": c["objection_type"], "count": c["signal_count"], "impact": c["avg_monetization_impact"], "angle": c.get("recommended_response_angle", "")})
        if c["avg_monetization_impact"] > highest_impact:
            highest_impact = c["avg_monetization_impact"]
            highest_type = c["objection_type"]

    return {
        "top_objections": top,
        "total_signals": total_signals,
        "total_clusters": len(clusters),
        "highest_impact_type": highest_type,
        "summary": f"{total_signals} objections across {len(clusters)} types. Highest impact: {highest_type or 'none'}",
    }
