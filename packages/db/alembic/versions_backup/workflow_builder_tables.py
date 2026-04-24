"""Enterprise Workflow Builder tables.

Revision ID: wf_001
Revises: es_001
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "wf_001"
down_revision: Union[str, None] = "es_001"
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
        "wf_definitions",
        *_b(),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("brand_id", sa.UUID()),
        sa.Column("workflow_name", sa.String(255), nullable=False),
        sa.Column("workflow_type", sa.String(60), nullable=False),
        sa.Column("scope_type", sa.String(40), server_default="org"),
        sa.Column("scope_id", sa.UUID()),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "wf_steps",
        *_b(),
        sa.Column("definition_id", sa.UUID(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.String(120), nullable=False),
        sa.Column("step_type", sa.String(40), nullable=False),
        sa.Column("required_role", sa.String(80)),
        sa.Column("required_action", sa.String(40), server_default="approve"),
        sa.Column("auto_advance", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("config_json", JSONB(), server_default="{}"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["definition_id"], ["wf_definitions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "wf_assignments",
        *_b(),
        sa.Column("definition_id", sa.UUID(), nullable=False),
        sa.Column("step_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID()),
        sa.Column("role_name", sa.String(80)),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["definition_id"], ["wf_definitions.id"]),
        sa.ForeignKeyConstraint(["step_id"], ["wf_steps.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "wf_instances",
        *_b(),
        sa.Column("definition_id", sa.UUID(), nullable=False),
        sa.Column("brand_id", sa.UUID()),
        sa.Column("resource_type", sa.String(60), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=False),
        sa.Column("current_step_order", sa.Integer(), server_default="1"),
        sa.Column("status", sa.String(30), server_default="in_progress"),
        sa.Column("initiated_by", sa.UUID()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["definition_id"], ["wf_definitions.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["initiated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wfi_status", "wf_instances", ["status"])

    op.create_table(
        "wf_instance_steps",
        *_b(),
        sa.Column("instance_id", sa.UUID(), nullable=False),
        sa.Column("step_id", sa.UUID(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), server_default="pending"),
        sa.Column("acted_by", sa.UUID()),
        sa.Column("notes", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["instance_id"], ["wf_instances.id"]),
        sa.ForeignKeyConstraint(["step_id"], ["wf_steps.id"]),
        sa.ForeignKeyConstraint(["acted_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "wf_approvals",
        *_b(),
        sa.Column("instance_id", sa.UUID(), nullable=False),
        sa.Column("step_id", sa.UUID(), nullable=False),
        sa.Column("approved_by", sa.UUID(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["instance_id"], ["wf_instances.id"]),
        sa.ForeignKeyConstraint(["step_id"], ["wf_steps.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "wf_rejections",
        *_b(),
        sa.Column("instance_id", sa.UUID(), nullable=False),
        sa.Column("step_id", sa.UUID(), nullable=False),
        sa.Column("rejected_by", sa.UUID(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["instance_id"], ["wf_instances.id"]),
        sa.ForeignKeyConstraint(["step_id"], ["wf_steps.id"]),
        sa.ForeignKeyConstraint(["rejected_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "wf_overrides",
        *_b(),
        sa.Column("instance_id", sa.UUID(), nullable=False),
        sa.Column("overridden_by", sa.UUID(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("override_type", sa.String(40), server_default="skip_step"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["instance_id"], ["wf_instances.id"]),
        sa.ForeignKeyConstraint(["overridden_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "wf_templates",
        *_b(),
        sa.Column("template_name", sa.String(255), nullable=False),
        sa.Column("workflow_type", sa.String(60), nullable=False),
        sa.Column("steps_json", JSONB(), server_default="[]"),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    for t in (
        "wf_templates",
        "wf_overrides",
        "wf_rejections",
        "wf_approvals",
        "wf_instance_steps",
        "wf_instances",
        "wf_assignments",
        "wf_steps",
        "wf_definitions",
    ):
        op.drop_table(t)
