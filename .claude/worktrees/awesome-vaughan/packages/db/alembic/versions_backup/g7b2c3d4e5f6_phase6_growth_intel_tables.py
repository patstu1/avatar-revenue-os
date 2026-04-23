"""phase6 trust signals + paid candidate flag

Revision ID: g7b2c3d4e5f6
Revises: f8a1c2d3e4b5
Create Date: 2026-03-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "g7b2c3d4e5f6"
down_revision: Union[str, None] = "f8a1c2d3e4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trust_signal_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("creator_account_id", sa.UUID(), nullable=True),
        sa.Column("trust_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("components", JSONB(), nullable=True),
        sa.Column("recommendations", JSONB(), nullable=True),
        sa.Column("evidence", JSONB(), nullable=True),
        sa.Column("confidence_label", sa.String(length=20), nullable=False, server_default="medium"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["creator_account_id"], ["creator_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trust_signal_reports_brand_id"), "trust_signal_reports", ["brand_id"], unique=False)
    op.create_index(op.f("ix_trust_signal_reports_creator_account_id"), "trust_signal_reports", ["creator_account_id"], unique=False)
    op.add_column(
        "paid_amplification_jobs",
        sa.Column("is_candidate", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.alter_column("paid_amplification_jobs", "is_candidate", server_default=None)


def downgrade() -> None:
    op.drop_column("paid_amplification_jobs", "is_candidate")
    op.drop_index(op.f("ix_trust_signal_reports_creator_account_id"), table_name="trust_signal_reports")
    op.drop_index(op.f("ix_trust_signal_reports_brand_id"), table_name="trust_signal_reports")
    op.drop_table("trust_signal_reports")
