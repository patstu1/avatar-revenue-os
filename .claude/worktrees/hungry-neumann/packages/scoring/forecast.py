"""Expected profit forecast engine.

Formula:
  expected_revenue = impressions * ctr * conversion_rate * value_per_conversion
  expected_profit = expected_revenue - generation_cost - distribution_cost
                    - fatigue_penalty - risk_penalty

All inputs are explicit. No hidden assumptions.
"""
from dataclasses import dataclass

FORMULA_VERSION = "v1"


@dataclass
class ForecastInput:
    expected_impressions: int = 0
    expected_ctr: float = 0.0
    expected_conversion_rate: float = 0.0
    expected_value_per_conversion: float = 0.0

    expected_generation_cost: float = 0.0
    expected_distribution_cost: float = 0.0
    fatigue_penalty_dollars: float = 0.0
    risk_penalty_dollars: float = 0.0


@dataclass
class ForecastResult:
    expected_clicks: float
    expected_conversions: float
    expected_revenue: float
    expected_cost: float
    expected_profit: float
    expected_rpm: float
    expected_epc: float
    roi: float
    confidence: str
    assumptions: dict
    explanation: str
    formula_version: str = FORMULA_VERSION


def compute_profit_forecast(inp: ForecastInput) -> ForecastResult:
    clicks = inp.expected_impressions * inp.expected_ctr
    conversions = clicks * inp.expected_conversion_rate
    revenue = conversions * inp.expected_value_per_conversion

    total_cost = (
        inp.expected_generation_cost
        + inp.expected_distribution_cost
        + inp.fatigue_penalty_dollars
        + inp.risk_penalty_dollars
    )

    profit = revenue - total_cost

    rpm = (revenue / inp.expected_impressions * 1000) if inp.expected_impressions > 0 else 0.0
    epc = (revenue / clicks) if clicks > 0 else 0.0
    roi = (profit / total_cost) if total_cost > 0 else 0.0

    signal_count = sum(1 for v in [
        inp.expected_impressions, inp.expected_ctr, inp.expected_conversion_rate,
        inp.expected_value_per_conversion
    ] if v > 0)

    if signal_count == 4 and inp.expected_impressions >= 1000:
        confidence = "high"
    elif signal_count >= 3:
        confidence = "medium"
    elif signal_count >= 1:
        confidence = "low"
    else:
        confidence = "insufficient"

    assumptions = {
        "impressions": inp.expected_impressions,
        "ctr": inp.expected_ctr,
        "conversion_rate": inp.expected_conversion_rate,
        "value_per_conversion": inp.expected_value_per_conversion,
        "generation_cost": inp.expected_generation_cost,
        "distribution_cost": inp.expected_distribution_cost,
        "fatigue_penalty_dollars": inp.fatigue_penalty_dollars,
        "risk_penalty_dollars": inp.risk_penalty_dollars,
    }

    explanation = (
        f"Forecast: {inp.expected_impressions} impressions → "
        f"{clicks:.0f} clicks → {conversions:.1f} conversions → "
        f"${revenue:.2f} revenue - ${total_cost:.2f} cost = ${profit:.2f} profit. "
        f"RPM ${rpm:.2f}, EPC ${epc:.2f}, ROI {roi:.1%}."
    )

    if confidence == "insufficient":
        explanation += " Insufficient data for reliable forecast."

    return ForecastResult(
        expected_clicks=clicks,
        expected_conversions=conversions,
        expected_revenue=round(revenue, 2),
        expected_cost=round(total_cost, 2),
        expected_profit=round(profit, 2),
        expected_rpm=round(rpm, 2),
        expected_epc=round(epc, 2),
        roi=round(roi, 4),
        confidence=confidence,
        assumptions=assumptions,
        explanation=explanation,
    )
