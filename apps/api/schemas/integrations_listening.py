"""Pydantic schemas for Integrations + Listening."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class ILConnectorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; connector_name: str; connector_type: str; status: str; sync_direction: str; last_sync_status: str | None = None

class ILListeningOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; signal_type: str; platform: str | None = None; raw_text: str; sentiment: float; relevance_score: float

class ILCompetitorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; competitor_name: str; signal_type: str; sentiment: float; opportunity_score: float

class ILClusterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; cluster_type: str; cluster_label: str; signal_count: int; avg_sentiment: float; recommended_action: str | None = None

class ILBlockerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; blocker_type: str; description: str; severity: str

class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0; status: str = "completed"
