"""Enterprise Security + Compliance tables.

Revision ID: es_001
Revises: bg_001
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "es_001"
down_revision: Union[str, None] = "bg_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _base():
    return [sa.Column("id", sa.UUID(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)]

def upgrade() -> None:
    op.create_table("es_roles", *_base(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("role_name", sa.String(80), nullable=False), sa.Column("role_level", sa.Integer(), server_default="50"), sa.Column("description", sa.Text()), sa.Column("is_system", sa.Boolean(), server_default=sa.text("false")), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("es_permissions", *_base(), sa.Column("role_id", sa.UUID(), nullable=False), sa.Column("permission_key", sa.String(120), nullable=False), sa.Column("resource_type", sa.String(60), nullable=False), sa.Column("action", sa.String(40), nullable=False), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["role_id"], ["es_roles.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("es_user_groups", *_base(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("group_name", sa.String(120), nullable=False), sa.Column("scope_type", sa.String(40), nullable=False), sa.Column("scope_id", sa.UUID()), sa.Column("role_id", sa.UUID(), nullable=False), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.ForeignKeyConstraint(["role_id"], ["es_roles.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("es_access_scopes", *_base(), sa.Column("user_id", sa.UUID(), nullable=False), sa.Column("scope_type", sa.String(40), nullable=False), sa.Column("scope_id", sa.UUID()), sa.Column("role_id", sa.UUID(), nullable=False), sa.Column("granted_by", sa.UUID()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["user_id"], ["users.id"]), sa.ForeignKeyConstraint(["role_id"], ["es_roles.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("es_audit_trail", *_base(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("user_id", sa.UUID()), sa.Column("action", sa.String(60), nullable=False), sa.Column("resource_type", sa.String(60), nullable=False), sa.Column("resource_id", sa.UUID()), sa.Column("before_state", JSONB(), server_default="{}"), sa.Column("after_state", JSONB(), server_default="{}"), sa.Column("ip_address", sa.String(50)), sa.Column("detail", sa.Text()), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.ForeignKeyConstraint(["user_id"], ["users.id"]), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_esat_org", "es_audit_trail", ["organization_id"])
    op.create_index("ix_esat_action", "es_audit_trail", ["action"])

    op.create_table("es_sensitive_data_policies", *_base(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("policy_name", sa.String(120), nullable=False), sa.Column("data_class", sa.String(40), nullable=False), sa.Column("restricted_fields", JSONB(), server_default="[]"), sa.Column("masking_rules", JSONB(), server_default="{}"), sa.Column("model_restriction", sa.String(60)), sa.Column("private_mode", sa.Boolean(), server_default=sa.text("false")), sa.Column("training_leak_prevention", sa.Boolean(), server_default=sa.text("true")), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("es_model_isolation", *_base(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("provider_key", sa.String(80), nullable=False), sa.Column("isolation_mode", sa.String(30), server_default="shared"), sa.Column("dedicated_instance_id", sa.String(255)), sa.Column("data_residency", sa.String(40)), sa.Column("explanation", sa.Text()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("es_compliance_controls", *_base(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("framework", sa.String(40), nullable=False), sa.Column("control_id", sa.String(60), nullable=False), sa.Column("control_name", sa.String(255), nullable=False), sa.Column("status", sa.String(30), server_default="not_assessed"), sa.Column("evidence", JSONB(), server_default="{}"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("es_risk_overrides", *_base(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("user_id", sa.UUID(), nullable=False), sa.Column("override_type", sa.String(60), nullable=False), sa.Column("resource_type", sa.String(60), nullable=False), sa.Column("resource_id", sa.UUID()), sa.Column("reason", sa.Text(), nullable=False), sa.Column("approved_by", sa.UUID()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.ForeignKeyConstraint(["user_id"], ["users.id"]), sa.PrimaryKeyConstraint("id"))


def downgrade() -> None:
    for t in ("es_risk_overrides", "es_compliance_controls", "es_model_isolation", "es_sensitive_data_policies", "es_audit_trail", "es_access_scopes", "es_user_groups", "es_permissions", "es_roles"):
        op.drop_table(t)
