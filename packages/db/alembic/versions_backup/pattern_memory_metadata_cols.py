"""Add structured pattern metadata columns to content_items.

Revision ID: pattern_meta_001
Revises: pattern_mem_001
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "pattern_meta_001"
down_revision: Union[str, None] = "pattern_mem_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("content_items", sa.Column("cta_type", sa.String(60), nullable=True))
    op.add_column("content_items", sa.Column("offer_angle", sa.String(60), nullable=True))
    op.add_column("content_items", sa.Column("hook_type", sa.String(60), nullable=True))
    op.add_column("content_items", sa.Column("creative_structure", sa.String(60), nullable=True))
    op.add_column("content_items", sa.Column("audience_response_profile", JSONB(), server_default="{}", nullable=True))


def downgrade() -> None:
    op.drop_column("content_items", "audience_response_profile")
    op.drop_column("content_items", "creative_structure")
    op.drop_column("content_items", "hook_type")
    op.drop_column("content_items", "offer_angle")
    op.drop_column("content_items", "cta_type")
