"""add voided to outcomes

Revision ID: c4f8e2a91b07
Revises: 75ea1b948b2a
Create Date: 2026-08-06 01:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4f8e2a91b07"
down_revision: Union[str, Sequence[str], None] = "75ea1b948b2a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "outcomes",
        sa.Column(
            "voided",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # No index on voided: list/analytics already scope by indexed user_id;
    # a boolean alone is too low-selectivity to justify a standalone index.


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("outcomes", "voided")
