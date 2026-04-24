"""Add REDDIT to platform PostgreSQL enum.

Revision ID: b3c4d5e6f7g8
Revises: a2b3c4d5e6f7
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b3c4d5e6f7g8"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE platform ADD VALUE IF NOT EXISTS 'REDDIT'")


def downgrade() -> None:
    pass
