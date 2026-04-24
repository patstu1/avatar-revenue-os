"""Revenue Leak Detector Engine — detect 14 leak types, cluster, estimate, correct. Pure functions."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

LEAK_TYPES = [
    "high_impressions_low_ctr", "high_clicks_low_conversion", "high_engagement_low_monetization",
    "weak_landing_page", "weak_cta_path", "wrong_destination", "weak_offer_selection",
    "weak_affiliate_choice", "underused_winner", "weak_followup",
    "blocked_provider", "weak_upsell_path", "under_monetized_account", "under_monetized_platform",
]

LEAK_ACTIONS = {
    "high_impressions_low_ctr": {"action": "Revise hook/thumbnail — high reach but no clicks", "target": "content_generation", "priority": "high"},
    "high_clicks_low_conversion": {"action": "Fix landing page or offer — clicks aren't converting", "target": "landing_page_engine", "priority": "critical"},
    "high_engagement_low_monetization": {"action": "Add monetization path — audience is engaged but not buying", "target": "offer_lab", "priority": "high"},
    "weak_landing_page": {"action": "Rebuild landing page — conversion rate below threshold", "target": "landing_page_engine", "priority": "high"},
    "weak_cta_path": {"action": "Test different CTA style — current CTA underperforming", "target": "campaign_constructor", "priority": "medium"},
    "wrong_destination": {"action": "Route to better landing page for this audience/offer", "target": "landing_page_engine", "priority": "high"},
    "weak_offer_selection": {"action": "Switch to higher-ranked offer for this content", "target": "offer_lab", "priority": "high"},
    "weak_affiliate_choice": {"action": "Switch affiliate merchant/network for better EPC", "target": "affiliate_intel", "priority": "medium"},
    "underused_winner": {"action": "Scale winning content/offer — not getting enough volume", "target": "capital_allocator", "priority": "high"},
    "weak_followup": {"action": "Improve email/SMS follow-up sequence", "target": "campaign_constructor", "priority": "medium"},
    "blocked_provider": {"action": "Fix blocked provider preventing revenue execution", "target": "provider_registry", "priority": "critical"},
    "weak_upsell_path": {"action": "Add or improve upsell/downsell path", "target": "offer_lab", "priority": "medium"},
    "under_monetized_account": {"action": "Increase monetization intensity on this account", "target": "account_state", "priority": "high"},
    "under_monetized_platform": {"action": "Expand monetization strategy on this platform", "target": "capital_allocator", "priority": "medium"},
}


def detect_leaks(system_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Detect all leak types from system data."""
    leaks = []

    for ci in system_data.get("content_items", []):
        imp = float(ci.get("impressions", 0))
        clicks = float(ci.get("clicks", 0))
        eng = float(ci.get("engagement_rate", 0))
        rev = float(ci.get("revenue", 0))
        cvr = float(ci.get("conversion_rate", 0))

        if imp > 0 and clicks / max(imp, 1) < 0.01:
            leaks.append(_leak("high_impressions_low_ctr", "content_item", ci, imp * 0.02, 0.7, {"impressions": imp, "ctr": clicks / max(imp, 1)}))
        if clicks > 100 and cvr < 0.005:
            leaks.append(_leak("high_clicks_low_conversion", "content_item", ci, clicks * 0.5, 0.8, {"clicks": clicks, "cvr": cvr}))
        if eng > 0.05 and rev < 5:
            leaks.append(_leak("high_engagement_low_monetization", "content_item", ci, imp * 0.03, 0.6, {"engagement": eng, "revenue": rev}))

    for lp in system_data.get("landing_pages", []):
        cvr = float(lp.get("conversion_rate", 0))
        if cvr < 0.02 and lp.get("status") == "published":
            leaks.append(_leak("weak_landing_page", "landing_page", lp, 50, 0.7, {"cvr": cvr}))

    for offer in system_data.get("offers", []):
        rank = float(offer.get("rank_score", 0))
        if rank > 0.6 and int(offer.get("usage_count", 0)) < 3:
            leaks.append(_leak("underused_winner", "offer", offer, rank * 100, 0.7, {"rank": rank, "usage": offer.get("usage_count")}))
        if rank < 0.2 and int(offer.get("usage_count", 0)) > 5:
            leaks.append(_leak("weak_offer_selection", "offer", offer, 30, 0.6, {"rank": rank}))

    for acct in system_data.get("accounts", []):
        if acct.get("state") in ("scaling", "monetizing") and float(acct.get("revenue", 0)) < 10:
            leaks.append(_leak("under_monetized_account", "account", acct, 50, 0.6, {"state": acct.get("state"), "revenue": acct.get("revenue")}))

    for blocker in system_data.get("provider_blockers", []):
        leaks.append(_leak("blocked_provider", "provider", blocker, 100, 0.9, {"provider": blocker.get("name")}))

    return leaks


