"""Pydantic schemas for MXP Market Timing."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class MacroSignalEventOut(BaseModel):
    id: str
    brand_id: Optional[str] = None
    signal_type: str
    source_name: str
    signal_metadata_json: Optional[dict[str, Any]] = None
    observed_at: Optional[datetime] = None
    data_source: str = "synthetic_proxy"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MarketTimingReportOut(BaseModel):
    id: str
    brand_id: str
    market_category: str
    timing_score: float
    active_window: Optional[str] = None
    recommendation: str
    expected_uplift: float
    confidence_score: float
    explanation_json: Optional[dict] = None
    is_active: bool
    data_source: str = "synthetic_proxy"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
