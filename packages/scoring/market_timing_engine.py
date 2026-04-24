"""Market timing engine — recession resilience, sponsor cycles, seasonal buying,
holiday monetization, election volatility, algorithm shifts, CPM windows,
low-competition launches (pure functions, no I/O, no SQLAlchemy)."""
from __future__ import annotations

from typing import Any

MARKET_TIMING = "market_timing_engine"

# ---------------------------------------------------------------------------
# Category definitions
# ---------------------------------------------------------------------------

_CATEGORIES: list[str] = [
    "recession_resistant",
    "sponsor_friendly_cycle",
    "seasonal_buying",
    "holiday_monetization",
    "election_volatility",
    "platform_algorithm_shift",
    "cpm_friendly",
    "low_competition_launch",
]

# Niches with inherent recession resilience
_RECESSION_RESISTANT_NICHES: set[str] = {
    "finance", "personal finance", "budgeting", "frugal", "health", "wellness",
    "fitness", "education", "self improvement", "mental health", "cooking",
    "food", "nutrition", "diy", "repair", "career", "job search",
}

# Niches that attract premium sponsor cycles (Q4, Q1)
_SPONSOR_FRIENDLY_NICHES: set[str] = {
    "tech", "technology", "software", "saas", "finance", "fintech",
    "ecommerce", "business", "marketing", "beauty", "fashion",
}

# Holiday-month mapping (1-indexed months)
_HOLIDAY_MONTHS: dict[int, str] = {
    1: "New Year / resolution season",
    2: "Valentine's Day",
    3: "Spring launch window",
    5: "Mother's Day / Memorial Day",
    6: "Father's Day / mid-year reviews",
    7: "Prime Day / summer sales",
    9: "Back to school / fall launch",
    10: "Halloween / pre-holiday prep",
    11: "Black Friday / Cyber Monday",
    12: "Holiday gifting / year-end",
}

# Seasonal buying peaks by niche keyword
_SEASONAL_NICHE_PEAKS: dict[str, list[int]] = {
    "fitness": [1, 6, 9],
    "health": [1, 6, 9],
    "wellness": [1, 6],
    "finance": [1, 4, 10],
    "personal finance": [1, 4],
    "tech": [1, 6, 9, 11],
    "technology": [1, 6, 9, 11],
    "ecommerce": [3, 7, 11, 12],
    "beauty": [2, 5, 11, 12],
    "fashion": [3, 9, 11],
    "education": [1, 8, 9],
    "gaming": [6, 11, 12],
    "travel": [3, 6, 12],
    "food": [5, 11, 12],
    "cooking": [5, 11, 12],
}

# CPM-friendly months (lower advertiser competition = cheaper paid promotion)
_CPM_FRIENDLY_MONTHS: set[int] = {1, 2, 3, 6, 7, 8}

# Low-competition launch months (audience attention available, fewer launches)
_LOW_COMPETITION_MONTHS: set[int] = {1, 2, 6, 7, 8}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _niche_tokens(niche: str) -> list[str]:
    return [w.strip() for w in niche.lower().replace("-", " ").replace("_", " ").split() if w.strip()]


def _macro_signal_value(macro_signals: list[dict], signal_type: str) -> float | None:
    for sig in macro_signals:
        if sig.get("signal_type") == signal_type:
            return float(sig.get("value", 0))
    return None


def _macro_signal_present(macro_signals: list[dict], signal_type: str) -> bool:
    return any(sig.get("signal_type") == signal_type for sig in macro_signals)


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

