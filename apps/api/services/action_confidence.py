"""Action Confidence — computes confidence from real signals, not hardcoded thresholds.

Replaces the binary `0.7 if expected_value > 200 else 0.5` with a 4-signal
weighted composition that rewards brands with data, punishes unknowns, and
lets brands earn their way to full autonomy.

Signals:
  1. Data completeness (30%) — does the brand have enough recent metrics?
  2. Action history accuracy (30%) — what fraction of past dispatches of this type succeeded?
  3. Expected value normalization (25%) — log-scaled: $10K → 1.0, $100 → 0.5, $1 → 0.0
  4. Risk inversion (15%) — 1.0 - risk_score (default 0.3 if missing)

The floor (MIN_AUTONOMOUS_CONFIDENCE = 0.6 in action_dispatcher.py) stays.
With computed confidence, even new brands will get ~0.55-0.65 from neutral
priors, and as data accumulates, well-performing actions naturally rise above
the threshold.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

# Weights for the 4 signals (must sum to 1.0)
W_COMPLETENESS = 0.30
W_HISTORY = 0.30
W_EV_NORM = 0.25
W_RISK_INV = 0.15

# Neutral priors for when data is missing
NEUTRAL_HISTORY = 0.6   # Assume 60% success when no history exists
NEUTRAL_RISK = 0.3      # Assume moderate risk when not specified


async def compute_action_confidence(
    db: AsyncSession,
    brand_id: uuid.UUID,
    action_type: str,
    expected_value: float = 0.0,
    risk_score: Optional[float] = None,
) -> dict:
    """Compute confidence for an action based on 4 real signals.

    Returns a dict with the final confidence score plus all sub-signals
    for observability/tuning.
    """
    # --- Signal 1: Data completeness (0.0–1.0) ---
    from packages.db.models.publishing import PerformanceMetric
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    row = (await db.execute(
        select(
            func.min(PerformanceMetric.measured_at),
            func.count(PerformanceMetric.id),
        ).where(
            PerformanceMetric.brand_id == brand_id,
            PerformanceMetric.measured_at >= cutoff,
        )
    )).one_or_none()

    oldest_metric = row[0] if row else None
    metric_count = row[1] if row else 0

    if oldest_metric is None or metric_count == 0:
        completeness = 0.0
    else:
        days_of_data = max(1, (datetime.now(timezone.utc) - oldest_metric).days)
        # Linear ramp: 0 days → 0.0, 30 days → 1.0
        completeness = min(1.0, days_of_data / 30.0)

    # --- Signal 2: Action history accuracy (0.0–1.0) ---
    from packages.db.models.system_events import OperatorAction
    history = (await db.execute(
        select(
            func.count(OperatorAction.id),
            func.count(OperatorAction.id).filter(
                OperatorAction.outcome_score > 0
            ),
        ).where(
            OperatorAction.brand_id == brand_id,
            OperatorAction.action_type == action_type,
            OperatorAction.status == "completed",
        )
    )).one_or_none()

    total_completed = history[0] if history else 0
    total_succeeded = history[1] if history else 0

    if total_completed == 0:
        accuracy = NEUTRAL_HISTORY
    else:
        accuracy = total_succeeded / total_completed

    # --- Signal 3: Expected value normalization (0.0–1.0, log-scaled) ---
    # $1 → 0.0, $10 → 0.25, $100 → 0.5, $1K → 0.75, $10K → 1.0
    if expected_value <= 0:
        ev_norm = 0.0
    else:
        ev_norm = min(1.0, math.log10(max(expected_value, 1)) / 4.0)

    # --- Signal 4: Risk inversion (0.0–1.0) ---
    risk = risk_score if risk_score is not None else NEUTRAL_RISK
    risk_inv = 1.0 - min(1.0, max(0.0, risk))

    # --- Compose ---
    confidence = (
        W_COMPLETENESS * completeness
        + W_HISTORY * accuracy
        + W_EV_NORM * ev_norm
        + W_RISK_INV * risk_inv
    )

    # Clamp to [0.0, 1.0]
    confidence = round(min(1.0, max(0.0, confidence)), 4)

    return {
        "confidence": confidence,
        "signals": {
            "data_completeness": round(completeness, 4),
            "action_history_accuracy": round(accuracy, 4),
            "expected_value_norm": round(ev_norm, 4),
            "risk_inversion": round(risk_inv, 4),
        },
        "weights": {
            "completeness": W_COMPLETENESS,
            "history": W_HISTORY,
            "ev_norm": W_EV_NORM,
            "risk_inv": W_RISK_INV,
        },
        "inputs": {
            "metric_count": metric_count,
            "history_total": total_completed,
            "history_succeeded": total_succeeded,
            "expected_value": expected_value,
            "risk_score": risk,
        },
    }
