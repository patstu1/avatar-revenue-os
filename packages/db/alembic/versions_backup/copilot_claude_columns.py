"""Add Claude generation tracking columns to copilot_chat_messages.

Revision ID: copilot_claude_001
Revises: copilot_001
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "copilot_claude_001"
down_revision: Union[str, None] = "copilot_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("copilot_chat_messages", sa.Column("generation_mode", sa.String(40), nullable=True))
    op.add_column("copilot_chat_messages", sa.Column("generation_model", sa.String(80), nullable=True))
    op.add_column("copilot_chat_messages", sa.Column("context_hash", sa.String(64), nullable=True))
    op.add_column("copilot_chat_messages", sa.Column("failure_reason", sa.Text(), nullable=True))
    op.create_index("ix_copilot_chat_messages_generation_mode", "copilot_chat_messages", ["generation_mode"])


def downgrade() -> None:
    op.drop_index("ix_copilot_chat_messages_generation_mode", table_name="copilot_chat_messages")
    op.drop_column("copilot_chat_messages", "failure_reason")
    op.drop_column("copilot_chat_messages", "context_hash")
    op.drop_column("copilot_chat_messages", "generation_model")
    op.drop_column("copilot_chat_messages", "generation_mode")
