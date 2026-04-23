"""Market timing: timing reports and macro signal events."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class MarketTimingReport(Base):
    __tablename__ = "market_timing_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    market_category: Mapped[str] = mapped_column(String(100), nullable=False)
    timing_score: Mapped[float] = mapped_column(Float, default=0.0)
    active_window: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    expected_uplift: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    explanation_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MacroSignalEvent(Base):
    __tablename__ = "macro_signal_events"

    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True, index=True
    )
    signal_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    signal_metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    observed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
