"""AI Personality System — persistent character identities for content channels.

Each account can have an AI personality that maintains consistent identity, backstory,
appearance, voice, and memory across all content. This builds parasocial relationships
with audiences, driving 5-10x higher affiliate conversion.
"""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class AIPersonality(Base):
    """Core personality definition — who this character IS."""
    __tablename__ = "ai_personalities"

    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("creator_accounts.id"), nullable=False, index=True, unique=True)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)

    # Identity
    character_name: Mapped[str] = mapped_column(String(120), nullable=False)
    character_tagline: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    character_backstory: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    character_age_range: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    character_gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    character_archetype: Mapped[str] = mapped_column(String(60), default="expert")

    # Personality traits
    personality_traits: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    communication_style: Mapped[str] = mapped_column(String(60), default="direct")
    humor_level: Mapped[str] = mapped_column(String(20), default="moderate")
    energy_level: Mapped[str] = mapped_column(String(20), default="high")
    formality_level: Mapped[str] = mapped_column(String(20), default="casual")

    # Catchphrases and verbal identity
    catchphrases: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    intro_phrases: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    outro_phrases: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    forbidden_phrases: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)

    # Visual identity
    avatar_provider: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    avatar_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_image_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    higgsfield_character_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    visual_style: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    # Voice identity
    voice_provider: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    voice_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    voice_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Content preferences
    favorite_topics: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    expertise_areas: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    opinion_stances: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    content_philosophy: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PersonalityMemory(Base):
    """What the personality remembers — references to past content, running themes, audience interactions."""
    __tablename__ = "ai_personality_memories"

    personality_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_personalities.id"), nullable=False, index=True)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)

    memory_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    memory_key: Mapped[str] = mapped_column(String(255), nullable=False)
    memory_value: Mapped[str] = mapped_column(Text, nullable=False)
    importance_score: Mapped[float] = mapped_column(Float, default=0.5)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    last_referenced_at: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    source_content_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PersonalityEvolution(Base):
    """Track how the personality evolves over time — opinion changes, new expertise, audience feedback."""
    __tablename__ = "ai_personality_evolution"

    personality_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_personalities.id"), nullable=False, index=True)
    evolution_type: Mapped[str] = mapped_column(String(40), nullable=False)
    before_state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    after_state: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
