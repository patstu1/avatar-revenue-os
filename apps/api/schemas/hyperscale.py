"""Pydantic schemas for Hyper-Scale Execution."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class HSCapacityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; total_queued: int; total_running: int; throughput_per_hour: float; burst_active: bool; degraded: bool; health_status: str

class HSQueueSegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; segment_key: str; segment_type: str; queue_depth: int; running_count: int; max_concurrency: int; priority: int

class HSCeilingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; ceiling_type: str; max_value: float; current_value: float; period: str; enforced: bool

class HSScaleHealthOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; health_status: str; queue_depth_total: int; ceiling_utilization_pct: float; burst_count_24h: int; degradation_count_24h: int; recommendation: str | None = None

class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0; status: str = "completed"
