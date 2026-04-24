"""Revenue Forecasting Engine — project future revenue from historical data.

Uses linear regression on trailing revenue-per-post by niche/platform,
projected forward based on planned posting cadence + fleet status.
"""
from __future__ import annotations

from typing import Any


def compute_revenue_per_post(daily_data: list[dict[str, Any]]) -> float:
    """Average revenue per post from daily metrics. Each entry: {posts, revenue}."""
    total_posts = sum(d.get("posts", 0) for d in daily_data)
    total_revenue = sum(d.get("revenue", 0) for d in daily_data)
    if total_posts == 0:
        return 0.0
    return total_revenue / total_posts


def linear_trend(values: list[float]) -> tuple[float, float]:
    """Simple linear regression: returns (slope, intercept)."""
    n = len(values)
    if n < 2:
        return (0.0, values[0] if values else 0.0)
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    den = sum((i - x_mean) ** 2 for i in range(n))
    slope = num / den if den != 0 else 0
    intercept = y_mean - slope * x_mean
    return (slope, intercept)


def forecast_revenue(
    daily_revenue: list[float],
    planned_posts_per_day: int = 10,
    forecast_days: int = 30,
    accounts_active: int = 25,
    accounts_planned: int = 0,
) -> dict[str, Any]:
    """Forecast monthly revenue based on historical data + planned scaling."""
    if not daily_revenue or len(daily_revenue) < 7:
        return {
            "forecast_revenue_30d": 0, "confidence": "low",
            "reason": "Insufficient data (need 7+ days)", "data_days": len(daily_revenue),
        }

    slope, intercept = linear_trend(daily_revenue)
    daily_revenue[-1] if daily_revenue else 0
    trend_daily = intercept + slope * (len(daily_revenue) + forecast_days / 2)

    avg_recent = sum(daily_revenue[-7:]) / 7
    conservative = avg_recent * forecast_days
    trending = max(0, trend_daily * forecast_days)

    expansion_uplift = 0
    if accounts_planned > 0 and accounts_active > 0:
        per_account_daily = avg_recent / max(accounts_active, 1)
        expansion_uplift = per_account_daily * accounts_planned * forecast_days * 0.3

    forecast_low = conservative * 0.8
    forecast_mid = (conservative + trending) / 2 + expansion_uplift
    forecast_high = trending * 1.2 + expansion_uplift

    confidence = "low"
    if len(daily_revenue) >= 30:
        confidence = "high"
    elif len(daily_revenue) >= 14:
        confidence = "medium"

    return {
        "forecast_revenue_30d": round(forecast_mid, 2),
        "forecast_low": round(forecast_low, 2),
        "forecast_high": round(forecast_high, 2),
        "current_daily_avg": round(avg_recent, 2),
        "trend_direction": "up" if slope > 0 else "down" if slope < 0 else "flat",
        "trend_slope_daily": round(slope, 4),
        "expansion_uplift": round(expansion_uplift, 2),
        "confidence": confidence,
        "data_days": len(daily_revenue),
        "accounts_active": accounts_active,
        "accounts_planned": accounts_planned,
    }


def forecast_by_niche(
    niche_data: dict[str, list[float]],
    posts_per_day_by_niche: dict[str, int] | None = None,
) -> dict[str, dict[str, Any]]:
    """Forecast revenue for each niche independently."""
    results = {}
    for niche, daily_rev in niche_data.items():
        ppd = (posts_per_day_by_niche or {}).get(niche, 5)
        results[niche] = forecast_revenue(daily_rev, planned_posts_per_day=ppd)
    return results


def generate_forecast_summary(forecast: dict[str, Any]) -> str:
    """Human-readable forecast summary for operator reports."""
    if forecast["confidence"] == "low":
        return f"Insufficient data for reliable forecast ({forecast['data_days']} days). Need 7+ days of revenue data."

    direction = forecast["trend_direction"]
    arrows = {"up": "trending up", "down": "trending down", "flat": "holding steady"}

    summary = (
        f"30-day revenue forecast: ${forecast['forecast_revenue_30d']:,.0f} "
        f"(range: ${forecast['forecast_low']:,.0f} - ${forecast['forecast_high']:,.0f}). "
        f"Revenue is {arrows.get(direction, 'stable')} at ${forecast['current_daily_avg']:,.2f}/day. "
        f"Confidence: {forecast['confidence']}."
    )
    if forecast["expansion_uplift"] > 0:
        summary += f" Expansion uplift: +${forecast['expansion_uplift']:,.0f} from {forecast['accounts_planned']} planned accounts."
    return summary
