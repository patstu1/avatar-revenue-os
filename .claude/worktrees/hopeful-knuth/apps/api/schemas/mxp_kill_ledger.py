"""Pydantic schemas for MXP Kill Ledger."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class KillLedgerEntryOut(BaseModel):
    id: str
    brand_id: str
    scope_type: str
    scope_id: str
    kill_reason: str
    performance_snapshot_json: Optional[dict] = None
    replacement_recommendation_json: Optional[dict] = None
    confidence_score: float
    killed_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class KillHindsightReviewOut(BaseModel):
    id: str
    brand_id: str
    kill_ledger_entry_id: str
    hindsight_outcome: str
    was_correct_kill: Optional[bool] = None
    explanation_json: Optional[dict] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class KillLedgerEntryWithHindsightOut(BaseModel):
    """Flattened row for dashboards: entry fields plus optional linked hindsight."""

    id: str
    brand_id: str
    scope_type: str
    scope_id: str
    kill_reason: str
    performance_snapshot_json: Optional[dict] = None
    replacement_recommendation_json: Optional[dict] = None
    confidence_score: float
    killed_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    scope_name: Optional[str] = None
    hindsight: Optional[KillHindsightReviewOut] = None


class KillLedgerBundleOut(BaseModel):
    entries: list[KillLedgerEntryOut]
    hindsight_reviews: list[KillHindsightReviewOut]
    entries_with_hindsight: list[KillLedgerEntryWithHindsightOut]
