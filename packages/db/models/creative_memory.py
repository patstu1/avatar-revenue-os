"""Creative memory: atoms (reusable content patterns) and links to scoped entities."""

import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class CreativeMemoryAtom(Base):
    __tablename__ = "creative_memory_atoms"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    atom_type: Mapped[str] = mapped_column(String(100), nullable=False)
    content_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    niche: Mapped[Optional[str]] = mapped_column(String(200))
    audience_segment_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    platform: Mapped[Optional[str]] = mapped_column(String(50))
    monetization_type: Mapped[Optional[str]] = mapped_column(String(100))
    account_type: Mapped[Optional[str]] = mapped_column(String(50))
    funnel_stage: Mapped[Optional[str]] = mapped_column(String(100))
    performance_summary_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    reuse_recommendations_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    originality_caution_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.5)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CreativeMemoryLink(Base):
    __tablename__ = "creative_memory_links"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    atom_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creative_memory_atoms.id"), nullable=False, index=True
    )
    linked_scope_type: Mapped[str] = mapped_column(String(100), nullable=False)
    linked_scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False)
