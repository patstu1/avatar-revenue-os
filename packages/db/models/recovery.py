"""Recovery system: incidents detected by the engine and prescribed actions."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class RecoveryIncident(Base):
    __tablename__ = "recovery_incidents"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    incident_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(100), nullable=False)
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    detected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="open")
    explanation_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    escalation_state: Mapped[str] = mapped_column(String(50), default="open")
    recommended_recovery_action: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    automatic_action_taken: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)


class RecoveryAction(Base):
    __tablename__ = "recovery_actions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recovery_incidents.id"), nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    action_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    executed: Mapped[bool] = mapped_column(Boolean, default=False)
    expected_effect_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    result_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
