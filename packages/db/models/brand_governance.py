"""Brand Governance OS — governance, voices, knowledge, editorial, assets."""

import uuid
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class BrandGovernanceProfile(Base):
    __tablename__ = "bg_profiles"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    brand_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tone_profile: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    governance_level: Mapped[str] = mapped_column(String(20), default="standard")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BrandVoiceRule(Base):
    __tablename__ = "bg_voice_rules"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    rule_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    rule_key: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_value: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    severity: Mapped[str] = mapped_column(String(20), default="hard")
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BrandKnowledgeBase(Base):
    __tablename__ = "bg_knowledge_bases"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    kb_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BrandKnowledgeDocument(Base):
    __tablename__ = "bg_knowledge_docs"
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bg_knowledge_bases.id"), nullable=False, index=True
    )
    doc_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BrandAudienceProfile(Base):
    __tablename__ = "bg_audience_profiles"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    segment_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trust_level: Mapped[str] = mapped_column(String(20), default="medium")
    objection_patterns: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    preferred_content_forms: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    monetization_sensitivity: Mapped[str] = mapped_column(String(20), default="medium")
    channel_preferences: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    language: Mapped[str] = mapped_column(String(10), default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BrandEditorialRule(Base):
    __tablename__ = "bg_editorial_rules"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    rule_category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    check_type: Mapped[str] = mapped_column(String(40), nullable=False)
    check_value: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    severity: Mapped[str] = mapped_column(String(20), default="hard")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BrandAssetLibrary(Base):
    __tablename__ = "bg_asset_libraries"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    asset_name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BrandStyleToken(Base):
    __tablename__ = "bg_style_tokens"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    token_key: Mapped[str] = mapped_column(String(80), nullable=False)
    token_value: Mapped[str] = mapped_column(String(500), nullable=False)
    token_category: Mapped[str] = mapped_column(String(40), default="general")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BrandGovernanceViolation(Base):
    __tablename__ = "bg_violations"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True, index=True
    )
    violation_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    rule_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="hard")
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BrandGovernanceApproval(Base):
    __tablename__ = "bg_approvals"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True, index=True
    )
    approved_by: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    approval_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
