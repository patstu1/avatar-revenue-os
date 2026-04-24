"""Pydantic schemas for MXP Market Timing."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class MacroSignalEventOut(BaseModel):
    id: str
    brand_id: str | None = None
    signal_type: str
    source_name: str
    signal_metadata_json: dict[str, Any] | None = None
    observed_at: datetime | None = None
    data_source: str = "synthetic_proxy"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MarketTimingReportOut(BaseModel):
    id: str
    brand_id: str
    market_category: str
    timing_score: float
    active_window: str | None = None
    recommendation: str
    expected_uplift: float
    confidence_score: float
    explanation_json: dict | None = None
    is_active: bool
    data_source: str = "synthetic_proxy"
    created_at: datetime | None = None
    updated_at: datetime | None = None
