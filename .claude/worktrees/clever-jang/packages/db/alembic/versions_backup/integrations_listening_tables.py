"""Integrations + Listening OS tables.

Revision ID: il_001
Revises: hs_001
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "il_001"
down_revision: Union[str, None] = "hs_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _b():
    return [sa.Column("id", sa.UUID(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)]

def upgrade() -> None:
    op.create_table("il_connectors", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("connector_name", sa.String(120), nullable=False), sa.Column("connector_type", sa.String(40), nullable=False), sa.Column("endpoint_url", sa.String(1000)), sa.Column("auth_method", sa.String(30), server_default="api_key"), sa.Column("credential_env_key", sa.String(120)), sa.Column("sync_direction", sa.String(20), server_default="inbound"), sa.Column("status", sa.String(20), server_default="configured"), sa.Column("last_sync_status", sa.String(20)), sa.Column("config_json", JSONB(), server_default="{}"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("il_connector_syncs", *_b(), sa.Column("connector_id", sa.UUID(), nullable=False), sa.Column("sync_status", sa.String(20), nullable=False), sa.Column("records_synced", sa.Integer(), server_default="0"), sa.Column("errors", sa.Integer(), server_default="0"), sa.Column("detail", sa.Text()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["connector_id"], ["il_connectors.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("il_social_listening", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("brand_id", sa.UUID()), sa.Column("signal_type", sa.String(40), nullable=False), sa.Column("platform", sa.String(50)), sa.Column("source_url", sa.String(1000)), sa.Column("raw_text", sa.Text(), nullable=False), sa.Column("sentiment", sa.Float(), server_default="0"), sa.Column("relevance_score", sa.Float(), server_default="0.5"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("il_competitor_signals", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("brand_id", sa.UUID()), sa.Column("competitor_name", sa.String(255), nullable=False), sa.Column("signal_type", sa.String(40), nullable=False), sa.Column("raw_text", sa.Text(), nullable=False), sa.Column("sentiment", sa.Float(), server_default="0"), sa.Column("opportunity_score", sa.Float(), server_default="0"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("il_business_signals", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("brand_id", sa.UUID()), sa.Column("signal_type", sa.String(40), nullable=False), sa.Column("source_system", sa.String(60), nullable=False), sa.Column("data_json", JSONB(), server_default="{}"), sa.Column("priority", sa.String(20), server_default="medium"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("il_listening_clusters", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("brand_id", sa.UUID()), sa.Column("cluster_type", sa.String(40), nullable=False), sa.Column("cluster_label", sa.String(255), nullable=False), sa.Column("signal_count", sa.Integer(), server_default="0"), sa.Column("avg_sentiment", sa.Float(), server_default="0"), sa.Column("avg_relevance", sa.Float(), server_default="0"), sa.Column("representative_texts", JSONB(), server_default="[]"), sa.Column("recommended_action", sa.Text()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("il_signal_responses", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("cluster_id", sa.UUID(), nullable=False), sa.Column("response_type", sa.String(60), nullable=False), sa.Column("response_action", sa.Text(), nullable=False), sa.Column("target_system", sa.String(60), nullable=False), sa.Column("priority", sa.String(20), server_default="medium"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.ForeignKeyConstraint(["cluster_id"], ["il_listening_clusters.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("il_blockers", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("connector_id", sa.UUID()), sa.Column("blocker_type", sa.String(60), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("severity", sa.String(20), server_default="high"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.ForeignKeyConstraint(["connector_id"], ["il_connectors.id"]), sa.PrimaryKeyConstraint("id"))


def downgrade() -> None:
    for t in ("il_blockers", "il_signal_responses", "il_listening_clusters", "il_business_signals", "il_competitor_signals", "il_social_listening", "il_connector_syncs", "il_connectors"):
        op.drop_table(t)
