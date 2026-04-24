"""Offer Parameter Learning — update offer economics from measured performance data.

Closes the loop: offer seed values → content published → performance measured → offer updated.
"""
from __future__ import annotations

from typing import Any


def compute_learned_offer_params(
    offer_id: str,
    current_epc: float,
    current_cvr: float,
    current_aov: float,
    measured_clicks: int,
    measured_conversions: int,
    measured_revenue: float,
    min_sample_clicks: int = 50,
    learning_rate: float = 0.3,
) -> dict[str, Any]:
    """Blend measured performance into offer parameters.

    Uses exponential moving average: new = (1 - lr) * current + lr * measured.
    Only updates when sample size exceeds minimum threshold.
    """
    result: dict[str, Any] = {
        "offer_id": offer_id,
        "updated": False,
        "learned_epc": current_epc,
        "learned_cvr": current_cvr,
        "learned_aov": current_aov,
        "sample_clicks": measured_clicks,
        "sample_conversions": measured_conversions,
        "sample_revenue": measured_revenue,
        "confidence": 0.0,
        "reason": "",
    }

    if measured_clicks < min_sample_clicks:
        result["reason"] = f"Insufficient sample: {measured_clicks} clicks < {min_sample_clicks} minimum"
        return result

    measured_cvr = measured_conversions / max(1, measured_clicks)
    measured_epc = measured_revenue / max(1, measured_clicks)
    measured_aov = measured_revenue / max(1, measured_conversions) if measured_conversions > 0 else current_aov

    lr = learning_rate
    learned_cvr = round((1 - lr) * current_cvr + lr * measured_cvr, 6)
    learned_epc = round((1 - lr) * current_epc + lr * measured_epc, 4)
    learned_aov = round((1 - lr) * current_aov + lr * measured_aov, 2)

    confidence = min(0.95, 0.3 + (measured_clicks / 500) * 0.4 + (measured_conversions / 20) * 0.25)

    result.update({
        "updated": True,
        "learned_epc": learned_epc,
        "learned_cvr": learned_cvr,
        "learned_aov": learned_aov,
        "confidence": round(confidence, 3),
        "reason": f"Updated from {measured_clicks} clicks, {measured_conversions} conversions, ${measured_revenue:.2f} revenue",
    })
    return result
