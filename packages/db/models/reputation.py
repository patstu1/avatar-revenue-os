"""Reputation monitoring: risk reports and reputation events."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class ReputationReport(Base):
    __tablename__ = "reputation_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    scope_type: Mapped[str] = mapped_column(String(100), nullable=False)
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    reputation_risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    primary_risks_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    recommended_mitigation_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    expected_impact_if_unresolved: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ReputationEvent(Base):
    __tablename__ = "reputation_events"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
