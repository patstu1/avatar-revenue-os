"""Account-State Intelligence tables.

Revision ID: asi_001
Revises: cap_alloc_001
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "asi_001"
down_revision: Union[str, None] = "cap_alloc_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "asi_account_state_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("current_state", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0"),
        sa.Column("next_best_move", sa.String(255), nullable=True),
        sa.Column("blocked_actions", JSONB(), server_default="[]", nullable=True),
        sa.Column("suitable_content_forms", JSONB(), server_default="[]", nullable=True),
        sa.Column("monetization_intensity", sa.String(20), server_default="low"),
        sa.Column("posting_cadence", sa.String(20), server_default="normal"),
        sa.Column("expansion_eligible", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("inputs_json", JSONB(), server_default="{}", nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["creator_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_asr_brand", "asi_account_state_reports", ["brand_id"])
    op.create_index("ix_asr_account", "asi_account_state_reports", ["account_id"])

    op.create_table(
        "asi_account_state_transitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("from_state", sa.String(40), nullable=False),
        sa.Column("to_state", sa.String(40), nullable=False),
        sa.Column("trigger", sa.String(120), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["creator_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "asi_account_state_actions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("action_type", sa.String(60), nullable=False),
        sa.Column("action_detail", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(20), server_default="medium"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["creator_accounts.id"]),
        sa.ForeignKeyConstraint(["report_id"], ["asi_account_state_reports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    for t in ("asi_account_state_actions", "asi_account_state_transitions", "asi_account_state_reports"):
        op.drop_table(t)
