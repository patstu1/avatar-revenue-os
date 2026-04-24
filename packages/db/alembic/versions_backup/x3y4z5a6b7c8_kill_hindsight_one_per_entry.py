"""Unique constraint: one hindsight review per kill ledger entry.

Revision ID: x3y4z5a6b7c8
Revises: w1x2y3z4a5b6
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "x3y4z5a6b7c8"
down_revision: Union[str, None] = "w1x2y3z4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_kill_hindsight_reviews_kill_ledger_entry_id",
        "kill_hindsight_reviews",
        ["kill_ledger_entry_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_kill_hindsight_reviews_kill_ledger_entry_id",
        "kill_hindsight_reviews",
        type_="unique",
    )
