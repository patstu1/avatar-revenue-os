"""Enterprise Affiliate Governance + Owned Program tables.

Revision ID: afe_001
Revises: ei_001
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "afe_001"
down_revision: Union[str, None] = "ei_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _b():
    return [sa.Column("id", sa.UUID(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)]

def upgrade() -> None:
    op.create_table("af_governance_rules", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("rule_type", sa.String(40), nullable=False), sa.Column("rule_key", sa.String(255), nullable=False), sa.Column("rule_value", JSONB(), server_default="{}"), sa.Column("severity", sa.String(20), server_default="hard"), sa.Column("explanation", sa.Text()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("af_banned_entities", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("entity_type", sa.String(30), nullable=False), sa.Column("entity_name", sa.String(255), nullable=False), sa.Column("reason", sa.Text(), nullable=False), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("af_approvals", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("entity_type", sa.String(30), nullable=False), sa.Column("entity_id", sa.UUID(), nullable=False), sa.Column("approval_status", sa.String(20), server_default="pending"), sa.Column("approved_by", sa.UUID()), sa.Column("notes", sa.Text()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.ForeignKeyConstraint(["approved_by"], ["users.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("af_audit_events", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("user_id", sa.UUID()), sa.Column("action", sa.String(60), nullable=False), sa.Column("entity_type", sa.String(30), nullable=False), sa.Column("entity_id", sa.UUID()), sa.Column("detail", sa.Text()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.ForeignKeyConstraint(["user_id"], ["users.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("af_risk_flags", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("offer_id", sa.UUID()), sa.Column("merchant_id", sa.UUID()), sa.Column("risk_type", sa.String(40), nullable=False), sa.Column("risk_score", sa.Float(), server_default="0"), sa.Column("detail", sa.Text(), nullable=False), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.ForeignKeyConstraint(["offer_id"], ["af_offers.id"]), sa.ForeignKeyConstraint(["merchant_id"], ["af_merchants.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("af_own_partners", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("partner_name", sa.String(255), nullable=False), sa.Column("partner_email", sa.String(255)), sa.Column("partner_status", sa.String(20), server_default="pending"), sa.Column("partner_score", sa.Float(), server_default="0"), sa.Column("conversion_quality", sa.Float(), server_default="0"), sa.Column("fraud_risk", sa.Float(), server_default="0"), sa.Column("total_conversions", sa.Integer(), server_default="0"), sa.Column("total_revenue_generated", sa.Float(), server_default="0"), sa.Column("total_payout", sa.Float(), server_default="0"), sa.Column("asset_kit_assigned", sa.Boolean(), server_default=sa.text("false")), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("af_own_partner_conversions", *_b(), sa.Column("partner_id", sa.UUID(), nullable=False), sa.Column("conversion_value", sa.Float(), server_default="0"), sa.Column("commission_paid", sa.Float(), server_default="0"), sa.Column("quality_score", sa.Float(), server_default="0.5"), sa.Column("fraud_flag", sa.Boolean(), server_default=sa.text("false")), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["partner_id"], ["af_own_partners.id"]), sa.PrimaryKeyConstraint("id"))


def downgrade() -> None:
    for t in ("af_own_partner_conversions", "af_own_partners", "af_risk_flags", "af_audit_events", "af_approvals", "af_banned_entities", "af_governance_rules"):
        op.drop_table(t)
