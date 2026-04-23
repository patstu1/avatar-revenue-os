"""Integrations + Listening Engine — cluster, extract, route, recommend. Pure functions."""
from __future__ import annotations
from typing import Any
from collections import defaultdict

SIGNAL_TYPES = ["brand_mention", "competitor_mention", "objection_cluster", "demand_signal", "trend_signal", "sales_signal", "support_pain"]
CONNECTOR_TYPES = ["crm", "erp", "internal_db", "social_listening", "analytics", "support_desk", "email_marketing", "custom_api"]
RESPONSE_TARGETS = ["content_generation", "objection_mining", "offer_lab", "campaign_constructor", "executive_dashboard", "copilot"]


def evaluate_connector_sync(connector: dict[str, Any], last_sync: dict[str, Any] = None) -> dict[str, Any]:
    """Evaluate a connector's health and sync readiness."""
    status = connector.get("status", "configured")
    has_creds = bool(connector.get("credential_env_key"))
    has_endpoint = bool(connector.get("endpoint_url"))

    if not has_endpoint:
        return {"healthy": False, "reason": "No endpoint configured", "blocker": "no_endpoint"}
    if not has_creds:
        return {"healthy": False, "reason": "No credentials configured", "blocker": "no_credentials"}
    if last_sync and last_sync.get("sync_status") == "failed":
        return {"healthy": False, "reason": f"Last sync failed: {last_sync.get('detail', '')}", "blocker": "sync_failed"}
    return {"healthy": True, "reason": "Connector ready"}


def cluster_listening_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cluster listening signals by type."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for s in signals:
        groups[s.get("signal_type", "unknown")].append(s)

    clusters = []
    for stype, members in groups.items():
        avg_sent = sum(m.get("sentiment", 0) for m in members) / max(1, len(members))
        avg_rel = sum(m.get("relevance_score", 0.5) for m in members) / max(1, len(members))
        reps = [m.get("raw_text", "")[:100] for m in members[:5]]

        action = _recommend_action(stype, avg_sent, len(members))
        clusters.append({
            "cluster_type": stype,
            "cluster_label": f"{stype} ({len(members)} signals)",
            "signal_count": len(members),
            "avg_sentiment": round(avg_sent, 3),
            "avg_relevance": round(avg_rel, 3),
            "representative_texts": reps,
            "recommended_action": action,
        })
    return sorted(clusters, key=lambda c: -c["signal_count"])


def extract_competitor_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract and score competitor signals."""
    scored = []
    for s in signals:
        sentiment = float(s.get("sentiment", 0) or 0)
        opp_score = max(0, 1.0 - sentiment) if sentiment < 0 else 0.3
        if any(kw in s.get("raw_text", "").lower() for kw in ("switching", "leaving", "disappointed", "looking for alternative")):
            opp_score = min(1.0, opp_score + 0.4)
        scored.append({**s, "opportunity_score": round(opp_score, 3)})
    return sorted(scored, key=lambda x: -x["opportunity_score"])


def route_business_signal(signal: dict[str, Any]) -> list[dict[str, Any]]:
    """Route an internal business signal to appropriate downstream systems."""
    stype = signal.get("signal_type", "")
    routes = []
    routing_map = {
        "demand_signal": [("content_generation", "Create content addressing demand"), ("campaign_constructor", "Build campaign around demand")],
        "sales_signal": [("offer_lab", "Evaluate offer fit for sales signal"), ("content_generation", "Create sales-enablement content")],
        "support_pain": [("objection_mining", "Feed support pain into objection clusters"), ("content_generation", "Create FAQ/support content")],
        "trend_signal": [("content_generation", "Create trend-responsive content"), ("campaign_constructor", "Build trend campaign")],
        "brand_mention": [("copilot", "Surface brand mention for operator"), ("content_generation", "Consider response content")],
    }
    for target, action in routing_map.get(stype, [("copilot", "Review signal")]):
        routes.append({"target_system": target, "response_action": action, "response_type": f"route_{stype}", "priority": signal.get("priority", "medium")})
    return routes


def generate_response_recommendations(clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate response recommendations from clusters."""
    recs = []
    for c in clusters:
        routes = route_business_signal({"signal_type": c["cluster_type"], "priority": "high" if c["signal_count"] > 5 else "medium"})
        for r in routes:
            recs.append({**r, "cluster_id": c.get("id"), "cluster_type": c["cluster_type"]})
    return sorted(recs, key=lambda r: {"critical": 0, "high": 1, "medium": 2}.get(r.get("priority", "medium"), 3))


def _recommend_action(stype: str, sentiment: float, count: int) -> str:
    if stype == "objection_cluster":
        return "Feed into objection mining and create objection-handling content"
    if stype == "demand_signal":
        return "Create content and campaigns addressing this demand"
    if stype == "competitor_mention" and sentiment < -0.2:
        return "Competitive content opportunity — address competitor weakness"
    if stype == "support_pain":
        return "Create FAQ/support content and improve offer positioning"
    if stype == "trend_signal":
        return "Create trend-responsive content quickly"
    if count > 10:
        return f"High-volume signal ({count}) — prioritize response"
    return "Monitor and evaluate for content opportunity"