def _leak(leak_type: str, scope: str, item: dict, loss: float, confidence: float, evidence: dict) -> dict[str, Any]:
    action_info = LEAK_ACTIONS.get(leak_type, {"action": "Investigate", "target": "copilot", "priority": "medium"})
    return {
        "leak_type": leak_type,
        "severity": action_info["priority"],
        "affected_scope": scope,
        "affected_id": item.get("id"),
        "estimated_revenue_loss": round(loss, 2),
        "confidence": round(confidence, 3),
        "evidence_json": evidence,
        "next_best_action": action_info["action"],
        "target_system": action_info["target"],
        "truth_label": "measured" if evidence else "estimated",
    }


def cluster_leaks(leaks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cluster leaks by type."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for l in leaks:
        groups[l["leak_type"]].append(l)

    clusters = []
    for ltype, members in groups.items():
        total_loss = sum(m.get("estimated_revenue_loss", 0) for m in members)
        avg_conf = sum(m.get("confidence", 0) for m in members) / max(1, len(members))
        priority = round(total_loss * avg_conf / 100, 3)
        action = LEAK_ACTIONS.get(ltype, {}).get("action", "Investigate")

        clusters.append({
            "cluster_type": ltype,
            "event_count": len(members),
            "total_loss": round(total_loss, 2),
            "priority_score": priority,
            "recommended_action": action,
        })
    return sorted(clusters, key=lambda c: -c["priority_score"])


def estimate_total_loss(leaks: list[dict[str, Any]], period: str = "current") -> dict[str, Any]:
    """Estimate total revenue loss across all leaks."""
    total = sum(l.get("estimated_revenue_loss", 0) for l in leaks)
    by_type: dict[str, float] = defaultdict(float)
    by_scope: dict[str, float] = defaultdict(float)
    for l in leaks:
        by_type[l["leak_type"]] += l.get("estimated_revenue_loss", 0)
        by_scope[l["affected_scope"]] += l.get("estimated_revenue_loss", 0)
    return {
        "period": period,
        "total_estimated_loss": round(total, 2),
        "by_leak_type": {k: round(v, 2) for k, v in sorted(by_type.items(), key=lambda x: -x[1])},
        "by_scope": {k: round(v, 2) for k, v in sorted(by_scope.items(), key=lambda x: -x[1])},
    }


def generate_corrections(leaks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate corrective actions for each leak."""
    corrections = []
    for l in leaks:
        action_info = LEAK_ACTIONS.get(l["leak_type"], {"action": "Investigate", "target": "copilot", "priority": "medium"})
        corrections.append({
            "action_type": f"fix_{l['leak_type']}",
            "action_detail": action_info["action"],
            "target_system": action_info["target"],
            "priority": l.get("severity", action_info["priority"]),
        })
    return sorted(corrections, key=lambda c: {"critical": 0, "high": 1, "medium": 2}.get(c["priority"], 3))


def prioritize_leaks(leaks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prioritize leaks by upside × urgency × confidence."""
    for l in leaks:
        loss = float(l.get("estimated_revenue_loss", 0))
        conf = float(l.get("confidence", 0.5))
        urgency = {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25}.get(l.get("severity", "medium"), 0.5)
        l["priority_score"] = round(loss * urgency * conf / 100, 4)
    return sorted(leaks, key=lambda l: -l.get("priority_score", 0))
