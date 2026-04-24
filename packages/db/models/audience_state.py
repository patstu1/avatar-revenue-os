"""Audience state machine: reports per segment and state-transition events."""

import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class AudienceStateReport(Base):
    __tablename__ = "audience_state_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    audience_segment_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    state_name: Mapped[str] = mapped_column(String(100), nullable=False)
    state_score: Mapped[float] = mapped_column(Float, default=0.0)
    transition_probabilities_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    best_next_action: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    explanation_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AudienceStateEvent(Base):
    __tablename__ = "audience_state_events"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    audience_segment_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    from_state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    to_state: Mapped[str] = mapped_column(String(100), nullable=False)
    trigger_reason_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
