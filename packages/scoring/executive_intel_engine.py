"""Executive Intelligence Engine — KPIs, forecasts, costs, uptime, oversight. Pure functions."""
from __future__ import annotations

from typing import Any

FORECAST_TYPES = ["revenue", "profit", "content_volume", "conversion_rate", "cost"]
OVERSIGHT_MODES = ["full_auto", "hybrid", "human_primary", "human_only"]
RELIABILITY_GRADES = {"A": (99.0, 100), "B": (95.0, 99.0), "C": (90.0, 95.0), "D": (80.0, 90.0), "F": (0, 80.0)}


def rollup_kpis(revenue_data: dict, content_data: dict, performance_data: dict, account_data: dict, campaign_data: dict) -> dict[str, Any]:
    """Roll up all KPIs into a single report."""
    return {
        "total_revenue": round(float(revenue_data.get("total_revenue", 0)), 2),
        "total_profit": round(float(revenue_data.get("total_profit", 0)), 2),
        "total_spend": round(float(revenue_data.get("total_spend", 0)), 2),
        "content_produced": int(content_data.get("produced", 0)),
        "content_published": int(content_data.get("published", 0)),
        "total_impressions": float(performance_data.get("total_impressions", 0)),
        "avg_engagement_rate": round(float(performance_data.get("avg_engagement_rate", 0)), 4),
        "avg_conversion_rate": round(float(performance_data.get("avg_conversion_rate", 0)), 4),
        "active_accounts": int(account_data.get("active_count", 0)),
        "active_campaigns": int(campaign_data.get("active_count", 0)),
    }


def forecast_metric(historical_values: list[float], periods_ahead: int = 1) -> dict[str, Any]:
    """Simple trend-based forecast from historical values."""
    if len(historical_values) < 2:
        return {"predicted_value": historical_values[-1] if historical_values else 0, "confidence": 0.2, "risk_factors": ["insufficient_history"], "opportunity_factors": []}

    trend = (historical_values[-1] - historical_values[-2]) / max(abs(historical_values[-2]), 0.01)
    last = historical_values[-1]
    predicted = round(last * (1 + trend * periods_ahead), 2)

    n = len(historical_values)
    stability = 1.0 - min(1.0, sum(abs(historical_values[i] - historical_values[i-1]) for i in range(1, n)) / max(1, n * max(abs(last), 1)))
    confidence = round(min(0.95, 0.3 + stability * 0.4 + min(0.25, n * 0.05)), 3)

    risks = []
    opps = []
    if trend < -0.1:
        risks.append(f"Declining trend ({trend:.1%})")
    if trend > 0.1:
        opps.append(f"Growth trend ({trend:.1%})")
    if n < 5:
        risks.append("Small sample size")

    return {"predicted_value": predicted, "confidence": confidence, "risk_factors": risks, "opportunity_factors": opps, "trend": round(trend, 4)}


def compute_usage_cost(tasks_by_provider: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    """Compute usage cost breakdown by provider."""
    results = []
    for provider, data in tasks_by_provider.items():
        tasks = int(data.get("tasks", 0))
        cost = float(data.get("cost", 0))
        hero_cost = float(data.get("hero_cost", 0))
        bulk_cost = float(data.get("bulk_cost", 0))
        results.append({
            "provider_key": provider,
            "tasks_executed": tasks,
            "cost_incurred": round(cost, 2),
            "cost_by_tier": {"hero": round(hero_cost, 2), "bulk": round(bulk_cost, 2)},
        })
    return sorted(results, key=lambda r: -r["cost_incurred"])


def compute_uptime(provider_key: str, total_requests: int, failed_requests: int, avg_latency_ms: float) -> dict[str, Any]:
    """Compute provider uptime and reliability grade."""
    if total_requests == 0:
        return {"provider_key": provider_key, "uptime_pct": 100.0, "reliability_grade": "A", "total_requests": 0, "failed_requests": 0, "avg_latency_ms": 0}
    uptime = round((1 - failed_requests / total_requests) * 100, 2)
    grade = "F"
    for g, (lo, hi) in RELIABILITY_GRADES.items():
        if lo <= uptime <= hi:
            grade = g
            break
    return {"provider_key": provider_key, "uptime_pct": uptime, "reliability_grade": grade, "total_requests": total_requests, "failed_requests": failed_requests, "avg_latency_ms": round(avg_latency_ms, 1)}


def evaluate_oversight(auto_count: int, human_count: int, override_count: int) -> dict[str, Any]:
    """Evaluate oversight mode and recommend adjustments."""
    total = auto_count + human_count
    if total == 0:
        return {"mode": "hybrid", "ai_accuracy_estimate": 0, "recommendation": "No actions to evaluate"}
    auto_pct = auto_count / total
    override_rate = override_count / max(total, 1)
    accuracy = round(1.0 - override_rate, 3)

    if accuracy > 0.95 and auto_pct > 0.7:
        mode = "full_auto"
        rec = "AI accuracy high — safe for full automation"
    elif accuracy > 0.85:
        mode = "hybrid"
        rec = "Hybrid mode recommended — AI handles routine, human reviews edge cases"
    elif accuracy > 0.70:
        mode = "human_primary"
        rec = "Override rate elevated — increase human review"
    else:
        mode = "human_only"
        rec = "AI accuracy too low — switch to human-only until quality improves"

    return {"mode": mode, "auto_approved_count": auto_count, "human_reviewed_count": human_count, "override_count": override_count, "ai_accuracy_estimate": accuracy, "recommendation": rec}


def generate_executive_alerts(kpis: dict, forecasts: list[dict], uptime: list[dict], oversight: dict) -> list[dict[str, Any]]:
    """Generate executive-level alerts from aggregated intelligence."""
    alerts = []
    if kpis.get("total_revenue", 0) == 0:
        alerts.append({"alert_type": "zero_revenue", "severity": "critical", "title": "No revenue recorded", "detail": "Total revenue is $0 — check revenue tracking and offer activity", "recommended_action": "Verify affiliate/revenue integrations"})

    for f in forecasts:
        if f.get("trend", 0) < -0.15:
            alerts.append({"alert_type": "declining_forecast", "severity": "high", "title": f"Declining {f.get('forecast_type', '')} forecast", "detail": f"Trend is {f.get('trend', 0):.1%} with confidence {f.get('confidence', 0):.0%}", "recommended_action": "Investigate root cause and adjust strategy"})

    for u in uptime:
        if u.get("reliability_grade") in ("D", "F"):
            alerts.append({"alert_type": "provider_reliability", "severity": "high", "title": f"Provider {u['provider_key']} reliability grade {u['reliability_grade']}", "detail": f"Uptime {u['uptime_pct']:.1f}%, {u['failed_requests']} failures", "recommended_action": "Switch to backup provider or investigate failures"})

    if oversight.get("ai_accuracy_estimate", 1) < 0.75:
        alerts.append({"alert_type": "ai_accuracy_low", "severity": "high", "title": "AI accuracy below threshold", "detail": f"Accuracy estimate {oversight.get('ai_accuracy_estimate', 0):.0%}", "recommended_action": oversight.get("recommendation", "Increase human review")})

    return sorted(alerts, key=lambda a: {"critical": 0, "high": 1, "medium": 2}.get(a["severity"], 3))
