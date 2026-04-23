"""Publish Policy Rules — first-match rule table for autonomous publishing.

Each rule specifies match conditions and a tier outcome (auto_publish, sample_review,
manual_approval, block). Rules are evaluated in ascending priority order. First match wins.
NULL match fields act as wildcards (match anything).
"""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class PublishPolicyRule(Base):
    __tablename__ = "publish_policy_rules"

    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=True, index=True,
        comment="NULL = global default rule. Set = brand-specific override.",
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100, index=True)
    tier: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="auto_publish | sample_review | manual_approval | block",
    )
    sample_rate: Mapped[float] = mapped_column(Float, default=0.0,
        comment="Only for sample_review tier. Fraction 0.0-1.0 of items flagged for async review.",
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Match fields (NULL = wildcard, matches anything) ──
    match_content_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    match_platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    match_monetization_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    match_hook_type: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    match_creative_structure: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    match_has_offer: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    match_tags_contain: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True,
        comment="List of tag strings. Matches if content tags contain ANY of these.",
    )
    match_account_health: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    match_governance_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    max_account_age_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True,
        comment="Match if account is NEWER than this many days.",
    )
    min_qa_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_qa_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_confidence: Mapped[Optional[str]] = mapped_column(String(20), nullable=True,
        comment="Minimum confidence level: high, medium, low, insufficient",
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
