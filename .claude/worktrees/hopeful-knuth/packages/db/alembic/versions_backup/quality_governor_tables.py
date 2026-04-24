"""Quality Governor tables.

Revision ID: qg_001
Revises: asi_001
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "qg_001"
down_revision: Union[str, None] = "asi_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("qg_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("content_item_id", sa.UUID(), nullable=False),
        sa.Column("total_score", sa.Float(), server_default="0"),
        sa.Column("verdict", sa.String(10), nullable=False),
        sa.Column("publish_allowed", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("confidence", sa.Float(), server_default="0"),
        sa.Column("reasons", JSONB(), server_default="[]", nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_qgr_brand", "qg_reports", ["brand_id"])
    op.create_index("ix_qgr_ci", "qg_reports", ["content_item_id"])

    op.create_table("qg_dimension_scores",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("dimension", sa.String(40), nullable=False),
        sa.Column("score", sa.Float(), server_default="0"),
        sa.Column("max_score", sa.Float(), server_default="1"),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["report_id"], ["qg_reports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table("qg_blocks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("content_item_id", sa.UUID(), nullable=False),
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("block_reason", sa.String(120), nullable=False),
        sa.Column("severity", sa.String(20), server_default="hard"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"]),
        sa.ForeignKeyConstraint(["report_id"], ["qg_reports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table("qg_improvement_actions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("dimension", sa.String(40), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(20), server_default="medium"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["report_id"], ["qg_reports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    for t in ("qg_improvement_actions", "qg_blocks", "qg_dimension_scores", "qg_reports"):
        op.drop_table(t)
