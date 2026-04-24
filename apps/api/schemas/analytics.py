"""Pydantic schemas for Phase 4 analytics, attribution, and dashboards."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PerformanceIngestRequest(BaseModel):
    content_item_id: uuid.UUID
    creator_account_id: uuid.UUID
    platform: str
    metrics: dict


class ClickTrackRequest(BaseModel):
    brand_id: uuid.UUID
    content_item_id: Optional[uuid.UUID] = None
    offer_id: Optional[uuid.UUID] = None
    creator_account_id: Optional[uuid.UUID] = None
    platform: Optional[str] = None
    source_url: Optional[str] = None
    tracking_id: Optional[str] = None


class ConversionTrackRequest(BaseModel):
    brand_id: uuid.UUID
    content_item_id: Optional[uuid.UUID] = None
    offer_id: Optional[uuid.UUID] = None
    creator_account_id: Optional[uuid.UUID] = None
    event_type: str = "purchase"
    event_value: float = 0.0
    currency: str = "USD"
    platform: Optional[str] = None
    attribution_model: str = "last_click"
    source_url: Optional[str] = None
    tracking_id: Optional[str] = None


class AttributionEventResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    content_item_id: Optional[uuid.UUID]
    offer_id: Optional[uuid.UUID]
    event_type: str
    event_value: float
    platform: Optional[str]
    tracking_id: Optional[str]
    event_at: datetime
    model_config = {"from_attributes": True}


class PerformanceMetricResponse(BaseModel):
    id: uuid.UUID
    content_item_id: uuid.UUID
    creator_account_id: uuid.UUID
    platform: str
    impressions: int
    views: int
    clicks: int
    ctr: float
    watch_time_seconds: int
    avg_watch_pct: float
    likes: int
    comments: int
    shares: int
    saves: int
    followers_gained: int
    revenue: float
    rpm: float
    engagement_rate: float
    measured_at: datetime
    model_config = {"from_attributes": True}
