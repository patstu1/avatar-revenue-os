"""Kill ledger: kill entries and hindsight reviews."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class KillLedgerEntry(Base):
    __tablename__ = "kill_ledger_entries"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    scope_type: Mapped[str] = mapped_column(String(100), nullable=False)
    scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    kill_reason: Mapped[str] = mapped_column(Text, nullable=False)
    performance_snapshot_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    replacement_recommendation_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    killed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class KillHindsightReview(Base):
    __tablename__ = "kill_hindsight_reviews"
    __table_args__ = (
        UniqueConstraint(
            "kill_ledger_entry_id",
            name="uq_kill_hindsight_reviews_kill_ledger_entry_id",
        ),
    )

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    kill_ledger_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kill_ledger_entries.id"), nullable=False, index=True
    )
    hindsight_outcome: Mapped[str] = mapped_column(Text, nullable=False)
    was_correct_kill: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    explanation_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
