"""Pydantic schemas for MXP Kill Ledger."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class KillLedgerEntryOut(BaseModel):
    id: str
    brand_id: str
    scope_type: str
    scope_id: str
    kill_reason: str
    performance_snapshot_json: dict | None = None
    replacement_recommendation_json: dict | None = None
    confidence_score: float
    killed_at: datetime | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class KillHindsightReviewOut(BaseModel):
    id: str
    brand_id: str
    kill_ledger_entry_id: str
    hindsight_outcome: str
    was_correct_kill: bool | None = None
    explanation_json: dict | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class KillLedgerEntryWithHindsightOut(BaseModel):
    """Flattened row for dashboards: entry fields plus optional linked hindsight."""

    id: str
    brand_id: str
    scope_type: str
    scope_id: str
    kill_reason: str
    performance_snapshot_json: dict | None = None
    replacement_recommendation_json: dict | None = None
    confidence_score: float
    killed_at: datetime | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    scope_name: str | None = None
    hindsight: KillHindsightReviewOut | None = None


class KillLedgerBundleOut(BaseModel):
    entries: list[KillLedgerEntryOut]
    hindsight_reviews: list[KillHindsightReviewOut]
    entries_with_hindsight: list[KillLedgerEntryWithHindsightOut]
