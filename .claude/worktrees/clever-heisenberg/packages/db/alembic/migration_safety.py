"""Migration safety utilities — idempotent DDL helpers for Alembic.

Every helper checks existence before acting, making migrations safe to re-run.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the current database."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in set(inspector.get_table_names())


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists on a table."""
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = :table AND column_name = :col"
    ), {"table": table_name, "col": column_name})
    return result.fetchone() is not None


def get_columns(table_name: str) -> set[str]:
    """Return set of column names for a table."""
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = :table"
    ), {"table": table_name})
    return {row[0] for row in rows}


def index_exists(index_name: str) -> bool:
    """Check if an index exists."""
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT 1 FROM pg_indexes WHERE indexname = :name"
    ), {"name": index_name})
    return result.fetchone() is not None


def constraint_exists(table_name: str, constraint_name: str) -> bool:
    """Check if a constraint exists on a table."""
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.table_constraints "
        "WHERE table_name = :table AND constraint_name = :name"
    ), {"table": table_name, "name": constraint_name})
    return result.fetchone() is not None


def fk_exists(constraint_name: str) -> bool:
    """Check if a foreign key constraint exists."""
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.table_constraints "
        "WHERE constraint_name = :name AND constraint_type = 'FOREIGN KEY'"
    ), {"name": constraint_name})
    return result.fetchone() is not None


def safe_create_table(table_name: str, *columns, **kwargs):
    """Create table only if it doesn't exist."""
    if not table_exists(table_name):
        op.create_table(table_name, *columns, **kwargs)
        return True
    return False


def safe_add_column(table_name: str, column_name: str, column_def):
    """Add column only if it doesn't exist."""
    if not column_exists(table_name, column_name):
        op.add_column(table_name, column_def)
        return True
    return False


def safe_create_index(index_name: str, table_name: str, columns: list[str], **kwargs):
    """Create index only if it doesn't exist."""
    if not index_exists(index_name):
        op.create_index(index_name, table_name, columns, **kwargs)
        return True
    return False


def safe_create_unique_constraint(name: str, table_name: str, columns: list[str]):
    """Create unique constraint only if it doesn't exist."""
    if not constraint_exists(table_name, name):
        op.create_unique_constraint(name, table_name, columns)
        return True
    return False


def safe_create_fk(name: str, source_table: str, referent_table: str,
                   local_cols: list[str], remote_cols: list[str], **kwargs):
    """Create foreign key only if it doesn't exist."""
    if not fk_exists(name):
        op.create_foreign_key(name, source_table, referent_table,
                              local_cols, remote_cols, **kwargs)
        return True
    return False


def safe_drop_column(table_name: str, column_name: str):
    """Drop column only if it exists."""
    if column_exists(table_name, column_name):
        op.drop_column(table_name, column_name)
        return True
    return False


def safe_drop_table(table_name: str):
    """Drop table only if it exists."""
    if table_exists(table_name):
        op.drop_table(table_name)
        return True
    return False
