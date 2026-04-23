"""Consolidated schema — creates all tables from SQLAlchemy models.

This replaces the previous 73 individual migration files (backed up in versions_backup/).
For a fresh database, this single migration creates all 419 tables.

Revision ID: 001_consolidated
Revises: None
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa

revision = "001_consolidated"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables from SQLAlchemy models using metadata.create_all."""
    from packages.db.base import Base
    import packages.db.models  # noqa: F401 — registers all models

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    """Drop all tables."""
    from packages.db.base import Base
    import packages.db.models  # noqa: F401

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
