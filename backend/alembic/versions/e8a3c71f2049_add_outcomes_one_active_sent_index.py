"""add partial unique index: one non-voided SENT per generated_email

Revision ID: e8a3c71f2049
Revises: c4f8e2a91b07
Create Date: 2026-08-07 21:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e8a3c71f2049"
down_revision: Union[str, Sequence[str], None] = "c4f8e2a91b07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Partial unique index: at most one non-voided SENT per generated_email_id.
# Voided SENT rows are excluded so a legitimate retract can be followed by a
# fresh SENT log. See DATA_MODEL.md §2.8.
INDEX_NAME = "uq_outcomes_generated_email_id_nonvoided_sent"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        INDEX_NAME,
        "outcomes",
        ["generated_email_id"],
        unique=True,
        postgresql_where=sa.text(
            "voided = false AND event_type = 'sent'"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(INDEX_NAME, table_name="outcomes")
