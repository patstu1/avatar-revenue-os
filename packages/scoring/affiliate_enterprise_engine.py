"""Enterprise Affiliate Engine — governance, merchant/network ranking, owned program. Pure functions."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

GOVERNANCE_RULE_TYPES = ["required_disclosure", "banned_merchant", "banned_category", "max_commission_rate", "approval_required", "platform_disclosure"]


def evaluate_governance(offer: dict[str, Any], rules: list[dict[str, Any]], banned: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Check an offer against governance rules and banned lists."""
    violations = []
    merchant = offer.get("merchant_name", "").lower()
    category = offer.get("product_category", "").lower()

    for b in banned:
        if b.get("entity_type") == "merchant" and b.get("entity_name", "").lower() == merchant:
            violations.append({"violation_type": "banned_merchant", "severity": "hard", "detail": f"Merchant '{merchant}' is banned: {b.get('reason', '')}"})
        if b.get("entity_type") == "category" and b.get("entity_name", "").lower() == category:
            violations.append({"violation_type": "banned_category", "severity": "hard", "detail": f"Category '{category}' is banned: {b.get('reason', '')}"})

    for r in rules:
        rt = r.get("rule_type", "")
        if rt == "max_commission_rate":
            max_rate = float(r.get("rule_value", {}).get("max", 100))
            if float(offer.get("commission_rate", 0)) > max_rate:
                violations.append({"violation_type": "commission_too_high", "severity": "soft", "detail": f"Commission {offer.get('commission_rate')}% exceeds max {max_rate}%"})
        if rt == "approval_required" and not offer.get("approved"):
            violations.append({"violation_type": "approval_required", "severity": "hard", "detail": "Offer requires approval before activation"})

    return violations


def flag_risk(offer: dict[str, Any]) -> list[dict[str, Any]]:
    """Flag risky offers."""
    flags = []
    trust = float(offer.get("trust_score", 0.5) or 0.5)
    refund = float(offer.get("refund_rate", 0) or 0)
    epc = float(offer.get("epc", 0) or 0)

    if trust < 0.3:
        flags.append({"risk_type": "low_trust", "risk_score": 1.0 - trust, "detail": f"Trust score {trust:.2f} is below threshold"})
    if refund > 0.15:
        flags.append({"risk_type": "high_refund", "risk_score": min(1.0, refund * 3), "detail": f"Refund rate {refund:.0%} is high"})
    if epc == 0:
        flags.append({"risk_type": "no_epc_data", "risk_score": 0.5, "detail": "No EPC data — offer not validated"})
    return flags


def rank_merchants(merchants: list[dict[str, Any]], offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank merchants by aggregate offer performance."""
    merchant_offers: dict[str, list] = defaultdict(list)
    for o in offers:
        mid = str(o.get("merchant_id", ""))
        if mid:
            merchant_offers[mid].append(o)

    ranked = []
    for m in merchants:
        mid = str(m.get("id", ""))
        m_offers = merchant_offers.get(mid, [])
        avg_epc = sum(float(o.get("epc", 0)) for o in m_offers) / max(1, len(m_offers))
        avg_trust = sum(float(o.get("trust_score", 0.5)) for o in m_offers) / max(1, len(m_offers))
        score = round(0.5 * min(1, avg_epc / 3) + 0.3 * avg_trust + 0.2 * min(1, len(m_offers) / 5), 3)
        ranked.append({**m, "merchant_rank_score": score, "offer_count": len(m_offers), "avg_epc": round(avg_epc, 2)})

    return sorted(ranked, key=lambda x: -x["merchant_rank_score"])


def rank_networks(networks: list[dict[str, Any]], offers: list[dict[str, Any]], merchants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank networks by merchant quality and offer volume."""
    net_merchants: dict[str, int] = defaultdict(int)
    net_offers: dict[str, int] = defaultdict(int)
    for m in merchants:
        nid = str(m.get("network_id", ""))
        if nid:
            net_merchants[nid] += 1
    for o in offers:
        nid = str(o.get("network_id", ""))
        if nid:
            net_offers[nid] += 1

    ranked = []
    for n in networks:
        nid = str(n.get("id", ""))
        mc = net_merchants.get(nid, 0)
        oc = net_offers.get(nid, 0)
        score = round(min(1.0, mc * 0.1 + oc * 0.05), 3)
        ranked.append({**n, "network_rank_score": score, "merchant_count": mc, "offer_count": oc})
    return sorted(ranked, key=lambda x: -x["network_rank_score"])


def score_partner(partner: dict[str, Any]) -> dict[str, Any]:
    """Score an owned affiliate partner."""
    conversions = int(partner.get("total_conversions", 0) or 0)
    quality = float(partner.get("conversion_quality", 0) or 0)
    fraud = float(partner.get("fraud_risk", 0) or 0)
    revenue = float(partner.get("total_revenue_generated", 0) or 0)

    score = round(0.3 * min(1, conversions / 50) + 0.3 * quality + 0.2 * (1 - fraud) + 0.2 * min(1, revenue / 1000), 3)

    status = "active" if score > 0.5 and fraud < 0.3 else "warning" if score > 0.3 else "suppressed"
    return {"partner_score": score, "recommended_status": status, "fraud_risk": fraud}


def detect_partner_fraud(conversions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect potential fraud in partner conversions."""
    flags = []
    if not conversions:
        return flags

    total = len(conversions)
    low_quality = sum(1 for c in conversions if float(c.get("quality_score", 0.5)) < 0.2)
    if total > 5 and low_quality / total > 0.5:
        flags.append({"fraud_type": "low_quality_ratio", "detail": f"{low_quality}/{total} conversions below quality threshold"})

    flagged = sum(1 for c in conversions if c.get("fraud_flag"))
    if flagged > 0:
        flags.append({"fraud_type": "flagged_conversions", "detail": f"{flagged} conversions flagged for fraud"})

    return flags
