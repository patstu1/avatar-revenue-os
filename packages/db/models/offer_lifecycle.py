"""Offer lifecycle models — health tracking, state transitions, and decay detection."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class OfferLifecycleReport(Base):
    __tablename__ = "offer_lifecycle_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    offer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("offers.id"), nullable=False, index=True
    )
    lifecycle_state: Mapped[str] = mapped_column(String(50), nullable=False)
    health_score: Mapped[float] = mapped_column(Float, default=0.0)
    dependency_risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    decay_score: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_next_action: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    expected_impact_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    explanation_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OfferLifecycleEvent(Base):
    __tablename__ = "offer_lifecycle_events"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    offer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("offers.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    from_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reason_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
