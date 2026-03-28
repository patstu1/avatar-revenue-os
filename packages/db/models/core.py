"""Core entity models: organizations, users, brands, avatars, provider profiles."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.db.base import Base
from packages.db.enums import HealthStatus, ProviderType, UserRole


class Organization(Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    plan: Mapped[str] = mapped_column(String(50), default="free")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    settings: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    users: Mapped[list["User"]] = relationship(back_populates="organization", lazy="selectin")
    brands: Mapped[list["Brand"]] = relationship(back_populates="organization", lazy="selectin")


class User(Base):
    __tablename__ = "users"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.VIEWER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    organization: Mapped["Organization"] = relationship(back_populates="users")


class Brand(Base):
    __tablename__ = "brands"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    niche: Mapped[Optional[str]] = mapped_column(String(255))
    sub_niche: Mapped[Optional[str]] = mapped_column(String(255))
    target_audience: Mapped[Optional[str]] = mapped_column(Text)
    tone_of_voice: Mapped[Optional[str]] = mapped_column(Text)
    brand_guidelines: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    decision_mode: Mapped[str] = mapped_column(String(50), default="guarded_auto")

    organization: Mapped["Organization"] = relationship(back_populates="brands")
    avatars: Mapped[list["Avatar"]] = relationship(back_populates="brand", lazy="selectin")


class Avatar(Base):
    __tablename__ = "avatars"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    persona_description: Mapped[Optional[str]] = mapped_column(Text)
    voice_style: Mapped[Optional[str]] = mapped_column(String(255))
    visual_style: Mapped[Optional[str]] = mapped_column(String(255))
    default_language: Mapped[str] = mapped_column(String(10), default="en")
    personality_traits: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    speaking_patterns: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    visual_reference_urls: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    brand: Mapped["Brand"] = relationship(back_populates="avatars")
    provider_profiles: Mapped[list["AvatarProviderProfile"]] = relationship(
        back_populates="avatar", lazy="selectin"
    )
    voice_profiles: Mapped[list["VoiceProviderProfile"]] = relationship(
        back_populates="avatar", lazy="selectin"
    )


class AvatarProviderProfile(Base):
    __tablename__ = "avatar_provider_profiles"

    avatar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avatars.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_avatar_id: Mapped[Optional[str]] = mapped_column(String(255))
    provider_config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    capabilities: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    health_status: Mapped[HealthStatus] = mapped_column(
        Enum(HealthStatus), default=HealthStatus.HEALTHY
    )
    last_health_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cost_per_minute: Mapped[Optional[float]] = mapped_column(Float)

    avatar: Mapped["Avatar"] = relationship(back_populates="provider_profiles")


class VoiceProviderProfile(Base):
    __tablename__ = "voice_provider_profiles"

    avatar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avatars.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_voice_id: Mapped[Optional[str]] = mapped_column(String(255))
    provider_config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    capabilities: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    health_status: Mapped[HealthStatus] = mapped_column(
        Enum(HealthStatus), default=HealthStatus.HEALTHY
    )
    last_health_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cost_per_minute: Mapped[Optional[float]] = mapped_column(Float)

    avatar: Mapped["Avatar"] = relationship(back_populates="voice_profiles")
