"""Brand Governance OS tables.

Revision ID: bg_001
Revises: af_001
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "bg_001"
down_revision: Union[str, None] = "af_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for tbl, cols in [
        ("bg_profiles", [sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("brand_summary", sa.Text()), sa.Column("tone_profile", sa.Text()), sa.Column("region", sa.String(60)), sa.Column("language", sa.String(10), server_default="en"), sa.Column("governance_level", sa.String(20), server_default="standard"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"])]),
        ("bg_voice_rules", [sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("rule_type", sa.String(40), nullable=False), sa.Column("rule_key", sa.String(255), nullable=False), sa.Column("rule_value", JSONB(), server_default="{}"), sa.Column("severity", sa.String(20), server_default="hard"), sa.Column("explanation", sa.Text()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"])]),
        ("bg_knowledge_bases", [sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("kb_type", sa.String(60), nullable=False), sa.Column("title", sa.String(255), nullable=False), sa.Column("summary", sa.Text()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"])]),
        ("bg_knowledge_docs", [sa.Column("knowledge_base_id", sa.UUID(), nullable=False), sa.Column("doc_type", sa.String(40), nullable=False), sa.Column("title", sa.String(500), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("metadata_json", JSONB(), server_default="{}"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["knowledge_base_id"], ["bg_knowledge_bases.id"])]),
        ("bg_audience_profiles", [sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("segment_name", sa.String(255), nullable=False), sa.Column("trust_level", sa.String(20), server_default="medium"), sa.Column("objection_patterns", JSONB(), server_default="[]"), sa.Column("preferred_content_forms", JSONB(), server_default="[]"), sa.Column("monetization_sensitivity", sa.String(20), server_default="medium"), sa.Column("channel_preferences", JSONB(), server_default="[]"), sa.Column("language", sa.String(10), server_default="en"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"])]),
        ("bg_editorial_rules", [sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("rule_category", sa.String(40), nullable=False), sa.Column("rule_name", sa.String(255), nullable=False), sa.Column("check_type", sa.String(40), nullable=False), sa.Column("check_value", JSONB(), server_default="{}"), sa.Column("severity", sa.String(20), server_default="hard"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"])]),
        ("bg_asset_libraries", [sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("asset_type", sa.String(40), nullable=False), sa.Column("asset_name", sa.String(255), nullable=False), sa.Column("asset_url", sa.String(1000)), sa.Column("metadata_json", JSONB(), server_default="{}"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"])]),
        ("bg_style_tokens", [sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("token_key", sa.String(80), nullable=False), sa.Column("token_value", sa.String(500), nullable=False), sa.Column("token_category", sa.String(40), server_default="general"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"])]),
        ("bg_violations", [sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("content_item_id", sa.UUID()), sa.Column("violation_type", sa.String(60), nullable=False), sa.Column("rule_id", sa.UUID()), sa.Column("severity", sa.String(20), server_default="hard"), sa.Column("detail", sa.Text(), nullable=False), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"])]),
        ("bg_approvals", [sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("content_item_id", sa.UUID()), sa.Column("approved_by", sa.String(120)), sa.Column("approval_status", sa.String(20), server_default="pending"), sa.Column("notes", sa.Text()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"])]),
    ]:
        base = [sa.Column("id", sa.UUID(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)]
        op.create_table(tbl, *base, *cols, sa.PrimaryKeyConstraint("id"))


def downgrade() -> None:
    for t in ("bg_approvals", "bg_violations", "bg_style_tokens", "bg_asset_libraries", "bg_editorial_rules", "bg_audience_profiles", "bg_knowledge_docs", "bg_knowledge_bases", "bg_voice_rules", "bg_profiles"):
        op.drop_table(t)
