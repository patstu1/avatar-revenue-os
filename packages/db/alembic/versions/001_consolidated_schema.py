"""Consolidated schema — creates all tables from SQLAlchemy models.

This replaces the previous 73 individual migration files (backed up in versions_backup/).
For a fresh database, this single migration creates all 419 tables.

Revision ID: 001_consolidated
Revises: None
Create Date: 2026-04-02
"""
from alembic import op

revision = "001_consolidated"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables from SQLAlchemy models using metadata.create_all.

    Idempotent: create_all with checkfirst=True (the default) skips
    tables that already exist.
    """
    import packages.db.models  # noqa: F401 — registers all models
    from packages.db.base import Base

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    """Drop all tables — DISABLED in production.

    This downgrade is intentionally guarded. Running drop_all on a
    production database is catastrophic. If you genuinely need to
    tear down the schema, set the env var ALLOW_DESTRUCTIVE_DOWNGRADE=1.
    """
    import os
    if os.environ.get("ALLOW_DESTRUCTIVE_DOWNGRADE") != "1":
        raise RuntimeError(
            "Downgrade of 001_consolidated is blocked. "
            "This would DROP ALL TABLES. Set ALLOW_DESTRUCTIVE_DOWNGRADE=1 "
            "if you really mean it."
        )
    import packages.db.models  # noqa: F401
    from packages.db.base import Base

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
