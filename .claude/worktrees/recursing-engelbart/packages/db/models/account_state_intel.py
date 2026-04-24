"""Account-State Intelligence — live operating state per account."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class AccountStateReport(Base):
    __tablename__ = "asi_account_state_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("creator_accounts.id"), nullable=False, index=True)
    current_state: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    next_best_move: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    blocked_actions: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    suitable_content_forms: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    monetization_intensity: Mapped[str] = mapped_column(String(20), default="low")
    posting_cadence: Mapped[str] = mapped_column(String(20), default="normal")
    expansion_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    inputs_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AccountStateTransition(Base):
    __tablename__ = "asi_account_state_transitions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("creator_accounts.id"), nullable=False, index=True)
    from_state: Mapped[str] = mapped_column(String(40), nullable=False)
    to_state: Mapped[str] = mapped_column(String(40), nullable=False)
    trigger: Mapped[str] = mapped_column(String(120), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AccountStateAction(Base):
    __tablename__ = "asi_account_state_actions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("creator_accounts.id"), nullable=False, index=True)
    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("asi_account_state_reports.id"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(60), nullable=False)
    action_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
