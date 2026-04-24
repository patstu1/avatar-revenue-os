"""Content Form Selection + Mix Allocation tables.

Revision ID: content_form_001
Revises: expansion_adv_001
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "content_form_001"
down_revision: Union[str, None] = "expansion_adv_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "content_form_recommendations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("recommended_content_form", sa.String(80), nullable=False),
        sa.Column("secondary_content_form", sa.String(80), nullable=True),
        sa.Column("format_family", sa.String(40), nullable=False),
        sa.Column("short_or_long", sa.String(10), server_default="short", nullable=False),
        sa.Column("avatar_mode", sa.String(30), server_default="none", nullable=False),
        sa.Column("trust_level_required", sa.String(30), server_default="low", nullable=False),
        sa.Column("production_cost_band", sa.String(20), server_default="low", nullable=False),
        sa.Column("expected_upside", sa.Float(), server_default="0", nullable=False),
        sa.Column("expected_cost", sa.Float(), server_default="0", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("urgency", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("truth_label", sa.String(30), server_default="recommendation", nullable=False),
        sa.Column("blockers", JSONB(), server_default="[]", nullable=True),
        sa.Column("details_json", JSONB(), server_default="{}", nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["creator_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cfr_brand", "content_form_recommendations", ["brand_id"])
    op.create_index("ix_cfr_platform", "content_form_recommendations", ["platform"])
    op.create_index("ix_cfr_form", "content_form_recommendations", ["recommended_content_form"])

    op.create_table(
        "content_form_mix_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("dimension", sa.String(40), nullable=False),
        sa.Column("dimension_value", sa.String(120), nullable=False),
        sa.Column("mix_allocation", JSONB(), server_default="{}", nullable=False),
        sa.Column("total_expected_upside", sa.Float(), server_default="0", nullable=False),
        sa.Column("avg_confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cfmr_brand", "content_form_mix_reports", ["brand_id"])
    op.create_index("ix_cfmr_dim", "content_form_mix_reports", ["dimension"])

    op.create_table(
        "content_form_blockers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("content_form", sa.String(80), nullable=False),
        sa.Column("blocker_type", sa.String(80), nullable=False),
        sa.Column("severity", sa.String(30), server_default="high", nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("operator_action", sa.Text(), nullable=False),
        sa.Column("resolved", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cfb_brand", "content_form_blockers", ["brand_id"])


def downgrade() -> None:
    op.drop_table("content_form_blockers")
    op.drop_table("content_form_mix_reports")
    op.drop_table("content_form_recommendations")
