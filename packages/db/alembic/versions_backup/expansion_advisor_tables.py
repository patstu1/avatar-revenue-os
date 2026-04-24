"""Account Expansion Advisor table.

Revision ID: expansion_adv_001
Revises: gatekeeper_001
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "expansion_adv_001"
down_revision: Union[str, None] = "gatekeeper_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "account_expansion_advisories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("should_add_account_now", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("platform", sa.String(50), nullable=True),
        sa.Column("niche", sa.String(255), nullable=True),
        sa.Column("sub_niche", sa.String(255), nullable=True),
        sa.Column("account_type", sa.String(80), nullable=True),
        sa.Column("content_role", sa.String(80), nullable=True),
        sa.Column("monetization_path", sa.Text(), nullable=True),
        sa.Column("expected_upside", sa.Float(), server_default="0", nullable=False),
        sa.Column("expected_cost", sa.Float(), server_default="0", nullable=False),
        sa.Column("expected_time_to_signal_days", sa.Integer(), server_default="14", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("urgency", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("hold_reason", sa.Text(), nullable=True),
        sa.Column("blockers", JSONB(), server_default="[]", nullable=True),
        sa.Column("evidence", JSONB(), server_default="{}", nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_expansion_advisories_brand_id", "account_expansion_advisories", ["brand_id"])
    op.create_index(
        "ix_account_expansion_advisories_should_add", "account_expansion_advisories", ["should_add_account_now"]
    )


def downgrade() -> None:
    op.drop_index("ix_account_expansion_advisories_should_add", table_name="account_expansion_advisories")
    op.drop_index("ix_account_expansion_advisories_brand_id", table_name="account_expansion_advisories")
    op.drop_table("account_expansion_advisories")
