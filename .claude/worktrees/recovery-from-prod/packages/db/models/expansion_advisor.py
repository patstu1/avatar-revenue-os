"""Account Expansion Advisor — execution-grade expansion/hold recommendations."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class AccountExpansionAdvisory(Base):
    __tablename__ = "account_expansion_advisories"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    should_add_account_now: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    niche: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sub_niche: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    account_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    content_role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    monetization_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_upside: Mapped[float] = mapped_column(Float, default=0.0)
    expected_cost: Mapped[float] = mapped_column(Float, default=0.0)
    expected_time_to_signal_days: Mapped[int] = mapped_column(Integer, default=14)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    urgency: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    hold_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    blockers: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    evidence: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