def evaluate_market_timing(
    brand_context: dict,
    macro_signals: list[dict],
) -> list[dict[str, Any]]:
    """Evaluate market timing across 8 categories for the brand.

    Parameters
    ----------
    brand_context:
        Dict with keys: niche (str), month (int 1-12), audience_size (int),
        avg_monthly_revenue (float), content_types (list[str]),
        active_offer_count (int), platform (str, optional).
    macro_signals:
        List of dicts: {signal_type, value (float), source, detail (str, optional)}.
        Known signal_types: recession_indicator, cpi_trend, ad_spend_trend,
        election_cycle, platform_update, cpm_index, competitor_launch_count.

    Returns
    -------
    list[dict] — one entry per applicable category: market_category, timing_score,
    active_window, recommendation, expected_uplift, confidence, explanation,
    MARKET_TIMING marker.
    """
    niche = str(brand_context.get("niche", "")).lower().strip()
    niche_parts = _niche_tokens(niche)
    month = int(brand_context.get("month", 1))
    audience_size = int(brand_context.get("audience_size", 0))
    float(brand_context.get("avg_monthly_revenue", 0))
    offer_count = int(brand_context.get("active_offer_count", 0))

    results: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ 1. recession_resistant
    niche_match = any(tok in _RECESSION_RESISTANT_NICHES for tok in niche_parts) or niche in _RECESSION_RESISTANT_NICHES
    recession_val = _macro_signal_value(macro_signals, "recession_indicator")
    if niche_match or (recession_val is not None and recession_val > 0.5):
        base = 0.55 if niche_match else 0.30
        if recession_val is not None:
            base += _clamp(recession_val * 0.30)
        score = round(_clamp(base), 3)
        results.append(_entry(
            "recession_resistant", score,
            "Evergreen — resilient regardless of macro cycle",
            f"Lean into value-first messaging; audience seeks practical {niche} content during downturns",
            round(score * 0.12, 4),
            _confidence(score, audience_size, offer_count),
            f"Niche '{niche}' shows recession resilience (score {score:.2f}). "
            f"Demand for practical, money-saving, or essential {niche} content rises during contraction.",
        ))

    # ------------------------------------------------------------------ 2. sponsor_friendly_cycle
    sponsor_niche = any(tok in _SPONSOR_FRIENDLY_NICHES for tok in niche_parts) or niche in _SPONSOR_FRIENDLY_NICHES
    ad_spend = _macro_signal_value(macro_signals, "ad_spend_trend")
    if sponsor_niche or (ad_spend is not None and ad_spend > 0.6):
        base = 0.50 if sponsor_niche else 0.30
        if month in (10, 11, 12, 1):
            base += 0.20
        if ad_spend is not None:
            base += _clamp(ad_spend * 0.20)
        score = round(_clamp(base), 3)
        window = "Q4–Q1 sponsor budget flush" if month in (10, 11, 12, 1) else "Steady sponsor cycle"
        results.append(_entry(
            "sponsor_friendly_cycle", score,
            window,
            f"Pitch sponsors now — {niche} niche aligns with active ad-spend windows",
            round(score * 0.18, 4),
            _confidence(score, audience_size, offer_count),
            f"Sponsor-friendly cycle score {score:.2f}. "
            f"{'Q4-Q1 budget flush active. ' if month in (10, 11, 12, 1) else ''}"
            f"Ad spend trend: {ad_spend if ad_spend is not None else 'unknown'}.",
        ))

    # ------------------------------------------------------------------ 3. seasonal_buying
    peak_months: list[int] = []
    for tok in niche_parts:
        peak_months.extend(_SEASONAL_NICHE_PEAKS.get(tok, []))
    if niche in _SEASONAL_NICHE_PEAKS:
        peak_months.extend(_SEASONAL_NICHE_PEAKS[niche])
    peak_months = list(set(peak_months))

    if month in peak_months:
        score = round(_clamp(0.65 + 0.10 * (len(peak_months) / 12.0)), 3)
        results.append(_entry(
            "seasonal_buying", score,
            f"Month {month} is a peak buying month for {niche}",
            f"Accelerate offer launches and promotions — seasonal demand is elevated for {niche}",
            round(score * 0.15, 4),
            _confidence(score, audience_size, offer_count),
            f"Month {month} hits a seasonal buying peak for '{niche}' (score {score:.2f}). "
            f"Peak months identified: {sorted(peak_months)}.",
        ))
    elif peak_months:
        next_peak = min((m for m in peak_months if m > month), default=min(peak_months))
        months_away = (next_peak - month) % 12
        score = round(_clamp(0.25 + 0.05 * max(0, 3 - months_away)), 3)
        results.append(_entry(
            "seasonal_buying", score,
            f"Next peak in ~{months_away} month(s) (month {next_peak})",
            f"Prepare content and offers now for the upcoming {niche} seasonal window",
            round(score * 0.08, 4),
            _confidence(score, audience_size, offer_count),
            f"Not currently in a seasonal peak (score {score:.2f}). "
            f"Next peak month {next_peak} is ~{months_away} month(s) away.",
        ))

    # ------------------------------------------------------------------ 4. holiday_monetization
    if month in _HOLIDAY_MONTHS:
        holiday = _HOLIDAY_MONTHS[month]
        score = round(_clamp(0.60 + (0.15 if month in (11, 12) else 0.0)), 3)
        results.append(_entry(
            "holiday_monetization", score,
            f"{holiday} (month {month})",
            f"Activate holiday-themed offers, bundles, and urgency CTAs tied to {holiday}",
            round(score * 0.20, 4),
            _confidence(score, audience_size, offer_count),
            f"Holiday window active: {holiday} (score {score:.2f}). "
            f"{'Peak gifting / BFCM season — maximum urgency.' if month in (11, 12) else 'Standard holiday monetization window.'}",
        ))

    # ------------------------------------------------------------------ 5. election_volatility
    election_sig = _macro_signal_present(macro_signals, "election_cycle")
    election_val = _macro_signal_value(macro_signals, "election_cycle")
    if election_sig:
        vol = election_val if election_val is not None else 0.5
        score = round(_clamp(0.30 + vol * 0.50), 3)
        results.append(_entry(
            "election_volatility", score,
            "Election cycle — ad costs spike, audience attention fragments",
            "Avoid major paid-spend launches during peak election ad windows; shift to organic and owned channels",
            round(score * -0.08, 4),
            _confidence(score, audience_size, offer_count),
            f"Election volatility detected (score {score:.2f}). "
            f"CPM inflation and audience distraction reduce paid promotion ROI. "
            f"Shift budget toward organic content and email/SMS.",
        ))

    # ------------------------------------------------------------------ 6. platform_algorithm_shift
    algo_sig = _macro_signal_present(macro_signals, "platform_update")
    if algo_sig:
        algo_val = _macro_signal_value(macro_signals, "platform_update") or 0.5
        score = round(_clamp(0.40 + algo_val * 0.40), 3)
        results.append(_entry(
            "platform_algorithm_shift", score,
            "Active algorithm change — early adopters rewarded",
            "Lean into the new format or feature the platform is pushing; first-mover advantage is real",
            round(score * 0.14, 4),
            _confidence(score, audience_size, offer_count),
            f"Platform algorithm shift detected (score {score:.2f}). "
            f"Brands that adapt quickly to algorithm changes capture outsized reach.",
        ))

    # ------------------------------------------------------------------ 7. cpm_friendly
    cpm_val = _macro_signal_value(macro_signals, "cpm_index")
    is_cheap_month = month in _CPM_FRIENDLY_MONTHS
    if is_cheap_month or (cpm_val is not None and cpm_val < 0.5):
        base = 0.55 if is_cheap_month else 0.35
        if cpm_val is not None:
            base += _clamp((1.0 - cpm_val) * 0.30)
        score = round(_clamp(base), 3)
        results.append(_entry(
            "cpm_friendly", score,
            f"Month {month} — lower CPMs available",
            "Deploy paid promotion tests now while CPMs are below annual average",
            round(score * 0.12, 4),
            _confidence(score, audience_size, offer_count),
            f"CPM-friendly window (score {score:.2f}). "
            f"{f'Month {month} historically shows lower ad costs. ' if is_cheap_month else ''}"
            f"CPM index: {cpm_val if cpm_val is not None else 'unknown'}.",
        ))

    # ------------------------------------------------------------------ 8. low_competition_launch
    competitor_count = _macro_signal_value(macro_signals, "competitor_launch_count")
    is_quiet_month = month in _LOW_COMPETITION_MONTHS
    if is_quiet_month or (competitor_count is not None and competitor_count < 3):
        base = 0.50 if is_quiet_month else 0.35
        if competitor_count is not None:
            base += _clamp((1.0 - competitor_count / 10.0) * 0.30)
        score = round(_clamp(base), 3)
        results.append(_entry(
            "low_competition_launch", score,
            f"Month {month} — reduced competitive noise",
            "Launch new offers or accounts during this low-competition window for maximum visibility",
            round(score * 0.15, 4),
            _confidence(score, audience_size, offer_count),
            f"Low-competition launch window (score {score:.2f}). "
            f"{f'Month {month} sees fewer competitor launches. ' if is_quiet_month else ''}"
            f"Competitor launch count: {competitor_count if competitor_count is not None else 'unknown'}.",
        ))

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(
    market_category: str,
    timing_score: float,
    active_window: str,
    recommendation: str,
    expected_uplift: float,
    confidence: float,
    explanation: str,
) -> dict[str, Any]:
    return {
        "market_category": market_category,
        "timing_score": timing_score,
        "active_window": active_window,
        "recommendation": recommendation,
        "expected_uplift": expected_uplift,
        "confidence": confidence,
        "explanation": explanation,
        MARKET_TIMING: True,
    }


def _confidence(score: float, audience_size: int, offer_count: int) -> float:
    audience_signal = _clamp(audience_size / 100_000.0) * 0.20
    offer_signal = _clamp(offer_count / 5.0) * 0.15
    return round(_clamp(0.35 + score * 0.30 + audience_signal + offer_signal), 3)
