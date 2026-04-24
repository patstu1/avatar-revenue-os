"""Adaptive Calibration Layer — neutralizes artificial ceilings in scoring engines.

The pre-existing scoring engines contain hardcoded thresholds that impose
artificial growth ceilings. This calibration layer provides portfolio-relative
parameters that override those fixed values.

Instead of modifying 18 engine files (high destabilization risk), this layer:
1. Computes dynamic thresholds from actual portfolio data
2. Provides replacement normalization divisors
3. Exposes calibration context that engines can use
4. Ensures no fixed number controls the machine's ambition

USAGE:
    from packages.scoring.adaptive_calibration import get_calibration_context
    ctx = get_calibration_context(accounts, revenue_data, offers)
    # ctx contains dynamic thresholds derived from YOUR portfolio

The calibration context replaces:
- Fixed follower thresholds (500, 1000, 5000, 10000, 25000, 50000)
  → portfolio_max_followers, portfolio_avg_followers, portfolio_median_followers
- Fixed revenue thresholds (100, 500, 1000, 2000, 5000, 10000, 50000)
  → portfolio_total_revenue, portfolio_avg_revenue_per_account, portfolio_max_source_revenue
- Fixed normalization divisors (/1000, /5000, /10000, /50000, /100000)
  → dynamic divisors based on actual portfolio scale
- Fixed price bands (500, 2500, 5000)
  → derived from actual offer payout distribution
"""
from __future__ import annotations

import statistics
from typing import Any


def get_calibration_context(
    accounts: list[dict],
    revenue_by_source: dict[str, float],
    offers: list[dict],
    *,
    total_content: int = 0,
    total_impressions: int = 0,
) -> dict[str, Any]:
    """Compute dynamic calibration parameters from actual portfolio data.

    Every threshold is derived from what the portfolio actually is,
    not from what someone assumed it should be.
    """
    # ── Follower calibration ──
    follower_counts = [a.get("followers", 0) or a.get("follower_count", 0) or 0 for a in accounts]
    follower_counts = [f for f in follower_counts if f > 0] or [0]

    portfolio_max_followers = max(follower_counts) if follower_counts else 1
    portfolio_avg_followers = statistics.mean(follower_counts) if follower_counts else 1
    portfolio_median_followers = statistics.median(follower_counts) if follower_counts else 1
    portfolio_total_followers = sum(follower_counts)

    # Dynamic follower normalization: the machine's reference is its own scale
    follower_norm = max(portfolio_max_followers, 1)  # Replaces /50000, /100000

    # ── Revenue calibration ──
    total_revenue = sum(revenue_by_source.values())
    max_source_revenue = max(revenue_by_source.values()) if revenue_by_source else 0
    avg_source_revenue = total_revenue / max(len(revenue_by_source), 1)

    # Dynamic revenue normalization: replaces /1000, /5000, /10000
    revenue_norm = max(total_revenue, 1)
    source_norm = max(max_source_revenue, 1)

    # Revenue per follower (yield efficiency)
    rev_per_follower = total_revenue / max(portfolio_total_followers, 1)

    # ── Offer calibration ──
    payouts = [o.get("payout", 0) or o.get("payout_amount", 0) or 0 for o in offers]
    payouts = [p for p in payouts if p > 0] or [0]

    max_payout = max(payouts) if payouts else 1
    avg_payout = statistics.mean(payouts) if payouts else 1

    # Dynamic price bands: derived from actual offer distribution
    price_band_low = avg_payout * 0.3
    price_band_mid = avg_payout
    price_band_high = avg_payout * 3
    price_band_premium = max_payout * 2

    # ── Impression calibration ──
    impression_norm = max(total_impressions, 1)

    # ── Content velocity calibration ──
    content_norm = max(total_content, 1)

    # ── Deal value calibration ──
    deal_norm = max(max_payout * 10, total_revenue * 0.5, 1)  # Deals scaled to portfolio

    return {
        # Follower thresholds (replaces 500, 1000, 5000, 10000, 25000, 50000)
        "follower_norm": follower_norm,
        "follower_low": max(1, int(portfolio_avg_followers * 0.1)),   # Replaces 500
        "follower_mid": max(1, int(portfolio_avg_followers * 0.5)),   # Replaces 5000
        "follower_high": max(1, int(portfolio_avg_followers)),         # Replaces 10000
        "follower_top": max(1, int(portfolio_max_followers * 0.8)),    # Replaces 50000
        "portfolio_total_followers": portfolio_total_followers,
        "portfolio_max_followers": portfolio_max_followers,
        "portfolio_avg_followers": portfolio_avg_followers,

        # Revenue thresholds (replaces 100, 500, 1000, 5000, 10000)
        "revenue_norm": revenue_norm,
        "source_norm": source_norm,
        "revenue_low": max(1, total_revenue * 0.01),   # Replaces 100
        "revenue_mid": max(1, total_revenue * 0.1),    # Replaces 1000
        "revenue_high": max(1, total_revenue * 0.3),   # Replaces 5000
        "revenue_top": max(1, total_revenue * 0.5),    # Replaces 10000
        "total_revenue": total_revenue,
        "rev_per_follower": rev_per_follower,

        # Price bands (replaces 500, 2500, 5000)
        "price_band_low": price_band_low,
        "price_band_mid": price_band_mid,
        "price_band_high": price_band_high,
        "price_band_premium": price_band_premium,
        "max_payout": max_payout,
        "avg_payout": avg_payout,

        # Normalization divisors (replaces /1000, /5000, /10000, /50000)
        "impression_norm": impression_norm,
        "content_norm": content_norm,
        "deal_norm": deal_norm,

        # Portfolio scale indicators
        "account_count": len(accounts),
        "offer_count": len(offers),
        "source_count": len(revenue_by_source),
        "has_revenue": total_revenue > 0,
        "has_multiple_sources": len(revenue_by_source) >= 2,
    }


def normalize(value: float, reference: float, floor: float = 0.0, ceiling: float = 1.0) -> float:
    """Normalize a value against a dynamic reference, not a fixed number.

    Usage: normalize(followers, ctx["follower_norm"])
    Instead of: min(1.0, followers / 50000)
    """
    if reference <= 0:
        return floor
    return max(floor, min(ceiling, value / reference))


def relative_threshold(value: float, portfolio_avg: float, multiplier: float = 1.0) -> bool:
    """Check if a value exceeds a portfolio-relative threshold.

    Usage: relative_threshold(followers, ctx["portfolio_avg_followers"], 2.0)
    Instead of: followers > 10000
    """
    return value > (portfolio_avg * multiplier)


def dynamic_price_band(price: float, ctx: dict) -> str:
    """Classify price into bands derived from actual portfolio data.

    Usage: dynamic_price_band(offer.payout, ctx)
    Instead of: "premium" if price > 5000 else "high" if price > 2500 else "mid"
    """
    if price >= ctx.get("price_band_premium", float('inf')):
        return "premium"
    if price >= ctx.get("price_band_high", float('inf')):
        return "high"
    if price >= ctx.get("price_band_mid", float('inf')):
        return "mid"
    return "entry"
