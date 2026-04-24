"""Operator Permission Matrix tables.

Revision ID: opm_001
Revises: rec_001
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "opm_001"
down_revision: Union[str, None] = "rec_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _b():
    return [
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "opm_matrix",
        *_b(),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("brand_id", sa.UUID()),
        sa.Column("action_class", sa.String(60), nullable=False),
        sa.Column("autonomy_mode", sa.String(30), nullable=False),
        sa.Column("approval_role", sa.String(80)),
        sa.Column("override_allowed", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("override_role", sa.String(80)),
        sa.Column("explanation", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "opm_action_policies",
        *_b(),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("action_class", sa.String(60), nullable=False),
        sa.Column("default_mode", sa.String(30), nullable=False),
        sa.Column("conditions_json", JSONB(), server_default="{}"),
        sa.Column("escalation_path", sa.String(120)),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "opm_approval_requirements",
        *_b(),
        sa.Column("matrix_id", sa.UUID(), nullable=False),
        sa.Column("required_role", sa.String(80), nullable=False),
        sa.Column("min_role_level", sa.Integer(), server_default="50"),
        sa.Column("timeout_hours", sa.Integer(), server_default="24"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["matrix_id"], ["opm_matrix.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "opm_override_rules",
        *_b(),
        sa.Column("matrix_id", sa.UUID(), nullable=False),
        sa.Column("override_condition", sa.String(120), nullable=False),
        sa.Column("allowed_role", sa.String(80), nullable=False),
        sa.Column("reason_required", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["matrix_id"], ["opm_matrix.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "opm_execution_modes",
        *_b(),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("action_class", sa.String(60), nullable=False),
        sa.Column("current_mode", sa.String(30), nullable=False),
        sa.Column("last_evaluated_reason", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    for t in (
        "opm_execution_modes",
        "opm_override_rules",
        "opm_approval_requirements",
        "opm_action_policies",
        "opm_matrix",
    ):
        op.drop_table(t)
