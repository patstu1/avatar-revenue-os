"""Content Routing decisions + cost reports.

Revision ID: content_routing_001
Revises: content_form_001
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "content_routing_001"
down_revision: Union[str, None] = "content_form_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "content_routing_decisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("task_id", sa.String(255), nullable=True),
        sa.Column("content_type", sa.String(40), nullable=False),
        sa.Column("quality_tier", sa.String(20), nullable=False),
        sa.Column("routed_provider", sa.String(80), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("is_promoted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("estimated_cost", sa.Float(), server_default="0", nullable=False),
        sa.Column("actual_cost", sa.Float(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("details_json", JSONB(), server_default="{}", nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crd_brand", "content_routing_decisions", ["brand_id"])
    op.create_index("ix_crd_provider", "content_routing_decisions", ["routed_provider"])
    op.create_index("ix_crd_tier", "content_routing_decisions", ["quality_tier"])

    op.create_table(
        "content_routing_cost_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("report_date", sa.String(20), nullable=False),
        sa.Column("total_cost", sa.Float(), server_default="0", nullable=False),
        sa.Column("total_decisions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("by_provider", JSONB(), server_default="{}", nullable=True),
        sa.Column("by_tier", JSONB(), server_default="{}", nullable=True),
        sa.Column("by_content_type", JSONB(), server_default="{}", nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crcr_brand", "content_routing_cost_reports", ["brand_id"])
    op.create_index("ix_crcr_date", "content_routing_cost_reports", ["report_date"])


def downgrade() -> None:
    op.drop_table("content_routing_cost_reports")
    op.drop_table("content_routing_decisions")
