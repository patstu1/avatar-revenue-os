"""Failure-Family Suppression — detect and suppress recurring bad patterns."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class FailureFamilyReport(Base):
    __tablename__ = "ff_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    family_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    family_key: Mapped[str] = mapped_column(String(255), nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_fail_score: Mapped[float] = mapped_column(Float, default=0.0)
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    recommended_alternative: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class FailureFamilyMember(Base):
    __tablename__ = "ff_members"

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ff_reports.id"), nullable=False, index=True
    )
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True
    )
    pattern_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    fail_score: Mapped[float] = mapped_column(Float, default=0.0)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SuppressionRule(Base):
    __tablename__ = "ff_suppression_rules"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ff_reports.id"), nullable=False, index=True
    )
    family_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    family_key: Mapped[str] = mapped_column(String(255), nullable=False)
    suppression_mode: Mapped[str] = mapped_column(String(20), default="temporary")
    retest_after_days: Mapped[int] = mapped_column(Integer, default=30)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SuppressionEvent(Base):
    __tablename__ = "ff_suppression_events"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ff_suppression_rules.id"), nullable=False, index=True
    )
    blocked_target: Mapped[str] = mapped_column(String(255), nullable=False)
    blocked_context: Mapped[str] = mapped_column(String(60), nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
