"""Content Form Selection + Mix Allocation models."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class ContentFormRecommendation(Base):
    __tablename__ = "content_form_recommendations"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    account_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("creator_accounts.id"), nullable=True, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    recommended_content_form: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    secondary_content_form: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    format_family: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    short_or_long: Mapped[str] = mapped_column(String(10), default="short", index=True)
    avatar_mode: Mapped[str] = mapped_column(String(30), default="none", index=True)
    trust_level_required: Mapped[str] = mapped_column(String(30), default="low")
    production_cost_band: Mapped[str] = mapped_column(String(20), default="low")
    expected_upside: Mapped[float] = mapped_column(Float, default=0.0)
    expected_cost: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    urgency: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    truth_label: Mapped[str] = mapped_column(String(30), default="recommendation", index=True)
    blockers: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ContentFormMixReport(Base):
    __tablename__ = "content_form_mix_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    dimension: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    dimension_value: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    mix_allocation: Mapped[dict] = mapped_column(JSONB, default=dict)
    total_expected_upside: Mapped[float] = mapped_column(Float, default=0.0)
    avg_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ContentFormBlocker(Base):
    __tablename__ = "content_form_blockers"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    content_form: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    blocker_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(30), default="high", index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    operator_action: Mapped[str] = mapped_column(Text, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
