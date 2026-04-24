"""Pydantic schemas for Objection Mining."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class ObjectionSignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source_type: str
    objection_type: str
    extracted_objection: str
    severity: float
    monetization_impact: float
    platform: str | None = None


class ObjectionClusterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    objection_type: str
    cluster_label: str
    signal_count: int
    avg_severity: float
    avg_monetization_impact: float
    recommended_response_angle: str | None = None


class ObjectionResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    response_type: str
    response_angle: str
    target_channel: str
    priority: str


class ObjectionPriorityReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    total_signals: int
    total_clusters: int
    highest_impact_type: str | None = None
    summary: str | None = None


class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0
    status: str = "completed"
