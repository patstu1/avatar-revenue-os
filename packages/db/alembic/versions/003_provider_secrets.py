"""Add provider_secrets table for dashboard API key management.

Revision ID: 003_provider_secrets
Revises: 002_cinema_studio
Create Date: 2026-04-02
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from packages.db.alembic.migration_safety import safe_create_table

revision = "003_provider_secrets"
down_revision = "002_cinema_studio"
branch_labels = None
depends_on = None


def upgrade() -> None:
    safe_create_table(
        "provider_secrets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("provider_name", sa.String(100), nullable=False, index=True),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), onupdate=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("organization_id", "provider_name", name="uq_org_provider"),
    )


def downgrade() -> None:
    from packages.db.alembic.migration_safety import safe_drop_table
    safe_drop_table("provider_secrets")
